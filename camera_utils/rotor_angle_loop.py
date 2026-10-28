#!/usr/bin/env python3
"""In-process rotor angle from the Basler, at frame rate.

MEASURES ONLY. Commands nothing, touches no EPICS setpoint. This is the
measurement half of the feedback loop, built and validated first so the angle
stream can be trusted before anything drives the electrodes.

WHY IN-PROCESS, NOT grab_basler.py + /dev/shm
    The snapshot path is camera -> JPEG encode -> /dev/shm -> read -> JPEG
    decode -> angle, and `--snapshot-every` throttles it to 2 Hz no matter what
    the camera is doing. At 50 fps that throws away 24 of every 25 frames. It
    also means reading a file while another process writes it. Here the frame
    goes straight from pypylon into numpy.

    Measured on worker2 2026-10-28: angle from a raw array 0.14 ms, EPICS write
    0.44 ms, camera frame interval 20 ms at 50 fps. The camera is the slow
    element by a factor of ~20, so there is no value in optimising the rest.

THE CAMERA IS HELD EXCLUSIVELY
    This cannot run at the same time as grab_basler.py -- whichever opens first
    wins. So this writes its own periodic /dev/shm snapshot (--snapshot-every),
    otherwise you are blind while it runs. It does NOT serve MJPEG; stop it and
    go back to grab_basler.py if you want the browser view.

ORIENTATION
    No flip flags. The camera has the correct orientation saved in UserSet1 and
    UserSetDefault=UserSet1, so the raw array is already right and every tool
    inherits the same frame. Adding a single flip here would mirror the image
    and silently reverse the apparent sense of rotation.

HOW THE ANGLE IS MEASURED
    The white dot on the rotor, as the weighted centroid of the brightest
    N_BRIGHT pixels in the rotor region. Deliberately threshold-free: a
    percentile/connected-component detector was tried first and dropped frames
    whenever the dot dimmed, silently substituting a different bright feature.
    The centroid is always defined, and a bad frame shows up as a radial
    outlier rather than a plausible-looking wrong answer.

    Angle is atan2 about the fitted rotation centre, so it is a full 360 deg --
    no mod-180 ambiguity, and no divisor convention of the kind that has cost
    the LES analyses repeatedly.

    Centre: --centre x,y to pin it, else fitted from the first --calib-s
    seconds. The fit needs the rotor to MOVE through a decent arc; if it is
    sitting still the fit is meaningless and the script says so.

QUALITY
    Each row carries the radial residual from the fitted circle. Frames where
    that exceeds --max-resid are flagged bad. Measured 2026-10-28: 84% of frames
    within 3 px. Below ~100% a feedback loop would occasionally commutate on a
    wrong angle, so watch this number.
"""
import cv2                       # must come before pypylon (CXXABI clash)
import numpy as np
from pypylon import pylon

import argparse, os, signal, sys, time
from datetime import datetime

_GPS_UNIX_OFFSET = 315964800 - 18
N_BRIGHT = 60                    # pixels in the centroid window


def gps_now():
    return time.time() - _GPS_UNIX_OFFSET


def dot_centroid(frame, box):
    """Weighted centroid of the brightest N_BRIGHT pixels inside box=(x0,y0,x1,y1)."""
    x0, y0, x1, y1 = box
    sub = cv2.GaussianBlur(frame[y0:y1, x0:x1].astype(np.float32), (3, 3), 0)
    flat = sub.ravel()
    idx = np.argpartition(flat, -N_BRIGHT)[-N_BRIGHT:]
    ys, xs = np.unravel_index(idx, sub.shape)
    w = flat[idx] - flat[idx].min() + 1e-6
    return (float(np.average(xs, weights=w)) + x0,
            float(np.average(ys, weights=w)) + y0,
            float(flat[idx].mean()),
            int((flat[idx] >= 254).sum()))


