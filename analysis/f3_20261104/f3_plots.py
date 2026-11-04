#!/usr/bin/env python3
"""Figures for F3 live run 2 (2026-11-04): spin-up, 0.5 rev/s hold, brake.

    python3 f3_plots.py [RUN_DIR] [OUT_DIR]

RUN_DIR (default Dropbox .../data/feedback/f3/live2) holds the tracker CSV (blob_live_*.csv) and the drive log
(feedback_*.csv, with '# phase NAME host_time' lines). Figures go to OUT_DIR (default plots/).
Energy E = w^2/2 + w0sq (1 - cos(theta - rest)), w0sq 4.94 rad/s^2 (F2 1x trap), rest 229.8 deg, as the controller.
"""
import csv
import glob
import os
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RUN = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/feedback/f3/live2')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), '..', '..', 'plots')
os.makedirs(OUT, exist_ok=True)
REST, W0SQ, TARGET, BAND, PUSH_MAX = 229.8, 4.94, 0.5, 0.2, 0.3
C = {'push+': '#2a78d6', 'push-': '#eb6834', 'off': '#c8c8c8', 'ink': '#333333', 'muted': '#777777'}
PH = {'spin': '#f2f2f2', 'hold': '#e6f2ea', 'brake': '#fbeee6'}
plt.rcParams.update({'font.size': 10, 'axes.edgecolor': '#bbbbbb', 'xtick.color': C['muted'], 'ytick.color': C['muted'],
                     'axes.grid': True, 'grid.color': '#e8e8e8', 'grid.linewidth': 0.6, 'axes.spines.top': False,
                     'axes.spines.right': False})

rows = list(csv.DictReader(l for l in open(glob.glob(os.path.join(RUN, 'blob_live_*.csv'))[0]) if not l.startswith('#')))
tt = np.array([float(r['host_time']) for r in rows])
ang = np.degrees(np.unwrap(np.radians([float(r['angle_deg']) for r in rows])))
ncc = np.array([float(r['ncc']) for r in rows])
logf = glob.glob(os.path.join(RUN, 'feedback_*.csv'))[0]
phases = []
for line in open(logf):
    if line.startswith('# phase'):
        _, _, name, ht = line.split()[:4]
        phases.append((name, float(ht)))
lg = list(csv.DictReader(l for l in open(logf) if not l.startswith('#')))
lt = np.array([float(r['host_time']) for r in lg]); lead = np.array([float(r['lead']) for r in lg])
psi = np.array([float(r['psi_deg']) for r in lg])
t0 = phases[0][1]
t = tt - t0; tl = lt - t0
bounds = [(n, h - t0) for n, h in phases]

# speed: smoothed derivative (0.1 s window)
from scipy.signal import medfilt
k = 5
a_s = np.convolve(medfilt(ang, 5), np.ones(k) / k, mode='same')   # median first: single-frame tracker jumps
w = np.gradient(a_s, t) / 360.0                       # rev/s, sign = image-angle direction
rel = np.radians(ang - REST)
E = 0.5 * np.radians(w * 360) ** 2 + W0SQ * (1 - np.cos(rel))
barrier = 2 * W0SQ
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lab_utils'))
try:
    from feedback_drive import energy_for_rate
    E_lo, E_hi = energy_for_rate(TARGET * (1 - BAND), W0SQ), energy_for_rate(TARGET * (1 + BAND), W0SQ)
except Exception:
    E_lo = E_hi = None

# completed turns (over the top: angle - rest crosses 180 + k*360)
u = np.floor((ang - REST - 180.0) / 360.0)
idx = np.where(np.diff(u) != 0)[0] + 1
turn_t = t[idx]; turn_dir = np.sign(np.diff(u)[idx - 1])
turn_rate = np.full(turn_t.size, np.nan)
turn_rate[1:] = turn_dir[1:] / np.diff(turn_t)
same = np.r_[False, turn_dir[1:] == turn_dir[:-1]]
turn_rate[~same] = np.nan

# drive state per log row: off / push along + / push along -   (lead -88 accelerates +, 167 accelerates -)
state = np.where(psi < 0, 'off', np.where(lead < 0, 'push+', 'push-'))
t_end = bounds[-1][1] if bounds[-1][0] == 'end' else tl[-1]


def shade(ax):
    for (n, a), (_, b) in zip(bounds[:-1], bounds[1:]):
        if n in PH:
            ax.axvspan(a, b, color=PH[n], zorder=0, lw=0)
    for n, a in bounds:
        ax.axvline(a, color='#bbbbbb', lw=0.6, zorder=1)


# ---------- figure 1: overview
fig, ax = plt.subplots(4, 1, figsize=(11, 10), sharex=True, gridspec_kw={'height_ratios': [1.1, 1.4, 1.1, 0.45]})
shade(ax[0]); ax[0].plot(t, (ang - REST) / 360.0, color=C['ink'], lw=1.2)
ax[0].set_ylabel('turns from rest')
for n, a in bounds[:-1]:
    ax[0].text(a + 1, ax[0].get_ylim()[1] if False else 0, '', fontsize=8)
