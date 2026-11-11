#!/usr/bin/env python3
"""Gate G2 (spin-up plan): brake from a large swing with the G1 map, in simulation, DC-coupled amp. Mac only.

    python3 g2_sim.py      # -> g2_summary.md, g2_cells.json, plots/g2_traces.png

Controller: the live code itself, brake_offsets.choose() with --map g1 (branch voltage-steps, ~/Desktop/VSCode/
decay_sail_wt_vs/lab_utils), every 125 ms, one phase at LEVEL; live safety as in brake_offsets (field off for good if the
swing over the last 4 s exceeds 1.2 x the start, or the angle leaves 176-258 deg).
Plant (M measured, A assumed):
  trap   M: G1 tables (analysis/spinup_g1_20261111/pushmap_g1.json), 'joint_run' or 'free_post_run', x0.9/1.0/1.1.
         Leaving 172-262 deg counts as a failure (unmapped).
  push   M: G1+B2 shape and shifts at 800 counts. Scaling g(x) = (1 - f) x + f x^2, x = level/800, f = 0 / 0.1 / 0.2
         (0.1 fits G1's 1600/800 ratio). A: DC coupling, so the electrode level equals the command (no 5.57 s decay;
         the DC path's V/count is not yet measured: covered by push x0.75/1.0/1.25).
  timing M: lands on the next 8 Hz intake after write + C, C = 0/30/60 ms; tick phase random; 50 fps, 0.05 deg noise;
         energy damping 3.5e-4 /s (B1).
PASS (proposed, as B3/G2 plan): from +-40 deg, below +-10 deg within 120 s, never above 1.2 x start, never out of range,
in every cell.
"""
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.expanduser('~/Desktop/VSCode/decay_sail_wt_vs/lab_utils'))
G1 = json.load(open(os.path.join(HERE, '..', 'spinup_g1_20261111', 'pushmap_g1.json')))
NODES = np.array(G1['trap']['nodes_deg'], float)
TRAPS = {'run': np.array(G1['trap']['joint_run'], float), 'post': np.array(G1['trap']['free_post_run'], float)}
J = G1['scaling']['G1_plus_B2']
C8, S8, C16, S16, C0 = J['coef']
SHIFT = (0.0, J['s_B_deg'], J['s_C_deg'])
GAMMA, INTAKE = 3.5e-4, 0.125
LO, HI = 172.0, 262.0
SAFE = (176.0, 258.0)
CENTRE = 216.4                      # G1 post-run swing centre (M)


def F(th):
    x = np.radians(th)
    return C0 + C8 * np.cos(8 * x) + S8 * np.sin(8 * x) + C16 * np.cos(16 * x) + S16 * np.sin(16 * x)


def run(cell, T=120.0, dt=0.002, amp0=40.0, trace=False):
    import brake_offsets as B
    B.set_map('g1')
    trapname, tscale, pscale, f, c, seed, level = cell
    rng = np.random.default_rng(seed)
    tab = TRAPS[trapname] * tscale
    th, w = CENTRE + amp0 * (1 if seed % 2 == 0 else -1), 0.0
    tick0 = rng.uniform(0, INTAKE)
    pending, hist = [], []
    cmd = np.zeros(3)
    last_write = -1.0
    aborted = out_of_range = False
    ts, ths = [], []
    peak = amp0
    nfr = int(round(0.02 / dt))
    x = level / 800.0
    g = (1 - f) * x + f * x * x
    for i in range(int(T / dt)):
        t = i * dt
        if i % nfr == 0:
            hist.append((t, th + rng.normal(0, 0.05))); hist = hist[-8:]
            if not aborted and t - last_write >= INTAKE - 1e-9 and len(hist) >= 5:
                last_write = t
                out, _ = B.choose(hist, t, level)
                land = math.ceil((t + c - tick0) / INTAKE) * INTAKE + tick0
                pending.append((land, np.array(out, float) > 0))
        while pending and pending[0][0] <= t:
            cmd = pending.pop(0)[1]
        a_f = sum(pscale * g * F(th - SHIFT[q]) for q in range(3) if cmd[q])
        w += (float(np.interp(th, NODES, tab)) + a_f - 0.5 * GAMMA * w) * dt
        th += math.degrees(w * dt)
        if th < LO or th > HI:
            out_of_range = True
            break
        if i % nfr == 0:
            ts.append(t); ths.append(th)
            if len(ths) > 200:
                amp = (max(ths[-200:]) - min(ths[-200:])) / 2
                peak = max(peak, amp)
                if not aborted and (amp > 1.2 * amp0 or not (SAFE[0] <= th <= SAFE[1])):
                    aborted = True; pending = []; cmd = np.zeros(3, bool)
            elif not aborted and not (SAFE[0] <= th <= SAFE[1]):
                aborted = True; pending = []; cmd = np.zeros(3, bool)
    ts, ths = np.array(ts), np.array(ths)
    end = ts > ts[-1] - 10
    final = float((ths[end].max() - ths[end].min()) / 2) if end.any() else float('nan')
    t10 = next((ts[k] for k in range(200, len(ths)) if (max(ths[k - 200:k]) - min(ths[k - 200:k])) / 2 < 10), None)
    ok = (not out_of_range) and (not aborted) and final < 10 and peak <= 1.2 * amp0
    r = dict(trap=trapname, tscale=tscale, pscale=pscale, f=f, c_ms=round(1e3 * c), seed=seed, level=level, final=final,
             peak=peak, t_below10=t10, aborted=aborted, out_of_range=out_of_range, ok=bool(ok))
    if trace:
        r['t'], r['th'] = ts, ths
    return r


