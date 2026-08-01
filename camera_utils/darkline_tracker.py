#!/usr/bin/env python3
"""Dark-line rotor angle tracker.

Distilled from the spoke tracker in runbrakereverse.py / spinner_learned.py, adapted
for rotors whose trackable feature is a thin DARK line through the centre (as opposed
to the outer teeth). Validated on output_roi_gps1468161639.avi: it captures the
libration phase (bounded wobble) and the spin-up (~4.4 rev @ ~0.12 Hz), and the total
agrees with an independent teeth-harmonic method (~4.1 rev).

Two things that mattered versus the stock tracker:
  1. Sample an INNER radial band (~0.12-0.45 R) where the dark line lives, not the
     0.48-0.84 R teeth band (12-fold teeth alias a single-minimum tracker).
  2. CONTINUITY GATING: the per-frame arg-min is stateless and over-counts on jumps;
     pick the dark minimum nearest the predicted angle instead. (monotone frac 0.12 ->
     0.80, net 9.4 -> 4.4 rev.)

The measured angle is modulo pi (the line is diametric / 2-fold), unwrapped across
frames into a continuous angle. Confidence here is darkness-based and can read low even
when tracking is correct -- prefer loop-closure / cross-method to validate a new sample.

CLI:  python darkline_tracker.py VIDEO [--cx --cy --radius] [--r-in --r-out]
                                       [--csv out.csv] [--plot out.png]
"""
import argparse
import math

import cv2
import numpy as np

TAU = 2.0 * math.pi


class DarkLineTracker:
    def __init__(self, center=None, radius=None,
                 r_in=0.12, r_out=0.45,
                 angular_samples=720, radial_samples=48,
                 broad_width=61, fine_width=9,
                 step_sigma_deg=20.0, vel_smooth=0.6):
        self.center = center            # (cx, cy) or None -> auto-detect
        self.radius = radius            # px or None -> auto-detect
        self.r_in, self.r_out = r_in, r_out
        self.AS, self.RS = angular_samples, radial_samples
        self.half = angular_samples // 2
        self.broad_width, self.fine_width = broad_width, fine_width
        self.step_sigma = math.radians(step_sigma_deg)
        self.vel_smooth = vel_smooth
        self._maps = None               # cached remap grids
        self.reset()

    def reset(self):
        self.acc = None                 # continuous angle (rad, mod-pi unwrapped)
        self.vel = 0.0                  # per-frame angular velocity estimate (rad)
        self.n = 0

    # -- geometry -----------------------------------------------------------
    def _detect_geometry(self, gray):
        scale = 0.75
        small = cv2.medianBlur(
            cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA), 7)
        h, w = small.shape
        circles = cv2.HoughCircles(small, cv2.HOUGH_GRADIENT, dp=1.2,
                                   minDist=min(h, w) * 0.15, param1=100, param2=35,
                                   minRadius=int(min(h, w) * 0.10),
                                   maxRadius=int(min(h, w) * 0.46))
        if circles is None:
            raise RuntimeError("Could not auto-detect the rotor circle; pass "
                               "center=(cx,cy) and radius=...")
        cand = circles[0]
        img_c = np.array([w / 2.0, h / 2.0])
        score = np.linalg.norm(cand[:, :2] - img_c, axis=1) - 0.15 * cand[:, 2]
        best = cand[int(np.argmin(score))]
        self.center = (float(best[0] / scale), float(best[1] / scale))
        self.radius = float(best[2] / scale)

    def _build_maps(self):
        cx, cy = self.center
        r1, r2 = self.radius * self.r_in, self.radius * self.r_out
        phi = np.linspace(0.0, TAU, self.AS, endpoint=False, dtype=np.float32)
        radii = np.linspace(r1, r2, self.RS, dtype=np.float32)
        map_x = (cx + np.outer(radii, np.cos(phi))).astype(np.float32)
        map_y = (cy + np.outer(radii, np.sin(phi))).astype(np.float32)
        self._maps = (map_x, map_y)

    @staticmethod
    def _csmooth(v, width):
        width = max(3, int(width) | 1)
        pad = width // 2
        padded = np.concatenate([v[-pad:], v, v[:pad]])
        return np.convolve(padded, np.ones(width, np.float32) / width, mode="valid")

    # -- per-frame measurement ---------------------------------------------
    def _residual(self, gray):
        map_x, map_y = self._maps
        polar = cv2.remap(gray, map_x, map_y, interpolation=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REFLECT)
        full = np.median(polar, axis=0).astype(np.float32)          # per-angle intensity
        profile = 0.5 * (full[:self.half] + full[self.half:2 * self.half])  # fold mod-pi
        broad = self._csmooth(profile, self.broad_width)             # illumination
        return self._csmooth(profile - broad, self.fine_width)      # narrow dark spokes

    def update(self, frame):
        """Feed one frame (BGR, grayscale, or mono). Returns
        (angle_deg_continuous, angle_mod180_deg, confidence[0..1])."""
        gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = gray.astype(np.float32)
        if self.center is None or self.radius is None:
            self._detect_geometry(gray)
        if self._maps is None:
            self._build_maps()

        resid = self._residual(gray)
        sa = math.pi / self.half
        ang = np.arange(self.half) * sa
        med = float(np.median(resid))
        mad = float(np.median(np.abs(resid - med))) + 1e-6

        if self.acc is None:
            mi = int(np.argmin(resid))
            self.acc = mi * sa
        else:
            pred = self.acc + self.vel
            # signed mod-pi distance of every angle bin from the prediction
            dist = np.angle(np.exp(1j * 2.0 * (ang - pred))) / 2.0
            zdark = (resid - med) / (1.4826 * mad)          # negative in dark valleys
            cost = zdark + (dist / self.step_sigma) ** 2    # dark AND near prediction
            mi = int(np.argmin(cost))
            step = float(np.angle(np.exp(1j * 2.0 * (ang[mi] - pred))) / 2.0)
            self.acc = pred + step
            self.vel = (1 - self.vel_smooth) * self.vel + self.vel_smooth * (self.vel + step)

        # sub-sample refine around chosen bin
        l, m, r = resid[(mi - 1) % self.half], resid[mi], resid[(mi + 1) % self.half]
        denom = l - 2 * m + r
        if abs(denom) > 1e-9:
            self.acc += np.clip(0.5 * (l - r) / denom, -0.5, 0.5) * sa

        darkness_sigma = max(0.0, (med - float(resid[mi])) / (1.4826 * mad))
        conf = float(np.clip(darkness_sigma / 8.0, 0.0, 1.0))
        self.n += 1
        return math.degrees(self.acc), math.degrees(self.acc % math.pi), conf


