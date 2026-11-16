#!/usr/bin/env python3
"""Spin-up gate G1 (2026-11-16): trap, push map and write timing fitted from the 11-14/15 overnight drive logs.
Mac only, reads Dropbox; no hardware.

    python3 drive_fit.py          # -> drive_fit.json, drive_fit_stdout.txt (via shell), plots/ (gitignored)

Data: Dropbox spinup/2026-11-14/overnight/series/brake_*.csv (61 brake_offsets runs: 60 spin-ups at level 800, one
final brake at 1600). Every frame: angle (live tracker, 50 fps), and at each write: host write time and the levels
written to V2, V4, V3 (= phases A, B, C).

Model, per frame (rad, s):  alpha + omega / TAU = T(theta) + sum_q u_q(t) G_q(theta)
  T     trap acceleration, Fourier m = 0..MT over the full circle (free)
  u_q   level of phase q / 800, as landed (see timing), else 0
  G_q   push map of phase q (rad/s^2 at 800 counts): Fourier m in MSET (G1/B2 used {0, 8, 16})
  TAU   coast damping (34 min, analysis/overnight_20261114), fixed; negligible here
alpha is the 7-frame cubic Savitzky-Golay second derivative of the unwrapped angle; the regressors are passed through the
exact kernel that maps theta'' to that estimate (so the fit is unbiased by the smoothing). Frames within 5 of
ncc < 0.5 are dropped. Time = frame index x 20 ms + median offset to host (camera isochronous, DECISIONS).

Timing models compared:
  'const'  each write takes effect a fixed delay after its host write time (the controller's assumption: mean intake
           wait 62.5 ms + 30 ms); delay scanned.
  'grid'   the front end takes EPICS values only at its 8 Hz ticks (DECISIONS 2026-11-10). Ticks on the host clock every
           0.125 / (1 + R) s, R = front-end clock rate minus host (+0.1234 %: overnight_20261114 README; G1 refit
           1.001237). A write lands at the first tick after it and acts from tick + DELTA. Tick phase fitted per run;
           DELTA scanned.
Iterate: fit maps with one timing model, rescan timing per run with the maps fixed, refit.
"""
import csv
import glob
import json
import os
import sys

import numpy as np
from scipy.signal import savgol_coeffs

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-14/overnight/series')
DT = 0.02
TAU = 34.0 * 60
R = 0.001234
TICK = 0.125 / (1 + R)
MT = 24
MSET = (0, 8, 16)
G1MAP = dict(c8=0.2197, s8=-0.1149, c16=-0.4549, s16=-0.2857, const=-0.0292, shift=(0.0, -15.37, 13.83))

H = savgol_coeffs(7, 3, deriv=2, delta=DT, use='conv')


def make_kernel():
    n, j = 61, 30
    r = DT * DT * np.maximum(np.arange(n) - j, 0)
    y = np.convolve(r, H, 'same')
    k = y[j - 6:j + 7]
    return k


K = make_kernel()


def smooth(x):
    return np.convolve(x, K, 'same')


# Tracker centre correction (2026-11-16, derived): the overnight tracker ran about (131.03, 178.79), but the dot's
# circle (all 2.8 M frames, circle fit) is centred at (128.98, 176.60), radius 23.46 px; r_px varied 19.9-26.1 px once
# per turn. Angles are recomputed about the fitted centre, with r = R + e.u(theta) (first order).
SHIFT_PX = (-2.05, -2.19)
R_PX = 23.46
CORRECT = True


def correct(a):
    a = np.asarray(a, float)
    if CORRECT:
        ex, ey = SHIFT_PX
        r = R_PX + ex * np.cos(a) + ey * np.sin(a)
        a = np.arctan2(r * np.sin(a) - ey, r * np.cos(a) - ex)
    return np.unwrap(a)


def load_run(f):
    hdr = open(f).readline()
    rows = [r for r in csv.DictReader(l for l in open(f) if not l.startswith('#'))]
    fr = np.array([int(r['frame']) for r in rows])
    ft = np.array([float(r['frame_t']) for r in rows])
    t = (fr - fr[0]) * DT
    t = t + np.median(ft - t)
    th = correct(np.radians([float(r['angle']) for r in rows]))
    ncc = np.array([float(r['ncc']) for r in rows])
    w = [(float(r['write_t1']), float(r['V2']), float(r['V4']), float(r['V3'])) for r in rows if r['write_t1']]
    level = 1600.0 if '--level 1600' in hdr else 800.0
    d = -1 if '--dir -1' in hdr else 1
    alpha = np.convolve(th, H, 'same')
    omega = np.convolve(th, savgol_coeffs(7, 3, deriv=1, delta=DT, use='conv'), 'same')
    bad = ncc < 0.5
    good = ~np.convolve(bad, np.ones(11), 'same').astype(bool)
    good[:8] = False; good[-8:] = False
    return dict(name=os.path.basename(f)[6:-4], t=t, th=th, alpha=alpha, omega=omega, good=good, w2=omega ** 2,
                w=np.array(w).reshape(-1, 4), level=level, dir=d, spin='--spin-to 0.5' in hdr)


def u_of_t(run, model, p):
    """Landed level / 800 per phase (A, B, C = V2, V4, V3) at each frame."""
    t = run['t']; w = run['w']
    if model == 'const':
        eff = w[:, 0] + p['delay']
    else:
        n = np.ceil((w[:, 0] - p['phase']) / TICK)
        eff = p['phase'] + n * TICK + p['delta']
    # later writes landing on the same tick win: keep the last write per effective time
    order = np.argsort(eff, kind='stable')
    eff, lv = eff[order], w[order, 1:]
    keep = np.r_[eff[1:] != eff[:-1], True]
    eff, lv = eff[keep], lv[keep]
    idx = np.searchsorted(eff, t, side='right') - 1
    u = np.zeros((len(t), 3))
    m = idx >= 0
    u[m] = lv[idx[m]] / 800.0
    return u


