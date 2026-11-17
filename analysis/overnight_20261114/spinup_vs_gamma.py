#!/usr/bin/env python3
"""Overnight 2026-11-14/15: does the coast-to-coast scatter in gamma follow the preceding spin-up? (2026-11-16)
Mac only, reads Dropbox series/ (series.csv, brake_<host>.csv, console_On.txt) and pair_table.csv (gamma per coast).

    python3 spinup_vs_gamma.py     # -> spinup_vs_gamma.csv, prints correlations; plots/spinup_vs_gamma.png (gitignored)

Per coast: gamma at 0.435 Hz (pair_plots.gamma_mid, from pair_table.csv), residual = gamma minus its direction mean
(and, second version, minus a per-direction linear trend in hour). Spin-up features from the brake_offsets log of the
spin-up just before that coast:
  spin_s       field-off minus spin start (s)
  drive_s      time with any electrode nonzero (s; frames x their spacing)
  v2_int       sum over frames of (V2^2 + V3^2 + V4^2) dt, counts^2 s (torque ~ V^2)
  vabs_int     sum |V| dt (counts s; a charge-like measure)
  f_off        mean of the last 3 turns at stop (Hz)
  swing0       start swing (deg) from the console
  late_s       drive time in the last 60 s before field off (s)
Pearson r with a two-sided p from the t distribution; n ~ 24 per direction, so |r| > ~0.4 is p < 0.05 and many
features are tested (look-elsewhere: ~7 features x 2 directions x 2 detrendings). Observations only.
"""
import csv
import glob
import os
import re

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-14/overnight/series')
FEATS = ['spin_s', 'drive_s', 'v2_int', 'vabs_int', 'f_off', 'swing0', 'late_s']


def brake_features(path, t_off):
    host, V = [], []
    with open(path) as fh:
        for r in csv.DictReader(l for l in fh if not l.startswith('#')):
            try:
                host.append(float(r['host_t'])); V.append([float(r['V2'] or 0), float(r['V4'] or 0), float(r['V3'] or 0)])
            except (ValueError, KeyError):
                continue
    host, V = np.array(host), np.array(V)
    dt = np.r_[np.diff(host), 0.02]
    on = np.any(V != 0, axis=1)
    late = host >= t_off - 60
    return dict(drive_s=float(dt[on].sum()), v2_int=float((np.sum(V ** 2, axis=1) * dt).sum()),
                vabs_int=float((np.sum(np.abs(V), axis=1) * dt).sum()), late_s=float(dt[on & late].sum()))


def main():
    gam = {}
    for r in csv.DictReader(open(os.path.join(HERE, 'pair_table.csv'))):
        a, b = r['pair'].split('/')
        gam[a] = (1, 1e3 * float(r['gamma_plus_mHz']), float(r['hour']))
        gam[b] = (-1, 1e3 * float(r['gamma_minus_mHz']), float(r['hour']))
    series = {r['name']: r for r in csv.DictReader(open(os.path.join(D, 'series.csv')))}
    brakes = sorted(glob.glob(os.path.join(D, 'brake_*.csv')))
    bt = np.array([float(re.search(r'brake_(\d+)', p).group(1)) for p in brakes])
    rows = []
    for name, (d, g, hour) in sorted(gam.items()):
        s = series[name]
        t0, toff = float(s['spin_start_host']), float(s['field_off_host'])
        i = int(np.argmin(np.abs(bt - t0)))
        if abs(bt[i] - t0) > 30:
            print(f'{name}: no brake log near spin start'); continue
        f = brake_features(brakes[i], toff)
        con = open(os.path.join(D, f'console_{name}.txt')).read()
        m = re.search(r'start swing \+-([0-9.]+)', con)
        turns = [float(x) for x in s['last_turns_hz'].split(',') if x.strip()]
        rows.append(dict(name=name, dir=d, hour=hour, gamma_uHz=g, spin_s=toff - t0, f_off=float(np.mean(turns)),
                         swing0=float(m.group(1)) if m else np.nan, **f))
    for d in (1, -1):
        s = [r for r in rows if r['dir'] == d]
        g = np.array([r['gamma_uHz'] for r in s]); h = np.array([r['hour'] for r in s])
        for r, x in zip(s, g - g.mean()):
            r['res'] = x
        for r, x in zip(s, g - np.polyval(np.polyfit(h, g, 1), h)):
            r['res_detr'] = x
    with open(os.path.join(HERE, 'spinup_vs_gamma.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f'{len(rows)} coasts with gamma and a spin-up log\n')
    print(f"{'feature':>9} {'dir':>4} {'r(res)':>7} {'p':>6} {'r(detr)':>8} {'p':>6}   range")
    for ft in FEATS:
        for d in (1, -1):
            s = [r for r in rows if r['dir'] == d and np.isfinite(r[ft])]
            x = np.array([r[ft] for r in s])
            if np.std(x) == 0:
                continue
            r1, p1 = stats.pearsonr(x, [r['res'] for r in s])
            r2, p2 = stats.pearsonr(x, [r['res_detr'] for r in s])
            print(f'{ft:>9} {d:+4d} {r1:7.2f} {p1:6.3f} {r2:8.2f} {p2:6.3f}   {x.min():.3g} .. {x.max():.3g}')
    plot(rows)


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(2, 4, figsize=(15, 6.5))
    for ax, ft in zip(axs.flat, FEATS + ['hour']):
        for d, c in ((1, '#1f3b73'), (-1, '#4a90a4')):
            s = [r for r in rows if r['dir'] == d]
            ax.plot([r[ft] for r in s], [r['res'] for r in s], 'o', ms=4, color=c, label='+' if d > 0 else '−')
        ax.set_xlabel(ft); ax.grid(alpha=0.3)
    axs[0, 0].set_ylabel('γ − direction mean (µHz)'); axs[1, 0].set_ylabel('γ − direction mean (µHz)')
    axs[0, 0].legend(frameon=False)
    fig.suptitle('Overnight 2026-11-14/15: γ per coast (residual) vs the preceding spin-up (observations only)')
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig.savefig(os.path.join(HERE, 'plots', 'spinup_vs_gamma.png'), dpi=120)


if __name__ == '__main__':
    main()
