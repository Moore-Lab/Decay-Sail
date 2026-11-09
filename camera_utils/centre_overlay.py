#!/usr/bin/env python3
"""Click circles on the camera image and read how far the rotor is off the board centre.

For centring the rotor with the tilt stage. READS IMAGES ONLY: it never opens the
camera, so grab_basler.py keeps running (and recording) underneath it.

    # worker2 desktop (AnyDesk/console), with grab_basler.py running:
    python centre_overlay.py                      # reads /dev/shm/basler_latest.jpg
    # Mac on the lab LAN, grab_basler.py --mjpeg running on worker2:
    python centre_overlay.py --url http://worker2:8080/snapshot.jpg
    # offline, a recorded video or a still:
    python centre_overlay.py --video output_basler_gps1477428272.avi --frame 100
    python centre_overlay.py --image frame.png

HOW TO USE (keys act in the image window)
    b        board mode: click >= 3 points on a circular BOARD feature (the reference),
             e.g. the round pads at the ends of the outer-radius stator spokes
    r        rotor mode: click >= 3 points that sit at one radius on the ROTOR. Its edge is
             hard to see on the dark board centre, so the white dot is easier: click it,
             unfreeze, let it move, freeze, click again (points carry over), or use m
    Enter    fit a circle to the clicked points of the current mode
    Bksp     undo last click        c   clear the current mode's points and circle
    space    freeze / unfreeze the live image (freeze before clicking)
    m        toggle a max-projection of the live frames since pressed: a moving white dot
             draws its orbit as a bright arc, whose centre is the rotor centre
    s        log the current offset to the CSV (and print it), and save a record of it:
             <log stem>_<YYYYmmdd-HHMMSS>.png   the overlay as shown (circles, clicked points)
             <log stem>_<YYYYmmdd-HHMMSS>_raw.png  the unprocessed frame
             <log stem>_<YYYYmmdd-HHMMSS>.json  source, frame, both fits, all clicked points
             The timestamp matches the CSV row's time, so names sort in click order.
    q / Esc  quit
    The board circle is saved to --ref (JSON) and reloaded next time. The rotor circle
    is not saved: after each tilt step, unfreeze, freeze, and click the rotor again.

WHAT THE NUMBERS MEAN
    dx, dy = rotor centre - board centre, in IMAGE pixels (+x right, +y down), for the
    frame shown. mm only if a scale is given (--mm-per-px, or a known diameter of
    either clicked circle); a diameter-derived scale is printed and labelled derived.
    The camera-to-board direction mapping is not established (docs/STATUS.md), so learn
    which tilt knob moves the rotor which way from successive logged rows.

CAVEATS
    * One frame gives the rotor's instantaneous position, not the trap centre. If it is
      swinging, wait for it to settle or log several frames and average.
    * An oblique view turns circles into ellipses; the circle fit is then approximate.
    * If the camera is not fixed to the chamber, a tilt step also moves the board in the
      image: re-fit the board circle (b, clicks, Enter) after each step.
"""
import argparse, csv, json, os, subprocess, sys, time, urllib.request
from datetime import datetime

import cv2
import numpy as np


# ------------------------------------------------------------------ geometry
def fit_circle(x, y):
    """Algebraic least-squares circle (as in tracking/centre_estimate.py).
    Returns cx, cy, R, rms radial residual (px)."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    A = np.c_[2 * x, 2 * y, np.ones_like(x)]
    b = x ** 2 + y ** 2
    (cx, cy, c), *_ = np.linalg.lstsq(A, b, rcond=None)
    R = np.sqrt(c + cx ** 2 + cy ** 2)
    rms = float(np.sqrt(np.mean((np.hypot(x - cx, y - cy) - R) ** 2)))
    return float(cx), float(cy), float(R), rms


def display_stretch(img, lo=1, hi=99):
    """Percentile contrast stretch for display only (same as grab_basler.py)."""
    p_lo, p_hi = np.percentile(img, (lo, hi))
    if p_hi <= p_lo:
        return img
    out = (img.astype(np.float32) - p_lo) * (255.0 / (p_hi - p_lo))
    return np.clip(out, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ sources
def video_frame(path, n):
    """One Mono8 frame from a video via ffmpeg (Mac OpenCV can't decode FFV1)."""
    png = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'select=eq(n\\,{n})',
                          '-vframes', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'],
                         capture_output=True, check=True).stdout
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        sys.exit(f'could not read frame {n} of {path}')
    return img


