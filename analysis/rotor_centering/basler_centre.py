#!/usr/bin/env python3
"""Rotor-vs-board centring from a Basler video (ROI 256x292). Written 2026-11-06.

    python basler_centre.py VIDEO.avi [--spot X,Y] [--board-guess X,Y] [--stride 5] [--plot plots/x.png]

Everything is relative to the board centre measured in the SAME frames, so it does not
care where the camera is. Prints, per 30 s quarter and for the whole video:
  board  : least-squares convergence of the radial spoke edges (Hough segments on the
           median frame, r 45-115 px from the guess, robust re-fit)
  edge   : circle fit to the rotor's outer rim on the max frame (bright rotor -> dark
           board, strongest falling gradient on 180 rays, r 30-55 px from the board centre)
  swing  : circle fit to the white mark's track (--spot given): brightness-weighted
           centroid above a percentile, at several percentiles, because on a short arc the
           fitted centre depends on that choice (see README)
Reads frames with ffmpeg (Mac OpenCV can't decode FFV1).
"""
import argparse, subprocess, sys
import numpy as np, cv2


def read_video(path, stride):
    W, H = map(int, subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                    'stream=width,height', '-of', 'csv=p=0', path],
                                   capture_output=True, text=True).stdout.strip().split(','))
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'select=not(mod(n\\,{stride}))',
                          '-vsync', '0', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W)


