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


def display_stretch(img, lo, hi):
    """Percentile contrast stretch for DISPLAY ONLY (never the recording/snapshot).

    Maps the lo/hi intensity percentiles to 0..255 so the dark graphite rotor and
    the faint grey mark become visible on screen. Returns the frame unchanged if
    the percentiles collapse (e.g. a flat frame).
    """
    p_lo, p_hi = np.percentile(img, (lo, hi))
    if p_hi <= p_lo:
        return img
    out = (img.astype(np.float32) - p_lo) * (255.0 / (p_hi - p_lo))
    return np.clip(out, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------- args
p = argparse.ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--exposure', type=float, default=2.0, help='exposure in ms (default 2.0)')
p.add_argument('--gain', type=float, default=0.0, help='gain in dB (default 0)')
p.add_argument('--fps', type=float, default=50.0,
               help='cap acquisition frame rate (default 50; raise usbfs_memory_mb '
                    'to 1000 before going much above ~60). Use 0 for uncapped. '
                    'NOTE: --exposure sets a hard ceiling of 1000/exposure_ms fps, so '
                    'e.g. 20 ms caps you at 50 fps however high this is set.')
p.add_argument('--roi', type=str, default='544,432,256,292',
               help='hardware ROI as x,y,w,h. Default 544,432,256,292 crops to the rotor '
                    '+ electrodes (glare clipped, top trimmed). NOTE: with the hardware flip '
                    'active the sensor is mirrored BEFORE the AOI, so x,y are DISPLAY (post-flip) '
                    'coords, not raw sensor coords. Pass 0,0,1440,1080 for the full frame.')
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
p.add_argument('--show', action='store_true',
               help='pop up a live window like the uEye image mode '
                    '(needs a graphical display; use --mjpeg over plain SSH)')
p.add_argument('--show-scale', type=float, default=2.0,
               help='enlarge the --show window by this factor (default 2.0). Display only '
                    '-- does not change the ROI, recording or snapshot. The window is also '
                    'resizable by dragging.')
p.add_argument('--flip-v', action='store_true',
               help='flip the image top<->bottom to match the physical view. Applied at '
                    'the source (hardware ReverseY if available, else software) so the '
                    'recording, snapshot, stream, AND raw array all share one orientation '
                    '-- important so a future feedback tracker sees the same frame.')
p.add_argument('--flip-h', action='store_true',
               help='flip the image left<->right (hardware ReverseX if available, else '
                    'software). NOTE: a single flip (-v OR -h) mirrors the image and so '
                    'reverses the apparent sense of rotation; combining -v AND -h is a '
                    '180 deg rotation that preserves rotation direction.')
p.add_argument('--codec', type=str, default='ffv1',
               help="recording codec (default 'ffv1'). 'ffv1' writes LOSSLESS Mono8 "
                    "directly (isColor=False) so faint marks on the rotor survive -- this "
                    "is the point of the change. If FFV1 cannot open on this build it "
                    "falls back to MJPG at quality 100 (still lossy). Pass 'mjpg' to force "
                    "the old colour MJPG path. The codec actually used is printed at start.")
p.add_argument('--stretch', action='store_true',
               help='DISPLAY-ONLY contrast stretch for the --show window and the MJPEG '
                    'stream, so the dark graphite rotor shows detail. Does NOT touch the '
                    'recorded .avi or the /dev/shm snapshot that tooling reads -- those '
                    'stay the raw sensor frame.')
p.add_argument('--stretch-pct', type=str, default='1,99',
               help='low,high percentiles for --stretch (default 1,99). Display only.')
args = p.parse_args()

SNAP = bool(args.snapshot)

# A pop-up window needs an X/Wayland display. Fail early with a clear message
# instead of the cryptic Qt "could not connect to display" abort.
if args.show and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
    sys.exit("--show needs a graphical display, but none was found ($DISPLAY unset).\n"
             "  * At the worker2 console/desktop it will work.\n"
             "  * Over SSH, either forward X (ssh -Y worker2) or, better, use --mjpeg\n"
             "    and open http://localhost:8080/ (or http://worker2:8080/) in a browser.")


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
            if self.path == '/':
                # HTML wrapper: browsers render MJPEG reliably inside an <img>,
                # even when they refuse the raw multipart stream as a top page.
                page = (b"<!doctype html><html><head><meta charset='utf-8'>"
                        b"<title>Basler live</title><style>html,body{margin:0;"
                        b"height:100%;background:#111;display:flex;align-items:center;"
                        b"justify-content:center}img{max-width:100%;max-height:100vh}"
                        b"</style></head><body><img src='/stream'></body></html>")
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(page)))
                self.end_headers()
                self.wfile.write(page)
            elif self.path in ('/stream', '/stream.mjpg'):
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

