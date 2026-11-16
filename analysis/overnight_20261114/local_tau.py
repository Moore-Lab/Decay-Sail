#!/usr/bin/env python3
"""Local decay time vs speed, overnight coasts 2026-11-14/15 (tracker per turn). Mac only.

    python3 local_tau.py      # -> local_tau.json, printed table

Per coast that starts >= 0.485 Hz: tau from a log-linear fit of the per-turn rates inside each 0.02 Hz slice
(0.37-0.49 Hz; >= 15 turns per slice). Mean and sd over coasts per direction; - vs + from the means.
"""
import json
import os

import numpy as np

import pair_plots as PP

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    C = PP.coast_turns()
    edges = np.arange(0.37, 0.495, 0.02)
    out = {1: [], -1: []}
    for nm, c in C.items():
        tr = c['tr']
        if tr[0, 1] < 0.485:
            continue
        row = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            s = (tr[:, 1] >= lo) & (tr[:, 1] < hi)
            row.append(PP.fit_tau(tr[s, 0], tr[s, 1])[0] / 60 if s.sum() >= 15 else np.nan)
        out[c['dir']].append(row)
    res = []
    for k, (lo, hi) in enumerate(zip(edges[:-1], edges[1:])):
        r = dict(band=f'{lo:.2f}-{hi:.2f}')
        for d in (1, -1):
            v = np.array(out[d])[:, k]; v = v[~np.isnan(v)]
            r[f'tau{d:+d}'] = float(v.mean()); r[f'sd{d:+d}'] = float(v.std(ddof=1)); r[f'n{d:+d}'] = int(v.size)
        r['minus_vs_plus_pct'] = 100 * (r['tau-1'] / r['tau+1'] - 1)
        r['minus_vs_plus_err_pct'] = 100 * np.hypot(r['sd+1'] / np.sqrt(r['n+1']), r['sd-1'] / np.sqrt(r['n-1'])) / r['tau+1']
        res.append(r)
        print(f"{r['band']} Hz  +: {r['tau+1']:.2f} (sd {r['sd+1']:.2f}, n {r['n+1']})  -: {r['tau-1']:.2f} "
              f"(sd {r['sd-1']:.2f}, n {r['n-1']})  - vs +: {r['minus_vs_plus_pct']:+.2f} ± {r['minus_vs_plus_err_pct']:.2f} %")
    json.dump(res, open(os.path.join(HERE, 'local_tau.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
