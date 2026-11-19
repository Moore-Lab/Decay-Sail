#!/usr/bin/env python3
"""Torque against rotor angle from the 50 fps tracker angles: noise floor for seeing the laser's push within a turn. (2026-11-19)
Mac only; reads the tracker cache made by `coasts.py` (LASER_DIR=.../2026-11-18/laser python3 coasts.py first) and the
coast files of the ND2 run.

    python3 angle_profile.py      # prints; plots/angle_profile_nd2_run.png (gitignored); angle_profile.json

Idea (D): per frame, angular acceleration theta'' = N(theta)/I from a Savitzky-Golay second derivative of the unwrapped
tracker angle. In a coast N = hill torque (gravity/magnetic, lab-fixed, speed-independent) + drag (sign follows the
rotation) + laser (lab-fixed, same sign for both rotation directions). Averaging theta'' by rotor angle over many turns
gives N(theta)/I; laser on minus laser off (same direction, same speed band) leaves the laser's torque against angle.
Noise floor: laser-off coasts split in two interleaved halves (A = 1st, 3rd, ... off coast of that direction; B = the
others); A - B per angle bin is what a laser-free comparison gives. Compared with the expected laser bump:
turn-averaged torque from Delta gamma (2.6e-15 N m/mW at the window, ND1 calibration), assumed to act over a 45 deg window.
Observations only; the window width and position are assumed.
"""
import glob
import importlib
import json
import os
import sys

