#!/usr/bin/env python3
"""How steady is the laser-off CW/CCW offset, Delta gamma = gamma(-) - gamma(+)? (2026-11-20) MEASURED, Mac only.

    python3 offset_stability.py     # prints; plots/offset_stability.png (gitignored)

Pairs with no laser on the sail: 11-14/15 overnight (no laser, overnight_20261114/pair_table.csv, 24 pairs),
11-16 off1 (one pair, laser blocked before the chamber, HANDOFF), and the laser-off pairs of the interleaved nights
ND4 11-17/18, ND3 11-18, ND2 11-18/19 (night_pairs*.csv). All pairs kept (no outlier rule); ND2 includes the O39 pair
(marked). Within a night: means of k consecutive off pairs; if the offset only had independent pair noise, their sd
would fall as sd/sqrt(k); slower means a slow wander. Between nights: chi2 of night means about their weighted mean.
Observations only; the cause of the offset is unknown.
"""
import csv
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ON = os.path.join(HERE, '..', 'overnight_20261114', 'pair_table.csv')
NIGHTS = [('11-14/15 no laser', None), ('ND4 11-17/18', 'night_pairs.csv'), ('ND3 11-18', 'night_pairs_nd3_night.csv'),
          ('ND2 11-18/19', 'night_pairs_nd2_run.csv')]
OFF1 = 0.90           # 11-16 off1, one pair (HANDOFF table, M)
RECOIL = 0.09         # uHz, D (hill factor 1.23 included)


def load():
    out = []
    for lab, f in NIGHTS:
        if f is None:
            R = list(csv.DictReader(open(ON)))
            h = np.array([float(r['hour']) for r in R]); d = np.array([float(r['dgamma_uHz']) for r in R])
            names = [r['pair'] for r in R]
        else:
            R = [r for r in csv.DictReader(open(os.path.join(HERE, f))) if r['laser'] == 'off']
            h = np.array([float(r['hour']) for r in R]); d = np.array([float(r['dg']) for r in R])
            names = [r['pair'] for r in R]
        out.append((lab, h, d, names))
    return out


def block_sd(d, k):
    n = len(d) // k
    if n < 3:
        return np.nan, n
    m = d[:n * k].reshape(n, k).mean(1)
    return m.std(ddof=1), n


def main():
    data = load()
    means = []
    print('laser-off Delta gamma per night (uHz):')
    for lab, h, d, names in data:
        sem = d.std(ddof=1) / np.sqrt(len(d))
        means.append((lab, d.mean(), sem))
        print(f'  {lab:18s} n {len(d):2d}  mean {d.mean():+6.2f} +- {sem:.2f}  median {np.median(d):+6.2f}  '
              f'pair sd {d.std(ddof=1):5.2f}  span {h[-1] - h[0]:.1f} h')
        for k in (2, 4, 6):
            s, n = block_sd(d, k)
            if n >= 3:
                print(f'      blocks of {k} pairs: sd {s:.2f} (n {n}); pure pair noise would give {d.std(ddof=1) / np.sqrt(k):.2f}')
    print(f'  11-16 off1          n  1  {OFF1:+.2f} (one pair)')
    m = np.array([x[1] for x in means]); e = np.array([x[2] for x in means]); w = 1 / e ** 2
    wm = np.sum(w * m) / w.sum(); chi2 = np.sum(w * (m - wm) ** 2)
    print(f'night means: weighted mean {wm:+.2f}; chi2 {chi2:.1f} for {len(m) - 1} dof; spread (sd) {m.std(ddof=1):.2f} uHz')
    print(f'recoil (D) ~{RECOIL} uHz: night-to-night spread / recoil = {m.std(ddof=1) / RECOIL:.0f}')
    plot(data, means)


def plot(data, means):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'sans-serif', 'axes.spines.top': False, 'axes.spines.right': False})
    fig, ax = plt.subplots(1, 2, figsize=(15, 5.5), gridspec_kw={'width_ratios': [3, 1.3]})
    cols = ['0.45', '#1f3b73', '#2a9d8f', '#c0392b']
    for (lab, h, d, names), c in zip(data, cols):
        ax[0].plot(h, d, 'o', color=c, ms=4, alpha=0.8, label=lab)
        if len(d) >= 4:
            k = 4
            mh = np.convolve(h, np.ones(k) / k, 'valid'); md = np.convolve(d, np.ones(k) / k, 'valid')
            ax[0].plot(mh, md, '-', color=c, lw=1.6)
    ax[0].set_ylim(-25, 6)
    lo = [(h, d) for (_, h, d, _) in data if d.min() < -25]
    for h, d in lo:
        i = np.argmin(d); ax[0].plot(h[i], -24.5, 'v', color=cols[3], ms=7)
        ax[0].annotate(f'{d[i]:.0f} (off scale)', (h[i], -24.5), xytext=(6, 2), textcoords='offset points', fontsize=8,
                       color=cols[3])
    ax[0].axhline(0, color='0.6', lw=0.8)
    ax[0].set_xlabel('hours into the night'); ax[0].set_ylabel('laser-off Δγ = γ(−) − γ(+)  (µHz)')
    ax[0].set_title('Each laser-off pair (dots) and the mean of 4 consecutive (lines)', fontsize=10)
    ax[0].legend(frameon=False, fontsize=9, loc='lower right'); ax[0].grid(alpha=0.3)
    labs = [x[0] for x in means] + ['11-16 off1 (1 pair)']
    y = np.arange(len(labs))[::-1]
    for yi, (lab, mu, se), c in zip(y, means, cols):
        ax[1].errorbar(mu, yi, xerr=se, fmt='o', color=c, capsize=4)
    ax[1].plot(OFF1, y[-1], 'D', color='0.2')
    ax[1].set_yticks(y); ax[1].set_yticklabels(labs, fontsize=9)
    ax[1].axvline(0, color='0.6', lw=0.8)
    ax[1].set_xlabel('night mean (µHz) ± 1σ'); ax[1].grid(axis='x', alpha=0.3)
    ax[1].set_title(f'Night means (expected recoil ~{RECOIL} µHz, D)', fontsize=10)
    fig.suptitle('How steady is the CW/CCW offset with no laser on the sail? (measured; all pairs kept)', fontsize=12)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig.savefig(os.path.join(HERE, 'plots', 'offset_stability.png'), dpi=120)


if __name__ == '__main__':
    main()
