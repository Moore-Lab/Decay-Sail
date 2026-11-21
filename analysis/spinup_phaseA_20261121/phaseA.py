#!/usr/bin/env python3
"""Phase A: spin-up governor parameter scan in simulation (no hardware). Mac only.
   python3 phaseA.py MODE ARG [GRID]   MODE = a1 TARGET_HZ | rev START_F ;  GRID = full | live | quick | refine
Imports spin_sim from ../spinup_spin_20261111 (unmodified); sets its module globals as spin_sim_rate.py /
spin_sim_reverse.py do; c_assumed is passed by wrapping brake_offsets.choose_spin in the worker.
12 cells per setting: 3 plant variants (trap x, f, push x) x C 15/30 ms x dir +-1, seed alternating 0/1 (same for every setting)."""
import functools, itertools, json, os, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'spinup_spin_20261111'))
import spin_sim as S  # noqa: E402

VARIANTS = ((1.0, 0.1, 1.0), (0.9, 0.0, 0.75), (1.1, 0.2, 1.25))
WPM = (120, 160, 200, 240, 280, 320)
LEVEL = (800, 1200, 1600)
TOLS = (0.05, 0.1)
CAS = (0.030, 0.045, 0.060)


def cell_list(f_t, level, wpm):
    out = []
    for d in (1, -1):
        for tin, f, ps in VARIANTS:
            for C in (0.015, 0.03):
                out.append((f_t, d, tin, 1.0, f, ps, C, float(level), len(out) % 2, float(wpm)))
    return out


def turns_from_trace(th, t, d, start_f):
    """turn-completion times (linearly interpolated), same definition as spin_sim.run"""
    x = d * th
    base = np.minimum.accumulate(x) if start_f > 0 else x[0]
    y = x - base
    tt, n = [], 1
    for i in range(1, len(y)):
        while y[i] >= 360.0 * n and y[i] > y[i - 1]:
            tt.append(t[i - 1] + (360.0 * n - y[i - 1]) / (y[i] - y[i - 1]) * (t[i] - t[i - 1])); n += 1
    return np.array(tt)


def t3(tt, f_t, tol=0.01):
    """time when the 3rd of 3 consecutive turn rates within tol of f_t completes; None if never"""
    if tt.size < 4:
        return None
    r = 1.0 / np.diff(tt); good = np.abs(r / f_t - 1) < tol
    for i in range(len(r) - 2):
        if good[i] and good[i + 1] and good[i + 2]:
            return float(tt[i + 3])
    return None


def work(job):
    cell, tol, ca, start_f, T = job
    import brake_offsets as B
    B.INTAKE = S.INTAKE = 0.125
    S.TRAP_SRC, S.START_F, S.TOL = 'coast', start_f, tol
    if os.environ.get('VARIANT') == 'avg':             # tier 2: own copy of the controller (tier2.py), sim only
        import tier2
        B.choose_spin = functools.partial(tier2.choose_spin_avg, c_assumed=ca, B=B)
    else:
        B.choose_spin = functools.partial(B.choose_spin.func if isinstance(B.choose_spin, functools.partial) else B.choose_spin,
                                          c_assumed=ca)
    r = S.run(cell, T=T, trace=True)
    tr = r.pop('trace')
    tt = turns_from_trace(tr['th'], tr['t'], cell[1], start_f)
    r['t3'] = t3(tt, cell[0]); r['tol'] = tol; r['ca'] = ca; r['start_f'] = start_f
    return r


def run_mode(mode, arg, grid):
    if mode == 'a1':
        f_t = float(arg); T, start_f = 600.0, 0.0
    else:
        start_f = float(arg); f_t = 0.5; T = 300.0
    jobs = [(c, tol, ca, start_f, T) for wpm, lv, tol, ca in grid for c in cell_list(f_t, lv, wpm)]
    with ProcessPoolExecutor() as ex:
        return list(ex.map(work, jobs, chunksize=4))


if __name__ == '__main__':
    mode, arg = sys.argv[1], sys.argv[2]
    tag = sys.argv[3] if len(sys.argv) > 3 else 'full'
    grid = list(itertools.product(WPM, LEVEL, TOLS, CAS))
    if tag == 'live':
        grid = [(120, 800, 0.05, 0.030)]
    elif tag == 'coarse':
        grid = list(itertools.product(WPM, LEVEL, (0.05,), (0.030,)))
    elif tag == 'refine':
        grid = list(itertools.product((100, 120, 140, 160), LEVEL, TOLS, (0.030, 0.060)))
    elif tag == 'quick':
        grid = [(120, 800, 0.05, 0.030), (240, 1600, 0.05, 0.030)]
    elif tag.startswith('grid='):                      # grid=wpm:lv:tol:ca,wpm:lv:tol:ca
        grid = [tuple(float(v) for v in g.split(':')) for g in tag[5:].split(',')]
    rows = run_mode(mode, arg, grid)
    tag = ('t2_' + tag) if os.environ.get('VARIANT') == 'avg' else tag
    json.dump(rows, open(os.path.join(HERE, f'cells_{mode}_{arg}_{tag[:20].replace("=", "").replace(":", "_").replace(",", "-")}.json'), 'w'))
    print('done', len(rows))
