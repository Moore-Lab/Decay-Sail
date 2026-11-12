#!/usr/bin/env python3
"""Spin-up by pumping over the top, then holding a mean rate (2026-11-11; DECISIONS rule amended for this run). Mac only.

    python3 spin_sim.py           # -> spin_summary.md, spin_cells.json, plots/spin_traces.png

Controller: the live code, brake_offsets.choose_spin() (branch voltage-steps, --map g1), every 125 ms, one phase at LEVEL;
mean rate over the last full turn (brake_offsets.mean_rate); safety --w-cap 500 deg/s (field off for good).
Plant (M measured, A assumed), from analysis/carry_sim_20261111/carry_sim.py:
  trap   M 180-254 deg (G1 joint_run), A outside: k-sinusoid (k 4.25 rad/s^2) x OUT = 1, 1.5, 2, plus a 0.6 rad/s^2 m=8/16
         ripple; inside x TIN = 1 or 1.12.
  push   M: G1+B2 shape, 45-deg periodic (A beyond 167-267), amplitude per phase x (1 + 0.1 N(0,1)) x PSCALE 0.75/1/1.25;
         DC coupled (A, checked 11-11): level = command; g(x) = (1 - f) x + f x^2, x = level/800, f = 0/0.1/0.2 (A above 1600).
  timing M: 8 Hz intake grid + C (15 ms; 60 ms = always one tick late); 1/400 updates lost; 50 fps, 0.05 deg noise;
         damping 3.5e-4 /s on energy (B1).
Run: from rest (+-2 deg), SPIN to F_T along DIR for 600 s.
Report per cell: time of the first full turn (and its direction), time to reach F_T (mean rate within 5 %), then over the
last 300 s: mean rate, its spread (per-turn rates), fraction of turns within 5 % / 1 % of F_T, peak speed.
PROPOSED live pass (Molly to set): first turn along DIR; F_T reached; then 300 s with every turn's rate within 5 % and no
safety stop.
"""
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.expanduser('~/Desktop/VSCode/decay_sail_wt_vs/lab_utils'))
sys.path.insert(0, os.path.join(HERE, '..', 'carry_sim_20261111'))
import carry_sim as CS  # noqa: E402

INTAKE, GAMMA = 0.125, 3.5e-4
REST = 208.5
SWITCH = None          # (t, new target Hz): spin-down test
TRAP_SRC = 'assumed'   # or 'coast'
TOL = 0.05             # governor deadband width (live --tol)
COAST = json.load(open(os.path.join(HERE, 'coast_trap.json'))) if os.path.exists(os.path.join(HERE, 'coast_trap.json')) else None