def fit_circle(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    A = np.c_[2 * x, 2 * y, np.ones_like(x)]
    (cx, cy, c), *_ = np.linalg.lstsq(A, x ** 2 + y ** 2, rcond=None)
    R = np.sqrt(c + cx ** 2 + cy ** 2)
    return cx, cy, R, float(np.sqrt(np.mean((np.hypot(x - cx, y - cy) - R) ** 2)))


def _converge(segs):
    A = np.zeros((2, 2)); b = np.zeros(2)
    for p, d in segs:
        P = np.eye(2) - np.outer(d, d); A += P; b += P @ p
    return np.linalg.solve(A, b)


def board_centre(med, guess, rmin=45, rmax=115):
    e = cv2.Canny(cv2.GaussianBlur(med, (3, 3), 0), 30, 90)
    yy, xx = np.mgrid[:med.shape[0], :med.shape[1]]
    guess = np.asarray(guess, float)
    for _ in range(3):
        r = np.hypot(xx - guess[0], yy - guess[1])
        L = cv2.HoughLinesP(e * ((r > rmin) & (r < rmax)).astype(np.uint8), 1, np.pi / 720, 25,
                            minLineLength=25, maxLineGap=3)
        segs = []
        for x1, y1, x2, y2 in L[:, 0]:
            p = np.array([x1, y1], float); d = np.array([x2 - x1, y2 - y1], float); d /= np.linalg.norm(d)
            rv = (p + [x2, y2]) / 2 - guess; rv /= np.linalg.norm(rv)
            if abs(rv @ d) > 0.97:                       # keep radial segments only
                segs.append((p, d))
        c = _converge(segs)
        for _ in range(3):
            miss = np.array([abs(np.cross(d, c - p)) for p, d in segs])
            segs = [s for s, m in zip(segs, miss) if m < max(3, 2.5 * np.median(miss))]
            c = _converge(segs)
        guess = c
    return c, len(segs)


def rotor_edge(img, c, rmin=30, rmax=55, nang=180):
    im = cv2.GaussianBlur(img.astype(np.float32), (5, 5), 1.2)
    rs = np.arange(rmin, rmax, 0.25); pts = []
    for a in np.linspace(0, 2 * np.pi, nang, endpoint=False):
        x = (c[0] + rs * np.cos(a)).astype(np.float32); y = (c[1] + rs * np.sin(a)).astype(np.float32)
        prof = cv2.remap(im, x[None], y[None], cv2.INTER_LINEAR)[0]
        g = -np.gradient(prof); i = np.argmax(g)              # bright inside -> dark outside
        pts.append((x[i], y[i], g[i]))
    p = np.array(pts); strong = p[:, 2] > np.percentile(p[:, 2], 30); keep = strong
    for _ in range(5):
        cx, cy, R, rms = fit_circle(p[keep, 0], p[keep, 1])
        res = np.abs(np.hypot(p[:, 0] - cx, p[:, 1] - cy) - R)
        keep = strong & (res < max(1.5, 2.5 * np.median(res[keep])))
    return (cx, cy, R, rms), p[keep]


def spot_track(frames, spot, pct=98, half=26):
    x, y = spot; P = []
    for g in frames:
        g = g.astype(np.float32)
        x0, x1, y0, y1 = int(x - half), int(x + half), int(y - half), int(y + half)
        roi = g[y0:y1, x0:x1]; w = np.clip(roi - np.percentile(roi, pct), 0, None)
        if w.sum() <= 0:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1]
        x, y = (w * xx).sum() / w.sum(), (w * yy).sum() / w.sum(); P.append((x, y))
    return np.array(P)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video')
    ap.add_argument('--board-guess', default='122,170')
    ap.add_argument('--spot', help='X,Y of the white mark in the first frame (enables the swing fit)')
    ap.add_argument('--stride', type=int, default=5)
    ap.add_argument('--fps', type=float, default=50.0)
    ap.add_argument('--plot', help='write an overlay PNG here (plots/ is gitignored)')
    a = ap.parse_args()

    v = read_video(a.video, a.stride); t = np.arange(len(v)) * a.stride / a.fps
    print(f'{a.video}: {len(v)} frames used (every {a.stride}), {t[-1]:.0f} s')
    guess = [float(s) for s in a.board_guess.split(',')]

    quarters = np.array_split(np.arange(len(v)), 4)
    for q in [np.arange(len(v))] + quarters:
        seg = v[q]
        med = np.median(seg, 0).astype(np.uint8); mx = seg.max(0)
        b, n = board_centre(med, guess)
        (ex, ey, eR, erms), pk = rotor_edge(mx, b)
        lab = 'all' if len(q) == len(v) else f'{t[q[0]]:4.0f}-{t[q[-1]]:4.0f} s'
        print(f'  {lab:>11}: board ({b[0]:.1f}, {b[1]:.1f}) [{n} segs]   rotor edge ({ex:.1f}, {ey:.1f}) '
              f'R {eR:.1f} rms {erms:.1f}   edge - board ({ex - b[0]:+.1f}, {ey - b[1]:+.1f}) px')
        if len(q) == len(v):
            B, E, MED, MX, PK = b, (ex, ey, eR), med, mx, pk

    print('  board-centre robustness (3 guesses x 3 annuli):')
    bs = np.array([board_centre(MED, B + dg, r0, r1)[0] for dg in ([0, 0], [9, 0], [4, 2])
                   for r0, r1 in ((45, 115), (55, 120), (40, 100))])
    print(f'    x {bs[:, 0].min():.1f}..{bs[:, 0].max():.1f}  y {bs[:, 1].min():.1f}..{bs[:, 1].max():.1f}  '
          f'std ({bs[:, 0].std():.1f}, {bs[:, 1].std():.1f}) px')

    if a.spot:
        spot = [float(s) for s in a.spot.split(',')]
        print('  swing (white-mark track) centre vs spot definition:')
        for pct, half in ((98, 26), (99.5, 26), (95, 26), (98, 14), (90, 14)):
            P = spot_track(v, spot, pct, half); cx, cy, R, rms = fit_circle(P[:, 0], P[:, 1])
            ang = np.degrees(np.unwrap(np.arctan2(P[:, 1] - cy, P[:, 0] - cx)))
            print(f'    >{pct}th pct, box +-{half}: centre ({cx:.1f}, {cy:.1f}) R {R:.1f} rms {rms:.2f} '
                  f'arc {np.ptp(ang):.0f} deg   - board ({cx - B[0]:+.1f}, {cy - B[1]:+.1f})')

    if a.plot:
        S = 3
        def tile(img):
            lo, hi = np.percentile(img, (1, 99))
            im = np.clip((img.astype(np.float32) - lo) * 255 / max(hi - lo, 1), 0, 255).astype(np.uint8)
            im = cv2.cvtColor(cv2.resize(im, None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
            P = lambda x, y: (int(x * S), int(y * S))
            for x, y, _ in PK: cv2.circle(im, P(x, y), 2, (0, 255, 0), -1)
            cv2.circle(im, P(E[0], E[1]), int(E[2] * S), (0, 255, 255), 1)
            cv2.drawMarker(im, P(E[0], E[1]), (0, 255, 255), cv2.MARKER_CROSS, 24, 2)
            cv2.drawMarker(im, P(*B), (0, 0, 255), cv2.MARKER_TILTED_CROSS, 24, 2)
            return im
        out = np.hstack([tile(MED), tile(MX)])
        cv2.putText(out, 'median | max.  red x: board (spoke convergence)  yellow: rotor rim fit (green pts)',
                    (6, 18), 0, 0.5, (255, 255, 255), 1)
        cv2.imwrite(a.plot, out); print('  plot ->', a.plot)


if __name__ == '__main__':
    main()