ymax = np.nanmax((ang - REST) / 360.0)
for (n, a), (_, b) in zip(bounds[:-1], bounds[1:]):
    ax[0].text((a + b) / 2, ymax * 1.02, {'spin': 'spin-up', 'hold': 'hold 0.5 rev/s', 'brake': 'brake'}.get(n, n),
               ha='center', va='bottom', fontsize=9, color=C['ink'])
ax[0].set_title('F3 live run 2 (2026-11-04 20:41Z): feedback through EPICS, amp 4000 on pedestal 6400', loc='left', fontsize=11, color=C['ink'])

shade(ax[1])
ax[1].plot(t, w, color='#9a9a9a', lw=0.6, label='instantaneous speed')
ax[1].axhspan(TARGET * (1 - BAND), TARGET * (1 + BAND), color='#2a78d6', alpha=0.12, lw=0, label='target band 0.4-0.6 rev/s (mean per turn)')
ax[1].axhline(TARGET, color='#2a78d6', lw=1, ls='--')
ax[1].plot(turn_t, turn_rate, 'o', color=C['ink'], ms=4, label='mean rate of each full turn')
ax[1].axhline(0, color='#999999', lw=0.6)
ax[1].set_ylabel('rotation rate, rev/s\n(+ = increasing image angle)'); ax[1].set_ylim(-1.0, 1.0)
ax[1].legend(frameon=False, fontsize=8, loc='lower left', ncol=3)

shade(ax[2])
ax[2].plot(t, E / barrier, color=C['ink'], lw=0.7)
ax[2].axhline(1, color='#999999', lw=0.8, ls=':')
ax[2].text(t[-1], 1.01, 'top of the trap', ha='right', va='bottom', fontsize=8, color=C['muted'])
if E_lo:
    ax[2].axhspan(E_lo / barrier, E_hi / barrier, color='#2a78d6', alpha=0.12, lw=0)
    ax[2].text(t[-1], E_hi / barrier, 'energy band for 0.4-0.6 rev/s', ha='right', va='bottom', fontsize=8, color=C['muted'])
ax[2].set_ylabel('energy / barrier')
ax[2].set_ylim(0, 1.8)

for s_, y in (('push+', 2), ('push-', 1), ('off', 0)):
    m = state == s_
    ax[3].plot(tl[m], np.full(m.sum(), y), '|', color=C[s_], ms=7)
ax[3].set_yticks([0, 1, 2]); ax[3].set_yticklabels(['field off', 'push towards -', 'push towards +'], fontsize=8)
ax[3].set_ylim(-0.6, 2.6); ax[3].grid(False)
ax[3].set_xlabel('s from loop start')
ax[3].set_xlim(-2, t[-1])
fig.tight_layout(); fig.savefig(os.path.join(OUT, 'f3_live2_overview.png'), dpi=150); plt.close(fig)

# ---------- figure 2: one hold turn in detail: speed vs angle, where the drive pushes
hb = [b for n, b in bounds if n == 'hold'][0]; he = [b for n, b in bounds if n == 'brake'][0]
m = (t > hb) & (t < he)
phi = ((ang[m] - REST + 180) % 360) - 180              # angle from rest, -180..180 (0 = bottom of the trap)
fig, ax = plt.subplots(1, 2, figsize=(11, 4.3), gridspec_kw={'width_ratios': [1.6, 1]})
ax[0].plot(phi, np.abs(w[m]), '.', ms=1.2, color='#9a9a9a', label='rotor speed (tracker)')
st_at = np.interp(t[m], tl, (state == 'push+').astype(float) + 2 * (state == 'push-').astype(float))
for code, s_, lab in ((1, 'push+', 'drive pushing along the motion (+)'), (2, 'push-', 'drive pushing against it (-)')):
    mm = np.isclose(st_at, code)
    ax[0].plot(phi[mm], np.abs(w[m][mm]), '.', ms=2.5, color=C[s_], label=lab)
ax[0].axhline(PUSH_MAX, color='#999999', ls=':', lw=0.8)
ax[0].text(175, PUSH_MAX + 0.02, 'push only below 0.3 rev/s', ha='right', fontsize=8, color=C['muted'])
th = np.linspace(-180, 180, 361)
for Ev, lab in ((E_lo, '0.4 rev/s mean'), (E_hi, '0.6 rev/s mean')):
    if Ev:
        v = np.sqrt(np.clip(2 * (Ev - W0SQ * (1 - np.cos(np.radians(th)))), 0, None)) / (2 * np.pi)
        ax[0].plot(th, v, color='#2a78d6', lw=0.8, ls='--')
