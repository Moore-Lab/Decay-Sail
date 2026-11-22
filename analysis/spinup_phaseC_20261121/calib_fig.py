#!/usr/bin/env python3
"""Calibrated plant (push_x 0.65, trap_x 1.0, coast-matched start) vs live reversals: table + figure (sim only)."""
import json, os
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sim_c as S, live_metrics as L, calib as K

HERE = os.path.dirname(os.path.abspath(__file__))
CAL = dict(push_x=0.65, trap_x=1.0)
KEYS = ('t_rot_stop', 't_brake_end', 't_first_turn', 't_reach', 'hunt', 't_stop')

if __name__ == '__main__':
    out = {}
    with ProcessPoolExecutor() as ex:
        for st in (0.01, 0.1):
            rows = list(ex.map(K.job, [(c, dict(stop_tol=st, **CAL)) for c in K.cal_cells()]))
            out[str(st)] = {k: K.stat(rows, k if k != 't_stop' else 't_stop') for k in KEYS + ('rest_min_w',)}
            out[str(st)]['n_target'] = sum(r['reason'] == 'target' for r in rows); out[str(st)]['n'] = len(rows)
            out[str(st)]['gap_brake_end_to_turn'] = K.stat(rows, 'gap')
    out['live_R1_R6_tol0.01'] = K.live_stats(['R1', 'R2', 'R3', 'R4', 'R5', 'R6'])
    out['live_R7_tol0.1'] = K.live_stats(['R7'])
    json.dump(out, open(os.path.join(HERE, 'calib_result.json'), 'w'), indent=1)
    for st in ('0.01', '0.1'):
        print('SIM stop_tol', st, {k: tuple(round(x, 1) if x is not None else None for x in v) for k, v in out[st].items() if isinstance(v, tuple)}, out[st]['n_target'], '/', out[st]['n'])
    print('LIVE R1-R6', {k: tuple(round(x, 1) for x in v) for k, v in out['live_R1_R6_tol0.01'].items()})
    print('LIVE R7', {k: round(v[0], 1) for k, v in out['live_R7_tol0.1'].items()})
    # figure
    fig, ax = plt.subplots(3, 2, figsize=(13, 9), sharex=True)
    for col, (steps, cell) in enumerate((((('R1', 'R3'), dict(d=-1, tin=1.0, f=0.1, ps=1.0, C=0.03, seed=0))),
                                         (('R2', 'R4'), dict(d=1, tin=1.0, f=0.1, ps=1.0, C=0.03, seed=1)))):
        r = S.run(cell, dict(stop_tol=0.01, **CAL)); rc = r['rec']; d = cell['d']
        for s in steps:
            dd, t, ang, ch, fm, fa = L.series(s)
            ax[0, col].plot(t, d * (ang - ang[0]) / 360, lw=0.8, label=f'live {s}')
            ax[1, col].plot(t, fa, lw=0.8, label=f'live {s}')
            ax[2, col].plot(t, fm, lw=0.8, label=f'live {s}')
        ax[0, col].plot(rc['t'], d * (rc['th'] - rc['th'][0]) / 360, 'k', lw=1.0, label='sim')
        ax[1, col].plot(rc['t'], rc['fa'], 'k', lw=1.0); ax[2, col].plot(rc['t'], rc['f'], 'k', lw=1.0)
        ax[0, col].set_title(f'dir {d:+d}: live {steps} vs sim (calibrated plant, seed {cell["seed"]})', fontsize=9)
        ax[0, col].set_ylabel('turns along d'); ax[1, col].set_ylabel('f_against (Hz, 30 s)'); ax[2, col].set_ylabel('f_mean (Hz)')
        ax[1, col].axhline(0.05, color='r', ls=':'); ax[2, col].axhline(0.5, color='r', ls=':'); ax[2, col].set_xlabel('s from field on')
        ax[0, col].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'calib_fig.png'), dpi=90)