# NOTE (2026-07-23): the chamber-view orientation is ALREADY SOLVED IN HARDWARE.
# This camera (acA1440-220um serial 40103621) has ReverseX+ReverseY (a 180deg
# rotation, matching the physical chamber) saved in its UserSet1, which is the
# power-up default (UserSetDefault=UserSet1). So with NO flags the camera already
# serves the correct orientation and every tool that opens it inherits the same
# frame. The --flip-v/--flip-h flags below are therefore usually unnecessary --
# they're kept as a recovery path if the camera is ever reset to factory default,
# and as documentation. A single flip mirrors the image (reverses rotation sense);
# both flips = 180deg rotation (preserves rotation direction). To revert the
# hardware default: set UserSetDefault=Default (or ReverseX/Y False + re-save).
#
# vertical flip (top<->bottom). Prefer the sensor's hardware ReverseY so the raw
# res.Array is already flipped -- then every consumer, including any future feedback
# tracker, sees one identical orientation. Fall back to a per-frame software flip if
# the camera doesn't expose the feature.
sw_flip_v = sw_flip_h = False
if args.flip_v:
    try:
        cam.ReverseY.Value = True
        print("  ReverseY (hardware vertical flip) enabled")
    except Exception:
        sw_flip_v = True
        print("  ReverseY not available; using software vertical flip")
if args.flip_h:
    try:
        cam.ReverseX.Value = True
        print("  ReverseX (hardware horizontal flip) enabled")
    except Exception:
        sw_flip_h = True
        print("  ReverseX not available; using software horizontal flip")

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
writer_is_color = True
csv_file = None
if args.record:
    os.makedirs(args.outdir, exist_ok=True)
    gps = gps_now()
    fname = os.path.join(args.outdir, f"output_basler_gps{gps}.avi")

    # FFV1 is lossless and keeps Mono8 as a single plane (isColor=False), so the
    # faint grey paint mark that MJPG's colour compression washed out survives.
    # Fall back to MJPG q=100 only if this OpenCV build can't open FFV1.
    codec = args.codec.lower()
    codec_used = None
    if codec == 'ffv1':
        w = cv2.VideoWriter(fname, cv2.VideoWriter_fourcc(*'FFV1'),
                            actual_fps, (W, H), isColor=False)
        if w.isOpened():
            writer, writer_is_color, codec_used = w, False, 'FFV1 (lossless Mono8)'
        else:
            w.release()
            print("  FFV1 could not open on this build -- falling back to MJPG q=100")
            codec = 'mjpg'
    if writer is None:
        # MJPG (or any requested colour codec): gray promoted to BGR, quality maxed.
        fourcc = 'MJPG' if codec in ('mjpg', 'ffv1') else args.codec.upper()
        w = cv2.VideoWriter(fname, cv2.VideoWriter_fourcc(*fourcc),
                            actual_fps, (W, H), isColor=True)
        try:
            w.set(cv2.VIDEOWRITER_PROP_QUALITY, 100)
        except Exception:
            pass
        writer, writer_is_color, codec_used = w, True, f'{fourcc} q=100 (lossy)'
    if not writer.isOpened():
        cam.Close()
        sys.exit(f"VideoWriter failed to open ({fname})")

    # Per-frame timestamp sidecar, same GPS-stamped name with .csv. Lets the
    # tracker put each frame on an absolute clock and spot dropped frames.
    csv_name = os.path.join(args.outdir, f"output_basler_gps{gps}.csv")
    csv_file = open(csv_name, 'w', buffering=1)
    csv_file.write('frame_index,block_id,cam_timestamp_ns,host_time\n')

    utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"  recording -> {fname}  ({utc})")
    print(f"  codec     -> {codec_used}")
    print(f"  timestamps-> {csv_name}")

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
if args.show:
    # resizable window, opened pre-enlarged by --show-scale (display only)
    cv2.namedWindow('Basler live', cv2.WINDOW_NORMAL)
    if args.show_scale and args.show_scale > 0:
        cv2.resizeWindow('Basler live',
                         int(W * args.show_scale), int(H * args.show_scale))
    print(f"  live window   -> 'Basler live' ({args.show_scale:g}x, resizable; "
          f"press q in the window to quit)")
