#!/usr/bin/env python3
"""Reversal: rotor turning at 0.5 Hz against DIR; the spin-up governor (brake_offsets.choose_spin with the reverse rule,
2026-11-12) asked for DIR. Trap from S1's coast; push variants x C x both directions x 2 seeds; targets 0.495 / 0.5 Hz;
level 800, push limit 120 deg/s. Mac only.   python3 spin_sim_reverse.py  # -> spin_reverse_summary.md"""
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import spin_sim as S

HERE = os.path.dirname(os.path.abspath(__file__))


def run(c):
    S.TRAP_SRC, S.START_F, S.TOL = 'coast', 0.5, 0.05
    return S.run(c)


def cells():
    return [(ft, d, tin, 1.0, f, ps, C, 800.0, sd, 120.0) for ft in (0.495, 0.5) for d in (1, -1)
            for tin, f, ps in ((1.0, 0.1, 1.0), (0.9, 0.0, 0.75), (1.1, 0.2, 1.25)) for C in (0.015, 0.03) for sd in (0, 1)]


if __name__ == '__main__':
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(run, cells(), chunksize=2))
    txt = 'Reversal from 0.5 Hz against dir (sim, coast trap, level 800, push limit 120 deg/s, 12 cells per row).\n\n' + \
        S.table(rows, ['f_t', 'dir']) + '\n'
    print(txt); open(os.path.join(HERE, 'spin_reverse_summary.md'), 'w').write(txt)
