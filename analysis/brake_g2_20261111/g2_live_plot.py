#!/usr/bin/env python3
"""G2 live brakes (2026-11-11 evening): angle vs time for the three passing brakes, with the commanded electrode.
Mac only, reads the brake CSVs on Dropbox.

    python3 g2_live_plot.py      # -> plots/g2_live_brakes.png
"""
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-11/g2')
RUNS = [('Repeat 1', 'brake_1794444651', 'safe 176-258'),
        ('Repeat 2 (rerun)', 'brake_1794446406', 'safe 173-261'),
        ('Repeat 3', 'brake_1794446727', 'safe 176-258')]
REST = 208.4            # final rest centre after the brakes (measured)
COL = {'A': '#d62728', 'B': '#2ca02c', 'C': '#1f77b4'}


def load(name):
    import csv
    rows = [r for r in csv.DictReader(l for l in open(os.path.join(D, name + '.csv')) if not l.startswith('#'))]
    t = np.array([float(r['frame_t']) for r in rows])
    th = np.array([float(r['angle']) for r in rows])
    ph = np.array([r['phase'] for r in rows])
    v = np.array([[float(r['V2'] or 0), float(r['V4'] or 0), float(r['V3'] or 0)] for r in rows])
    t0 = t[np.argmax(ph == 'brake')]
    return t - t0, th, v


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    for ax, (lab, name, safe) in zip(axes, RUNS):
        t, th, v = load(name)
        m = (t >= -5) & (t <= 40)
        ax.axhspan(REST - 10, REST + 10, color='0.9', zorder=0, label='rest ±10° (pass band)')
        ax.plot(t[m], th[m], 'k', lw=0.8, label='rotor angle (live tracker)')
        ax.axvline(0, color='0.4', ls='--', lw=0.8)
        lo, hi = (float(x) for x in safe.split()[1].split('-'))
        ax.axhline(lo, color='r', ls=':', lw=0.7); ax.axhline(hi, color='r', ls=':', lw=0.7, label=f'{safe} deg')
        # strip: commanded electrode (A, B, C = V2, V4, V3) at 800 counts
        y0 = lo - 9
        for q, key in enumerate('ABC'):
            on = (v[:, q] > 0) & m
            ax.fill_between(t, y0, y0 + 5, where=on, color=COL[key], step='mid', lw=0, label=f'{key} on (800 counts)')
        amp0 = (th[(t >= -4) & (t < 0)].max() - th[(t >= -4) & (t < 0)].min()) / 2
        late = (t >= 30) & (t <= 40)
        ax.set_title(f'{lab}: start ±{amp0:.1f}°, after 30-40 s ±{(th[late].max() - th[late].min()) / 2:.1f}°', fontsize=10,
                     loc='left')
        ax.set_ylabel('angle (deg)')
        ax.set_ylim(y0 - 2, hi + 6)
    axes[0].legend(fontsize=7, ncol=4, loc='upper right')
    axes[-1].set_xlabel('s from brake start (field off before 0: observe window)')
    fig.suptitle('G2: live braking from ±35-40° through the electrode offsets (800 counts, 8 updates/s, DC-coupled amp), '
                 '2026-11-11', fontsize=11)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig.savefig(os.path.join(HERE, 'plots', 'g2_live_brakes.png'), dpi=110)


if __name__ == '__main__':
    main()
