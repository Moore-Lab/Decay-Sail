#!/usr/bin/env python3
"""Laser pickoff photodiode over the ND4 interleaved night 2026-11-16/17, from the PD reads coast_series.py logged in
laser.csv (one read per switch, coast start and coast end). Mac only.

    python3 pd_night.py    # -> plots/pd_night.png (gitignored)

PD = Y1:RDS-PD_INMON, after the ND filter, before the chamber window. Power = counts / 222 counts per mW
(calibration_history.md, 2026-11-16; Ophir before the window). No dark subtraction: the dark offset drifts (~1 count).
"""
import csv
import os

import numpy as np

import coasts as C

HERE = os.path.dirname(os.path.abspath(__file__))
K = 222.0          # counts per mW


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    R = [r for r in csv.DictReader(l for l in open(os.path.join(C.D, 'night_nd4_il2', 'laser.csv')) if not l.startswith('#'))]
    t0 = min(float(r['host']) for r in R)
    fig, ax = plt.subplots(figsize=(11, 4.8))
    for st, col in (('off', '0.45'), ('on', '#c0392b')):
        s = [r for r in R if r['state'] == st]
        h = np.array([(float(r['host']) - t0) / 3600 for r in s]); p = np.array([float(r['pd']) for r in s]) / K * 1e3
        ax.plot(h, p, 'o', ms=4, color=col, label=f'laser {st} (setpoint {s[0]["setpoint"]}): mean {p.mean():.2f} µW, sd {p.std():.2f}')
    ax.axhline(0, color='0.6', lw=0.8)
    off = np.mean([float(r['pd']) for r in R if r['state'] == 'off']) / K * 1e3
    ax.axhline(off + 0.31, color='#c0392b', ls=':', lw=1.2, label='expected laser-on level with ND4 (off mean + 0.31 µW, assumed T = 1e-4)')
    ax.set_xlabel('hours after 19:52, 16 Nov'); ax.set_ylabel('laser power at the pickoff (µW)\n= PD counts / 222 counts per mW')
    ax.set_title('Pickoff PD over the ND4 interleaved night: the ND4 light (~0.3 µW) is below the PD noise (~1.3 µW sd)')
    ax.legend(frameon=False, fontsize=9, loc='upper right'); ax.grid(alpha=0.3)
    ax2 = ax.secondary_yaxis('right', functions=(lambda x: x * K / 1e3, lambda c: c / K * 1e3)); ax2.set_ylabel('PD (counts)')
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'pd_night.png'), dpi=140)


if __name__ == '__main__':
    main()
