#!/usr/bin/env python3
"""Live blob angle from the Basler, recording at the same time (gate 7).

    python live_blob_track.py --exposure 15 --outdir DIR [--duration S] [--show]
    python live_blob_track.py --replay VIDEO.avi [--centre X,Y] --outdir DIR      # no camera

MEASURES ONLY. Commands nothing, writes no EPICS channel. Holds the camera exclusively
(stop grab_basler.py first), so it records too, in grab_basler.py's format:
  output_basler_gps<GPS>.avi   FFV1 lossless Mono8
  output_basler_gps<GPS>.csv   frame_index,block_id,cam_timestamp_ns,host_time
  blob_live_gps<GPS>.csv       frame, host_time, angle_deg, r_px, ncc, ncc_elsewhere,
                               source, proc_ms (columns as blob_track.py, plus timing)
GPS is true GPS from worker2's clock, as in grab_basler.py.

Angle: blob_core.Tracker, the same per-frame code as blob_track.py, with a stored template
(default template_gps1477428272.npz: frame 0 of that video at 257 deg, the angle zero the
hand labels and score_angles.py --offset 0.56 refer to).

Centre: --centre X,Y pins it. Otherwise the first --calib-s seconds of frames are
median-combined and registered against the template video's median frame (static board,
rotor masked), and the template's centre is moved by that shift. Calibration frames are
recorded and tracked once the centre is known.

Orientation: no flip flags; the camera's UserSet1 already has it (see grab_basler.py).
--replay reads frames from a file instead of the camera (same per-frame path, no pypylon),
for testing off the lab machine.
"""
import cv2                       # must come before pypylon (CXXABI clash)
import numpy as np
import argparse, os, signal, subprocess, sys, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blob_core

GPS_UNIX_OFF = 315964800 - 18
HERE = os.path.dirname(os.path.abspath(__file__))

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--exposure', type=float, default=15.0, help='ms (default 15, as for gps1477428272)')
p.add_argument('--gain', type=float, default=0.0, help='dB (default 0)')
p.add_argument('--fps', type=float, default=50.0, help='frame rate cap (default 50)')
p.add_argument('--roi', default='544,432,256,292', help='x,y,w,h (default as grab_basler.py)')
p.add_argument('--template', default=os.path.join(HERE, 'template_gps1477428272.npz'))
p.add_argument('--centre', default='', help='X,Y to pin the centre (else registered)')
p.add_argument('--calib-s', type=float, default=2.0, help='seconds of frames for registration')
p.add_argument('--outdir', default='.')
p.add_argument('--duration', type=float, default=0.0, help='auto-stop after S seconds (0 = Ctrl-C)')
p.add_argument('--snapshot', default='/dev/shm/blob_live.jpg', help='overlay JPEG ("" = off)')
p.add_argument('--snapshot-every', type=float, default=0.5)
p.add_argument('--show', action='store_true', help='live window with the tracked point')
p.add_argument('--replay', default='', help='read frames from this video instead of the camera')
args = p.parse_args()

T, ref_angle, ref_centre, ref_median = blob_core.load_template(args.template)

# ------------------------------------------------------------------ frame source
if args.replay:
    W, H = (int(v) for v in subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
         '-of', 'csv=p=0', args.replay], capture_output=True, text=True, check=True).stdout.split(','))
    proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', args.replay, '-f', 'rawvideo',
                             '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE)
    fps = 50.0
    def frames():
        k = 0
        while True:
            buf = proc.stdout.read(W * H)
            if len(buf) < W * H: return
            yield np.frombuffer(buf, np.uint8).reshape(H, W), k, int(k * 1e9 / fps)
            k += 1
    close_source = proc.kill
    print('replay %s (%dx%d)' % (args.replay, W, H))
else:
    from pypylon import pylon
    tl = pylon.TlFactory.GetInstance()
    if not tl.EnumerateDevices():
        sys.exit('No Basler camera found.')
    cam = pylon.InstantCamera(tl.CreateFirstDevice()); cam.Open()
    cam.PixelFormat.Value = 'Mono8'
    x, y, w, h = (int(v) for v in args.roi.split(','))
    cam.OffsetX.Value = 0; cam.OffsetY.Value = 0
    cam.Width.Value = w - (w % cam.Width.Inc); cam.Height.Value = h - (h % cam.Height.Inc)
    cam.OffsetX.Value = x - (x % cam.OffsetX.Inc); cam.OffsetY.Value = y - (y % cam.OffsetY.Inc)
    try:
        cam.ExposureAuto.Value = 'Off'; cam.GainAuto.Value = 'Off'
    except Exception:
        pass
    cam.ExposureTime.Value = args.exposure * 1000.0
    try:
        cam.Gain.Value = args.gain
    except Exception as e:
        print('  (gain not set:', e, ')')
    cam.AcquisitionFrameRateEnable.Value = True; cam.AcquisitionFrameRate.Value = args.fps
    cam.MaxNumBuffer.Value = 500          # room for the calibration backlog (~10 s at 50 fps)
    W, H, fps = cam.Width.Value, cam.Height.Value, cam.ResultingFrameRate.Value
    print('%s: %dx%d Mono8, exposure %.2f ms, ~%.1f fps' % (
        cam.GetDeviceInfo().GetModelName(), W, H, cam.ExposureTime.Value / 1000, fps))
    cam.StartGrabbing(pylon.GrabStrategy_OneByOne)
    def frames():
        while cam.IsGrabbing():
            res = cam.RetrieveResult(2000, pylon.TimeoutHandling_ThrowException)
            try:
                if res.GrabSucceeded():
                    yield res.Array.copy(), int(res.BlockID), int(res.TimeStamp)
            finally:
                res.Release()
    def close_source():
        cam.StopGrabbing(); cam.Close()

