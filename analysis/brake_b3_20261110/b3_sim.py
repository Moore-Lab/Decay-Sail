#!/usr/bin/env python3
"""Gate B3 (Molly OK 2026-11-10): design the brake in simulation with the MEASURED trap and push map (B2). Mac only.

    python3 b3_sim.py            # scan -> b3_summary.md, b3_cells.json, plots/

Plant (all from analysis/brake_b2_20261110/pushmap_b2.json, measured 2026-11-10 on the offset route):
  trap      field-off angular acceleration vs angle, 2 deg table 184-242 deg ('run' joint fit, or the 'post-run' free
            fit; both scanned, each x0.9/1.0/1.1). Leaving 184-242 deg counts as a failure (unmapped).
  push      phase q (A, B, C = V2, V4, V3) at 800 counts: a_q(theta) = F(theta - s_q), F = const + m=8 + m=16 terms,
            s = 0, -16.0, +14.5 deg (shared shape). Scaled by g(v/800) with v the AC-coupled electrode level (tau 5.57 s):
            g = v^2 (torque ~ V^2, assumed in B2) or g = v (linear: the detent runs looked closer to linear); both
            scanned; push strength x0.75/1.0/1.25.
  timing    the controller writes at most 8/s; a write lands on the next 125 ms FE intake after write + c (c unknown:
            0, 30, 60 ms scanned), tick phase random; damping gamma 3.5e-4 /s on energy (B1). Camera 50 fps, 0.05 deg noise.
Brake: every 125 ms, predict (theta, w) at the middle of the hold the write will land in (wait + c_assumed, c_assumed =
30 ms), and switch on the phase (at LEVEL) whose push most opposes w there, if that push is > MIN_PUSH against the motion;
otherwise all off. Safety (live, as in DECISIONS 2026-11-10): field off for good if the swing exceeds 1.2 x the start, or
the angle leaves 190-236 deg.
PASS (proposed, Molly OK 2026-11-10): from the current ~+-22 deg swing, below +-10 deg within 120 s, never above 1.2 x
start, never out of the mapped range, in every cell.
"""
import json
import math
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PM = json.load(open(os.path.join(HERE, '..', 'brake_b2_20261110', 'pushmap_b2.json')))
NODES = np.array(PM['trap_run']['nodes_deg'], float)
TRAPS = {'run': np.array(PM['trap_run']['acc_rad_s2'], float), 'post': np.array(PM['trap_run']['acc_free_post_run'], float)}
SS = PM['shared_shape']
COEF = eval(SS['coef']) if isinstance(SS['coef'], str) else SS['coef']
SHIFT = {0: 0.0, 1: float(SS['s_B_deg']), 2: float(SS['s_C_deg'])}        # A, B, C
TAU_AC, GAMMA, INTAKE = 5.57, 3.5e-4, 0.125
LO, HI = 184.0, 242.0
SAFE = (190.0, 236.0)


def F(th_deg):
    x = np.radians(th_deg)
    return (COEF['const'] + COEF['c8'] * np.cos(8 * x) + COEF['s8'] * np.sin(8 * x)
            + COEF['c16'] * np.cos(16 * x) + COEF['s16'] * np.sin(16 * x))


def push(q, th_deg):
    return F(th_deg - SHIFT[q])


def trap(tab, th_deg):
    return float(np.interp(th_deg, NODES, tab))


def centre(tab):
    """Swing centre: where the trap's potential is lowest over the table (derived)."""
    U = -np.concatenate([[0], np.cumsum(0.5 * (tab[1:] + tab[:-1]) * np.diff(np.radians(NODES)))])
    return float(NODES[np.argmin(U)])