def fit_circle(X, Y):
    A = np.c_[X, Y, np.ones(len(X))]
    sol, *_ = np.linalg.lstsq(A, np.asarray(X)**2 + np.asarray(Y)**2, rcond=None)
    cx, cy = sol[0] / 2, sol[1] / 2
    return cx, cy, float(np.hypot(np.asarray(X) - cx, np.asarray(Y) - cy).mean())


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--exposure', type=float, default=8.0, help='ms (default 8)')
    p.add_argument('--gain', type=float, default=0.0)
    p.add_argument('--fps', type=float, default=50.0)
    p.add_argument('--roi', type=str, default='544,432,256,292')
    p.add_argument('--box', type=str, default=None,
                   help='rotor search box x0,y0,x1,y1 in ROI coords (default: the '
                        'middle ~70%%, which excludes the standoff glints at the edges)')
    p.add_argument('--centre', type=str, default=None, help='pin the rotation centre: x,y')
    p.add_argument('--calib-s', type=float, default=20.0,
                   help='seconds of frames used to fit the centre when --centre is absent')
    p.add_argument('--max-resid', type=float, default=3.0, help='px, flags a bad frame')
    p.add_argument('--csv', default=None, help='append rows here')
    p.add_argument('--snapshot', default='/dev/shm/rotor_angle_latest.jpg')
    p.add_argument('--snapshot-every', type=float, default=0.5)
    p.add_argument('--duration', type=float, default=0.0, help='0 = until Ctrl-C')
    p.add_argument('--quiet', action='store_true', help='CSV only, no per-second console line')
    args = p.parse_args()

    tl = pylon.TlFactory.GetInstance()
    devs = tl.EnumerateDevices()
    if not devs:
        sys.exit('no Basler found')
    cam = pylon.InstantCamera(tl.CreateFirstDevice())
    cam.Open()
    x, y, w, h = (int(v) for v in args.roi.split(','))
    cam.OffsetX.Value = 0; cam.OffsetY.Value = 0
    cam.Width.Value = w - (w % cam.Width.Inc)
    cam.Height.Value = h - (h % cam.Height.Inc)
    cam.OffsetX.Value = x - (x % cam.OffsetX.Inc)
    cam.OffsetY.Value = y - (y % cam.OffsetY.Inc)
    try:
        cam.ExposureTime.Value = args.exposure * 1000.0
    except Exception:
        cam.ExposureTimeAbs.Value = args.exposure * 1000.0
    try:
        cam.Gain.Value = args.gain
    except Exception:
        pass
    if args.fps > 0:
        cam.AcquisitionFrameRateEnable.Value = True
        cam.AcquisitionFrameRate.Value = args.fps
    W, H = cam.Width.Value, cam.Height.Value
    box = tuple(int(v) for v in args.box.split(',')) if args.box else \
          (int(W*0.15), int(H*0.15), int(W*0.85), int(H*0.85))
    print(f'# {W}x{H} ROI, exposure {args.exposure} ms, fps {args.fps}, box {box}')

    stop = {'f': False}
    signal.signal(signal.SIGINT, lambda *a: stop.__setitem__('f', True))
    cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

    cx = cy = R = None
    if args.centre:
        cx, cy = (float(v) for v in args.centre.split(','))
        print(f'# centre pinned at ({cx:.1f},{cy:.1f}); radius fitted as data arrives')

    fh = None
    if args.csv:
        new = not os.path.exists(args.csv)
        fh = open(args.csv, 'a', buffering=1)
        if new:
            fh.write('host_time,gps,cam_ts_ns,block_id,x,y,angle_deg,radius_px,'
                     'resid_px,brightness,n_sat,good\n')

    cal_x, cal_y = [], []
    t0 = time.time(); last_snap = 0.0; last_report = 0.0
    n = n_good = 0; t_proc = 0.0
    print(f'{"time":>8} {"fps":>6} {"angle":>8} {"resid":>6} {"bright":>7} {"sat":>4} {"good%":>6}')
    try:
        while not stop['f']:
            if args.duration and time.time() - t0 > args.duration:
                break
            res = cam.RetrieveResult(2000, pylon.TimeoutHandling_Return)
            if not res.GrabSucceeded():
                res.Release(); continue
            host = time.time()
            frame = res.Array
            blk = int(res.BlockID); cts = int(res.TimeStamp)
            res.Release()

            tp = time.perf_counter()
            px, py, bright, nsat = dot_centroid(frame, box)
            t_proc += time.perf_counter() - tp
            n += 1

            if cx is None:
                cal_x.append(px); cal_y.append(py)
                if time.time() - t0 >= args.calib_s:
                    spread = np.hypot(np.ptp(cal_x), np.ptp(cal_y))
                    if spread < 10:
                        print(f'! dot moved only {spread:.1f} px during calibration -- '
                              f'cannot fit a centre. Excite the rotor, or pass --centre.')
                        break
                    cx, cy, R = fit_circle(cal_x, cal_y)
                    print(f'# centre fitted ({cx:.1f},{cy:.1f}) radius {R:.1f} px '
                          f'from {len(cal_x)} frames, arc spread {spread:.0f} px')
                continue

            rad = float(np.hypot(px - cx, py - cy))
            if R is None:
                cal_x.append(px); cal_y.append(py)
                if len(cal_x) > 200: _, _, R = fit_circle(cal_x, cal_y)
                continue
            resid = abs(rad - R)
            ang = float(np.degrees(np.arctan2(py - cy, px - cx))) % 360.0
            good = resid <= args.max_resid
            n_good += good

            if fh:
                fh.write(f'{host:.6f},{host-_GPS_UNIX_OFFSET:.6f},{cts},{blk},'
                         f'{px:.3f},{py:.3f},{ang:.3f},{rad:.3f},{resid:.3f},'
                         f'{bright:.1f},{nsat},{int(good)}\n')
            if args.snapshot and host - last_snap >= args.snapshot_every:
                v = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                cv2.circle(v, (int(px), int(py)), 8, (0, 0, 255), 1)
                cv2.drawMarker(v, (int(cx), int(cy)), (0, 255, 0), cv2.MARKER_CROSS, 11, 1)
                cv2.imwrite(args.snapshot, v, [cv2.IMWRITE_JPEG_QUALITY, 85])
                last_snap = host
            if not args.quiet and host - last_report >= 1.0:
                el = host - t0
                print(f'{el:8.1f} {n/max(el,1e-9):6.1f} {ang:8.2f} {resid:6.2f} '
                      f'{bright:7.1f} {nsat:4d} {n_good/max(n,1)*100:5.0f}%', flush=True)
                last_report = host
    finally:
        cam.StopGrabbing(); cam.Close()
        if fh: fh.close()
        el = time.time() - t0
        print(f'\n{n} frames in {el:.1f} s = {n/max(el,1e-9):.1f} fps; '
              f'angle compute {t_proc/max(n,1)*1000:.3f} ms/frame; '
              f'good {n_good/max(n,1)*100:.0f}%')
        if cx is not None:
            print(f'centre ({cx:.1f},{cy:.1f}) radius {R:.1f} px' if R else '')


if __name__ == '__main__':
    sys.exit(main())