def _run(args):
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    center = (args.cx, args.cy) if args.cx is not None and args.cy is not None else None
    trk = DarkLineTracker(center=center, radius=args.radius,
                          r_in=args.r_in, r_out=args.r_out)
    ts, ang, conf = [], [], []
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        a, _, c = trk.update(f)
        ts.append(i / fps); ang.append(a); conf.append(c); i += 1
    cap.release()
    ts, ang, conf = np.array(ts), np.array(ang), np.array(conf)
    ang -= ang[0] if len(ang) else 0.0
    print(f"{len(ang)} frames @ {fps:.1f} fps  center={trk.center}  radius={trk.radius:.1f}")
    if len(ang):
        print(f"net rotation: {(ang[-1]-ang[0])/360:+.2f} rev   median confidence {np.median(conf):.2f}")
    if args.csv:
        np.savetxt(args.csv, np.column_stack([ts, ang, conf]),
                   delimiter=",", header="t_s,angle_deg,confidence", comments="")
        print("wrote", args.csv)
    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
        ax[0].plot(ts, ang / 360, lw=1); ax[0].set_ylabel("cumulative angle (rev)")
        ax[0].grid(alpha=.3); ax[0].set_title(args.video)
        ax[1].plot(ts, conf, lw=.7, color="C1"); ax[1].set_ylabel("confidence")
        ax[1].set_xlabel("time (s)"); ax[1].grid(alpha=.3)
        plt.tight_layout(); plt.savefig(args.plot, dpi=90)
        print("wrote", args.plot)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("video")
    p.add_argument("--cx", type=float, default=None)
    p.add_argument("--cy", type=float, default=None)
    p.add_argument("--radius", type=float, default=None)
    p.add_argument("--r-in", type=float, default=0.12, help="inner band fraction of R")
    p.add_argument("--r-out", type=float, default=0.45, help="outer band fraction of R")
    p.add_argument("--csv", type=str, default=None)
    p.add_argument("--plot", type=str, default=None)
    _run(p.parse_args())