# ------------------------------------------------------------------ outputs
os.makedirs(args.outdir, exist_ok=True)
gps = int(time.time() - GPS_UNIX_OFF)
stem = os.path.join(args.outdir, 'output_basler_gps%d' % gps)
writer = None                             # replay: the video already exists, so no copy
if not args.replay:
    writer = cv2.VideoWriter(stem + '.avi', cv2.VideoWriter_fourcc(*'FFV1'), fps, (W, H), isColor=False)
    if not writer.isOpened():
        close_source(); sys.exit('FFV1 VideoWriter failed to open (%s.avi)' % stem)
ts = open(stem + '.csv', 'w', buffering=1); ts.write('frame_index,block_id,cam_timestamp_ns,host_time\n')
ang_name = os.path.join(args.outdir, 'blob_live_gps%d.csv' % gps)
out = open(ang_name, 'w', buffering=1)
print('recording -> %s (%s)\nangles    -> %s' % (stem + '.avi' if writer else '(none, replay)', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'), ang_name))

running = {'go': True}
signal.signal(signal.SIGINT, lambda *a: running.update(go=False))
signal.signal(signal.SIGTERM, lambda *a: running.update(go=False))

trk = None; backlog = []; n = 0; dropped = 0; prev_block = None
last_snap = 0.0; t0 = time.time(); proc_ms = []

def start_tracker():
    global trk
    if args.centre:
        cx, cy = (float(v) for v in args.centre.split(',')); how = 'pinned'
    else:
        med = np.median(np.array([b[0] for b in backlog]), 0).astype(np.uint8)
        cx, cy, (dx, dy), resp = blob_core.register_centre(med, ref_median, ref_centre)
        how = 'registered: board shift (%+.2f, %+.2f) px, response %.2f' % (dx, dy, resp)
    trk = blob_core.Tracker(cx, cy, W, H, T, ref_angle)
    print('centre (%.2f, %.2f) %s' % (cx, cy, how))
    out.write('# live_blob_track.py gps%d centre=(%.6f,%.6f) %s template=%s exposure=%.1fms%s\n' % (
        gps, cx, cy, how, os.path.basename(args.template), args.exposure, ' replay=' + args.replay if args.replay else ''))
    out.write('frame,host_time,angle_deg,r_px,ncc,ncc_elsewhere,source,proc_ms\n')

def track(f, k, host):
    t1 = time.perf_counter(); a, r, c1, c2, src = trk.process(f); dt = 1e3 * (time.perf_counter() - t1)
    proc_ms.append(dt)
    out.write('%d,%.6f,%.2f,%.2f,%.3f,%.3f,%s,%.2f\n' % (k, host, a, r, c1, c2, src, dt))
    return a, r

def overlay(f, a, r):
    img = cv2.cvtColor(f, cv2.COLOR_GRAY2BGR)
    px = (int(round(trk.cx + r * np.cos(np.deg2rad(a)))), int(round(trk.cy + r * np.sin(np.deg2rad(a)))))
    cv2.circle(img, px, 9, (0, 0, 255), 1); cv2.drawMarker(img, (int(trk.cx), int(trk.cy)), (0, 255, 255), cv2.MARKER_CROSS, 8)
    cv2.putText(img, '%.1f deg' % a, (4, 14), 0, 0.45, (0, 255, 255), 1)
    return img

try:
    for f, block, cam_ns in frames():
        if not running['go']: break
        host = time.time(); n += 1
        if writer: writer.write(f)
        ts.write('%d,%d,%d,%.6f\n' % (n, block, cam_ns, host))
        if prev_block is not None and block > prev_block + 1: dropped += block - prev_block - 1
        prev_block = block
        if trk is None:
            backlog.append((f, n - 1, host))
            if len(backlog) >= max(1, int(args.calib_s * fps)) or args.centre:
                start_tracker()
                for bf, bk, bh in backlog: a, r = track(bf, bk, bh)
                backlog = []
            continue
        a, r = track(f, n - 1, host)
        if (args.snapshot or args.show) and host - last_snap >= args.snapshot_every:
            img = overlay(f, a, r); last_snap = host
            if args.snapshot:
                cv2.imwrite(args.snapshot + '.tmp.jpg', img); os.replace(args.snapshot + '.tmp.jpg', args.snapshot)
            if args.show:
                cv2.imshow('blob live', cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST))
                if (cv2.waitKey(1) & 0xFF) == ord('q'): running['go'] = False
        if args.duration and host - t0 >= args.duration: break
finally:
    close_source(); ts.close(); out.close()
    if writer: writer.release()
    if args.show: cv2.destroyAllWindows()
    dt = time.time() - t0; pm = np.array(proc_ms) if proc_ms else np.array([np.nan])
    print('\nStopped. %d frames in %.1f s; dropped (BlockID gaps) %d; tracking %.2f ms median, %.2f ms p99, %.2f ms max' % (
        n, dt, dropped, np.median(pm), np.percentile(pm, 99), pm.max()))