def fourier(th, ms):
    cols = []
    for m in ms:
        if m == 0:
            cols.append(np.ones_like(th))
        else:
            cols += [np.cos(m * th), np.sin(m * th)]
    return np.array(cols).T


W2 = True          # add omega^2 B(theta): tracker angle-bias curvature (measured = theta + b(theta) gives
                   # alpha_meas = alpha + omega^2 b''), or any speed dependence of the trap


def design(run, u, mset=MSET):
    th = run['th']
    T = fourier(th, range(0, MT + 1))
    F = fourier(th, mset)
    P = np.hstack([u[:, [q]] * F for q in range(3)])
    X = np.hstack([T, P])
    if W2:
        X = np.hstack([X, run['w2'][:, None] * fourier(th, range(1, MT + 1))])
    Xs = np.apply_along_axis(smooth, 0, X)
    y = run['alpha'] + smooth(run['omega']) / TAU
    g = run['good']
    return Xs[g], y[g]


def fit(runs, us, mset=MSET):
    XX, Xy, n, yy = 0, 0, 0, 0
    for run, u in zip(runs, us):
        X, y = design(run, u, mset)
        XX = XX + X.T @ X; Xy = Xy + X.T @ y; n += len(y); yy += y @ y
    b = np.linalg.solve(XX + 1e-6 * np.eye(len(XX)), Xy)
    rss = yy - 2 * b @ Xy + b @ XX @ b
    cov = np.linalg.inv(XX + 1e-6 * np.eye(len(XX))) * rss / (n - len(b))
    return b, float(rss), n, cov


def run_rss(run, u, b, mset=MSET):
    X, y = design(run, u, mset)
    r = y - X @ b
    return float(r @ r), len(y)


def scan_run(run, b, model, mset=MSET):
    best = None
    grid = ([dict(delay=d) for d in np.arange(0.0, 0.2001, 0.005)] if model == 'const' else
            [dict(phase=ph, delta=de) for ph in np.arange(0, TICK, 0.005) for de in (0.0, 0.01, 0.02, 0.03, 0.04)])
    # phase is absolute host time modulo TICK; anchor at a multiple of TICK near the run start
    t0 = np.floor(run['t'][0] / TICK) * TICK
    res = []
    for p in grid:
        q = dict(p)
        if model == 'grid':
            q['phase'] = t0 + p['phase']
        rss, n = run_rss(run, u_of_t(run, model, q), b, mset)
        res.append((rss, p))
        if best is None or rss < best[0]:
            best = (rss, q, p)
    return best, res


def main():
    files = sorted(glob.glob(os.path.join(D, 'brake_*.csv')))
    runs = [load_run(f) for f in files]
    print(f'{len(runs)} runs, {sum(r["good"].sum() for r in runs)} good frames, '
          f'{sum(len(r["w"]) for r in runs)} writes, {sum(int((r["w"][:, 1:] > 0).any(1).sum()) for r in runs)} pushes')
    out = {}
    # 0. constant delay at the controller's assumption
    p0 = dict(delay=0.0925)
    us = [u_of_t(r, 'const', p0) for r in runs]
    b, rss, n, cov = fit(runs, us)
    rss_nopush, _, _, _ = (None, 0, 0, 0)
    print(f'const 92.5 ms: rms {np.sqrt(rss / n):.4f} rad/s^2 (n {n})')
    out['const_92ms_rms'] = np.sqrt(rss / n)
    # 1. iterate: scan per run, refit (const model, then grid model)
    for model in ('const', 'grid'):
        for it in range(3):
            bests = [scan_run(r, b, model)[0] for r in runs]
            us = [u_of_t(r, model, bb[1]) for r, bb in zip(runs, bests)]
            b, rss, n, cov = fit(runs, us)
            print(f'{model} iter {it}: rms {np.sqrt(rss / n):.4f} rad/s^2')
        out[f'{model}_rms'] = np.sqrt(rss / n)
        out[f'{model}_params'] = [dict(name=r['name'], **{k: float(v) for k, v in bb[2].items()}) for r, bb in zip(runs, bests)]
        out[f'{model}_b'] = b.tolist()
        out[f'{model}_cov_diag'] = np.diag(cov).tolist()
        if model == 'const':
            dl = np.array([bb[2]['delay'] for bb in bests])
            print(f'  best const delay per run: median {np.median(dl) * 1e3:.0f} ms, range {dl.min() * 1e3:.0f}-{dl.max() * 1e3:.0f}')
        else:
            ph = np.array([bb[1]['phase'] for bb in bests]); de = np.array([bb[2]['delta'] for bb in bests])
            tr = np.array([r['t'][0] for r in runs])
            # one tick grid all night? phases mod TICK vs time
            pm = np.mod(ph, TICK)
            print('  grid phase mod tick per run (ms):', ' '.join(f'{x * 1e3:.0f}' for x in pm))
            print(f'  delta per run: median {np.median(de) * 1e3:.0f} ms; counts', dict(zip(*np.unique(de, return_counts=True))))
            out['grid_phase_mod_tick'] = pm.tolist(); out['grid_run_t0'] = tr.tolist()
    json.dump(out, open(os.path.join(HERE, 'drive_fit.json'), 'w'), indent=1)
    np.save(os.path.join(HERE, 'plots', 'b_grid.npy'), b) if os.path.isdir(os.path.join(HERE, 'plots')) else None


if __name__ == '__main__':
    main()