def run(cell, T=600.0, dt=0.002, trace=False):
    import brake_offsets as B
    B.set_map('g1')
    f_t, d, tin, out, f, pscale, C, level, seed, wpm = cell
    rng = np.random.default_rng(seed)
    if TRAP_SRC == 'coast':                         # measured over the full circle from S1's coast (coast_trap.json)
        trapP = tin * np.interp(CS.TH, COAST['theta_deg'], COAST['acc'], period=360.0)
    else:
        trapP = CS.trap_table(tin, out, 0.6, seed)
    trapP = trapP - trapP.mean()      # a static trap does no net work per turn (the stitched table was off by its mean)
    FP = CS.push_tables('G1B2', pscale * (1 + 0.1 * rng.standard_normal(3)))
    x = level / 800.0
    g = (1 - f) * x + f * x * x
    th, w = REST + rng.uniform(-2, 2), 0.0
    tick0 = rng.uniform(0, INTAKE)
    hist, trail, pending = [], [], []
    cmd = np.zeros(3, bool)
    last_write, aborted, reason = -1.0, False, ''
    nfr = int(round(0.02 / dt))
    th0 = th
    t_first, dir_first, t_reach = None, 0, None
    turn_times = []                                # (t, rate) at each completed turn along d
    next_turn = 1
    wmax = 0.0
    rec = {'t': [], 'th': [], 'f': [], 'on': []} if trace else None
    f_mean = 0.0
    for i in range(int(T / dt)):
        t = i * dt
        if i % nfr == 0:
            hist.append((t, th + rng.normal(0, 0.05))); hist = hist[-8:]
            if not trail or t - trail[-1][0] >= 0.1:
                trail.append((t, hist[-1][1]))
            trail = [p for p in trail if t - p[0] <= 30.0]
            f_mean = B.mean_rate(trail, t, hist[-1][1], d)
            if len(hist) >= 3:
                wn = (hist[-1][1] - hist[-3][1]) / (hist[-1][0] - hist[-3][0])
                wmax = max(wmax, abs(wn))
                if not aborted and abs(wn) > 500.0:
                    aborted, reason = True, 'w-cap'; pending = []; cmd = np.zeros(3, bool)
            if not aborted and t - last_write >= INTAKE - 1e-9 and len(hist) >= 5:
                last_write = t
                ft_now = f_t if (SWITCH is None or t < SWITCH[0]) else SWITCH[1]     # optional target change (spin-down test)
                o, _ = B.choose_spin(hist, t, level, d, f_mean, ft_now, TOL, wpm)
                land = math.ceil((t + C - tick0) / INTAKE) * INTAKE + tick0
                if rng.uniform() > 1 / 400:
                    pending.append((land, np.array(o) > 0))
            if trace:
                rec['t'].append(t); rec['th'].append(th); rec['f'].append(f_mean); rec['on'].append(int(cmd.any()))
        while pending and pending[0][0] <= t:
            cmd = pending.pop(0)[1]
        a_f = 0.0
        for q in range(3):
            if cmd[q]:
                a_f += CS.look(FP[q], th) * g
        w += (CS.look(trapP, th) + a_f - 0.5 * GAMMA * w) * dt
        th += math.degrees(w * dt)
        if t_first is None and abs(th - th0) >= 360.0:
            t_first, dir_first = t, int(np.sign(th - th0))
        if d * (th - th0) >= 360.0 * next_turn:
            turn_times.append(t); next_turn += 1
        if t_reach is None and f_mean > 0 and abs(f_mean / f_t - 1) < 0.05 and len(turn_times) >= 2:
            t_reach = t
    tt = np.array(turn_times)
    rates = 1.0 / np.diff(tt) if tt.size >= 2 else np.array([])
    late = rates[tt[1:] > T - 300.0] if rates.size else rates
    r = dict(f_t=f_t, dir=d, tin=tin, out=out, f=f, pscale=pscale, C_ms=round(1e3 * C), level=level, seed=seed, wpm=wpm,
             t_first=t_first, dir_first=dir_first, t_reach=t_reach, n_turns=int(tt.size), aborted=aborted, reason=reason,
             late_mean=float(late.mean()) if late.size else 0.0, late_min=float(late.min()) if late.size else 0.0,
             late_max=float(late.max()) if late.size else 0.0,
             frac5=float(np.mean(np.abs(late / f_t - 1) < 0.05)) if late.size else 0.0,
             frac1=float(np.mean(np.abs(late / f_t - 1) < 0.01)) if late.size else 0.0, wmax=wmax)
    r['ok'] = bool(not aborted and dir_first == d and t_reach is not None and t_reach < T - 300 and late.size > 0
                   and r['frac5'] == 1.0)
    if trace:
        r['trace'] = {k: np.array(v) for k, v in rec.items()}
    return r


def cells():
    out = []
    for f_t in (0.5, 0.75):
        for d in (1, -1):
            for tin, o in ((1.0, 1.0), (1.12, 1.0), (1.0, 1.5), (1.0, 2.0)):
                for f in (0.0, 0.1, 0.2):
                    for ps in (0.75, 1.0, 1.25):
                        for C in (0.015, 0.06):
                            out.append((f_t, d, tin, o, f, ps, C, 1600.0, len(out) % 5, 90.0))
    for f_t in (0.5, 0.75):                              # level and push-speed limit, nominal plant, 2 seeds
        for d in (1, -1):
            for sd in (7, 8):
                for lv in (800.0, 3200.0):
                    out.append((f_t, d, 1.0, 1.0, 0.1, 1.0, 0.015, lv, sd, 90.0))
                for wpm in (60.0, 120.0, 180.0, 240.0):
                    out.append((f_t, d, 1.0, 1.0, 0.1, 1.0, 0.015, 1600.0, sd, wpm))
    return out


