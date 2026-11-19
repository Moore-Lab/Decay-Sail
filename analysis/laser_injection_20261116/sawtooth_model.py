#!/usr/bin/env python3
"""Rough model of rotor speed within turns with the laser pushing only while the beam is on the sail (2026-11-19).
For the colleague's sketch (speed rising in each laser window, falling in between). DERIVED, not measured.

    python3 sawtooth_model.py      # prints the per-turn numbers; plots/sawtooth_model.png (gitignored)

Inputs: turn-averaged laser torque from the ND1 calibration (S1 = 52.2 +- ~5 uHz at 0.30 mW -> 2.6e-15 N m/mW at the
window, M/D); I = 1.1e-11 kg m^2 (A); drag gamma = 490 uHz (M, tau ~34 min); the once-per-turn hill as measured
(laser-off theta'' against rotor angle from the ND2 tracker, `angle_profile.py`, angle-mean removed so it is
conservative). Assumed: the beam is on the sail over a 45 deg window centred at 75 deg rotor angle (position not
measured), with constant torque inside it (8x the turn average). Direction +, f ~ 0.435 Hz.
"""
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
I = 1.1e-11
K = 2.6e-15               # N m/mW, turn-averaged
GAMMA = 490e-6            # 1/s
F0 = 0.435
WIN, CEN = 45.0, 75.0     # deg (assumed)
POWERS = {'full power, 3.08 mW': 3.08, 'ND1, 0.30 mW': 0.30, 'ND2, 0.031 mW': 0.0305}
RECOIL_NM = 1.1e-18


def hill_profile():
    import angle_profile as A
    C = A.C
    k, h, a, n = C.load_tracker(False)
    t_all = k / C.TC.FPS
    off = float(np.median(h - t_all))
    sets = []
    for p in sorted(glob.glob(os.path.join(C.D, A.RUN, 'coast_O*.txt'))):
        nm = os.path.basename(p)[6:-4]; m = A.meta(p)
        if nm == 'O39' or 'coast_end_host' not in m or m.get('laser') != 'off' or int(nm[1:]) % 2 == 0:
            continue
        r = A.coast_frames(k, h, a, n, t_all, off, m, 1)
        if r is not None:
            sets.append(r)
    prof, _ = A.profile(sets)
    return prof - prof.mean()          # rad/s^2 per 10 deg bin, conservative part


def simulate(P_mW, hill, turns=4, dt=1e-3):
    nbar = K * P_mW
    npk = nbar * 360.0 / WIN
    th, om = 0.0, 2 * np.pi * F0
    T, W, TH = [], [], []
    t = 0.0
    ctr = np.arange(len(hill)) * 360 / len(hill) + 180 / len(hill) if hill is not None else None
    while th < turns * 2 * np.pi:
        deg = np.degrees(th) % 360
        acc = -GAMMA * om
        if hill is not None:
            acc += np.interp(deg, np.r_[ctr - 360, ctr, ctr + 360], np.r_[hill, hill, hill])
        if abs((deg - CEN + 180) % 360 - 180) <= WIN / 2:
            acc += npk / I
        om += acc * dt; th += om * dt; t += dt
        T.append(t); W.append(om); TH.append(th)
    return np.array(T), np.array(W) / (2 * np.pi), np.degrees(np.array(TH))


def main():
    w0 = 2 * np.pi * F0
    T = 1 / F0
    print(f'drag per turn: {GAMMA * w0 * T / (2 * np.pi) * 1e6:.0f} uHz of rotation rate ({GAMMA * T * 100:.3f} % of f)')
    for lab, P in POWERS.items():
        npk = K * P * 360 / WIN
        kick = npk / I * (np.radians(WIN) / w0) / (2 * np.pi)
        print(f'{lab}: turn-avg torque {K * P:.2e} N m, in-window {npk:.2e} N m; kick per pass {kick * 1e6:.1f} uHz '
              f'({kick / F0 * 100:.4f} % of f), = {kick / (GAMMA * T * F0) * 100:.1f} % of the drag loss per turn')
    print(f'recoil: torque {RECOIL_NM:.1e} N m always on; per turn {RECOIL_NM / I * T / (2 * np.pi) * 1e6:.3f} uHz '
          f'({RECOIL_NM / I * T / (2 * np.pi) / (GAMMA * T * F0) * 100:.3f} % of the drag loss per turn)')
    hill = hill_profile()
    plot(hill)


def plot(hill):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'sans-serif', 'axes.spines.top': False, 'axes.spines.right': False})
    con, coff = '#c0392b', '0.45'
    fig, ax = plt.subplots(3, 1, figsize=(10, 11))
    # (a) no hill: the sawtooth, full power vs off, as departure from the laser-off line
    t0, f0, th0 = simulate(0.0, None)
    t1, f1, th1 = simulate(3.08, None)
    ax[0].plot(t0, (f0 - F0) * 1e3, color=coff, label='laser off')
    ax[0].plot(t1, (f1 - F0) * 1e3, color=con, label='laser on, full power (3.08 mW)')
    for tt, thh in ((t1, th1),):
        inw = np.abs((thh % 360 - CEN + 180) % 360 - 180) <= WIN / 2
        ax[0].fill_between(tt, -2.6, 0.2, where=inw, color=con, alpha=0.08, lw=0)
    ax[0].set_ylim(-2.6, 0.2)
    ax[0].set_xlabel('time (s)'); ax[0].set_ylabel('rotation rate − 0.435 Hz (mHz)'); ax[0].legend(frameon=False, loc='lower left')
    ax[0].set_title('(a) Without the hill: the laser adds a kick each time the sail passes the beam (shaded)', fontsize=11)
    # (b) with the measured hill: the raw speed
    t2, f2, _ = simulate(0.0, hill); t3, f3, th3 = simulate(3.08, hill)
    ax[1].plot(t2, f2, color=coff, label='laser off'); ax[1].plot(t3, f3, color=con, lw=1, ls='--', label='laser on, full power')
    ax[1].set_xlabel('time (s)'); ax[1].set_ylabel('rotation rate (Hz)'); ax[1].legend(frameon=False, loc='upper right')
    ax[1].set_title('(b) With the measured once-per-turn hill: the laser kicks are invisible in the raw speed', fontsize=11)
    # (c) on - off difference with the hill, compared at the same rotor angle (not the same time)
    tb, fb, thb = simulate(0.0, hill)
    for lab, P in POWERS.items():
        ta, fa, tha = simulate(P, hill)
        grid = np.linspace(0, min(tha[-1], thb[-1]), 4000)
        d = np.interp(grid, tha, fa) - np.interp(grid, thb, fb)
        ax[2].plot(grid / 360, d * 1e6, label=lab)
    ax[2].set_yscale('log'); ax[2].set_ylim(1, 3e3)
    for k_ in range(5):
        ax[2].axvspan(k_ + (CEN - WIN / 2) / 360, k_ + (CEN + WIN / 2) / 360, color=con, alpha=0.08, lw=0)
    ax[2].set_ylabel('laser on − off, same angle (µHz)'); ax[2].set_xlabel('turns'); ax[2].legend(frameon=False, loc='lower right')
    ax[2].set_title('(c) Laser on − off at the same rotor angle: a staircase, one step per pass (shaded); step ∝ power', fontsize=11)
    for a_ in ax:
        a_.grid(alpha=0.3)
    fig.suptitle('Rough model (derived, not measured): 45° beam window at 75° assumed; torque from the ND1 calibration', fontsize=12)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig.savefig(os.path.join(HERE, 'plots', 'sawtooth_model.png'), dpi=130)


if __name__ == '__main__':
    main()