print(f"Running{' with live window' if args.show else ' headless'} -- Ctrl-C to stop.")

jpeg_params = [cv2.IMWRITE_JPEG_QUALITY, int(args.jpeg_quality)]
stretch_lo, stretch_hi = (float(v) for v in args.stretch_pct.split(','))
if args.stretch:
    print(f"  display stretch -> {stretch_lo:g}-{stretch_hi:g} percentile "
          f"(--show + MJPEG only; recording/snapshot unchanged)")
want_disp = args.show or (server is not None)
last_snap = 0.0
t0 = time.time()
n = 0
# dropped-frame bookkeeping from camera BlockID gaps (recording path only)
dropped = 0
prev_block = None
first_block = None
try:
    while running['go']:
        res = cam.RetrieveResult(2000, pylon.TimeoutHandling_ThrowException)
        if res.GrabSucceeded():
            frame = res.Array                      # 2-D Mono8
            if sw_flip_v:
                frame = cv2.flip(frame, 0)         # flip top<->bottom (x-axis)
            if sw_flip_h:
                frame = cv2.flip(frame, 1)         # flip left<->right (y-axis)
            n += 1
            if writer is not None:
                # FFV1 path writes the Mono8 plane as-is (lossless); the MJPG
                # fallback still needs gray promoted to BGR.
                writer.write(frame if not writer_is_color
                             else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR))
            # per-frame timestamps + dropped-frame accounting
            if csv_file is not None:
                block = int(res.BlockID)
                tstamp = int(res.TimeStamp)
                host = time.time()
                csv_file.write(f"{n},{block},{tstamp},{host:.6f}\n")
                if first_block is None:
                    first_block = block
                if prev_block is not None and block > prev_block + 1:
                    dropped += block - prev_block - 1
                prev_block = block
            # display frame is stretched ONLY for show/stream; the snapshot that
            # tooling reads is always the raw sensor frame.
            disp = display_stretch(frame, stretch_lo, stretch_hi) \
                if (want_disp and args.stretch) else frame
            # snapshot (raw) and stream (disp) -- share the encode when not stretching
            raw_jpeg = None
            if SNAP or (server is not None and not args.stretch):
                ok, buf = cv2.imencode('.jpg', frame, jpeg_params)
                if ok:
                    raw_jpeg = buf.tobytes()
            if server is not None:
                if args.stretch:
                    ok, buf = cv2.imencode('.jpg', disp, jpeg_params)
                    stream_jpeg = buf.tobytes() if ok else None
                else:
                    stream_jpeg = raw_jpeg
                if stream_jpeg is not None:
                    hub.update(stream_jpeg)
            if SNAP and raw_jpeg is not None:
                now = time.time()
                if now - last_snap >= args.snapshot_every:
                    tmp = args.snapshot + '.tmp'
                    with open(tmp, 'wb') as f:
                        f.write(raw_jpeg)
                    os.replace(tmp, args.snapshot)   # atomic
                    last_snap = now
            if args.show:
                cv2.imshow('Basler live', disp)
                if (cv2.waitKey(1) & 0xFF) == ord('q'):
                    running['go'] = False
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
    if csv_file is not None:
        csv_file.close()
    if server is not None:
        server.shutdown()
    if args.show:
        cv2.destroyAllWindows()
    eff = n / dt if dt > 0 else 0.0
    print(f"\nStopped. {n} frames in {dt:.1f}s ({eff:.1f} fps effective).")
    if csv_file is not None:
        span = (prev_block - first_block + 1) if first_block is not None else 0
        print(f"Dropped frames (BlockID gaps): {dropped}"
              f"  ({n} received of {span} expected across the BlockID span).")
