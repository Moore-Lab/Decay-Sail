#!/usr/bin/env python3
"""Headless capture for the Basler acA1440-220um with three readout paths:

  1. /dev/shm snapshot  -- latest frame written as a JPEG (default on) so it can be
                           opened/scp'd or read by tooling with no display server.
  2. MJPEG HTTP stream  -- optional; watch the live feed in a browser over SSH,
                           no X11 (http://<worker2>:<port>/).
  3. GPS-named .avi      -- optional recording, mirrors record_ueye_video.py naming.

IMPORTANT: cv2 is imported BEFORE pypylon on purpose -- importing pypylon first
shifts the library path and makes cv2 pick up the system libstdc++ (CXXABI error).
"""
import cv2                       # must come before pypylon
import numpy as np
from pypylon import pylon

import argparse
import os
import signal
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# GPS epoch offset: Unix->GPS epoch, minus 18 leap seconds (GPS has no leap seconds).
_GPS_UNIX_OFFSET = 315964800 - 18


def gps_now():
    return int(time.time()) - _GPS_UNIX_OFFSET


# --------------------------------------------------------------------------- args
p = argparse.ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--exposure', type=float, default=3.0, help='exposure in ms (default 3.0)')
p.add_argument('--gain', type=float, default=0.0, help='gain in dB (default 0)')
p.add_argument('--fps', type=float, default=30.0,
               help='cap acquisition frame rate (default 30; raise usbfs_memory_mb '
                    'to 1000 before going much above ~60). Use 0 for uncapped.')
p.add_argument('--roi', type=str, default=None,
               help='hardware ROI as x,y,w,h (default full frame)')
p.add_argument('--snapshot', type=str, default='/dev/shm/basler_latest.jpg',
               help='path for the latest-frame JPEG (default /dev/shm/basler_latest.jpg); '
                    'set to "" to disable')
p.add_argument('--snapshot-every', type=float, default=0.5,
               help='seconds between snapshot writes (default 0.5)')
p.add_argument('--mjpeg', action='store_true', help='enable the MJPEG HTTP stream')
p.add_argument('--port', type=int, default=8080, help='MJPEG server port (default 8080)')
p.add_argument('--record', action='store_true', help='record a GPS-named .avi')
p.add_argument('--outdir', type=str, default='.', help='directory for recordings (default .)')
p.add_argument('--jpeg-quality', type=int, default=80, help='JPEG quality 1-100 (default 80)')
p.add_argument('--duration', type=float, default=0.0,
               help='auto-stop after N seconds (default 0 = run until Ctrl-C)')
args = p.parse_args()

SNAP = bool(args.snapshot)


# ------------------------------------------------------------------ shared frame
class FrameHub:
    """Thread-safe hand-off of the latest JPEG from the capture loop to HTTP clients."""
    def __init__(self):
        self.cond = threading.Condition()
        self.jpeg = None
        self.fid = 0

    def update(self, jpeg):
        with self.cond:
            self.jpeg = jpeg
            self.fid += 1
            self.cond.notify_all()

    def snapshot(self):
        with self.cond:
            return self.jpeg, self.fid

    def wait_new(self, last, timeout=2.0):
        with self.cond:
            self.cond.wait_for(lambda: self.fid != last, timeout=timeout)
            return self.jpeg, self.fid


hub = FrameHub()


def make_handler(hub):
    class MJPEGHandler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass  # keep the console quiet

        def do_GET(self):
            if self.path in ('/', '/stream', '/stream.mjpg'):
                self.send_response(200)
                self.send_header('Age', '0')
                self.send_header('Cache-Control', 'no-cache, private')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Content-Type',
                                 'multipart/x-mixed-replace; boundary=frame')
                self.end_headers()
                last = -1
                try:
                    while True:
                        jpeg, last = hub.wait_new(last)
                        if jpeg is None:
                            continue
                        self.wfile.write(b'--frame\r\n')
                        self.wfile.write(b'Content-Type: image/jpeg\r\n')
                        self.wfile.write(
                            b'Content-Length: ' + str(len(jpeg)).encode() + b'\r\n\r\n')
                        self.wfile.write(jpeg)
                        self.wfile.write(b'\r\n')
                except (BrokenPipeError, ConnectionResetError):
                    pass
            elif self.path == '/snapshot.jpg':
                jpeg, _ = hub.snapshot()
                if jpeg is None:
                    self.send_error(503)
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(jpeg)))
                self.end_headers()
                self.wfile.write(jpeg)
            else:
                self.send_error(404)
    return MJPEGHandler


# ------------------------------------------------------------------ usbfs warning
try:
    _mb = int(open('/sys/module/usbcore/parameters/usbfs_memory_mb').read())
    if _mb < 256 and (args.fps == 0 or args.fps > 60):
        print(f"WARNING: usbfs_memory_mb={_mb} is low for high frame rates; frames may "
              f"drop. Raise to 1000 (setup-usb.sh or usbcore.usbfs_memory_mb=1000).")