ax[0].set_xlabel('angle from rest, deg (0 = bottom of the trap, +-180 = top)')
ax[0].set_ylabel('speed, rev/s')
ax[0].set_title('Hold phase: the field stayed OFF (speed never fell below 0.3 rev/s): free rotation', loc='left', fontsize=10, color=C['ink'])
ax[0].legend(frameon=False, fontsize=8, loc='upper left')
ax[0].set_xlim(-180, 180)
ok = (turn_t > hb) & (turn_t < he) & np.isfinite(turn_rate)
ax[1].hist(np.abs(turn_rate[ok]), bins=np.linspace(0.4, 0.6, 21), color='#2a78d6')
ax[1].set_xlabel('mean rate per turn, rev/s'); ax[1].set_ylabel('turns')
ax[1].set_title(f'Hold: {ok.sum()} turns, {np.nanmin(np.abs(turn_rate[ok])):.3f}-{np.nanmax(np.abs(turn_rate[ok])):.3f} rev/s', loc='left', fontsize=10, color=C['ink'])
ax[1].set_xlim(0.4, 0.6)
fig.tight_layout(); fig.savefig(os.path.join(OUT, 'f3_live2_hold_detail.png'), dpi=150); plt.close(fig)

# ---------- figure 3: tracker match over the full circle
fig, ax = plt.subplots(figsize=(7, 3.4))
ab = ((ang - REST) % 360)
bins = np.arange(0, 361, 20)
med = [np.median(ncc[(ab >= a) & (ab < a + 20)]) for a in bins[:-1]]
mn = [np.min(ncc[(ab >= a) & (ab < a + 20)]) for a in bins[:-1]]
ax.plot(bins[:-1] + 10, med, '-o', color='#2a78d6', ms=4, label='median')
ax.plot(bins[:-1] + 10, mn, '-o', color='#eb6834', ms=3, label='minimum')
ax.axhline(0.7, color='#999999', ls=':', lw=0.8); ax.text(355, 0.705, 'watchdog 0.7', ha='right', fontsize=8, color=C['muted'])
ax.set_xlabel('angle from rest, deg'); ax.set_ylabel('tracker match (ncc)'); ax.set_ylim(0.65, 1.0); ax.set_xlim(0, 360)
ax.legend(frameon=False, fontsize=8, loc='lower left')
ax.set_title(f'Tracking over the full circle: {len(ncc)} frames, 0 dropped, none below 0.7', loc='left', fontsize=10, color=C['ink'])
fig.tight_layout(); fig.savefig(os.path.join(OUT, 'f3_live2_tracking.png'), dpi=150); plt.close(fig)
# ---------- figure 4: the trap measured from free rotation (hold phase; field off, so energy is conserved per turn)
m = (t > hb) & (t < he)
phi_all = ((ang[m] - REST + 180) % 360) - 180
ke = 0.5 * np.radians(w[m] * 360) ** 2                 # rad^2/s^2 (per unit I)
turn_id = np.floor((ang[m] - REST + 180) / 360.0)
U = np.full(ke.size, np.nan)
for tid in np.unique(turn_id):
    mm = turn_id == tid
    if mm.sum() < 50:
        continue
    bottom = np.abs(phi_all[mm]) < 10
    if not bottom.any():
        continue
    U[mm] = np.median(ke[mm][bottom]) - ke[mm]         # U(phi) - U(bottom), from energy conservation
bins = np.arange(-180, 181, 10)
Um = [np.nanmedian(U[(phi_all >= a) & (phi_all < a + 10)]) for a in bins[:-1]]
fig, ax = plt.subplots(figsize=(8, 4.2))
ax.plot(phi_all, U, '.', ms=1, color='#c8c8c8', label='each frame (hold, 33 turns)')
ax.plot(bins[:-1] + 5, Um, 'o-', color=C['ink'], ms=4, label='median per 10 deg')
th = np.linspace(-180, 180, 361)
ax.plot(th, W0SQ * (1 - np.cos(np.radians(th))), color='#2a78d6', lw=1.5, ls='--', label='1x trap from F2 (4.94 rad/s^2)')
ax.set_xlabel('angle from rest, deg'); ax.set_ylabel('trap potential U / I, rad^2/s^2')
ax.set_title('The trap over the full circle, from the free rotation (energy conservation)', loc='left', fontsize=10, color=C['ink'])
ax.legend(frameon=False, fontsize=8, loc='upper center'); ax.set_xlim(-180, 180); ax.set_ylim(-1, 13)
fig.tight_layout(); fig.savefig(os.path.join(OUT, 'f3_live2_trap_from_rotation.png'), dpi=150); plt.close(fig)
print('trap: U at +-180 (median of |phi|>170):', np.nanmedian(U[np.abs(phi_all) > 170]), ' 1x model 2*w0sq =', 2 * W0SQ)
imin = int(np.nanargmax(Um)); print('max of U at', bins[imin] + 5, 'deg')
print('hold turns', ok.sum(), 'rates', np.nanmin(np.abs(turn_rate[ok])), np.nanmax(np.abs(turn_rate[ok])))
print('figures in', os.path.abspath(OUT))
