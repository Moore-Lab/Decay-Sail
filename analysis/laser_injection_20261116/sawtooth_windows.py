#!/usr/bin/env python3
"""Sawtooth model with the side camera's laser window, and where the window sits on the hill (2026-11-19). DERIVED.

    python3 sawtooth_windows.py     # prints kick sizes; plots/sawtooth_windows.png (gitignored)

New inputs vs sawtooth_model.py:
 - window width from the side camera (worker2 ~/wt_sidecam/camera_utils/side_camera/HANDOFF.md, 2026-11-17, D): beam on
   the wing from -47 to +27 deg of rotor angle around face-on (74 deg; patchy to +53).
 - window position in tracker angle: ASSUMED at the centres of the two glare lobes in the top camera (glare_frames.py,
   ND2: strong at 40-130 and 210-310 deg), i.e. face-on at ~85 deg (and ~260 deg for the opposite wing). The side and
   top camera angle conventions have not been tied together, so the sign of the -47/+27 asymmetry is also assumed.
 - one wing (one window per turn) or two wings (two windows, 180 deg apart): not known yet (ask Molly).
Total push per turn is fixed by the measured Delta gamma (ND1 calibration, 2.6e-15 N m/mW turn-averaged, +-10 %),
shared equally between the windows. Speed against rotor angle (panel a) is MEASURED: ND2 laser-off turns averaging
0.43-0.44 Hz, time to cross each 10 deg from the raw tracker angles.
"""
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sawtooth_model as SM   # noqa: E402

FACE = (85.0, 260.0)
LO, HI = -47.0, 27.0
CASES = {'assumed before: one 45° window': [(SM.CEN - 22.5, SM.CEN + 22.5)],
         'side camera, one wing (74°)': [(FACE[0] + LO, FACE[0] + HI)],
         'side camera, two wings (2 × 74°)': [(FACE[0] + LO, FACE[0] + HI), (FACE[1] + LO, FACE[1] + HI)]}


def inwin(deg, wins):
    return any(((deg - a) % 360) <= (b - a) for a, b in wins)


def simulate(P_mW, hill, wins, turns=4, dt=1e-3, om0=None):
    width = sum(b - a for a, b in wins)
    npk = SM.K * P_mW * 360.0 / width
    th, om = 0.0, (om0 if om0 is not None else 2 * np.pi * SM.F0)
    ctr = np.arange(len(hill)) * 360 / len(hill) + 180 / len(hill) if hill is not None else None
    T, W, TH = [], [], []
    t = 0.0
    while th < turns * 2 * np.pi:
        deg = np.degrees(th) % 360
        acc = -SM.GAMMA * om
        if hill is not None:
            acc += np.interp(deg, np.r_[ctr - 360, ctr, ctr + 360], np.r_[hill, hill, hill])
        if inwin(deg, wins):
            acc += npk / SM.I
        om += acc * dt; th += om * dt; t += dt
        T.append(t); W.append(om); TH.append(th)
    return np.array(T), np.array(W) / (2 * np.pi), np.degrees(np.array(TH))


