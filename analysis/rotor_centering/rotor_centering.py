"""Rotor-on-stator centring from top-down microscope photos (rev G flex).

Usage:
    python rotor_centering.py BOARD_ONLY.jpg ROTOR1.jpg [ROTOR2.jpg ...] [--out DIR]

Board centre comes from the board-only photo: a circle fit to the stitching-via
ring (r = 3.15 mm, sets the px/mm scale) averaged with a radial edge fit of the
CTR disk. The camera must not move between shots; phase correlation against the
board-only photo checks this. The rotor centre is a robust circle fit to the
rotor's outer edge (outermost dark pixel followed by bright board on each ray).
See README.md for the 2026-10-21 result.
"""
import argparse, os
import cv2, numpy as np

VIA_RING_MM = 3.15


def fitc(P):
    x, y = P[:, 0], P[:, 1]
    A = np.c_[2 * x, 2 * y, np.ones(len(x))]
    s = np.linalg.lstsq(A, x**2 + y**2, rcond=None)[0]
    return s[0], s[1], np.sqrt(s[2] + s[0]**2 + s[1]**2)


def robust(P, thr=3):
    for _ in range(4):
        a, b, R = fitc(P)
        r = np.hypot(P[:, 0] - a, P[:, 1] - b) - R
        P = P[np.abs(r) < thr * (r.std() + 1e-9) + 1]
    return a, b, R, len(P), r.std()


def ray(img, c, th, rs):
    xs, ys = c[0] + rs * np.cos(th), c[1] + rs * np.sin(th)
    p = cv2.remap(img, xs.astype(np.float32)[None], ys.astype(np.float32)[None],
                  cv2.INTER_LINEAR)[0]
    return xs, ys, p


def board_centre(B):
    h, w = B.shape[:2]
    c0 = np.array([w / 2, h / 2])
    v = cv2.GaussianBlur(cv2.cvtColor(B, cv2.COLOR_BGR2HSV)[..., 2], (5, 5), 0)
    n, _, st, cen = cv2.connectedComponentsWithStats((v < 60).astype(np.uint8))
    P = np.array([cen[i] for i in range(1, n)
                  if 300 < st[i, 4] < 3000 and 0.7 < st[i, 2] / st[i, 3] < 1.4
                  and 1100 < np.hypot(*(cen[i] - c0)) < 1600])
    va, vb, vR, vn, _ = robust(P)
    scale = vR / VIA_RING_MM
    # CTR disk edge: strongest bright-to-dark step on rays from the via-ring centre
    g = cv2.GaussianBlur(cv2.cvtColor(B, cv2.COLOR_BGR2GRAY).astype(np.float32), (7, 7), 2)
    pts = []
    for th in np.linspace(0, 2 * np.pi, 720, endpoint=False):
        xs, ys, p = ray(g, (va, vb), th, np.arange(180, 320))
        d = np.diff(p); k = np.argmin(d)
        if d[k] < -4: pts.append((xs[k], ys[k]))
    da, db, *_ = robust(np.array(pts))
    print(f"via ring  ({va:.1f}, {vb:.1f}) n={vn}  scale {scale:.1f} px/mm")
    print(f"CTR disk  ({da:.1f}, {db:.1f})  |via-disk| = "
          f"{np.hypot(va - da, vb - db) / scale * 1e3:.0f} um")
    return np.array([(va + da) / 2, (vb + db) / 2]), scale


def rotor_fit(A, bc, scale):
    v = cv2.GaussianBlur(cv2.cvtColor(A, cv2.COLOR_BGR2HSV)[..., 2].astype(np.float32), (7, 7), 2)
    # rotor R ~ 1.7 mm. Keep the outer limit <= 2.07 mm: beyond that the "outermost
    # dark pixel" lands in the gaps between electrode fingers and the fit jumps to
    # R ~ 1.8-1.9 mm with ~0.2 mm fake offsets (checked 2026-10-22).
    rs = np.arange(int(1.38 * scale), int(2.07 * scale))
    c = bc.copy()
    for _ in range(3):
        pts = []
        for th in np.linspace(0, 2 * np.pi, 1440, endpoint=False):
            xs, ys, p = ray(v, c, th, rs)
            dark = np.nonzero(p < 70)[0]
            if len(dark) == 0: continue
            k = dark[-1]
            if k + 25 < len(p) and p[k + 5:k + 25].mean() > 110: pts.append((xs[k], ys[k]))
        P = np.array(pts)
        a, b, R, n, sd = robust(P, 2.0)
        c = np.array([a, b])
    return c, R, n, sd, P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("board_only")
    ap.add_argument("rotor", nargs="+")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    B = cv2.imread(a.board_only)
    bc, scale = board_centre(B)
    ref = cv2.cvtColor(B, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = ref.shape
    win = cv2.createHanningWindow((w, h), cv2.CV_32F)
    mask = np.ones_like(ref); cv2.circle(mask, (w // 2, h // 2), 900, 0, -1)
    tiles = []
    for f in a.rotor:
        A = cv2.imread(f)
        g = cv2.cvtColor(A, cv2.COLOR_BGR2GRAY).astype(np.float32)
        (sx, sy), _ = cv2.phaseCorrelate(ref * mask, g * mask, win)
        c, R, n, sd, P = rotor_fit(A, bc, scale)
        d = (c - bc) / scale * 1e3
        name = os.path.splitext(os.path.basename(f))[0]
        print(f"{name}: camera shift ({sx:+.1f},{sy:+.1f}) px  rotor R={R / scale:.3f} mm "
              f"n={n} rms={sd / scale * 1e3:.0f} um  offset dx={d[0]:+.0f} dy={d[1]:+.0f} "
              f"|d|={np.hypot(*d):.0f} um")
        vis = A.copy()
        cv2.circle(vis, tuple(int(x) for x in c), int(R), (255, 0, 255), 5)
        for p in P[::4]: cv2.circle(vis, (int(p[0]), int(p[1])), 6, (0, 0, 255), -1)
        cv2.drawMarker(vis, tuple(int(x) for x in c), (255, 0, 255), cv2.MARKER_CROSS, 90, 6)
        cv2.drawMarker(vis, tuple(int(x) for x in bc), (0, 200, 255), cv2.MARKER_CROSS, 90, 6)
        x0, y0 = int(bc[0]) - 1000, int(bc[1]) - 1000
        t = cv2.resize(vis[y0:y0 + 2000, x0:x0 + 2000], (800, 800))
        cv2.putText(t, f"{name}  |d| = {np.hypot(*d):.0f} um", (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 3)
        tiles.append(t)
    while len(tiles) % 2: tiles.append(np.zeros_like(tiles[0]))
    grid = np.vstack([np.hstack(tiles[i:i + 2]) for i in range(0, len(tiles), 2)])
    cv2.imwrite(os.path.join(a.out, "rotor_centering_fits.jpg"), grid)


if __name__ == "__main__":
    main()
