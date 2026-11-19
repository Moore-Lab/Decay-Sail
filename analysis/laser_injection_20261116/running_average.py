#!/usr/bin/env python3
"""Laser on - off of Delta gamma as pairs accumulate, plain average vs ABBA blocks, ND4 / ND3 / ND2 nights; and the
three nights combined as measured / expected. (2026-11-19) Mac only; reads night_pairs*.csv (night_plots.py).

    python3 running_average.py     # prints; plots/running_average.png (gitignored)

Plain: mean(on pairs) - mean(off pairs), error from the scatter of each set.
ABBA: per block of 4 consecutive pairs (off,on,on,off), mean(on) - mean(off); estimate = mean over blocks,
error = sd of blocks / sqrt(n blocks) (cancels a slow wander of the offset within each block).
All pairs kept (no outlier rule, Molly 2026-11-19). Expected (D, +-10 % from S1): ND4 +0.05, ND3 +0.63, ND2 +5.3.
Combined: measured / expected per night, inverse-variance weighted. Observations only.
"""
import csv
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
NIGHTS = [('ND4 (0.29 µW)', 'night_pairs.csv', 0.05), ('ND3 (3.6 µW)', 'night_pairs_nd3_night.csv', 0.63),
          ('ND2 (30.5 µW)', 'night_pairs_nd2_run.csv', 5.3)]


def load(f):
    R = list(csv.DictReader(open(os.path.join(HERE, f))))
    return np.array([float(r['gm']) - float(r['gp']) for r in R]), np.array([r['laser'] == 'on' for r in R])


def plain(dg, on):
    a, b = dg[on], dg[~on]
    if len(a) < 2 or len(b) < 2:
        return np.nan, np.nan
    return a.mean() - b.mean(), np.hypot(a.std(ddof=1) / np.sqrt(len(a)), b.std(ddof=1) / np.sqrt(len(b)))


def abba(dg, on):
    bl = [dg[i:i + 4][on[i:i + 4]].mean() - dg[i:i + 4][~on[i:i + 4]].mean() for i in range(0, len(dg) - 3, 4)]
    bl = np.array(bl)
    if len(bl) < 2:
        return np.nan, np.nan
    return bl.mean(), bl.std(ddof=1) / np.sqrt(len(bl))


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'sans-serif', 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axs = plt.subplots(1, 3, figsize=(16, 5))
    ratios = []
    for ax, (lab, f, exp) in zip(axs, NIGHTS):
        dg, on = load(f)
        ns = np.arange(4, len(dg) + 1, 4)
        P = np.array([plain(dg[:n], on[:n]) for n in ns]); A = np.array([abba(dg[:n], on[:n]) for n in ns])
        ax.fill_between(ns, P[:, 0] - P[:, 1], P[:, 0] + P[:, 1], color='0.6', alpha=0.25, lw=0)
        ax.plot(ns, P[:, 0], 'o-', color='0.4', ms=3, label='plain average ± 1σ')
        ax.fill_between(ns, A[:, 0] - A[:, 1], A[:, 0] + A[:, 1], color='#1f3b73', alpha=0.2, lw=0)
        ax.plot(ns, A[:, 0], 's-', color='#1f3b73', ms=3, label='ABBA blocks ± 1σ')
        ax.axhline(exp, color='#c0392b', ls='--', lw=1, label=f'expected {exp:+g}')
        ax.axhline(0, color='0.5', lw=0.8)
        ax.set_title(lab, fontsize=11); ax.set_xlabel('pairs used (in time order)'); ax.grid(alpha=0.3)
        p, a = plain(dg, on), abba(dg, on)
        print(f'{lab}: {len(dg)} pairs; plain {p[0]:+.2f} +- {p[1]:.2f}; ABBA {a[0]:+.2f} +- {a[1]:.2f} '
              f'({len(dg) // 4} blocks); expected {exp:+.2f}')
        ratios.append((lab, a[0] / exp, a[1] / exp, p[0] / exp, p[1] / exp))
    axs[0].set_ylabel('laser on − off of Δγ (µHz)'); axs[0].legend(frameon=False, fontsize=9)
    fig.suptitle('Laser effect as pairs accumulate: plain average vs ABBA (neighbour) comparison; all pairs kept', fontsize=12)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig.savefig(os.path.join(HERE, 'plots', 'running_average.png'), dpi=120)
    for k, name in ((1, 'ABBA'), (3, 'plain')):
        r = np.array([x[k] for x in ratios]); e = np.array([x[k + 1] for x in ratios]); w = 1 / e ** 2
        print(f'combined measured/expected ({name}): {np.sum(w * r) / w.sum():.2f} +- {1 / np.sqrt(w.sum()):.2f}  '
              + ', '.join(f'{x[0].split()[0]} {x[k]:.1f} +- {x[k + 1]:.1f}' for x in ratios))


if __name__ == '__main__':
    main()