def measured_speed_vs_angle():
    import angle_profile as A
    C = A.C
    k, h, a, n = C.load_tracker(False)
    t_all = k / C.TC.FPS
    off = float(np.median(h - t_all))
    acc = [[] for _ in range(36)]
    for p in sorted(glob.glob(os.path.join(C.D, A.RUN, 'coast_O*.txt'))):
        nm = os.path.basename(p)[6:-4]; m = A.meta(p)
        if nm == 'O39' or 'coast_end_host' not in m or m.get('laser') != 'off' or int(nm[1:]) % 2 == 0:
            continue
        t0, t1 = m['field_off_host'] + 5 - off, m['coast_end_host'] - 2 - off
        w = (t_all >= t0) & (t_all <= t1)
        x = np.degrees(np.unwrap(np.radians(a[w]))); tt = t_all[w]
        marks = np.arange(np.ceil(x[0] / 10) * 10, x[-1], 10)
        tc = np.interp(marks, x, tt)
        seg = np.diff(tc)
        turnT = np.convolve(seg, np.ones(36), 'same')
        ok = np.abs(1 / turnT - 0.435) < 0.005
        for s, mk, o in zip(seg, marks[:-1], ok):
            if o:
                acc[int(mk % 360 // 10)].append(10 / 360 / s)
    return np.array([np.median(v) for v in acc]), np.array([len(v) for v in acc])


def main():
    hill = SM.hill_profile()
    hill, om0 = SM.calibrate(hill)
    w0 = 2 * np.pi * SM.F0
    for lab, wins in CASES.items():
        width = sum(b - a for a, b in wins)
        npk = SM.K * 3.08 * 360 / width
        kick = npk / SM.I * (np.radians(width / len(wins)) / w0) / (2 * np.pi)
        print(f'{lab}: windows {wins}; in-window torque at full power {npk:.2e} N m '
              f'({npk / 3.08:.1e} N m/mW); kick per pass {kick * 1e6:.0f} uHz, {len(wins)} pass(es) per turn')
    sp, cnt = measured_speed_vs_angle()
    print(f'measured speed vs angle: min {sp.min():.3f} Hz at {np.argmin(sp) * 10 + 5} deg, max {sp.max():.3f} at '
          f'{np.argmax(sp) * 10 + 5} deg; turns per bin ~{int(np.median(cnt))}')
    plot(hill, om0, sp)


def shade(ax, wins, ymin, ymax, x_scale=1.0, turns=1, color='#c0392b', alpha=0.10):
    for k_ in range(turns + 1):
        for a, b in wins:
            ax.axvspan((k_ * 360 + a) / x_scale, (k_ * 360 + b) / x_scale, color=color, alpha=alpha, lw=0)


def plot(hill, om0, sp):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'sans-serif', 'axes.spines.top': False, 'axes.spines.right': False})
    cols = ['0.55', '#1f3b73', '#c0392b']
    fig, ax = plt.subplots(3, 1, figsize=(10, 12))
    ang = np.arange(36) * 10 + 5
    ax[0].plot(ang, sp, 'o-', color='k', ms=4, label='measured (ND2, laser off, turns averaging 0.435 Hz)')
    wins2 = CASES['side camera, two wings (2 × 74°)']
    for i, (a, b) in enumerate(wins2):
        ax[0].axvspan(a, b, color='#c0392b', alpha=0.12 if i == 0 else 0.06, lw=0,
                      label='beam on wing 1 (side camera width; position assumed)' if i == 0 else 'wing 2, if the sail has two')
    ax[0].axhline(0.435, color='0.6', ls=':', lw=1)
    ax[0].set_xlim(0, 360); ax[0].set_xticks(range(0, 361, 45))
    ax[0].set_xlabel('rotor angle (tracker, deg)'); ax[0].set_ylabel('rotation rate (Hz)')
    ax[0].legend(frameon=False, fontsize=9, loc='upper left')
    ax[0].set_title('(a) Where the beam window falls on the hill: speed through one turn (measured) and window (assumed position)', fontsize=10)
    for (lab, wins), c in zip(CASES.items(), cols):
        t, f, th = simulate(3.08, None, wins)
        ax[1].plot(th / 360, (f - SM.F0) * 1e3, color=c, lw=1.6 if 'two' in lab else 1.2, label=lab)
    t0, f0, th0 = simulate(0.0, None, [(0, 1)])
    ax[1].plot(th0 / 360, (f0 - SM.F0) * 1e3, color='0.3', ls='--', lw=1, label='laser off')
    ax[1].set_xlabel('turns'); ax[1].set_ylabel('rotation rate − 0.435 Hz (mHz)'); ax[1].legend(frameon=False, fontsize=9)
    ax[1].set_title('(b) Without the hill, full power: wider or doubled windows give smaller kicks; the same total per turn', fontsize=10)
    tb, fb, thb = simulate(0.0, hill, [(0, 1)], om0=om0)
    for (lab, wins), c in zip(CASES.items(), cols):
        ta, fa, tha = simulate(3.08, hill, wins, om0=om0)
        grid = np.linspace(0, min(tha[-1], thb[-1]), 4000)
        ax[2].plot(grid / 360, (np.interp(grid, tha, fa) - np.interp(grid, thb, fb)) * 1e6, color=c, label=lab)
    ax[2].set_xlabel('turns'); ax[2].set_ylabel('laser on − off, same angle (µHz)'); ax[2].legend(frameon=False, fontsize=9)
    ax[2].set_title('(c) With the measured hill, full power: the staircase; steps sit where the beam is on the wing', fontsize=10)
    for a_ in ax:
        a_.grid(alpha=0.3)
    fig.suptitle('Rough model (derived): side-camera window, torque from the ND1 calibration (±10 %), full power extrapolated',
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'plots', 'sawtooth_windows.png'), dpi=130)


if __name__ == '__main__':
    main()
