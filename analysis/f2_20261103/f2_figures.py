#!/usr/bin/env python3
"""Figures for F2 (2026-11-03). python3 f2_figures.py F2_DIR  ->  plots/f2_20261103_*.png (gitignored).
Same data and fits as f2_coupling.py."""
import csv, os, sys
import numpy as np
from scipy.signal import savgol_filter
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt

D = sys.argv[1]; OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'plots')
os.makedirs(OUT, exist_ok=True)
B = list(csv.DictReader(l for l in open(os.path.join(D, 'blob_live_gps1477756297.csv')) if not l.startswith('#')))
t = np.array([float(r['host_time']) for r in B]); th = np.unwrap(np.radians([float(r['angle_deg']) for r in B]))
ncc = np.array([float(r['ncc']) for r in B])
dtf = np.median(np.diff(t)); acc = savgol_filter(th, 9, 2, deriv=2, delta=dtf); om = savgol_filter(th, 9, 2, deriv=1, delta=dtf)
L = list(csv.DictReader(l for l in open(os.path.join(D, 'feedback_1477757064.csv')) if not l.startswith('#')))
lt = np.array([float(r['host_time']) for r in L]); psi = np.radians([float(r['psi_deg']) for r in L]); lead = np.array([float(r['lead']) for r in L])
trapX = lambda x: np.c_[[f(k * x) for k in (1, 2, 3, 4) for f in (np.sin, np.cos)]].T

# 1. rotor angle through prep hold, scan, free swing
t0 = lt[0]
fig, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
m = (t > t0 - 150) & (t < lt[-1] + 120)
ax[0].plot(t[m] - t0, np.degrees(th[m]) / 360, lw=0.7)
ax[0].set_ylabel('rotor angle (turns, image +)')
ax[1].plot(t[m] - t0, savgol_filter(om, 25, 2)[m] / (2 * np.pi), lw=0.6)
ax[1].set_ylabel('speed (rev/s)'); ax[1].set_xlabel('s from scan start')
for l in dict.fromkeys(lead):
    k = lead == l; a, b = lt[k][0] - t0, lt[k][-1] - t0
    for x in ax: x.axvspan(a, b, color='C1', alpha=0.08)
    ax[0].text((a + b) / 2, ax[0].get_ylim()[1], 'lead\n%+.0f' % l, ha='center', va='top', fontsize=7)
ax[0].set_title('F2 2026-11-03: rotor during the lead scan (shaded steps) and the free swing after')
fig.tight_layout(); fig.savefig(os.path.join(OUT, 'f2_20261103_rotor.png'), dpi=110); plt.close(fig)

# 2. trap: acceleration vs angle in the free swing, with the 4-harmonic fit
fr = (t > lt[-1] + 20) & (t < lt[-1] + 700) & (ncc > 0.8)
Xf = np.c_[trapX(th[fr]), np.ones(fr.sum()), om[fr]]; cf, *_ = np.linalg.lstsq(Xf, acc[fr], rcond=None)
ang = np.degrees(th[fr]) % 360
grid = np.radians(np.arange(0, 360, 1.0)); fit = np.c_[trapX(grid), np.ones(len(grid)), np.zeros(len(grid))] @ cf
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.plot(ang, acc[fr], ',', alpha=0.3, label='free swing, field off (each frame)')
ax.plot(np.degrees(grid), fit, 'r', label='fit: 1x-4x harmonics (1x = 4.94 rad/s^2)')
ax.set_xlabel('rotor image angle (deg)'); ax.set_ylabel('angular acceleration (rad/s^2)'); ax.set_ylim(-12, 12)
ax.set_title('Trap restoring acceleration vs angle (torque = I x accel, I = 1.1e-11 kg m^2)'); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(OUT, 'f2_20261103_trap.png'), dpi=110); plt.close(fig)

# 3. drive: residual acceleration vs field-rotor angle (delay 0.07 s), binned, with the 1x+2x fit
sc = (t > lt[0] + 0.5) & (t < lt[-1]) & (ncc > 0.8)
res = acc[sc] - np.c_[trapX(th[sc]), np.ones(sc.sum()), om[sc]] @ cf
k = np.searchsorted(lt + 0.07, t[sc], side='right') - 1; ok = k >= 0
dl = (psi[k[ok]] + 8 * th[sc][ok] + np.pi) % (2 * np.pi) - np.pi
X = np.c_[np.sin(dl), np.cos(dl), np.sin(2 * dl), np.cos(2 * dl)]; c, *_ = np.linalg.lstsq(X, res[ok], rcond=None)
bins = np.linspace(-np.pi, np.pi, 25); mid = (bins[1:] + bins[:-1]) / 2
mean = [res[ok][(dl >= a) & (dl < b)].mean() for a, b in zip(bins[:-1], bins[1:])]
sem = [res[ok][(dl >= a) & (dl < b)].std() / np.sqrt(max(1, ((dl >= a) & (dl < b)).sum())) for a, b in zip(bins[:-1], bins[1:])]
g = np.linspace(-np.pi, np.pi, 361)
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.errorbar(np.degrees(mid), mean, yerr=sem, fmt='o', ms=4, label='scan frames, binned (mean +- s.e.)')
ax.plot(np.degrees(g), c[0] * np.sin(g) + c[1] * np.cos(g) + c[2] * np.sin(2 * g) + c[3] * np.cos(2 * g), 'r',
        label='fit: 1x %.2f + 2x %.2f rad/s^2' % (np.hypot(c[0], c[1]), np.hypot(c[2], c[3])))
ax.axhline(0, color='k', lw=0.5)
ax.set_xlabel('field angle minus rotor pattern angle (-8 theta), electrical deg'); ax.set_ylabel('drive accel (rad/s^2)')
ax.set_title('Drive push vs where the field points relative to the rotor (amp 5000, delay 0.07 s)'); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(OUT, 'f2_20261103_drive_coupling.png'), dpi=110); plt.close(fig)
print('wrote', ', '.join('plots/f2_20261103_%s.png' % n for n in ('rotor', 'trap', 'drive_coupling')))