def read_live(args):
    """Latest frame from the snapshot file or URL; None if not available yet."""
    try:
        if args.url:
            data = urllib.request.urlopen(args.url, timeout=2).read()
            return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
        return cv2.imread(args.snapshot, cv2.IMREAD_GRAYSCALE)  # None mid-write/missing
    except Exception:
        return None


# ------------------------------------------------------------------ main
def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group()
    src.add_argument('--snapshot', default='/dev/shm/basler_latest.jpg',
                     help='JPEG written by grab_basler.py (default /dev/shm/basler_latest.jpg)')
    src.add_argument('--url', help='snapshot URL, e.g. http://worker2:8080/snapshot.jpg')
    src.add_argument('--image', help='a still image')
    src.add_argument('--video', help='a recorded video (use with --frame)')
    p.add_argument('--frame', type=int, default=0, help='frame index for --video (default 0)')
    p.add_argument('--poll', type=float, default=0.5, help='live refresh period, s (default 0.5)')
    p.add_argument('--scale', type=float, default=3.0, help='display zoom (default 3)')
    p.add_argument('--no-stretch', action='store_true', help='show the raw image (no contrast stretch)')
    p.add_argument('--ref', default='centre_overlay_board.json',
                   help='JSON holding the board circle; loaded at start, saved on fit')
    p.add_argument('--log', default='centre_overlay_log.csv', help="CSV that 's' appends to")
    p.add_argument('--mm-per-px', type=float, help='image scale, if known')
    p.add_argument('--board-diameter-mm', type=float,
                   help='true diameter of the clicked board feature (sets the scale)')
    p.add_argument('--rotor-diameter-mm', type=float,
                   help='true diameter of the clicked rotor circle (sets the scale)')
    args = p.parse_args()

    live = not (args.image or args.video)
    if sys.platform.startswith('linux') and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        sys.exit('needs a graphical display: run at the worker2 desktop (console/AnyDesk), '
                 'or on the Mac with --url http://worker2:8080/snapshot.jpg')

    if args.image:
        frame = cv2.imread(args.image, cv2.IMREAD_GRAYSCALE)
        if frame is None:
            sys.exit(f'could not read {args.image}')
    elif args.video:
        frame = video_frame(args.video, args.frame)
    else:
        frame = None
        print('waiting for', args.url or args.snapshot, '...')
        while frame is None:
            frame = read_live(args)
            if frame is None:
                time.sleep(0.5)

    S = args.scale
    st = {'mode': 'b', 'pts': {'b': [], 'r': []}, 'circ': {'b': None, 'r': None},
          'frozen': not live, 'frame': frame, 'max': None,
          'fitpts': {'b': [], 'r': []}, 'shown': None}
    source = (f'video {args.video} frame {args.frame}' if args.video else
              f'image {args.image}' if args.image else f'url {args.url}' if args.url
              else f'snapshot {args.snapshot}')
    if os.path.exists(args.ref):
        with open(args.ref) as f:
            d = json.load(f)
        st['circ']['b'] = (d['cx'], d['cy'], d['R'], d.get('rms', 0.0))
        st['fitpts']['b'] = [tuple(q) for q in d.get('points', [])]
        print(f"board circle loaded from {args.ref} (fitted {d.get('time', '?')}): "
              f"centre ({d['cx']:.1f}, {d['cy']:.1f}) R {d['R']:.1f} px")

    def on_mouse(ev, x, y, flags, _):
        if ev == cv2.EVENT_LBUTTONDOWN:
            st['pts'][st['mode']].append((x / S, y / S))   # back to image pixels

    win = 'centre overlay'
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(win, on_mouse)

    def scale_mm():
        """(mm per px, label) or (None, None)."""
        if args.mm_per_px:
            return args.mm_per_px, 'given'
        for key, dia in (('b', args.board_diameter_mm), ('r', args.rotor_diameter_mm)):
            c = st['circ'][key]
            if dia and c:
                return dia / (2 * c[2]), f"derived from {'board' if key == 'b' else 'rotor'} D={dia} mm"
        return None, None

    def offset():
        b, r = st['circ']['b'], st['circ']['r']
        if not (b and r):
            return None
        return r[0] - b[0], r[1] - b[1]

    def draw():
        base = st['max'] if st['max'] is not None else st['frame']
        img = base if args.no_stretch else display_stretch(base)
        img = cv2.resize(img, None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST)
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        colours = {'b': (0, 220, 255), 'r': (255, 120, 255)}   # board yellow, rotor magenta
        for k in 'br':
            col = colours[k]
            for (px, py) in st['fitpts'][k]:     # points behind the current fit
                cv2.circle(img, (int(px * S), int(py * S)), 4, col, 1, cv2.LINE_AA)
            for (px, py) in st['pts'][k]:        # points not yet fitted
                cv2.drawMarker(img, (int(px * S), int(py * S)), col, cv2.MARKER_CROSS, 12, 1)
            c = st['circ'][k]
            if c:
                cx, cy, R = c[0] * S, c[1] * S, c[2] * S
                cv2.circle(img, (int(round(cx)), int(round(cy))), int(round(R)), col, 1, cv2.LINE_AA)
                cv2.drawMarker(img, (int(round(cx)), int(round(cy))), col, cv2.MARKER_CROSS, 20, 1)
        off = offset()
        b = st['circ']['b']
        if off and b:
            cv2.line(img, (int(b[0] * S), int(b[1] * S)),
                     (int((b[0] + off[0]) * S), int((b[1] + off[1]) * S)), (0, 255, 0), 1, cv2.LINE_AA)
        lines = [f"mode: {'BOARD' if st['mode'] == 'b' else 'ROTOR'}  "
                 f"({len(st['pts'][st['mode']])} pts)  {'FROZEN' if st['frozen'] else 'live'}"
                 f"{'  MAX' if st['max'] is not None else ''}"]
        for k, name in (('b', 'board'), ('r', 'rotor')):
            c = st['circ'][k]
            if c:
                lines.append(f"{name}: ({c[0]:.1f}, {c[1]:.1f}) R {c[2]:.1f} rms {c[3]:.1f} px")
        if off:
            d = np.hypot(*off)
            lines.append(f"dx {off[0]:+.1f}  dy {off[1]:+.1f}  |d| {d:.1f} px")
            mm, lab = scale_mm()
            if mm:
                lines.append(f"   = {off[0]*mm*1e3:+.0f}, {off[1]*mm*1e3:+.0f} um  |d| {d*mm*1e3:.0f} um")
        lines.append("b/r mode  Enter fit  Bksp undo  c clear  space freeze  m max  s log  q quit")
        for i, t in enumerate(lines):
            y = 18 + 18 * i
            cv2.putText(img, t, (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(img, t, (6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        st['shown'] = img
        cv2.imshow(win, img)

    def do_fit():
        k = st['mode']
        pts = st['pts'][k]
        if len(pts) < 3:
            print('need >= 3 points'); return
        x, y = zip(*pts)
        c = fit_circle(x, y)
        st['circ'][k] = c
        print(f"{'board' if k == 'b' else 'rotor'} fit: centre ({c[0]:.2f}, {c[1]:.2f}) "
              f"R {c[2]:.2f} px, rms {c[3]:.2f} px, {len(pts)} pts")
        if c[3] > 3:
            print(f"  WARNING: rms {c[3]:.1f} px is large; the points may not lie on one "
                  f"circle (e.g. pads at two radii). Undo with c and re-click.")
        if k == 'b':
            with open(args.ref, 'w') as f:
                json.dump({'cx': c[0], 'cy': c[1], 'R': c[2], 'rms': c[3], 'n_pts': len(pts),
                           'points': pts,
                           'time': datetime.now().isoformat(timespec='seconds')},
                          f, indent=1)
            print('  saved to', args.ref)
        st['fitpts'][k] = list(pts)
        st['pts'][k] = []

    def do_log():
        off = offset()
        if not off:
            print('fit both circles first'); return
        b, r = st['circ']['b'], st['circ']['r']
        mm, lab = scale_mm()
        new = not os.path.exists(args.log)
        now = datetime.now()
        row = [now.isoformat(timespec='seconds'), *(f'{v:.2f}' for v in b[:3]),
               *(f'{v:.2f}' for v in r[:3]), f'{off[0]:.2f}', f'{off[1]:.2f}',
               f'{mm:.5f}' if mm else '', lab or '']
        with open(args.log, 'a', newline='') as f:
            w = csv.writer(f)
            if new:
                w.writerow(['time', 'board_cx', 'board_cy', 'board_R', 'rotor_cx', 'rotor_cy',
                            'rotor_R', 'dx_px', 'dy_px', 'mm_per_px', 'scale_source'])
            w.writerow(row)
        print('logged:', ', '.join(row))
        base = f"{os.path.splitext(args.log)[0]}_{now:%Y%m%d-%H%M%S}"
        if st['shown'] is not None:
            img = st['shown'].copy()
            short = source.split(' ', 1)[0] + ' ' + os.path.basename(source.split(' ', 1)[1])
            cv2.putText(img, f"{short}  {row[0]}", (6, img.shape[0] - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imwrite(base + '.png', img)
        cv2.imwrite(base + '_raw.png', st['frame'])
        with open(base + '.json', 'w') as f:
            json.dump({'time': row[0], 'source': source,
                       'board': dict(zip(('cx', 'cy', 'R', 'rms'), b)), 'board_points': st['fitpts']['b'],
                       'rotor': dict(zip(('cx', 'cy', 'R', 'rms'), r)), 'rotor_points': st['fitpts']['r'],
                       'dx_px': off[0], 'dy_px': off[1], 'mm_per_px': mm, 'scale_source': lab,
                       'display': 'max-projection' if st['max'] is not None else 'frame'}, f, indent=1)
        print(f'  saved {base}.png, _raw.png, .json')

    last = 0.0
    while True:
        if live and not st['frozen'] and time.time() - last > args.poll:
            f = read_live(args)
            if f is not None:
                st['frame'] = f
                if st['max'] is not None and st['max'].shape == f.shape:
                    st['max'] = np.maximum(st['max'], f)
            last = time.time()
        draw()
        k = cv2.waitKey(30) & 0xFF
        if k in (ord('q'), 27):
            break
        elif k == ord('b'):
            st['mode'] = 'b'
        elif k == ord('r'):
            st['mode'] = 'r'
        elif k in (13, 10):
            do_fit()
        elif k in (8, 127):
            if st['pts'][st['mode']]:
                st['pts'][st['mode']].pop()
        elif k == ord('c'):
            st['pts'][st['mode']] = []; st['circ'][st['mode']] = None; st['fitpts'][st['mode']] = []
        elif k == ord(' '):
            st['frozen'] = not st['frozen'] if live else True
        elif k == ord('s'):
            do_log()
        elif k == ord('m'):
            st['max'] = None if st['max'] is not None else st['frame'].copy()
        if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
            break
    cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
