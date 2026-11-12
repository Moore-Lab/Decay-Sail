#!/usr/bin/env python3
"""Clip of a G2 live brake from the saved tracker video, with angle and commanded electrode overlaid. Mac only.

    python3 g2_clip.py [brake_csv_stem] [t_before] [t_after]    # default repeat 2 rerun, -5..+25 s
Writes Dropbox data/spinup/2026-11-11/g2/clips/<stem>_clip.mp4.
"""
import csv
import os
import subprocess
import sys

import cv2  # only for resize/putText
import numpy as np

D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-11/g2')
VID = os.path.join(D, 'tracker_2b', 'output_basler_gps1478481358')
stem = sys.argv[1] if len(sys.argv) > 1 else 'brake_1794446406'
tb, ta = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else (5.0, 25.0)
LAB = {'brake_1794446406': 'G2 repeat 2 (rerun)', 'brake_1794446727': 'G2 repeat 3'}.get(stem, stem)

rows = [r for r in csv.DictReader(l for l in open(os.path.join(D, stem + '.csv')) if not l.startswith('#'))]
bt = np.array([float(r['frame_t']) for r in rows])
ph = np.array([r['phase'] for r in rows])
V = np.array([[float(r['V2'] or 0), float(r['V4'] or 0), float(r['V3'] or 0)] for r in rows])
t0 = bt[np.argmax(ph == 'brake')]

fr = [r for r in csv.DictReader(open(VID + '.csv'))]
ft = np.array([float(r['host_time']) for r in fr])
bl = [r for r in csv.DictReader(l for l in open(os.path.join(D, 'tracker_2b', 'blob_live_gps1478481358.csv')) if not l.startswith('#'))]
bh = np.array([float(r['host_time']) for r in bl]); ba = np.array([float(r['angle_deg']) for r in bl])
ang = {}
for i, h in enumerate(ft):                       # match tracker angles to video frames by host time
    j = int(np.clip(np.searchsorted(bh, h), 0, len(bh) - 1))
    if abs(bh[j] - h) < 0.005:
        ang[i] = ba[j]
i0, i1 = np.searchsorted(ft, t0 - tb), np.searchsorted(ft, t0 + ta)
# decode with ffmpeg (OpenCV here has no FFV1): frames i0..i1-1 by index, gray8
dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', VID + '.avi', '-vf', f'select=between(n\\,{int(i0)}\\,{int(i1) - 1})',
                        '-vsync', '0', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE)
out = os.path.join(D, 'clips', stem + '_clip.mp4')
S = 3
W, H = 256 * S, 292 * S + 90
ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', '50',
                       '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', out], stdin=subprocess.PIPE)
COLS = {0: ((40, 40, 214), 'A'), 1: ((44, 160, 44), 'B'), 2: ((180, 119, 31), 'C')}
cx, cy = 117.5 * S, 165.1 * S
for i in range(int(i0), int(i1)):
    buf = dec.stdout.read(256 * 292)
    if len(buf) < 256 * 292:
        break
    img = np.frombuffer(buf, np.uint8).reshape(292, 256)
    t = ft[i] - t0
    g = img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    g = cv2.resize(g, (256 * S, 292 * S), interpolation=cv2.INTER_NEAREST)
    canvas = np.zeros((H, W, 3), np.uint8); canvas[:292 * S] = g
    k = min(np.searchsorted(bt, ft[i]), len(bt) - 1)
    on = [q for q in range(3) if V[k, q] > 0] if ft[i] >= t0 else []
    a = ang.get(i)
    # no angle line: the tracker's angle is relative to its template zero, not the image axes
    y = 292 * S + 30
    cv2.putText(canvas, f'{LAB}   t = {t:+5.1f} s', (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(canvas, f'angle {a:6.1f} deg' if a is not None else 'angle --', (10, y + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (0, 255, 255), 2)
    status = 'field OFF (observing)' if ft[i] < t0 else ('electrode ' + COLS[on[0]][1] + ' ON (800 counts)' if on else 'brake: all off')
    col = COLS[on[0]][0] if on else (200, 200, 200)
    cv2.putText(canvas, status, (330, y + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
    ff.stdin.write(canvas.tobytes())
ff.stdin.close(); ff.wait()
print(out, os.path.getsize(out))