import numpy as np
from scipy.signal import savgol_filter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('LASER_DIR', os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-18/laser'))
C = importlib.import_module('coasts')
RUN = os.environ.get('RUN', 'nd2_run')
I = 1.1e-11                 # kg m^2 (A, +-10 %)
K = 2.6e-15                 # N m per mW at the window, turn-averaged (M, ND1)
P_FULL, P_ND1, P_RUN = 3.08, 0.30, 0.0305   # mW at the window (M; ND2 from the PD)
WIN = 45.0                  # deg, assumed window where the beam is on the sail
BAND = (0.40, 0.47)         # Hz
NB = 36                     # 10 deg bins
SG = int(os.environ.get('SG', '11'))   # frames in the Savitzky-Golay window (11 = 0.22 s ~ 35 deg at 0.44 Hz)


def meta(p):
    m = {}
    for line in open(p):
        q = line.split()
        if len(q) >= 2 and q[0] in ('field_off_host', 'coast_end_host'):
            m[q[0]] = float(q[1])
        elif len(q) >= 2 and q[0] == 'laser':
            m['laser'] = q[1]
    return m


def coast_frames(k, h, a, n, t_all, off, m, d):
    t0, t1 = m['field_off_host'] + 5 - off, m['coast_end_host'] - 2 - off
    w = (t_all >= t0) & (t_all <= t1)
    t, th, good = t_all[w], np.unwrap(np.radians(a[w])), n[w] >= 0.5
    if len(t) < 500 or np.any(np.diff(k[w]) != 1):
        gaps = int(np.sum(np.diff(k[w]) != 1))
        if gaps:
            print(f'   {gaps} frame gaps in a coast, skipping it'); return None
    dt = 1 / C.TC.FPS
    om = savgol_filter(th, SG, 3, deriv=1, delta=dt)
    al = savgol_filter(th, SG, 3, deriv=2, delta=dt)
    bad = np.convolve(~good, np.ones(SG), 'same') > 0          # any low-ncc frame inside the window
    # select by the turn-averaged speed (the speed itself swings +-30-50 % within a turn): mean over ~one turn
    f_inst = np.abs(om) / (2 * np.pi)
    L = int(round(C.TC.FPS / max(np.median(f_inst), 0.1)))
    f = np.convolve(f_inst, np.ones(L) / L, 'same')
    f[:L // 2] = 0; f[-(L // 2):] = 0
    s = (~bad) & (f >= BAND[0]) & (f <= BAND[1])
    ang = np.degrees(th[s]) % 360
    return ang, al[s], f[s]


def profile(sets):
    """Mean theta'' per angle bin over the given coasts, and its standard error from the spread between turns."""
    ang = np.concatenate([x[0] for x in sets]); al = np.concatenate([x[1] for x in sets])
    b = (ang // (360 / NB)).astype(int)
    m = np.array([al[b == i].mean() for i in range(NB)])
    # error: per-bin scatter of turn means (frames in one pass are correlated by the smoothing)
    e = np.array([al[b == i].std() / np.sqrt(max(1, (b == i).sum() / (SG / 2))) for i in range(NB)])
    return m, e


def main():
    k, h, a, n = C.load_tracker(False)
    t_all = k / C.TC.FPS
    off = float(np.median(h - t_all))
    rows = {}
    for p in sorted(glob.glob(os.path.join(C.D, RUN, 'coast_O*.txt'))):
        nm = os.path.basename(p)[6:-4]
        m = meta(p)
        if 'coast_end_host' not in m or nm == 'O39':       # O39: mid-coast drag change, left out of this check
            continue
        d = 1 if int(nm[1:]) % 2 else -1
        r = coast_frames(k, h, a, n, t_all, off, m, d)
        if r is not None:
            rows[nm] = (d, m['laser'], r)
    out = {'sg_frames': SG, 'band_Hz': BAND, 'bins_deg': 360 / NB}
    ctr = (np.arange(NB) + 0.5) * 360 / NB
    peak_full = K * P_FULL * (360 / WIN) / I
    out['expected_peak_rad_s2'] = {'full_3.08mW': peak_full, 'ND1': peak_full * P_ND1 / P_FULL, 'ND2': peak_full * P_RUN / P_FULL}
    prof = {}
    for d in (1, -1):
        offs = [v[2] for nm, v in sorted(rows.items()) if v[0] == d and v[1] == 'off']
        ons = [v[2] for nm, v in sorted(rows.items()) if v[0] == d and v[1] == 'on']
        A, eA = profile(offs[0::2]); B, eB = profile(offs[1::2]); Off, eOff = profile(offs); On, eOn = profile(ons)
        ab = A - B; oo = On - Off
        nturns_off = sum(len(x[0]) for x in offs) / (C.TC.FPS / np.mean([x[2].mean() for x in offs]))
        prof[d] = dict(off=Off, on=On, ab=ab, oo=oo, eab=np.hypot(eA, eB), eoo=np.hypot(eOn, eOff))
        out[f'dir{d:+d}'] = dict(
            n_off=len(offs), n_on=len(ons), turns_in_band_off=round(float(nturns_off)),
            hill_peak_to_peak=round(float(Off.max() - Off.min()), 4),
            rms_A_minus_B=round(float(np.sqrt(np.mean((ab - ab.mean()) ** 2))), 5),
            formal_A_minus_B=round(float(np.median(np.hypot(eA, eB))), 5),
            rms_on_minus_off=round(float(np.sqrt(np.mean((oo - oo.mean()) ** 2))), 5),
            mean_on_minus_off=round(float(oo.mean()), 6))
        print(f"dir {d:+d}: {len(offs)} off / {len(ons)} on coasts, ~{nturns_off:.0f} off turns in band; hill theta'' p-p "
              f"{Off.max() - Off.min():.3f} rad/s2; A-B rms {out[f'dir{d:+d}']['rms_A_minus_B']:.5f} (formal "
              f"{out[f'dir{d:+d}']['formal_A_minus_B']:.5f}); on-off rms {out[f'dir{d:+d}']['rms_on_minus_off']:.5f}, "
              f"mean {oo.mean():+.6f} rad/s2")
    print('expected laser peak (rad/s2, 45 deg window):', {kk: f'{v:.2e}' for kk, v in out['expected_peak_rad_s2'].items()})
    json.dump(out, open(os.path.join(HERE, 'angle_profile.json'), 'w'), indent=1, default=float)
    plot(ctr, prof, out)


def plot(ctr, prof, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'sans-serif', 'axes.spines.top': False, 'axes.spines.right': False})
    fig, ax = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    for d, c in ((1, '#1f3b73'), (-1, '#4a90a4')):
        ax[0].plot(ctr, prof[d]['off'], 'o-', ms=3, color=c, label=f"{'+' if d > 0 else '−'} coasts, laser off")
    ax[0].set_ylabel("θ̈ = torque / I (rad/s²)"); ax[0].grid(alpha=0.3); ax[0].legend(frameon=False)
    ax[0].set_title(f"Torque against rotor angle, laser off ({RUN}, {BAND[0]}–{BAND[1]} Hz): the once-per-turn hill", fontsize=11)
    pk = out['expected_peak_rad_s2']
    for d, c in ((1, '#1f3b73'), (-1, '#4a90a4')):
        ax[1].errorbar(ctr, prof[d]['ab'] - prof[d]['ab'].mean(), prof[d]['eab'], fmt='o', ms=3, color=c, capsize=2,
                       label=f"{'+' if d > 0 else '−'}: laser off, half A − half B (noise floor)")
    for nm, v, ls in (('full power 3.08 mW', pk['full_3.08mW'], '-'), ('ND1 0.30 mW', pk['ND1'], '--')):
        ax[1].axhline(v, color='#c0392b', ls=ls, lw=1, label=f'expected laser peak, {nm} ({v:.1e})')
    ax[1].axhline(0, color='0.5', lw=0.8)
    ax[1].set_ylabel('rad/s²'); ax[1].set_xlabel('rotor angle (deg, tracker)'); ax[1].grid(alpha=0.3)
    ax[1].legend(frameon=False, fontsize=8)
    ax[1].set_title('Laser-free comparison vs the expected laser bump (45° window assumed)', fontsize=11)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig.savefig(os.path.join(HERE, 'plots', f'angle_profile_{RUN}.png'), dpi=130)


if __name__ == '__main__':
    main()
