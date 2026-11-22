#!/usr/bin/env python3
"""Calibration scan: plant knobs (push_x, trap_x, C) vs live R1-R4 (fit) and R5-R7 (check). Sim only.
Cells: nominal plant variant (trap 1.0, f 0.1, push 1.0), dir +-1, seeds 0-5 (random start phase) = 12 per (dir) x C -> see cal_cells.
python3 calib.py [tag]"""
import itertools, json, os, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import sim_c as S
import live_metrics as L

HERE = os.path.dirname(os.path.abspath(__file__))


def cal_cells(Cs=(0.015, 0.03), seeds=range(6)):
    return [dict(d=d, tin=1.0, f=0.1, ps=1.0, C=C, seed=sd) for d in (1, -1) for C in Cs for sd in seeds]


def amp_at(rec, t0, dt_win=4.0):
    t, th = rec['t'], rec['th']
    m = (t > t0 - dt_win) & (t <= t0)
    return float((th[m].max() - th[m].min()) / 2) if m.any() else float('nan')


def job(a):
    cell, P = a
    r = S.run(cell, P)
    rec = r.pop('rec')
    be = r['t_brake_end']
    r['amp_be10'] = amp_at(rec, be + 10); r['amp_be20'] = amp_at(rec, be + 20); r['amp_be30'] = amp_at(rec, be + 30)
    return r


def stat(rows, k):
    v = [r[k] for r in rows if r[k] is not None]
    return (float(np.median(v)), float(np.percentile(v, 10)), float(np.percentile(v, 90)), len(v)) if v else (None,) * 4


def live_stats(steps):
    ms = [L.metrics(s) for s in steps]
    out = {}
    for k in ('t_stop', 't_rot_stop', 't_brake_end', 'over_brake', 't_first_turn', 't_reach', 'hunt', 'gap_brake_to_turn'):
        v = [m[k] for m in ms]; out[k] = (float(np.median(v)), min(v), max(v))
    return out


if __name__ == '__main__':
    tag = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    grid = [dict(push_x=px, trap_x=tx) for px in (0.5, 0.65, 0.8, 1.0) for tx in (1.0, 1.2, 1.4)]
    res = []
    with ProcessPoolExecutor() as ex:
        for g in grid:
            rows = list(ex.map(job, [(c, dict(stop_tol=0.01, **g)) for c in cal_cells()]))
            s = {k: stat(rows, k) for k in ('t_stop', 't_rot_stop', 'over_brake', 't_first_turn', 't_reach', 'hunt', 'gap', 'amp_be10', 'amp_be20', 'amp_be30')}
            res.append(dict(g=g, s=s, n_target=sum(r['reason'] == 'target' for r in rows), n=len(rows)))
            print(g, 'stop %.0f first %.0f reach %.0f hunt %.0f amp20 %.0f' % (s['t_stop'][0], s['t_first_turn'][0], s['t_reach'][0], s['hunt'][0], s['amp_be20'][0]),
                  'targ', res[-1]['n_target'], '/', len(rows), flush=True)
    json.dump(res, open(os.path.join(HERE, f'calib_{tag}.json'), 'w'), indent=1)
    print('LIVE R1-R4', live_stats(['R1', 'R2', 'R3', 'R4']))
    print('LIVE R5-R7', live_stats(['R5', 'R6', 'R7']))
