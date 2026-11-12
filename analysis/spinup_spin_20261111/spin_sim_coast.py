#!/usr/bin/env python3
"""Spin sim with the trap measured from S1's coast (full circle), scanning the push-speed limit. Mac only.
    python3 spin_sim_coast.py   # -> spin_coast_summary.md, spin_coast_cells.json
Validation: at --w-push-max 90 and level 1600 the live plateau was 0.45-0.47 Hz (S1, S3)."""
import json
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import spin_sim as S

HERE = os.path.dirname(os.path.abspath(__file__))


def run(c):
    S.TRAP_SRC = 'coast'
    return S.run(c)


def cells():
    out = []
    for f_t in (0.5, 0.75):
        for d in (1, -1):
            for wpm in (90.0, 120.0, 150.0, 180.0, 240.0):
                for lv in (800.0, 1600.0):
                    for tin in (0.9, 1.0, 1.1):
                        for f, ps in ((0.1, 1.0), (0.0, 0.75), (0.2, 1.25)):
                            for C in (0.015, 0.06):
                                out.append((f_t, d, tin, 1.0, f, ps, C, lv, len(out) % 5, wpm))
    return out


def main():
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(run, cells(), chunksize=2))
    json.dump(rows, open(os.path.join(HERE, 'spin_coast_cells.json'), 'w'), indent=0)
    txt = ('Trap from the S1 coast (x0.9/1.0/1.1); push (f, scale) in {(0.1,1), (0,0.75), (0.2,1.25)}; C 15/60 ms; both dirs.\n'
           'Pass: first turn along dir, target within 5 % before 300 s, every turn of the last 300 s within 5 %.\n\n'
           + S.table(rows, ['f_t', 'level', 'wpm']) + '\n')
    print(txt)
    open(os.path.join(HERE, 'spin_coast_summary.md'), 'w').write(txt)


if __name__ == '__main__':
    main()
