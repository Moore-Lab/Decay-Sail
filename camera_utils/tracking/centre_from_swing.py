#!/usr/bin/env python3
"""Rotation centre (and rest angle) from a video of the rotor SWINGING, for re-pinning live_blob_track.py after the
camera moved (2026-11-03). Tracks the white spot's intensity-weighted centroid in an ROI and fits a circle to it.

    python3 centre_from_swing.py VIDEO.avi --spot X,Y [--roi 26] [--step 2]

--spot: the spot's pixel position in the first frame (rough; see the printed brightest-region guesses if unsure).
Prints: the fitted centre (X,Y) and radius, the arc covered, residual; the tracker-convention angle of the swing's
centre (image angle, + = clockwise on screen, measured from +x, as blob_core uses, without its template offset).
Use the centre with `live_blob_track.py --centre X,Y`, then check the tracker on the same video with --replay:
the angle should follow the swing smoothly with median ncc >~ 0.9.
Reads frames through ffmpeg (OpenCV wheels on the Mac do not decode FFV1).
"""
import argparse
import subprocess

import numpy as np


def frames(path, step):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                            '-of', 'csv=p=0', path], capture_output=True, text=True).stdout.strip().split(',')
    W, H = int(probe[0]), int(probe[1])
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'select=not(mod(n\\,{step}))', '-vsync', '0',
                          '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE)
    while True:
        b = p.stdout.read(W * H)
        if len(b) < W * H:
            return
        yield np.frombuffer(b, np.uint8).reshape(H, W).astype(np.float32)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video')
    ap.add_argument('--spot', required=True, help='X,Y of the white spot in the first frame')
    ap.add_argument('--roi', type=int, default=26, help='half-size of the search box, px (follows the spot)')
    ap.add_argument('--step', type=int, default=2)
    a = ap.parse_args()
    x, y = [float(v) for v in a.spot.split(',')]
    pts = []
    for g in frames(a.video, a.step):
        x0, x1 = int(max(0, x - a.roi)), int(min(g.shape[1], x + a.roi))
        y0, y1 = int(max(0, y - a.roi)), int(min(g.shape[0], y + a.roi))
        roi = g[y0:y1, x0:x1]
        thr = np.percentile(roi, 98)
        w = np.clip(roi - thr, 0, None)
        if w.sum() <= 0:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1]
        x, y = (w * xx).sum() / w.sum(), (w * yy).sum() / w.sum()
        pts.append((x, y))
    P = np.array(pts)
    if max(np.ptp(P[:, 0]), np.ptp(P[:, 1])) < 10:
        raise SystemExit(f'! the spot moved only {np.ptp(P[:, 0]):.1f} x {np.ptp(P[:, 1]):.1f} px: no swing to fit a centre to')
    # Kasa circle fit: x^2 + y^2 + D x + E y + F = 0
    A = np.column_stack([P[:, 0], P[:, 1], np.ones(len(P))])
    b = -(P[:, 0] ** 2 + P[:, 1] ** 2)
    D, E, F = np.linalg.lstsq(A, b, rcond=None)[0]
    cx, cy = -D / 2, -E / 2
    r = np.sqrt(cx ** 2 + cy ** 2 - F)
    res = np.hypot(P[:, 0] - cx, P[:, 1] - cy) - r
    ang = np.degrees(np.arctan2(P[:, 1] - cy, P[:, 0] - cx))          # image angle, + = clockwise on screen (y down)
    ang = np.degrees(np.unwrap(np.radians(ang)))
    print(f'{len(P)} frames tracked; spot moved {np.ptp(P[:, 0]):.1f} x {np.ptp(P[:, 1]):.1f} px')
    print(f'centre {cx:.2f},{cy:.2f}  radius {r:.2f} px  arc {np.ptp(ang):.1f} deg  circle residual rms {res.std():.2f} px')
    if np.ptp(ang) < 20 or r < 10:
        print('! arc < 20 deg: the centre is poorly constrained; a larger swing is needed')
    print(f'swing: image angle {ang.min():.1f}..{ang.max():.1f} deg, middle {0.5 * (ang.min() + ang.max()):.1f} deg')
    print(f'use: live_blob_track.py --centre {cx:.1f},{cy:.1f}')


if __name__ == '__main__':
    main()
