#!/usr/bin/env python3
"""Write -> field delay from the rotor's response to S1's holds (2026-11-10). Analysis only, Mac.

    python3 delay_fit.py

The S1 hold block (one electrode at a time to 1200 counts for 4 s, then 0) moved the rotor from rest. Replay those
six writes into the measured-model simulator (f3_check.simulate_measured on branch feedback-drive, trap rescaled to
today's 0.379 Hz, as f3_step2.TRAP_S) with the field switched on at

    t_write (worker2 host) + rel (that write's measured wait for the 8 Hz intake, from OUT_DQ) + Delta

and fit Delta: the constant part of the delay, in the same host-clock frame as the camera timestamps the controller
uses (so it includes camera timestamp lag; that is the delay the controller must predict over, derived). The coupling
scale (amplitude) is free; both coupling models. Delta's analogue in f3_step2's scan: extra delay = Delta - write_ms
(4 ms), since the scan adds the intake wait itself.
"""
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.expanduser('~/Desktop/VSCode/decay_sail_wt_fb/lab_utils'))   # f3_check, f3_step2 (branch)
sys.path.insert(1, os.path.expanduser('~/Desktop/VSCode/decay_sail_wt_vs/lab_utils'))   # voltage_steps_score
import f3_check as F  # noqa: E402
import f3_step2 as S2  # noqa: E402

D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/voltage_steps/2026-11-10/vsteps_1794345310')
ROT = os.path.join(HERE, '..', 'voltage_steps_20261110_s1', 'rotor', 'rotor_angle_s1.csv')
REST_ABS = 208.6
AMP = 2.0 / 3.0 * 1200 / 4000          # one electrode at 1200 counts = balanced field 2/3 x 1200 (+ common mode, no torque)
PSI = {'2': 0.0, '4': 120.0, '3': 240.0}  # A, B, C = V2, V4, V3 (sim phase angles 0, -120, -240)
LEAD = 1.0


def load():
    import contextlib, io
    import voltage_steps_score as vss
    with contextlib.redirect_stdout(io.StringIO()):
        R = vss.load(D); res = vss.score(R)
    ws = sorted([w for w in R['W'] if w['block'] == 0], key=lambda w: w['h'])
    edges = [(w['h'], w['land'] - w['m'], w['chan'], w['v']) for w in ws]
    a = np.genfromtxt(ROT, delimiter=',', names=True, dtype=None, encoding=None)
    return edges, np.asarray(a['host_time'], float), np.unwrap(np.radians(np.asarray(a['angle_deg'], float)))


def sim(args):
    edges, delta, cpl, cs, T = args
    t0 = edges[0][0] - LEAD
    times = np.array([h + rel + delta - t0 for h, rel, c, v in edges])
    psi = np.array([PSI[str(c)] if v > 0 else -1.0 for h, rel, c, v in edges])
    eq = S2.equilibrium()
    t, ph, on, E = F.simulate_measured(T=T, phi0=eq, w0=0.0, coupling=S2.cpl_of(cpl), amp_scale=AMP, write_ms=0.0,
                                       upd_every=0.016, tick_phase=0.0, mtramp=0.0, noise=0.0,
                                       rest=REST_ABS - eq, replay=(times, psi), trap_scale=S2.TRAP_S, cpl_scale=cs)
    return t + t0, REST_ABS - eq + ph


def fit(edges, th, ang, T=6.0, deltas=np.arange(-0.05, 0.301, 0.005), scales=(0.5, 0.7, 1.0, 1.4, 2.0)):
    """chi2 (deg^2 per frame) of sim vs measured angle over [first edge - LEAD, + T - LEAD], per delta, best scale."""
    args = [(edges, d, c, s, T) for c in ('HOLD', '010') for d in deltas for s in scales]
    with ProcessPoolExecutor() as ex:
        out = list(ex.map(sim, args, chunksize=4))
    res = {}
    for (e, d, c, s, _), (ts, ys) in zip(args, out):
        m = (th >= ts[0]) & (th <= ts[-1])
        r = np.degrees(ang[m]) - np.interp(th[m], ts, ys)
        r -= np.mean(np.degrees(ang[(th >= ts[0]) & (th < edges[0][0])]) - REST_ABS)   # rest offset
        chi = float(np.mean(r ** 2))
        k = (c, round(d, 3))
        if k not in res or chi < res[k][0]:
            res[k] = (chi, s)
    return res


def main():
    edges, th, ang = load()
    print('hold writes (host t, rel wait ms, chan, counts):', [(round(h - edges[0][0], 3), round(1e3 * r, 1), c, v) for h, r, c, v in edges])
    out = {}
    for label, T in (('first edge (to +1.5 s)', 2.5), ('all six edges (25 s)', 26.0)):
        res = fit(edges, th, ang, T=T)
        print(f'\n{label}:')
        for c in ('HOLD', '010'):
            ds = sorted(d for cc, d in res if cc == c)
            chi = np.array([res[(c, d)][0] for d in ds])
            i = int(np.argmin(chi))
            ok = np.array(ds)[chi <= chi[i] * 1.2]     # rough range: within 20 % of the best chi2
            print(f'  {c}: best Delta {1e3 * ds[i]:.0f} ms (scale {res[(c, ds[i])][1]}), rms {np.sqrt(chi[i]):.2f} deg; '
                  f'within 20 % of best chi2: {1e3 * ok.min():.0f}..{1e3 * ok.max():.0f} ms')
            out[(label, c)] = (np.array(ds), chi, ds[i], res[(c, ds[i])][1])
    plot(edges, th, ang, out)


def plot(edges, th, ang, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
    for (label, c), (ds, chi, best, sc) in out.items():
        ax[0].plot(1e3 * ds, chi, label=f'{label}, {c}')
    ax[0].set_xlabel('Delta (ms)'); ax[0].set_ylabel('mean sq. residual (deg^2)'); ax[0].set_yscale('log'); ax[0].legend(fontsize=7)
    t0 = edges[0][0]
    for k, (win, key) in enumerate(((2.5, 'first edge (to +1.5 s)'), (26.0, 'all six edges (25 s)'))):
        m = (th >= t0 - LEAD) & (th <= t0 - LEAD + win)
        ax[k + 1].plot(th[m] - t0, np.degrees(ang[m]), 'k', lw=1, label='tracked')
        for c, col in (('HOLD', 'C0'), ('010', 'C1')):
            ds, chi, best, sc = out[(key, c)]
            ts, ys = sim((edges, best, c, sc, win))
            ax[k + 1].plot(ts - t0, ys, color=col, lw=1, label=f'sim {c}, Delta {1e3 * best:.0f} ms, x{sc}')
        for h, r, c, v in edges:
            ax[k + 1].axvline(h - t0, color='grey', lw=0.5, ls=':')
        ax[k + 1].set_xlabel('s from the first write (host)'); ax[k + 1].set_ylabel('rotor angle (deg)'); ax[k + 1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'delay_fit.png'), dpi=100); plt.close(fig)
    print('\nplot:', os.path.join(HERE, 'plots', 'delay_fit.png'))


if __name__ == '__main__':
    main()
