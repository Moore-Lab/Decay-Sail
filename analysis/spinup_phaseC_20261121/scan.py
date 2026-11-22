#!/usr/bin/env python3
"""Phase C scans in the calibrated sim (push_x 0.65, trap_x 1.0, coast-matched start). Sim only, existing CLI flags only (variant live).
python3 scan.py grid|oat|variant NAME   -> scan_<name>.json
Cells per setting: 12 Phase A cells (3 plant variants x C 15/30 ms x dir, seed 0/1) + 12 calibrated nominal cells (dir x C x seeds 0-2) = 24.
Metrics (mode rev: start 0.44 Hz coast against dir; mode up: from rest), time = field on -> stop (3 turns within stop_tol), failure = no stop
in T = 300 s (counted as 300 in the median/p90, reported separately)."""
import itertools, json, os, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import sim_c as S

HERE = os.path.dirname(os.path.abspath(__file__))
CAL = dict(push_x=0.65, trap_x=1.0)
T = 300.0


def all_cells():
    a = [(c, 'A') for c in S.cells()]
    b = [(dict(d=d, tin=1.0, f=0.1, ps=1.0, C=C, seed=sd), 'N') for d in (1, -1) for C in (0.015, 0.03) for sd in range(3)]
    return a + b


def job(a):
    cell, P = a
    r = S.run(cell, P); r.pop('rec')
    return dict(t=(r['t_stop'] if r['reason'] == 'target' else T), ok=r['reason'] == 'target', reason=r['reason'],
                first=r['t_first_turn'], peak_w=r['peak_w'], peak_f=r['peak_f'], rs=r['rates_stop'])


def stats(rows):
    t = np.array([r['t'] for r in rows])
    return dict(med=float(np.median(t)), p90=float(np.percentile(t, 90)), mean=float(t.mean()), fail=int(sum(not r['ok'] for r in rows)), n=len(rows),
                first_med=float(np.median([r['first'] if r['first'] is not None else T for r in rows])), wcap=int(sum(r['reason'] == 'w-cap' for r in rows)),
                peak_f_med=float(np.median([r['peak_f'] for r in rows])), peak_f_max=float(max(r['peak_f'] for r in rows)),
                rate_stop_med=float(np.median([np.mean(r['rs']) for r in rows if r['ok']])) if any(r['ok'] for r in rows) else None,
                rate_stop_p90=float(np.percentile([max(r['rs']) for r in rows if r['ok']], 90)) if any(r['ok'] for r in rows) else None)


def evaluate(settings, ex, modes=('rev', 'up')):
    cl = all_cells(); out = []
    for st in settings:
        row = dict(setting=st)
        for m in modes:
            P = dict(CAL, T=T, start_f=0.44 if m == 'rev' else 0.0, **{k: v for k, v in st.items()})
            if m == 'up':
                P['start_mode'] = 'rest'
            rows = list(ex.map(job, [(c, P) for c, _ in cl]))
            row[m] = stats(rows)
        out.append(row)
        print(st, 'rev med %.0f p90 %.0f fail %d | up med %.0f p90 %.0f fail %d' % (row['rev']['med'], row['rev']['p90'], row['rev']['fail'],
              row['up']['med'], row['up']['p90'], row['up']['fail']) if 'up' in row else '', flush=True)
    return out


BASE = dict(wpm=140.0, level=1600.0, tol=0.1, stop_tol=0.01, stop_n=3, ca=0.030, minp=0.15)

if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'grid':
        S_ = [dict(BASE, wpm=w, tol=t, stop_tol=s, stop_n=n) for w in (140, 180, 220, 260, 320) for t in (0.05, 0.1, 0.15, 0.2)
              for s in (0.05, 0.08, 0.12) for n in (2, 3)]
        S_ += [dict(BASE, wpm=140, tol=0.05, stop_tol=0.01), dict(BASE), dict(BASE, wpm=120, tol=0.05, level=800.0, stop_tol=0.01)]   # live recipe, R1-R6, + old
    elif mode == 'oat':
        best = json.loads(sys.argv[2])
        S_ = [dict(best, minp=m) for m in (0.05, 0.1, 0.15, 0.2, 0.3)] + [dict(best, ca=c) for c in (0.015, 0.030, 0.045, 0.06, 0.09)] + \
             [dict(best, level=l) for l in (800.0, 1200.0, 1600.0)]
    elif mode == 'sel':                                  # python3 scan.py sel '<json list of settings>' NAME  (rev + up)
        S_ = [dict(BASE, **b) for b in json.loads(sys.argv[2])]
    with ProcessPoolExecutor() as ex:
        res = evaluate(S_, ex, modes=('rev',) if mode == 'grid' else ('rev', 'up'))
    json.dump(res, open(os.path.join(HERE, f'scan_{sys.argv[3] if mode == "sel" else mode}.json'), 'w'), indent=1)
