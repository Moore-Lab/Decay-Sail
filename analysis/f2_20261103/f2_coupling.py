#!/usr/bin/env python3
"""F2 (2026-11-03) analysis: trap torque vs angle, and the drive's torque vs field-rotor angle.

    python3 f2_coupling.py F2_DIR      (Dropbox Microspheres/TFINER/data/feedback/f2)

1. Trap: in the free swing after the scan (field off, ncc > 0.8), fit the angular acceleration
   (Savitzky-Golay, 9 frames, quadratic) to sum_k a_k sin(k theta) + b_k cos(k theta), k = 1..4, + const
   - g * omega.
2. Drive: during the scan, take the residual acceleration after the trap model and regress it on
   sin/cos(delta) and sin/cos(2 delta), delta = psi_applied - s*m*theta. psi_applied = the logged command
   held from (write time + d) to the next write; d is scanned (0-0.2 s) and the best fit is kept.
   s*m in (-8, -16, -24, -4, +8, +16, +24, +4). Null: the same fit with the command sequence shifted in
   time (20 random shifts).
3. Torque-optimal field-rotor angles from the fitted 1x + 2x coupling.
Analysis only.
"""
import csv, os, sys
import numpy as np
from scipy.signal import savgol_filter

D = sys.argv[1]
B = list(csv.DictReader(l for l in open(os.path.join(D, 'blob_live_gps1477756297.csv')) if not l.startswith('#')))
t = np.array([float(r['host_time']) for r in B]); th = np.unwrap(np.radians([float(r['angle_deg']) for r in B]))
ncc = np.array([float(r['ncc']) for r in B])
dtf = np.median(np.diff(t)); acc = savgol_filter(th, 9, 2, deriv=2, delta=dtf); om = savgol_filter(th, 9, 2, deriv=1, delta=dtf)
L = list(csv.DictReader(l for l in open(os.path.join(D, 'feedback_1477757064.csv')) if not l.startswith('#')))
lt = np.array([float(r['host_time']) for r in L]); psi = np.radians([float(r['psi_deg']) for r in L])
trapX = lambda x: np.c_[[f(k * x) for k in (1, 2, 3, 4) for f in (np.sin, np.cos)]].T

fr = (t > lt[-1] + 20) & (t < lt[-1] + 700) & (ncc > 0.8)
Xf = np.c_[trapX(th[fr]), np.ones(fr.sum()), om[fr]]
cf, *_ = np.linalg.lstsq(Xf, acc[fr], rcond=None); rf = acc[fr] - Xf @ cf
print('1. trap (free swing, %d frames, angle %.0f..%.0f deg): R^2 %.3f; harmonics (rad/s^2) %s; damping %.2e /s'
      % (fr.sum(), np.degrees(th[fr]).min(), np.degrees(th[fr]).max(), 1 - rf.var() / acc[fr].var(),
         ' '.join('%dx %.2f' % (k + 1, np.hypot(cf[2 * k], cf[2 * k + 1])) for k in range(4)), -cf[-1]))

sc = (t > lt[0] + 0.5) & (t < lt[-1]) & (ncc > 0.8)
res = acc[sc] - np.c_[trapX(th[sc]), np.ones(sc.sum()), om[sc]] @ cf


def fit(sm, d, seq=psi):
    k = np.searchsorted(lt + d, t[sc], side='right') - 1; ok = k >= 0
    dl = seq[k[ok]] - sm * th[sc][ok]
    X = np.c_[np.sin(dl), np.cos(dl), np.sin(2 * dl), np.cos(2 * dl)]
    c, *_ = np.linalg.lstsq(X, res[ok], rcond=None); r = res[ok] - X @ c
    return 1 - r.var() / res[ok].var(), c


print('2. drive coupling (%d scan frames):' % sc.sum())
for sm in (-8, -16, -24, -4, 8, 16, 24, 4):
    R2, d = max((fit(sm, d)[0], d) for d in np.arange(0.0, 0.2, 0.01))
    print('   pattern %+3d*theta: best R^2 %.3f at delay %.2f s' % (sm, R2, d))
rng = np.random.default_rng(0)
null = [fit(-8, 0.07, np.roll(psi, rng.integers(50, 600)))[0] for _ in range(20)]
print('   null (command sequence shifted): R^2 median %.3f, max %.3f' % (np.median(null), max(null)))
R2, d = max((fit(-8, d)[0], d) for d in np.arange(0.0, 0.3, 0.005))
_, c = fit(-8, d)
print('   -8*theta, best delay %.3f s: 1x %.2f rad/s^2 (phase %.0f), 2x %.2f rad/s^2 (phase %.0f)'
      % (d, np.hypot(c[0], c[1]), np.degrees(np.arctan2(c[1], c[0])), np.hypot(c[2], c[3]), np.degrees(np.arctan2(c[3], c[2]))))
dd = np.radians(np.arange(-180, 180, 1.0))
f = c[0] * np.sin(dd) + c[1] * np.cos(dd) + c[2] * np.sin(2 * dd) + c[3] * np.cos(2 * dd)
print('3. field-rotor angle for max + accel %+.0f deg (%.2f rad/s^2); for max - accel %+.0f deg (%.2f rad/s^2)'
      % (np.degrees(dd[np.argmax(f)]), f.max(), np.degrees(dd[np.argmin(f)]), f.min()))
