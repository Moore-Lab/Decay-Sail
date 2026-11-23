#!/usr/bin/env python3
"""Raw TSP01B temperature/humidity log, plotted as recorded (no smoothing, no cuts). Analysis only, Mac.

One logger file covers 11-17 18:02 to 11-19 05:58 (spinup/2026-11-17/env/): the ND3 night and the ND2 run.
ext_T1_C is identical to ext_T0_C in every row (one external probe; the second channel mirrors it), so only T0 is shown.
The logger clock (host unix) is assumed, not verified against the front end.
Coasts are shaded by laser state from the coast_O*.txt files (field_off_host to coast_end_host).

    python3 temp_raw_plots.py   # -> plots/temp_raw_overview.png, plots/temp_raw_<run>.png, plots/temp_raw_nd2_run_zoom.png
"""
import glob
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup')
TSP = os.path.join(SP, '2026-11-17/env/tsp01b_host1794956558.csv')
RUNS = {'nd3_night': ('ND3 night, 11-17/18', os.path.join(SP, '2026-11-17/laser/nd3_night')),
        'nd2_run': ('ND2 run, 11-18/19', os.path.join(SP, '2026-11-18/laser/nd2_run'))}
TZ = ZoneInfo('America/New_York')
ON, OFF = '#d9822b', '#8a8f98'


def meta(p):
    m = {}
    for ln in open(p):
        k, _, v = ln.strip().partition(' ')
        m[k] = v
    return m


def coasts(d):
    out = []
    for p in sorted(glob.glob(os.path.join(d, 'coast_O*.txt'))):
        m = meta(p)
        if 'coast_end_host' in m and 'field_off_host' in m:
            out.append((float(m['field_off_host']), float(m['coast_end_host']), m.get('laser', ''),
                        os.path.basename(p)[6:-4]))
    return out


def dt(u):
    return [datetime.fromtimestamp(x, TZ) for x in np.atleast_1d(u)]


def panels(d, title, cs, path, ylim0=None, note=''):
    fig, ax = plt.subplots(3, 1, figsize=(11, 7.5), sharex=True)
    t = dt(d.unix.values)
    for a, col, lab in zip(ax, ('ext_T0_C', 'internal_T_C', 'humidity_RH'),
                           ('external probe T (°C)', 'logger internal T (°C)', 'humidity (% RH)')):
        a.plot(t, d[col].values, '-', lw=0.8, color='#2a5caa')
        a.set_ylabel(lab); a.grid(alpha=0.3)
        for t0, t1, las, _ in cs:
            a.axvspan(*dt([t0, t1]), color=ON if las == 'on' else OFF, alpha=0.18 if las == 'on' else 0.10, lw=0)
    if cs:
        ax[0].plot([], [], color=ON, alpha=0.4, lw=8, label='coast, laser on')
        ax[0].plot([], [], color=OFF, alpha=0.3, lw=8, label='coast, laser off')
        ax[0].legend(loc='upper right', fontsize=8)
    if ylim0:
        ax[0].set_ylim(*ylim0)
        ax[0].text(0.5, 0.04, note, transform=ax[0].transAxes, ha='center', fontsize=8, color='#555')
    ax[0].set_title(title + ' — TSP01B raw, every sample (13.5 s), no smoothing')
    ax[-1].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M', tz=TZ))
    ax[-1].set_xlabel('local time (US/Eastern, logger host clock)')
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
    print('wrote', path)


def main():
    d = pd.read_csv(TSP, skiprows=1)
    assert (d.ext_T0_C == d.ext_T1_C).all()
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    allc = []
    for key, (title, rd) in RUNS.items():
        cs = coasts(rd); allc += cs
        a, b = cs[0][0] - 1800, cs[-1][1] + 1800
        s = d[(d.unix >= a) & (d.unix <= b)]
        T = s.ext_T0_C
        print(f'{key}: {len(cs)} coasts, ext T min {T.min():.3f} max {T.max():.3f} median {T.median():.3f} °C')
        panels(s, title, cs, os.path.join(HERE, 'plots', f'temp_raw_{key}.png'))
        if key == 'nd2_run':
            panels(s, title + ' (zoom)', cs, os.path.join(HERE, 'plots', 'temp_raw_nd2_run_zoom.png'), (23.0, 25.0),
                   'y-axis clipped at 23 °C: the drop to 17.6 °C near 00:00 is the probe artefact (full range: temp_raw_nd2_run.png)')
    panels(d, 'Whole log 11-17 18:02 to 11-19 05:58', allc, os.path.join(HERE, 'plots', 'temp_raw_overview.png'))


if __name__ == '__main__':
    main()
