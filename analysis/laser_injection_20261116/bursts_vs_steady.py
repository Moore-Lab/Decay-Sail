#!/usr/bin/env python3
"""Does a push in two windows per turn (laser) give the same Delta gamma as a steady push (recoil) of the same
turn-averaged torque, on a rotor with the measured once-per-turn hill? (2026-11-19) SIMULATION, derived.

    python3 bursts_vs_steady.py     # prints (~40 s)

Simulated coasts: hill as measured (ND2, laser off, scaled to the measured 0.27-0.63 Hz swing; sawtooth_model.py),
linear drag gamma = 490 uHz, I = 1.1e-11; each coast from a turn-averaged 0.50 Hz for 600 s, + and - directions.
Torque cases, same turn-averaged value N: steady (any angle) or in two 74 deg windows at the assumed beam position
(sawtooth_windows.py). Analysis as for real data: per-turn rates from the crossing times, gamma at 0.435 Hz from a
quadratic in log f over 0.40-0.47 Hz (pair_plots.gamma_mid); Delta gamma = gamma(-) - gamma(+); laser effect =
Delta gamma(with torque) - Delta gamma(no torque). Expected N / (pi I f) at f = 0.435 Hz.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'overnight_20261114'))
import sawtooth_model as SM      # noqa: E402
import sawtooth_windows as SW    # noqa: E402
import pair_plots as PP          # noqa: E402

DT = 2e-3
T_COAST = 600.0


def run(hill_fn, d, N, wins, om_start):
    """Semi-implicit Euler; returns per-turn (t_mid, rate)."""
    width = sum(b - a for a, b in wins) if wins else 360.0
    npk = N * 360.0 / width
    th, om, t = 0.0, d * om_start, 0.0
    cross, nxt = [], 1
    I, G = SM.I, SM.GAMMA
    while t < T_COAST:
        deg = np.degrees(th) % 360
        acc = -G * om + hill_fn(deg)
        if wins is None or SW.inwin(deg, wins):
            acc += npk / I
        om += acc * DT; th += om * DT; t += DT
        if d * th >= nxt * 2 * np.pi:
            cross.append(t); nxt += 1
    c = np.array(cross)
    return np.c_[0.5 * (c[1:] + c[:-1]), 1 / np.diff(c)]


def gamma(tr):
    s = (tr[:, 1] >= PP.BAND[0]) & (tr[:, 1] <= PP.BAND[1])
    return PP.gamma_mid(tr[s, 0] - tr[s, 0][0], tr[s, 1])[0] * 1e6


def main():
    hill = SM.hill_profile()
    hill, om0 = SM.calibrate(hill)
    ctr = np.arange(len(hill)) * 360 / len(hill) + 180 / len(hill)
    xs, ys = np.r_[ctr - 360, ctr, ctr + 360], np.r_[hill, hill, hill]
    hill_fn = lambda deg: np.interp(deg, xs, ys)          # noqa: E731
    # start speed giving a turn-averaged 0.50 Hz: scale the calibrated om0 (turn-average 0.435) by energy
    om_start = om0 * 0.50 / 0.435
    wins = SW.CASES['side camera, two wings (2 × 74°)']
    out = {}
    base = {d: gamma(run(hill_fn, d, 0.0, None, om_start)) for d in (1, -1)}
    print(f'no torque: gamma + {base[1]:.2f}, - {base[-1]:.2f} uHz (hill only; Delta {base[-1] - base[1]:+.3f})')
    for lab, N in (('ND1 (7.8e-16 N m)', SM.K * 0.30), ('full power (8.0e-15 N m)', SM.K * 3.08)):
        exp = N / (np.pi * SM.I * 0.435) * 1e6
        for case, w in (('steady', None), ('two windows', wins)):
            g = {d: gamma(run(hill_fn, d, N, w, om_start)) for d in (1, -1)}
            eff = (g[-1] - g[1]) - (base[-1] - base[1])
            out[(lab, case)] = eff
            print(f'{lab:26s} {case:12s}: Delta gamma effect {eff:+.2f} uHz (expected N/(pi I f) = {exp:+.2f}); '
                  f'gamma + {g[1] - base[1]:+.2f}, - {g[-1] - base[-1]:+.2f}')
        print(f'   two windows / steady = {out[(lab, "two windows")] / out[(lab, "steady")]:.4f}')


if __name__ == '__main__':
    main()
