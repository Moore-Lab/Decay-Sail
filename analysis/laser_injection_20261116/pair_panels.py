#!/usr/bin/env python3
"""Laser injection 2026-11-16: per-pair coast-down panels (+ and - coast in the 0.40-0.47 Hz band, 1-min means and
exponential fit), the style of analysis/overnight_20261114/plots/pair_grid.png, for the laser-off and laser-on pairs.
Mac only; uses coasts.py's loader (run coasts.py --no-cache first to refresh the tracker cache).

    python3 pair_panels.py        # -> plots/laser_pair_panels.png (gitignored)
"""
import glob
import os

import numpy as np

import coasts as C

HERE = os.path.dirname(os.path.abspath(__file__))
LABEL = {'off1': 'laser blocked', 'on': 'laser on, ND1 (0.30 mW at window)'}


def band(run, name, k, h, a, n):
    meta = C.read_meta(os.path.join(C.D, run, f'coast_{name}.txt'))
    t_all = k / C.TC.FPS
    off = float(np.median(h - t_all))
    d = 1 if int(name[1:]) % 2 else -1
    t0, t1 = meta['field_off_host'] + 5 - off, meta['coast_end_host'] - 2 - off
    w = (t_all >= t0) & (t_all <= t1)
    tr = C.TC.turns(t_all[w] - t0, np.degrees(np.unwrap(np.radians(a[w]))), d, n[w] >= 0.5)
    s = (tr[:, 1] >= C.BAND[0]) & (tr[:, 1] <= C.BAND[1])
    t = tr[s, 0] - tr[s, 0][0]; f = tr[s, 1]
    g, ge = C.PP.gamma_mid(t, f)
    tau, f0 = C.PP.fit_tau(t, f)
    return dict(t=t, f=f, g=g, ge=ge, tau=tau, f0=f0, host=meta['field_off_host'])


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    k, h, a, n = C.load_tracker(False)
    pairs = []
    for run in ('off1', 'on'):
        names = sorted(os.path.basename(p)[6:-4] for p in glob.glob(os.path.join(C.D, run, 'coast_O*.txt')))
        for i in range(0, len(names) - 1, 2):
            pairs.append((run, names[i], names[i + 1], band(run, names[i], k, h, a, n),
                          band(run, names[i + 1], k, h, a, n)))
    t_first = min(P['host'] for *_, P, _ in pairs)
    cp, cm = '#1f3b73', '#4a90a4'
    plt.rcParams.update({'font.family': 'sans-serif', 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axs = plt.subplots(1, len(pairs), figsize=(5.2 * len(pairs), 4.4), sharey=True)
    for ax, (run, a_, b_, P, M) in zip(np.atleast_1d(axs), pairs):
        for S, col, lab in ((P, cp, '+'), (M, cm, '−')):
            bb = C.PP.binned(S['t'], S['f'])
            ax.plot(bb[:, 0] / 60, bb[:, 1], 'o', ms=4, color=col)
            tt = np.linspace(0, S['t'][-1], 200)
            ax.plot(tt / 60, S['f0'] * np.exp(-tt / S['tau']), '-', lw=1.4, color=col,
                    label=f"{lab} γ {1e3 * S['g']:.4f}±{1e3 * S['ge']:.4f} mHz")
        dg, de = 1e6 * (M['g'] - P['g']), 1e6 * float(np.hypot(P['ge'], M['ge']))
        ax.set_title(f"{LABEL.get(run, run)}\n{run} {a_}/{b_}  {(P['host'] - t_first) / 3600:.1f} h  "
                     f"Δγ {dg:+.2f}±{de:.2f} µHz", fontsize=10)
        ax.legend(frameon=False, fontsize=9, loc='upper right'); ax.grid(alpha=0.3)
        ax.set_xlabel('time since entering the band (min)')
    np.atleast_1d(axs)[0].set_ylabel('rotor frequency (Hz)')
    fig.suptitle('Laser injection 2026-11-16: + vs − coast-down, 0.40–0.47 Hz (tracker, 1-min means; '
                 'γ at 0.435 Hz, Δγ = γ(−) − γ(+))', fontsize=11)
    fig.tight_layout()
    out = os.path.join(HERE, 'plots', 'laser_pair_panels.png')
    fig.savefig(out, dpi=140)
    print(out)


if __name__ == '__main__':
    main()
