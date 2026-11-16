#!/usr/bin/env python3
"""Model-free push map from the 11-14/15 drive logs: push acceleration per phase in 10 deg bins (run after drive_fit.py).

    python3 map_bins.py     # -> map_bins.json, plots/map_bins.png

Uses drive_fit.py's 'grid' timing per run and its fitted trap T(theta) (Fourier m <= 24), then fits
    alpha + omega/TAU - T(theta) = sum_q u_q(t) * a_q[bin(theta)]
(one free value per phase per 10 deg bin, regressors through the same smoothing kernel). Bins with fewer than 300
pushed frames are not reported. Compared with: the G1 map (B2+G1, measured 167-267 deg, 45 deg periodic) and the
drive_fit.py Fourier fit (m 0, 8, 16).
Errors: 1-sigma from a jackknife over runs (delete one run of 61), since residuals within a run are correlated.
"""
import json
import os

import numpy as np

import drive_fit as d

HERE = os.path.dirname(os.path.abspath(__file__))
NB = 36


def main():
    import glob
    o = json.load(open(os.path.join(HERE, 'drive_fit.json')))
    b = np.array(o['grid_b']); nT = 1 + 2 * d.MT
    runs = [d.load_run(f) for f in sorted(glob.glob(os.path.join(d.D, 'brake_*.csv')))]
    per_run = []
    counts = np.zeros((3, NB))
    for run, p in zip(runs, o['grid_params']):
        t0 = np.floor(run['t'][0] / d.TICK) * d.TICK
        u = d.u_of_t(run, 'grid', dict(phase=t0 + p['phase'], delta=p['delta']))
        th = run['th']
        T = d.fourier(th, range(0, d.MT + 1)) @ b[:nT]
        y = run['alpha'] + d.smooth(run['omega']) / d.TAU - d.smooth(T)
        if len(b) > nT + 15:                                   # omega^2 B(theta) term of drive_fit.py (W2)
            y = y - d.smooth(run['w2'] * (d.fourier(th, range(1, d.MT + 1)) @ b[nT + 15:]))
        bins = (np.mod(np.degrees(th), 360) // (360 / NB)).astype(int)
        X = np.zeros((len(th), 3 * NB))
        for q in range(3):
            X[np.arange(len(th)), q * NB + bins] = u[:, q]
            counts[q] += np.bincount(bins[u[:, q] > 0], minlength=NB)
        Xs = np.apply_along_axis(d.smooth, 0, X)
        g = run['good']
        per_run.append((Xs[g].T @ Xs[g], Xs[g].T @ y[g]))
    XX = sum(a for a, _ in per_run); Xy = sum(c for _, c in per_run)
    reg = 1e-3 * np.eye(len(XX))
    a = np.linalg.solve(XX + reg, Xy)
    jk = np.array([np.linalg.solve(XX - A + reg, Xy - c) for A, c in per_run])
    n = len(per_run)
    err = np.sqrt((n - 1) / n * ((jk - jk.mean(0)) ** 2).sum(0))
    a = a.reshape(3, NB); err = err.reshape(3, NB)
    ctr = (np.arange(NB) + 0.5) * 360 / NB
    th = np.radians(ctr)
    g = d.G1MAP
    g1 = np.array([g['const'] + g['c8'] * np.cos(8 * (th - np.radians(s))) + g['s8'] * np.sin(8 * (th - np.radians(s)))
                   + g['c16'] * np.cos(16 * (th - np.radians(s))) + g['s16'] * np.sin(16 * (th - np.radians(s)))
                   for s in g['shift']])
    F = d.fourier(th, d.MSET)
    fit = np.array([F @ b[nT + 5 * q:nT + 5 * q + 5] for q in range(3)])
    # the maps are smeared over each bin's 10 deg (and the rotor's sweep within the smoothing); compare bin averages
    fine = np.radians(np.arange(0, 360, 0.5))
    def binavg(vals):
        return vals.reshape(NB, -1).mean(1)
    g1b = np.array([binavg(g['const'] + g['c8'] * np.cos(8 * (fine - np.radians(s))) + g['s8'] * np.sin(8 * (fine - np.radians(s)))
                           + g['c16'] * np.cos(16 * (fine - np.radians(s))) + g['s16'] * np.sin(16 * (fine - np.radians(s))))
                    for s in g['shift']])
    Ff = d.fourier(fine, d.MSET)
    fitb = np.array([binavg(Ff @ b[nT + 5 * q:nT + 5 * q + 5]) for q in range(3)])
    ok = counts >= 300
    print('bin centre | for A, B, C: measured ± err (pushed frames) | G1 map | Fourier fit   (rad/s^2 at 800 counts)')
    for i in range(NB):
        if not ok[:, i].any():
            continue
        s = f'{ctr[i]:5.0f} '
        for q in range(3):
            s += (f'| {a[q, i]:+.3f}±{err[q, i]:.3f} ({int(counts[q, i]):5d}) G1 {g1b[q, i]:+.3f} fit {fitb[q, i]:+.3f} '
                  if ok[q, i] else '| ' + ' ' * 45)
        print(s)
    m = ok
    for q, nm in enumerate('ABC'):
        mm = m[q]
        if mm.sum() < 2:
            continue
        chi_g1 = np.sum(((a[q, mm] - g1b[q, mm]) / err[q, mm]) ** 2)
        chi_fit = np.sum(((a[q, mm] - fitb[q, mm]) / err[q, mm]) ** 2)
        print(f'{nm}: {mm.sum()} bins; chi2 vs G1 map {chi_g1:.0f}, vs Fourier fit {chi_fit:.0f}; '
              f'rms(measured - G1) {np.sqrt(np.mean((a[q, mm] - g1b[q, mm]) ** 2)):.3f}; sign agreement with G1 '
              f'{int(np.sum(np.sign(a[q, mm]) == np.sign(g1b[q, mm])))}/{mm.sum()}')
    json.dump(dict(bin_centre_deg=ctr.tolist(), measured=a.tolist(), err=err.tolist(), pushed_frames=counts.tolist(),
                   g1_binavg=g1b.tolist(), fourier_binavg=fitb.tolist()), open(os.path.join(HERE, 'map_bins.json'), 'w'), indent=1)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(4, 1, figsize=(10, 11), sharex=True)
    for q, nm in enumerate('ABC'):
        mm = ok[q]
        ax[q].errorbar(ctr[mm], a[q, mm], err[q, mm], fmt='o', ms=4, color='k', label='measured (drive logs, 10 deg bins)')
        ax[q].plot(np.degrees(fine), g['const'] + g['c8'] * np.cos(8 * (fine - np.radians(g['shift'][q]))) + g['s8'] * np.sin(8 * (fine - np.radians(g['shift'][q])))
                   + g['c16'] * np.cos(16 * (fine - np.radians(g['shift'][q]))) + g['s16'] * np.sin(16 * (fine - np.radians(g['shift'][q]))),
                   color='C1', lw=1, label='G1 map (measured 167-267, 45 deg periodic)')
        ax[q].plot(np.degrees(fine), Ff @ b[nT + 5 * q:nT + 5 * q + 5], color='C0', lw=1, label='Fourier fit, these logs')
        ax[q].axvspan(167, 267, color='C1', alpha=0.08)
        ax[q].axhline(0, color='0.6', lw=0.5)
        ax[q].set_ylabel(f'phase {nm} push (rad/s^2)'); ax[q].set_ylim(-1.2, 1.2)
    ax[0].legend(fontsize=8, loc='upper right')
    for q, nm in enumerate('ABC'):
        ax[3].step(ctr, counts[q], where='mid', label=nm)
    ax[3].set_yscale('log'); ax[3].set_ylabel('pushed frames'); ax[3].set_xlabel('rotor angle (deg)'); ax[3].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'map_bins.png'), dpi=95)


if __name__ == '__main__':
    main()