def run(cell, T=120.0, dt=0.002, level=800.0, min_push=0.15, c_assumed=0.030, amp0=22.0, trace=False):
    trapname, tscale, pscale, gname, c, seed, level = cell
    rng = np.random.default_rng(seed)
    tab = TRAPS[trapname] * tscale
    # start at a turning point about the measured swing centre (B2 run: 187-238, centre ~212.5)
    th, w = 212.5 + amp0, 0.0
    tick0 = rng.uniform(0, INTAKE)
    v = np.zeros(3); hp_in = np.zeros(3); hp_out = np.zeros(3); a_hp = TAU_AC / (TAU_AC + dt)
    pending = []; hist = []; last_write = -1.0; aborted = False; out_of_range = False
    cmd_now = np.zeros(3)
    ts, ths, ons = [], [], []
    peak = amp0
    swing_max, swing_min = th, th
    g = (lambda x: x * np.abs(x)) if gname == 'v2' else (lambda x: x)     # sign kept for the linear case
    nfr = int(round(0.02 / dt))
    for i in range(int(T / dt)):
        t = i * dt
        if i % nfr == 0:                                   # camera frame
            hist.append((t, th + rng.normal(0, 0.05)))
            hist = hist[-8:]
            if not aborted and t - last_write >= INTAKE - 1e-9 and len(hist) >= 5:
                last_write = t
                tt = np.array([x[0] for x in hist]) - t; yy = np.array([x[1] for x in hist])
                p2 = np.polyfit(tt, yy, 2)
                th_e, w_e = p2[2], np.radians(p2[1])          # deg, rad/s
                h = c_assumed + INTAKE / 2 + INTAKE / 2        # to the middle of the hold the write lands in
                acc = trap(TRAPS['run'], th_e)                 # controller's own trap (nominal)
                th_p = th_e + np.degrees(w_e * h + 0.5 * acc * h * h); w_p = w_e + acc * h
                best, bq = 0.0, None
                for q in range(3):
                    pw = w_p * push(q, th_p)
                    if pw < best:
                        best, bq = pw, q
                new = np.zeros(3)
                if bq is not None and abs(push(bq, th_p)) > min_push:
                    new[bq] = level
                land = math.ceil((t + c - tick0) / INTAKE) * INTAKE + tick0
                pending.append((land, new))
        while pending and pending[0][0] <= t:
            cmd_now = pending.pop(0)[1]
        hp_out = a_hp * (hp_out + cmd_now - hp_in); hp_in = cmd_now.copy()
        a_f = sum(pscale * push(q, th) * g(hp_out[q] / 800.0) for q in range(3))
        # energy damping gamma -> velocity damping gamma/2
        w += (trap(tab, th) + a_f - 0.5 * GAMMA * w) * dt
        th += math.degrees(w * dt)
        if th < LO or th > HI:
            out_of_range = True
            break
        swing_max = max(swing_max, th); swing_min = min(swing_min, th)
        if i % nfr == 0:
            ts.append(t); ths.append(th); ons.append(cmd_now.any())
            if len(ths) > 200:                                 # running amplitude over the last ~4 s
                amp = (max(ths[-200:]) - min(ths[-200:])) / 2
                peak = max(peak, amp)
                if amp > 1.2 * amp0 or not (SAFE[0] <= th <= SAFE[1]):
                    if not aborted:
                        aborted = True; pending = []; cmd_now = np.zeros(3)
    ts, ths = np.array(ts), np.array(ths)
    end = ts > ts[-1] - 10 if ts.size else np.array([], bool)
    final = float((ths[end].max() - ths[end].min()) / 2) if end.any() else float('nan')
    t10 = next((ts[k] for k in range(200, len(ths)) if (max(ths[k - 200:k]) - min(ths[k - 200:k])) / 2 < 10), None)
    ok = (not out_of_range) and (not aborted) and final < 10 and peak <= 1.2 * amp0
    res = dict(trap=trapname, tscale=tscale, pscale=pscale, g=gname, c_ms=1e3 * c, seed=seed, level=level, final=final,
               peak=peak, t_below10=t10, aborted=aborted, out_of_range=out_of_range, on_frac=float(np.mean(ons)) if ons else 0,
               ok=bool(ok))
    if trace:
        res['t'], res['th'] = ts, ths
    return res


def cells():
    out = []
    for level in (800.0, 1600.0):
        for tr in ('run', 'post'):
            for ts_ in (0.9, 1.0, 1.1):
                for ps in (0.75, 1.0, 1.25):
                    for gn in ('v2', 'lin'):
                        for c in (0.0, 0.03, 0.06):
                            for sd in (0, 1):
                                out.append((tr, ts_, ps, gn, c, sd, level))
    return out


def summarise(rows):
    L = ['| level | g | cells passed | worst final (deg) | aborted | left range | median time to <10 deg (s) | pass by c 0/30/60 ms |',
         '|---|---|---|---|---|---|---|---|']
    for level in (800.0, 1600.0):
        for gn in ('v2', 'lin'):
            rr = [r for r in rows if r['level'] == level and r['g'] == gn]
            t10 = [r['t_below10'] for r in rr if r['t_below10'] is not None]
            byc = ' '.join(f'{sum(r["ok"] for r in rr if abs(r["c_ms"] - c) < 1)}/{sum(1 for r in rr if abs(r["c_ms"] - c) < 1)}'
                           for c in (0, 30, 60))
            L.append(f'| {level:.0f} | {gn} | {sum(r["ok"] for r in rr)}/{len(rr)} | {max(r["final"] for r in rr):.1f} | '
                     f'{sum(r["aborted"] for r in rr)} | {sum(r["out_of_range"] for r in rr)} | '
                     f'{np.median(t10) if t10 else float("nan"):.0f} | {byc} |')
    return '\n'.join(L)


def plots(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig, ax = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for k, level in enumerate((800.0, 1600.0)):
        for cell, col, lab in ((('run', 1.0, 1.0, 'v2', 0.03, 0, level), 'C0', 'nominal (c 30 ms, V^2)'),
                               (None, 'C3', 'worst cell')):
            if cell is None:
                rr = [r for r in rows if r['level'] == level]
                w = max(rr, key=lambda r: (r['out_of_range'] or r['aborted'], r['final']))
                cell = (w['trap'], w['tscale'], w['pscale'], w['g'], w['c_ms'] / 1e3, w['seed'], level)
                lab = f'worst: trap {w["trap"]} x{w["tscale"]}, push x{w["pscale"]}, {w["g"]}, c {w["c_ms"]:.0f} ms'
            r = run(cell, trace=True)
            ax[k].plot(r['t'], r['th'], color=col, lw=0.7, label=lab)
        ax[k].set_ylabel(f'{level:.0f} counts\nangle (deg)'); ax[k].legend(fontsize=8)
    ax[-1].set_xlabel('s')
    fig.suptitle('B3: simulated brake from a +-22 deg swing (measured trap and push map)', fontsize=11)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'b3_traces.png'), dpi=100); plt.close(fig)


def main():
    cl = cells()
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(run, cl, chunksize=4))
    json.dump(rows, open(os.path.join(HERE, 'b3_cells.json'), 'w'), indent=0)
    tab = summarise(rows)
    print(tab)
    open(os.path.join(HERE, 'b3_summary.md'), 'w').write(f'{len(rows)} cells. Pass: < 10 deg in 120 s, never > 1.2x start, '
                                                        f'never out of range, no abort.\n\n' + tab + '\n')
    plots(rows)


if __name__ == '__main__':
    main()
