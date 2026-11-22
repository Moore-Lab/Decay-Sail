#!/usr/bin/env python3
"""Laser spin-up + free coast, 2026-11-21 (LASER_OFFSET 1300, ND out, + direction; run by worker2). Analysis only, Mac.

Questions (Molly, 2026-11-21): (1) damping tau against speed, 0.3-0.6 Hz, vs September (85.5 min in 0.50-0.75 Hz);
(2) is the slow torque noise ("wobble") smaller at 0.5-0.6 Hz than at 0.40-0.47 Hz; (3) is it different while the laser
holds the rotor at 0.606 Hz (16:05-16:21) than in the free coast.
Estimators as g1_within_coast.py: per-turn rates from the 50 fps tracker; gamma per band from a quadratic in log f
(pair_plots.gamma_mid) with a 10-block jackknife; slow torque noise as the force-equivalent ASD (at r = 1.38 mm,
I = 1.1e-11) of the per-turn speed residuals, Welch on a 2 s grid.
    python3 damping_1300.py   # -> damping_1300.json
"""
import json
import os
import sys

import numpy as np
from scipy.signal import welch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'overnight_20261114'))
import pair_plots as PP       # noqa: E402
import tracker_coasts as TC   # noqa: E402

D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-21/laser/damping_1300')
LASER_OFF_HOST = 1795296085.180      # run_log.txt 16:21:25
BRAKE_HOST = 1795297547.785          # final brake launched
PLATEAU = (LASER_OFF_HOST - 16 * 60, LASER_OFF_HOST - 5)   # 16:05:25-16:21:20, laser 1300, 0.605-0.606 Hz
I, R, THERMAL = 1.1e-11, 1.38e-3, 6.8e-15


def load():
    import pandas as pd
    x = pd.read_csv(os.path.join(D, 'tracker', 'blob_live_gps1479326928.csv'), skiprows=1)
    t = x['frame'] / TC.FPS
    off = float(np.median(x['host_time'] - t))
    return (t + off).to_numpy(), x['angle_deg'].to_numpy(), x['ncc'].to_numpy()


def per_turn(h, a, ncc, t0, t1):
    w = (h >= t0) & (h <= t1)
    tr = TC.turns(h[w] - t0, np.degrees(np.unwrap(np.radians(a[w]))), 1, ncc[w] >= 0.5)
    return tr[:, 0], tr[:, 1]


def asd(t, df):
    tg = np.arange(t[0], t[-1], 2.0)
    nu, S = welch(np.interp(tg, t, df), fs=0.5, nperseg=min(128, len(tg)), detrend='linear')
    F = 2 * np.pi * I * 2 * np.pi * nu * np.sqrt(S) / R      # force-equivalent ASD, N/rtHz (valid for nu >> gamma)
    out = {}
    for lab, lo, hi in [('120-300 s', 1 / 300, 1 / 120), ('60-120 s', 1 / 120, 1 / 60), ('30-60 s', 1 / 60, 1 / 30),
                        ('10-30 s', 1 / 30, 1 / 10)]:
        b = (nu >= lo) & (nu < hi)
        if b.any():
            out[lab] = float(F[b].mean())
    return out


def segment(t, f, kind):
    tt = t - t[0]
    if kind == 'coast':
        g = PP.gamma_mid(tt, f)[0]
        jk = PP.jk(lambda idx: PP.gamma_mid(tt[idx], f[idx])[0], len(tt))
        res = np.log(f) - np.polyval(np.polyfit(tt, np.log(f), 2), tt)
        T = float(tt[-1])
        r = dict(gamma_uHz=1e6 * g, tau_min=1 / g / 60, jk_uHz=1e6 * jk, T_s=T, wobble10_uHz=1e6 * jk * np.sqrt(T / 600))
    else:
        res = np.log(f) - np.polyval(np.polyfit(tt, np.log(f), 1), tt)
        r = dict(mean_Hz=float(f.mean()), slope_Hz_per_10min=float(600 * np.polyfit(tt, f, 1)[0]), T_s=float(tt[-1]))
    df = f.mean() * res
    r.update(n_turns=len(f), f_lo=float(f.min()), f_hi=float(f.max()), resid_rms_mHz=float(1e3 * df.std()),
             lag1=float(np.corrcoef(res[:-1], res[1:])[0, 1]), force_asd_N_rtHz=asd(tt, df))
    return r


def main():
    h, a, ncc = load()
    out = {}
    t, f = per_turn(h, a, ncc, *PLATEAU)
    out['plateau_laser1300'] = segment(t, f, 'hold')
    t, f = per_turn(h, a, ncc, LASER_OFF_HOST + 60, BRAKE_HOST - 2)     # skip the first minute after laser-off
    out['coast_first_turn_Hz'] = float(f[0])
    for lo, hi in [(0.50, 0.59), (0.47, 0.50), (0.40, 0.47), (0.33, 0.40)]:
        s = (f >= lo) & (f < hi)
        out[f'coast_{lo:.2f}-{hi:.2f}'] = segment(t[s], f[s], 'coast')
    json.dump(out, open(os.path.join(HERE, 'damping_1300.json'), 'w'), indent=1)
    for k, v in out.items():
        if isinstance(v, dict):
            fa = v.pop('force_asd_N_rtHz')
            print(k, {kk: round(x, 3) if isinstance(x, float) else x for kk, x in v.items()})
            print('   force ASD (x thermal):', {kk: f'{x:.1e} ({x / THERMAL:.0f}x)' for kk, x in fa.items()})
        else:
            print(k, v)


if __name__ == '__main__':
    main()