except Exception:
    pass


# ------------------------------------------------------------------ camera setup
tl = pylon.TlFactory.GetInstance()
if not tl.EnumerateDevices():
    sys.exit("No Basler camera found (check USB3 cable and udev permissions).")
cam = pylon.InstantCamera(tl.CreateFirstDevice())
cam.Open()
info = cam.GetDeviceInfo()
print(f"Opened {info.GetModelName()} (serial {info.GetSerialNumber()})")

cam.PixelFormat.Value = 'Mono8'

# hardware ROI (must respect the sensor's offset/size increments; set offsets to 0
# first so a new width/height can't collide with the old offset range).
if args.roi:
    x, y, w, h = (int(v) for v in args.roi.split(','))
    cam.OffsetX.Value = 0
    cam.OffsetY.Value = 0
    cam.Width.Value = w - (w % cam.Width.Inc)
    cam.Height.Value = h - (h % cam.Height.Inc)
    cam.OffsetX.Value = x - (x % cam.OffsetX.Inc)
    cam.OffsetY.Value = y - (y % cam.OffsetY.Inc)

# exposure / gain (fixed, no auto -- auto-exposure hunts and blurs a spinning target)
try:
    cam.ExposureAuto.Value = 'Off'
    cam.GainAuto.Value = 'Off'
except Exception:
    pass
cam.ExposureTime.Value = args.exposure * 1000.0  # ms -> us
try:
    cam.Gain.Value = args.gain
except Exception as e:
    print("  (gain not set:", e, ")")

# frame-rate cap
if args.fps and args.fps > 0:
    cam.AcquisitionFrameRateEnable.Value = True
    cam.AcquisitionFrameRate.Value = args.fps
else:
    try:
        cam.AcquisitionFrameRateEnable.Value = False
    except Exception:
        pass

W, H = cam.Width.Value, cam.Height.Value
actual_fps = cam.ResultingFrameRate.Value
print(f"  {W}x{H} Mono8, exposure {cam.ExposureTime.Value/1000:.2f} ms, "
      f"~{actual_fps:.1f} fps")

# ------------------------------------------------------------------ optional .avi
writer = None
if args.record:
    os.makedirs(args.outdir, exist_ok=True)
    fname = os.path.join(args.outdir, f"output_basler_gps{gps_now()}.avi")
    writer = cv2.VideoWriter(fname, cv2.VideoWriter_fourcc(*'MJPG'),
                             actual_fps, (W, H), isColor=True)
    if not writer.isOpened():
        cam.Close()
        sys.exit(f"VideoWriter failed to open ({fname})")
    utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"  recording -> {fname}  ({utc})")

# ------------------------------------------------------------------ optional MJPEG
server = None
if args.mjpeg:
    server = ThreadingHTTPServer(('0.0.0.0', args.port), make_handler(hub))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host = socket.gethostname()
    print(f"  MJPEG stream -> http://{host}:{args.port}/   "
          f"(single frame: /snapshot.jpg)")

if SNAP:
    print(f"  snapshot     -> {args.snapshot}  (every {args.snapshot_every:.1f}s)")

# ------------------------------------------------------------------ capture loop
running = {'go': True}


def _stop(sig, frame):
    running['go'] = False


signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)

# LatestImageOnly for low-latency viewing; OneByOne when recording so no frame is lost.
strategy = (pylon.GrabStrategy_OneByOne if args.record
            else pylon.GrabStrategy_LatestImageOnly)
cam.StartGrabbing(strategy)
print("Running headless -- Ctrl-C to stop.")

jpeg_params = [cv2.IMWRITE_JPEG_QUALITY, int(args.jpeg_quality)]
last_snap = 0.0
t0 = time.time()
n = 0
try:
    while running['go']:
        res = cam.RetrieveResult(2000, pylon.TimeoutHandling_ThrowException)
        if res.GrabSucceeded():
            frame = res.Array                      # 2-D Mono8
            n += 1
            if writer is not None:
                writer.write(cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR))
            # encode once, reuse for stream + snapshot
            if server is not None or SNAP:
                ok, buf = cv2.imencode('.jpg', frame, jpeg_params)
                if ok:
                    jpeg = buf.tobytes()
                    if server is not None:
                        hub.update(jpeg)
                    now = time.time()
                    if SNAP and now - last_snap >= args.snapshot_every:
                        tmp = args.snapshot + '.tmp'
                        with open(tmp, 'wb') as f:
                            f.write(jpeg)
                        os.replace(tmp, args.snapshot)   # atomic
                        last_snap = now
        res.Release()
        if args.duration and (time.time() - t0) >= args.duration:
            break
except KeyboardInterrupt:
    pass
finally:
    dt = time.time() - t0
    cam.StopGrabbing()
    cam.Close()
    if writer is not None:
        writer.release()
    if server is not None:
        server.shutdown()
    print(f"\nStopped. {n} frames in {dt:.1f}s ({n/dt:.1f} fps effective).")
