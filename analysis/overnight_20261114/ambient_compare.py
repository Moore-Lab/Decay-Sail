#!/usr/bin/env python3
"""Room environment (GHS sensor, InfluxDB 'xsphere', measurement 'environment', location 'ghs'; 1-min means) against
gamma per coast and Δgamma per pair, overnight 2026-11-14/15. Mac only.

    python3 ambient_compare.py      # -> ambient_compare.json, plots/ambient_vs_gamma.png

Data: Dropbox spinup/2026-11-14/overnight/ambient/ghs_environment_1min_20261115T0100Z_2000Z.csv (pulled 2026-11-16 with
the Flux query in analysis/ambient_temp_pull.py's bucket/filters, aggregateWindow 1 m mean). Where the GHS sensor sits
relative to the apparatus is not recorded here (A: room air). Coast times: field-off host time (worker2, NTP).
Per coast: the environment averaged over the band window (field off + ~2 to ~8 min); correlations with gamma and the
pair difference; linear fits. Correlation over one night is not causation (both may just trend with time).
"""
import csv
import json
import os
from datetime import datetime

import numpy as np

import pair_plots as PP

HERE = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(PP.TC.D, 'ambient', 'ghs_environment_1min_20261115T0100Z_2000Z.csv')


def load():
    d = {}
    for r in csv.DictReader(l for l in open(F) if l.strip() and not l.startswith('#')):
        if not r.get('_time'):
            continue
        t = datetime.fromisoformat(r['_time'].replace('Z', '+00:00')).timestamp()
        d.setdefault(r['parameter'], []).append((t, float(r['_value'])))
    return {k: np.array(sorted(v)) for k, v in d.items()}


def main():
    env = load()
    rows = list(csv.DictReader(open(os.path.join(HERE, 'pair_table.csv'))))
    les = {c['name']: c for c in json.load(open(os.path.join(HERE, 'les_coasts.json')))['coasts']}
    t0 = min(c['host_off'] for c in les.values())
    out = dict(env_ranges={k: [float(v[:, 1].min()), float(v[:, 1].max())] for k, v in env.items()})
    pts = []
    for r in rows:
        a, b = r['pair'].split('/')
        e = {}
        for k, v in env.items():
            ta, tb = les[a]['host_off'], les[b]['host_off']
            e[k] = float(np.mean([np.mean(v[(v[:, 0] >= t + 120) & (v[:, 0] <= t + 480), 1]) for t in (ta, tb)]))
        pts.append(dict(pair=r['pair'], hour=float(r['hour']), gp=float(r['gamma_plus_mHz']), gm=float(r['gamma_minus_mHz']),
                        dg=float(r['dgamma_uHz']), **e))
    res = {}
    for k in env:
        x = np.array([p[k] for p in pts])
        for y in ('gp', 'gm', 'dg'):
            yy = np.array([p[y] for p in pts])
            c = np.corrcoef(x, yy)[0, 1]; s = np.polyfit(x, yy, 1)[0]
            res[f'{y} vs {k}'] = dict(corr=float(c), slope=float(s))
        res[f'{k} vs hour'] = float(np.corrcoef(x, [p['hour'] for p in pts])[0, 1])
    out['fits'] = res; out['pairs'] = pts
    for k, v in res.items():
        print(k, v)
    print('ranges over the pull window:', out['env_ranges'])
    json.dump(out, open(os.path.join(HERE, 'ambient_compare.json'), 'w'), indent=1)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    hv = lambda v: (v[:, 0] - t0) / 3600
    fig, ax = plt.subplots(4, 1, figsize=(10, 11), sharex=True)
    ax[0].plot([p['hour'] for p in pts], [p['gp'] for p in pts], 'o', color='#1f3b73', label='γ(+)')
    ax[0].plot([p['hour'] for p in pts], [p['gm'] for p in pts], 'o', color='#4a90a4', label='γ(−)')
    ax[0].set_ylabel('γ at 0.435 Hz (mHz)'); ax[0].legend(frameon=False)
    ax[1].plot([p['hour'] for p in pts], [p['dg'] for p in pts], 'o', color='k'); ax[1].set_ylabel('Δγ (µHz)')
    for i, (k, lab) in enumerate((('temperature', 'room T (°C)'), ('baro_pressure', 'room pressure (hPa)'))):
        if k in env:
            ax[2 + i].plot(hv(env[k]), env[k][:, 1], '-', lw=1, color='C3' if i == 0 else 'C0'); ax[2 + i].set_ylabel(lab)
    if 'humidity' in env:
        a2 = ax[2].twinx(); a2.plot(hv(env['humidity']), env['humidity'][:, 1], '-', lw=0.8, color='0.6'); a2.set_ylabel('RH (%)', color='0.5')
    for a in ax:
        a.grid(alpha=0.3)
    ax[-1].set_xlabel('hours after the first coast (23:11 EST, 11-14)'); ax[-1].set_xlim(-0.5, 13.5)
    fig.suptitle('GHS room sensor vs damping, overnight coast series (sensor location relative to the apparatus not recorded)', fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'ambient_vs_gamma.png'), dpi=120)


if __name__ == '__main__':
    main()
