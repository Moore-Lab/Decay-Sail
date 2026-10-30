"""Track the white blob's angle about a fixed rotation centre (gate 2).

    python blob_track.py VIDEO.avi WIDTH HEIGHT CENTRE.json REF_FRAME REF_ANGLE_DEG OUT.csv

Each frame is high-passed and unwrapped to polar (r, theta) about the centre, so a
rotation is a shift in theta. A blob template (r 12-35 px, +-28 deg) cut from REF_FRAME
at REF_ANGLE_DEG is matched to every frame by normalised cross-correlation, which does
not care how bright the blob is (side lighting makes it bright at the bottom of its orbit
and grey at the top). The search is over all 360 deg and +-8 px in r.

Two unwraps are matched and the higher NCC kept per frame:
  raw      works when the blob is bright;
  blanked  the sail (a bright line through the centre) zeroed first, so the template
           cannot lock onto it when the blob is dim. The sail finder is pulled onto the
           blob when the blob is bright, which is why the raw unwrap is kept too.
The angle is an absolute angle per frame (no tracking from frame to frame).

Columns: frame, angle_deg (image coords, x right, y down), r_px (template centre's
distance from the centre), ncc, ncc_elsewhere (best match >20 deg away), source.
First used 2026-10-30 on output_basler_gps1477419607.avi with REF 1100 at 82 deg.
"""
import json, subprocess, sys
import numpy as np, cv2

video, W, H, centre_file, REF, REF_ANG, out = sys.argv[1:8]
W, H, REF, REF_ANG = int(W), int(H), int(REF), float(REF_ANG)
cx, cy = json.load(open(centre_file))['centre_xy_px']
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                     capture_output=True, check=True).stdout
a = np.frombuffer(raw, np.uint8).reshape(-1, H, W); n = len(a)

Y, X = np.mgrid[:H, :W]; dx, dy = X - cx, Y - cy; r = np.hypot(dx, dy)
ann = (r > 8) & (r < 40)
k7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
# sail finder: line through the centre, bright on both halves (median, so the blob can't carry it alone)
sth = np.deg2rad(np.arange(0, 180, 0.5)); srr = np.r_[np.arange(-38, -9), np.arange(10, 39)]
SX = (cx + np.outer(np.cos(sth), srr)).astype(np.float32); SY = (cy + np.outer(np.sin(sth), srr)).astype(np.float32)
# polar grid, 1 deg x 1 px
TH = np.deg2rad(np.arange(360.)); RR = np.arange(42.)
MX = (cx + np.outer(RR, np.cos(TH))).astype(np.float32); MY = (cy + np.outer(RR, np.sin(TH))).astype(np.float32)

P_raw = np.empty((n, len(RR), 360), np.float32); P_blk = np.empty_like(P_raw)
for i, f in enumerate(a):
    g = f.astype(np.float32)
    s = (cv2.morphologyEx(f, cv2.MORPH_OPEN, k7) - cv2.GaussianBlur(g, (0, 0), 12)) * ann
    prof = cv2.remap(s.astype(np.float32), SX, SY, cv2.INTER_LINEAR)
    t = sth[np.argmax(np.minimum(np.median(prof[:, :29], 1), np.median(prof[:, 29:], 1)))]
    h = g - cv2.GaussianBlur(g, (0, 0), 8)
    P_raw[i] = cv2.remap(h, MX, MY, cv2.INTER_LINEAR)
    h[np.abs(-np.sin(t) * dx + np.cos(t) * dy) < 5] = 0
    P_blk[i] = cv2.remap(h, MX, MY, cv2.INTER_LINEAR)

R0, R1, HW, DR = 12, 36, 28, 8; PAD = HW + 1
k0 = int(round(REF_ANG))
T = P_raw[REF][R0:R1, np.arange(k0 - HW, k0 + HW + 1) % 360]

def sub(y0, y1, y2):
    q = y0 - 2 * y1 + y2
    return 0.5 * (y0 - y2) / q if q < 0 else 0.

def match(p):
    img = np.concatenate([p[:, -PAD:], p, p[:, :PAD]], 1)[R0 - DR:R1 + DR]
    c = cv2.matchTemplate(img, T, cv2.TM_CCOEFF_NORMED); j = np.unravel_index(np.argmax(c), c.shape)
    col = c.max(0); d = np.abs(((np.arange(len(col)) - j[1]) + 180) % 360 - 180)
    da = sub(c[j[0], j[1] - 1], c[j], c[j[0], (j[1] + 1) % c.shape[1]])
    dr = sub(c[j[0] - 1, j[1]], c[j], c[j[0] + 1, j[1]]) if 0 < j[0] < c.shape[0] - 1 else 0.
    return (j[1] + da - PAD + HW) % 360, (R0 + R1 - 1) / 2 + j[0] - DR + dr, c[j], col[d > 20].max()

rows = []
for i in range(n):
    A, B = match(P_raw[i]), match(P_blk[i])
    best, src = (A, 'raw') if A[2] >= B[2] else (B, 'blanked')
    rows.append((i, *best, src))
with open(out, 'w') as fh:
    fh.write('# blob_track.py %s centre=(%.1f,%.1f) ref=%d@%.0fdeg\n' % (video.split('/')[-1], cx, cy, REF, REF_ANG))
    fh.write('frame,angle_deg,r_px,ncc,ncc_elsewhere,source\n')
    for row in rows: fh.write('%d,%.2f,%.2f,%.3f,%.3f,%s\n' % row)

ang = np.array([x[1] for x in rows]); rad = np.array([x[2] for x in rows])
step = np.abs((np.diff(ang) + 180) % 360 - 180)
xb, yb = cx + rad * np.cos(np.deg2rad(ang)), cy + rad * np.sin(np.deg2rad(ang))
M = np.c_[2 * xb, 2 * yb, np.ones(n)]; (fx, fy, fc), *_ = np.linalg.lstsq(M, xb**2 + yb**2, rcond=None)
print('%d frames; largest frame-to-frame step %.1f deg; r median %.2f px, std %.2f' % (n, step.max(), np.median(rad), rad.std()))
print('orbit circle fit (%.2f, %.2f) R=%.2f, %.2f px from the centre; radial scatter %.2f px' % (
    fx, fy, np.sqrt(fc + fx**2 + fy**2), np.hypot(fx - cx, fy - cy), np.hypot(xb - fx, yb - fy).std()))
