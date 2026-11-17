#!/usr/bin/env python3
"""Laser pickoff photodiode, 16 Nov afternoon to the end of the ND4 night, from the frame builder's 1-s trend of
Y1:RDS-PD_IN1_DQ (fetched read-only by worker2 into Dropbox .../2026-11-16/laser/pd_trend/pd_trend_1s.csv). Mac only.

    python3 pd_trend.py    # -> plots/pd_trend.png (gitignored); prints the night's on/off levels

Power = counts / 222 counts per mW (calibration_history.md 2026-11-16; Ophir before the chamber window).
PD is after the ND filter, before the chamber. Time: FE GPS + 315947891.97 = host unix (laser.csv start row).
"""
import os
import time

import numpy as np

import coasts as C

HERE = os.path.dirname(os.path.abspath(__file__))
K = 222.0                      # counts per mW
HOST = 315947891.97            # host unix - FE GPS
NIGHT = (1478928643, 1478964758)


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from datetime import datetime
    z = np.genfromtxt(os.path.join(C.D, 'pd_trend', 'pd_trend_1s.csv'), delimiter=',', names=True)
    g, pd, off = z['gps'], z['pd_mean'], z['laser_offset']
    uw = pd / K * 1e3
    dt = np.array([datetime.fromtimestamp(x + HOST) for x in g])
    night = (g >= NIGHT[0]) & (g <= NIGHT[1])
    on, of = night & (off > 500), night & (off < 1)
    step = np.median(pd[on]) - np.median(pd[of])
    print(f'night: off median {np.median(pd[of]):.3f}, on median {np.median(pd[on]):.3f} counts; step {step:.3f} counts '
          f'= {step / K * 1e3:.3f} uW; / 686.5 (no filter) = {step / 686.5:.2e}')
    fig, ax = plt.subplots(2, 1, figsize=(12, 8.5))
    a = ax[0]
    a.plot(dt, np.where(uw > 0.5, uw, np.nan), lw=0.8, color='k')
    a.set_yscale('log'); a.set_ylim(0.5, 2e4)
    a.set_ylabel('laser power at the pickoff (µW)'); a.grid(alpha=0.3, which='both')
    for t_, y_, lab in (('16:30', 6e3, 'no filter, 3.08 mW'), ('17:50', 1e3, 'ND1, 0.30 mW'), ('18:41', 90, '31 µW\n(not in the logs)'),
                        ('22:00', 4, 'ND4 night: ~0.3 µW, below the PD dark level (see lower panel)')):
        a.text(datetime.strptime('2026-11-16 ' + t_, '%Y-%m-%d %H:%M'), y_, lab, fontsize=8, ha='center')
    a.set_title('Laser pickoff PD, 16 Nov afternoon to 17 Nov morning (1-s means; values below 0.5 µW not shown on the log scale)', fontsize=11)
    a.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    b = ax[1]
    m = night
    tm = (g[m] - NIGHT[0]) / 3600
    k = (tm * 60).astype(int)                       # 1-min means
    for st, sel, col in (('off (offset 0)', off[m] < 1, '0.45'), ('on (offset 1000)', off[m] > 500, '#c0392b')):
        kk = np.unique(k[sel])
        mm = np.array([uw[m][sel & (k == j)].mean() for j in kk])
        b.plot(kk / 60, mm, '.', ms=3, color=col, label=f'laser {st}: median {np.median(uw[m][sel]):.2f} µW')
    b.axhline(np.median(uw[of]), color='0.45', lw=0.8, ls='--'); b.axhline(np.median(uw[on]), color='#c0392b', lw=0.8, ls='--')
    b.set_xlabel('hours after 19:47, 16 Nov (start of the interleaved series)')
    b.set_ylabel('PD reading as power (µW)\nincluding the PD dark offset')
    b.set_title(f'ND4 night, 1-min means: laser on − off = {step / K * 1e3:.2f} µW at the pickoff '
                f'(= {step / 686.5:.1e} of the no-filter reading; ND4 nominal 1e-4)', fontsize=11)
    b.legend(frameon=False, fontsize=9, loc='upper right'); b.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'pd_trend.png'), dpi=140)


if __name__ == '__main__':
    main()
