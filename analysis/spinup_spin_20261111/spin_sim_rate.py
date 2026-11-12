#!/usr/bin/env python3
"""What update rate does each target need? Spin sim with the trap measured from S1's coast, at 8 / 16 / 25 / 50 updates
per second (8 = the EPICS helper today; 16 = the helper set back to 16 Hz, Alma 2026-11-11; 25-50 = a loop on worker2 at the
camera rate, e.g. through a USB/Ethernet DAC). Same controller (brake_offsets.choose_spin) with its update interval and the
landing grid set to 1/rate; push limit scanned as degrees moved per update (8 Hz x 15 deg/update = today's 120 deg/s).
Mac only.   python3 spin_sim_rate.py   # -> spin_rate_summary.md, spin_rate_cells.json
A: landing delay C 15 or 30 ms at every rate; camera 50 fps; DC push model as spin_sim (f, scale); trap x0.9/1/1.1."""
import json
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import spin_sim as S

HERE = os.path.dirname(os.path.abspath(__file__))
VARIANTS = ((1.0, 0.1, 1.0), (0.9, 0.0, 0.75), (1.1, 0.2, 1.25))     # (trap scale, f, push scale)


def run(cell):
    rate, dpu = cell[-2:]
    import brake_offsets as B
    S.TRAP_SRC = 'coast'
    S.INTAKE = B.INTAKE = 1.0 / rate
    c = list(cell[:-2]); c[-1] = dpu * rate                              # wpm = deg per update x rate
    r = S.run(tuple(c))
    r['rate'], r['dpu'] = rate, dpu
    return r


def cells():
    out = []
    for rate in (8.0, 16.0, 25.0, 50.0):
        for f_t in (0.5, 0.75, 1.0):
            for dpu in (10.0, 15.0, 20.0):
                for lv in (800.0, 1600.0):
                    for d in (1, -1):
                        for tin, f, ps in VARIANTS:
                            for C in (0.015, 0.03):
                                out.append((f_t, d, tin, 1.0, f, ps, C, lv, len(out) % 5, 0.0, rate, dpu))
    return out


def main():
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(run, cells(), chunksize=2))
    json.dump(rows, open(os.path.join(HERE, 'spin_rate_cells.json'), 'w'), indent=0)
    from itertools import groupby
    L = ['| rate (/s) | target (Hz) | best push limit (deg/update) and level | passed | turns within 5 % | within 1 % | '
         'median t to target (s) | last 300 s mean (Hz) |', '|---|---|---|---|---|---|---|---|']
    key = lambda r: (r['rate'], r['f_t'])
    for k, g in groupby(sorted(rows, key=key), key=key):
        g = list(g)
        sub = {}
        for r in g:
            sub.setdefault((r['dpu'], r['level']), []).append(r)
        best = max(sub, key=lambda s: (sum(r['ok'] for r in sub[s]), np.mean([r['frac5'] for r in sub[s]])))
        rr = sub[best]
        tr = [r['t_reach'] for r in rr if r['t_reach'] is not None]
        L.append(f'| {k[0]:.0f} | {k[1]} | {best[0]:.0f} ({best[0] * k[0]:.0f} deg/s), {best[1]:.0f} | '
                 f'{sum(r["ok"] for r in rr)}/{len(rr)} | {np.mean([r["frac5"] for r in rr]):.2f} | '
                 f'{np.mean([r["frac1"] for r in rr]):.2f} | {np.median(tr) if tr else float("nan"):.0f} | '
                 f'{np.mean([r["late_mean"] for r in rr]):.3f} |')
    txt = ('Trap from the S1 coast; variants (trap x, f, push x) = ' + str(VARIANTS) + '; C 15/30 ms; both directions; '
           '12 cells per setting.\nPass: first turn along dir, target within 5 % before 300 s, every turn of the last 300 s '
           'within 5 %.\n\n' + '\n'.join(L) + '\n')
    print(txt)
    open(os.path.join(HERE, 'spin_rate_summary.md'), 'w').write(txt)


if __name__ == '__main__':
    main()