def table(rows, keys):
    from itertools import groupby
    rows = sorted(rows, key=lambda r: tuple(r[k] for k in keys))
    L = ['| ' + ' | '.join(keys) + ' | passed | first turn along dir | reached F_T | median t first turn (s) | median t reach (s) | '
         'last 300 s mean (Hz) | worst turn (Hz) | turns within 5 % | peak speed (deg/s) | aborts |',
         '|' + '---|' * (len(keys) + 10)]
    for k, grp in groupby(rows, key=lambda r: tuple(r[k] for k in keys)):
        g = list(grp)
        tf = [r['t_first'] for r in g if r['t_first'] is not None]
        tr = [r['t_reach'] for r in g if r['t_reach'] is not None]
        lm = [r['late_mean'] for r in g if r['late_mean'] > 0]
        worst = max(g, key=lambda r: abs(r['late_min'] / r['f_t'] - 1) if r['late_min'] else 9)
        L.append('| ' + ' | '.join(str(x) for x in k) +
                 f' | {sum(r["ok"] for r in g)}/{len(g)} | {sum(r["dir_first"] == r["dir"] for r in g)}/{len(g)} | '
                 f'{len(tr)}/{len(g)} | {np.median(tf) if tf else float("nan"):.0f} | {np.median(tr) if tr else float("nan"):.0f} | '
                 f'{np.mean(lm) if lm else 0:.3f} | {worst["late_min"]:.3f}-{worst["late_max"]:.3f} | '
                 f'{np.mean([r["frac5"] for r in g]):.2f} | {max(r["wmax"] for r in g):.0f} | {sum(r["aborted"] for r in g)} |')
    return '\n'.join(L)


def main():
    cl = cells()
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(run, cl, chunksize=2))
    json.dump(rows, open(os.path.join(HERE, 'spin_cells.json'), 'w'), indent=0)
    main_rows = [r for r in rows if r['seed'] not in (7, 8)]
    txt = ('\n'.join([f'{len(rows)} cells, 600 s each from rest. Pass (proposed): first turn along dir, target reached '
                      f'before 300 s, then every turn in the last 300 s within 5 %, no abort.\n',
                      '## By target and direction (level 1600)\n', table(main_rows, ['f_t', 'dir']),
                      '\n## By target and trap case\n', table(main_rows, ['f_t', 'tin', 'out']),
                      '\n## By target and push (f, scale)\n', table(main_rows, ['f_t', 'f', 'pscale']),
                      '\n## By target and landing constant\n', table(main_rows, ['f_t', 'C_ms']),
                      '\n## Level and push-speed limit (nominal plant, both directions, 2 seeds)\n',
                      table([r for r in rows if r['seed'] in (7, 8)], ['f_t', 'level', 'wpm'])]))
    print(txt)
    open(os.path.join(HERE, 'spin_summary.md'), 'w').write(txt + '\n')
    plots()


def plots():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    picks = [('0.5 Hz, dir +1, nominal', (0.5, 1, 1.0, 1.0, 0.1, 1.0, 0.015, 1600.0, 0, 90.0)),
             ('0.5 Hz, dir -1, trap outside x2', (0.5, -1, 1.0, 2.0, 0.1, 1.0, 0.015, 1600.0, 0, 90.0)),
             ('0.75 Hz, dir +1, nominal', (0.75, 1, 1.0, 1.0, 0.1, 1.0, 0.015, 1600.0, 0, 90.0))]
    fig, ax = plt.subplots(len(picks), 2, figsize=(15, 3.3 * len(picks)), squeeze=False)
    for k, (lab, c) in enumerate(picks):
        r = run(c, trace=True); tr = r['trace']
        ax[k, 0].plot(tr['t'], (tr['th'] - REST) / 360.0, lw=0.7)
        ax[k, 0].set_ylabel('turns from rest'); ax[k, 0].set_title(f'{lab}: first turn {r["t_first"]}, reached {r["t_reach"]}',
                                                                    fontsize=9)
        ax[k, 1].plot(tr['t'], tr['f'], lw=0.7); ax[k, 1].axhline(c[0], color='r', ls=':')
        ax[k, 1].set_ylabel('mean rate, last turn (Hz)')
        ax[k, 1].set_title(f'last 300 s: {r["late_mean"]:.3f} Hz ({r["late_min"]:.3f}-{r["late_max"]:.3f}); peak '
                           f'{r["wmax"]:.0f} deg/s', fontsize=9)
    for a in ax[-1]:
        a.set_xlabel('s')
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'spin_traces.png'), dpi=90); plt.close(fig)


if __name__ == '__main__':
    main()