def cells():
    return [(tr, ts, ps, f, c, sd, lv) for lv in (800.0, 1600.0) for tr in ('run', 'post') for ts in (0.9, 1.0, 1.1)
            for ps in (0.75, 1.0, 1.25) for f in (0.0, 0.1, 0.2) for c in (0.0, 0.03, 0.06) for sd in (0, 1)]


def main():
    cl = cells()
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(run, cl, chunksize=4))
    json.dump(rows, open(os.path.join(HERE, 'g2_cells.json'), 'w'), indent=0)
    L = ['| level | f | passed | worst final (deg) | aborted | left range | median t to <10 deg (s) | pass by C 0/30/60 ms |',
         '|---|---|---|---|---|---|---|---|']
    for lv in (800.0, 1600.0):
        for f in (0.0, 0.1, 0.2):
            rr = [r for r in rows if r['level'] == lv and r['f'] == f]
            t10 = [r['t_below10'] for r in rr if r['t_below10'] is not None]
            byc = ' '.join(f'{sum(r["ok"] for r in rr if r["c_ms"] == c)}/{sum(1 for r in rr if r["c_ms"] == c)}' for c in (0, 30, 60))
            L.append(f'| {lv:.0f} | {f} | {sum(r["ok"] for r in rr)}/{len(rr)} | {max(r["final"] for r in rr):.1f} | '
                     f'{sum(r["aborted"] for r in rr)} | {sum(r["out_of_range"] for r in rr)} | '
                     f'{np.median(t10) if t10 else float("nan"):.0f} | {byc} |')
    by = {}
    for r in rows:
        by.setdefault((r['level'], r['trap'], r['tscale'], r['pscale']), []).append(r['ok'])
    fails = [f'{k}: {sum(v)}/{len(v)}' for k, v in sorted(by.items()) if not all(v)]
    txt = (f'{len(rows)} cells, start +-40 deg about {CENTRE}. Pass: < 10 deg in 120 s, never > 1.2x start, never out '
           f'of {SAFE}.\n\n' + '\n'.join(L) + '\n\nGroups (level, trap, trap scale, push scale) with failures:\n'
           + ('\n'.join(fails) if fails else 'none') + '\n')
    print(txt)
    open(os.path.join(HERE, 'g2_summary.md'), 'w').write(txt)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig, ax = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for k, lv in enumerate((800.0, 1600.0)):
        rr = [r for r in rows if r['level'] == lv]
        worst = max(rr, key=lambda r: (not r['ok'], r['final']))
        for c, col, lab in (((('run', 1.0, 1.0, 0.1, 0.03, 0, lv)), 'C0', 'nominal'),
                            (((worst['trap'], worst['tscale'], worst['pscale'], worst['f'], worst['c_ms'] / 1e3, worst['seed'], lv)),
                             'C3', f'worst: {worst["trap"]} x{worst["tscale"]}, push x{worst["pscale"]}, f {worst["f"]}, C {worst["c_ms"]} ms')):
            r = run(c, trace=True)
            ax[k].plot(r['t'], r['th'], color=col, lw=0.6, label=lab)
        ax[k].axhline(SAFE[0], color='grey', ls=':'); ax[k].axhline(SAFE[1], color='grey', ls=':')
        ax[k].set_ylabel(f'{lv:.0f} counts: angle (deg)'); ax[k].legend(fontsize=8)
    ax[-1].set_xlabel('s')
    fig.suptitle('G2 sim: brake from +-40 deg, G1 map, DC-coupled, live control law', fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'g2_traces.png'), dpi=90)


if __name__ == '__main__':
    main()
