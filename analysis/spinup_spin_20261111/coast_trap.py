#!/usr/bin/env python3
"""Trap over the full circle, and damping, from the free coast after spin-up S1 (2026-11-11). Mac only.

    python3 coast_trap.py      # -> coast_trap.json, plots/coast_trap.png, printed summary

With the field off, per unit moment of inertia: 1/2 w^2 + U(theta) = E(t), E slowly falling (damping). Fit, by linear
least squares on every tracked frame of the rotating part of the coast:
    1/2 w(t)^2 = E(t) - U(theta(t)),
with E(t) a low-order polynomial in time and U a Fourier series in theta (m = 1..M, no constant). Then the trap
a(theta) = -dU/dtheta (rad/s^2), compared with G1's measured table (180-254 deg). Damping: dE/dt against the mean w^2 at
the same time gives c in dE/dt = -c w^2 (viscous; B1's sims use c = 3.5e-4 / 2 = 1.75e-4 /s).
Speed w from a Savitzky-Golay derivative of the unwrapped angle; time from the frame index at 50.000 fps (worker2:
135001 frames in 2700 s, 0 dropped); frames with ncc < 0.85 dropped.
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-11/spin/tracker_S1')
G1 = json.load(open(os.path.join(HERE, '..', 'spinup_g1_20261111', 'pushmap_g1.json')))
STOP_HOST = 1794452333.8          # S1 field off (worker2)
LAST_TURN_HOST = 1794453014.7     # end of the last monotonic rotation (worker2)
FPS = 50.0
M = 24                            # Fourier orders in U
NE = 4                            # polynomial order of E(t)


def load():
    import csv
    rows = [r for r in csv.DictReader(l for l in open(os.path.join(D, 'blob_live_gps1478487186.csv')) if not l.startswith('#'))]
    k = np.array([int(r['frame']) for r in rows]); h = np.array([float(r['host_time']) for r in rows])
    a = np.array([float(r['angle_deg']) for r in rows]); n = np.array([float(r['ncc']) for r in rows])
    t = (k - k[0]) / FPS
    toff = np.median(h - t)                       # host time of frame 0 (jitter-free mapping)
    return t, toff, a, n


def main():
    from scipy.signal import savgol_filter
    t, toff, a, n = load()
    th = np.degrees(np.unwrap(np.radians(a)))
    w = np.radians(savgol_filter(th, 9, 3, deriv=1, delta=1 / FPS))          # rad/s
    t0, t1 = STOP_HOST + 5 - toff, LAST_TURN_HOST - 20 - toff                # rotating, field off, settled
    m = (t >= t0) & (t <= t1) & (n >= 0.85)
    tt, x, ww = t[m], np.radians(th[m]), w[m]
    y = 0.5 * ww ** 2
    ts = (tt - t0) / (t1 - t0)
    cols = [ts ** p for p in range(NE + 1)]                                   # E(t)
    for k in range(1, M + 1):                                                 # -U(theta)
        cols += [-np.cos(k * x), -np.sin(k * x)]
    A = np.column_stack(cols)
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    res = y - A @ coef
    rms = float(np.std(res))
    eC, uC = coef[:NE + 1], coef[NE + 1:]
    grid = np.radians(np.arange(0, 360, 0.5))
    U = sum(uC[2 * (k - 1)] * np.cos(k * grid) + uC[2 * (k - 1) + 1] * np.sin(k * grid) for k in range(1, M + 1))
    acc = -sum(k * (-uC[2 * (k - 1)] * np.sin(k * grid) + uC[2 * (k - 1) + 1] * np.cos(k * grid)) for k in range(1, M + 1))
    imin, imax = int(np.argmin(U)), int(np.argmax(U))
    # damping: E(t) and its slope against the turn-averaged w^2
    tg = np.linspace(0, 1, 200)
    E = sum(eC[p] * tg ** p for p in range(NE + 1))
    dE = sum(p * eC[p] * tg ** (p - 1) for p in range(1, NE + 1)) / (t1 - t0)
    w2 = np.interp(tg, ts, savgol_filter(ww ** 2, 1001 if ww.size > 1001 else ww.size // 2 * 2 - 1, 1))
    c = float(np.median(-dE / w2))
    # compare with G1 measured table
    nodes = np.array(G1['trap']['nodes_deg']); g1 = np.array(G1['trap']['joint_run'])
    sel = (nodes >= 180) & (nodes <= 254)
    a_at = np.interp(nodes[sel], np.degrees(grid), acc)
    cmp_rms = float(np.sqrt(np.mean((a_at - g1[sel]) ** 2)))
    out = dict(window_host=[t0 + toff, t1 + toff], n_frames=int(m.sum()), M=M, NE=NE, fit_rms_half_w2=rms,
               U_min_deg=float(np.degrees(grid[imin])), U_max_deg=float(np.degrees(grid[imax])),
               barrier_rad2_s2=float(U[imax] - U[imin]), acc_max=float(acc.max()), acc_min=float(acc.min()),
               E_start=float(E[0] - U[imin]), E_end=float(E[-1] - U[imin]), c_viscous_per_s=c,
               rms_vs_G1_180_254=cmp_rms, theta_deg=list(np.degrees(grid)), U=list(U - U[imin]), acc=list(acc))
    json.dump(out, open(os.path.join(HERE, 'coast_trap.json'), 'w'))
    print({k: (round(v, 5) if isinstance(v, float) else v) for k, v in out.items() if not isinstance(v, list)})
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig, ax = plt.subplots(1, 3, figsize=(17, 4.5))
    ax[0].plot(np.degrees(grid), U - U[imin]); ax[0].set_xlabel('theta (deg)'); ax[0].set_ylabel('U (rad^2/s^2, per I)')
    ax[0].axhline(E[0] - U[imin], color='C1', ls=':', label='E, coast start'); ax[0].axhline(E[-1] - U[imin], color='C2', ls=':',
                                                                                         label='E, coast end (fit window)')
    ax[0].legend(fontsize=8); ax[0].set_title('potential from the coast', fontsize=10)
    ax[1].plot(np.degrees(grid), acc, label='coast fit (field off, full circle)')
    ax[1].plot(nodes, g1, 'k.', ms=3, label='G1 table (measured 180-254 trusted)')
    ax[1].axvspan(180, 254, color='0.9'); ax[1].set_xlabel('theta (deg)'); ax[1].set_ylabel('trap a (rad/s^2)'); ax[1].legend(fontsize=8)
    ax[2].plot(tg * (t1 - t0), E - U[imin]); ax[2].set_xlabel('s after the window start (field off)'); ax[2].set_ylabel('E')
    ax[2].set_title(f'damping c = {c:.2e} /s (dE/dt = -c w^2); fit rms {rms:.3f}', fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'coast_trap.png'), dpi=95)


if __name__ == '__main__':
    main()
