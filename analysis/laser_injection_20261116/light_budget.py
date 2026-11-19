#!/usr/bin/env python3
"""Is the measured laser torque what radiation pressure can give? (2026-11-19) DERIVED, rough.

    python3 light_budget.py     # prints; plots/light_budget.png (gitignored)

Geometry (side camera, spinup/2026-11-17/side_camera/HANDOFF.md, D): beam a distance b = 1.34 +- 0.05 mm from the
axis (projected; true b = this x cos(beam-to-sightline angle), angle <~10 deg); sail SAL-001 = two radial aluminium
wings, r 0.88-1.88 mm (A, from logs/2026-q3.md, not re-measured); the beam is on a wing for |phi| <= arccos(b/1.88)
= 44.5 deg from face-on (geometric), measured lit -47..+27 deg continuously (patchy to +53).
Torque while the beam is on a radial plate (D): the hit point is at r = b / cos(phi) and the normal force is
(1 + R) (P/c) cos(phi) for reflectivity R (specular) and absorption of the rest, so N = (1 + R) P b / c,
independent of phi. Two wings -> lit fraction of the turn f_lit = 2 x window / 360.
Turn-averaged maximum = (1 + R) P b / c x f_lit (all the light on the wing, no loss in the window).
Measured: 2.6e-15 N m/mW turn-averaged (ND1 calibration; +-10 % from S1 and +-10 % from I = 1.1e-11, A).
"""
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
C_LIGHT = 2.998e8
P = 1e-3                  # per mW
B = (1.34e-3, 0.05e-3)
MEAS = (2.6e-15, 2.6e-15 * np.hypot(0.10, 0.10))
CASES = [('R = 0.90 (bare Al at 660 nm, A), geometric window ±44.5° × 2', 0.90, 89.0),
         ('R = 0.90, measured window 74° × 2', 0.90, 74.0),
         ('R = 0 (black / absorbing), geometric window', 0.0, 89.0)]


def main():
    rows = []
    in_win_max = 2 * P * B[0] / C_LIGHT
    print(f'in-window torque, perfect mirror: {in_win_max:.2e} N m per mW (independent of the wing angle)')
    for lab, R, win in CASES:
        f_lit = 2 * win / 360
        mx = (1 + R) * P * B[0] / C_LIGHT * f_lit
        e = mx * B[1] / B[0]
        ratio = MEAS[0] / mx
        rerr = ratio * np.hypot(MEAS[1] / MEAS[0], e / mx)
        rows.append((lab, mx, e, ratio, rerr, f_lit))
        print(f'{lab}: lit fraction {f_lit:.2f}; max turn-averaged {mx:.2e} N m/mW; measured / max = {ratio:.2f} +- {rerr:.2f}')
    plot(rows)


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'sans-serif', 'axes.spines.top': False, 'axes.spines.right': False})
    fig, ax = plt.subplots(figsize=(12, 4.8))
    labs = [r[0] for r in rows] + ['measured (ND1 calibration)']
    vals = [r[1] for r in rows] + [MEAS[0]]
    errs = [r[2] for r in rows] + [MEAS[1]]
    cols = ['0.6', '0.6', '0.8', '#1f3b73']
    y = np.arange(len(labs))[::-1]
    ax.barh(y, np.array(vals) * 1e15, xerr=np.array(errs) * 1e15, color=cols, capsize=4, height=0.6)
    for yi, v, r in zip(y, vals, rows + [None]):
        txt = f'{v * 1e15:.1f}' + (f'   (measured is {r[3]:.2f} ± {r[4]:.2f} of this)' if r else '')
        ax.text(v * 1e15 + 0.55, yi, txt, va='center', fontsize=9)
    ax.set_yticks(y); ax.set_yticklabels(labs, fontsize=9)
    ax.set_xlabel('turn-averaged torque per mW at the window (×1e-15 N m)'); ax.set_xlim(0, 8.5)
    ax.set_title('Measured laser push vs the most radiation pressure can give (derived, rough)', fontsize=11)
    ax.grid(axis='x', alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'plots', 'light_budget.png'), dpi=130)


if __name__ == '__main__':
    main()
