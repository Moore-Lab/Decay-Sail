#!/usr/bin/env python3
"""Stage-1 carry (directive: 0.01-0.05 Hz for 5 min, both directions) in simulation, with the measured trap and push map
(G1 + B2). Mac only, nothing live. Molly OK 2026-11-11.

    python3 carry_sim.py           # gain scan, then the robustness scan -> carry_summary.md, carry_cells.json, plots/
    python3 carry_sim.py --quick   # nominal cells only

PLANT (labels: M measured, D derived, A assumed)
  trap     M: G1 joint-run table (analysis/spinup_g1_20261111/pushmap_g1.json), trusted over 180-254 deg (frames on both
           sides of each node), blended to the outside model over 172-180 and 254-262.
           A: outside that, a = -k sin(theta - theta0) with k, theta0 fitted to 176-256 deg (k ~ 4.4 rad/s^2), scaled by
           OUT = 1, 1.5, 2 (the barrier was never reached, B1), plus a random m = 8/16 ripple of rms 0.6 rad/s^2.
           Inside scaled by TIN = 1 or 1.12 (B1's slope was 12 % above G1's: day-to-day spread, M).
  push     M: a_q = A_q F(theta - s_q) [(1 - f) x + f x^2], x = v_q / 800, v_q the electrode level (AC-coupled, tau 5.57 s,
           M S1). F, s from the G1+B2 joint fit (or B2's own, as an alternative shape).
           D/A: f = 0.1 reproduces the measured 1600/800 ratio 2.19 (f = 0 -> 2.0, f = 0.2 -> 2.4, both inside the 68 %
           range 1.93-2.45). The f x^2 part is taken unsigned (a V^2 force does not reverse with V) and with the same
           shape F (A). Linear sign reversal at negative counts is ASSUMED (amp bipolar, M Aug 2026; push at negative
           counts never measured). Extrapolation from 1600 to 12800 counts is A.
           A_q = AMP x (1 + 0.1 N(0,1)) per phase (per-phase G1 fits scatter by more, but are noisy).
  timing   M: writes land on the 8 Hz intake grid locked to the GPS second, plus a constant C (G1: 15 ms). C = 15 ms
           (lands on the tick the controller aims for) or 60 ms (always misses it: one tick late, 125 ms). 1 in 400
           updates lost (M, field test). Camera 50 fps, 0.05 deg noise. Energy damping 3.5e-4 /s (M, B1).
CONTROLLER (what the live code would do)
  Every 125 ms, 50 ms before an intake tick: quadratic fit to the last 8 frames -> (theta, w); predict with its own
  nominal model (trap measured + k-sinusoid outside, OUT = 1; push G1+B2, f = 0.1) to the middle of the hold the write
  lands in (assumes C = 15 ms); desired acceleration = -trap + reference acceleration + PID on the reference
  (theta_ref ramps from rest at 212.5 deg to the set speed in 15 s, then holds); choose the three commands with the
  commands nearest the pedestal PED that give it (Newton on the nominal push model), within 0 <= command <= 12800
  (amp input must be 0-2.1 V, CLAUDE.md). The electrode goes negative only through the AC coupling (level = command -
  its 5.57 s low-pass), so a pedestal (6400; 3200, 9600 scanned) is assumed set slowly beforehand (that step is not
  simulated) and the electrode swing is about +-PED.
  Safety (live): field off for good if |theta - theta_ref| > 30 deg (counts as a slip).
PASS (proposed): after the ramp, 300 s at the set speed with |theta - theta_ref| < 15 deg throughout, no abort.
"""
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
G1 = json.load(open(os.path.join(HERE, '..', 'spinup_g1_20261111', 'pushmap_g1.json')))
B2 = json.load(open(os.path.join(HERE, '..', 'brake_b2_20261110', 'pushmap_b2.json')))

TAU_AC, GAMMA, INTAKE, VPC = 5.57, 3.5e-4, 0.125, 0.0124   # s, 1/s, s, V/count (S1, first instant)
REST = 212.5
DT = 0.004
CTRL_F, AMP_NOISE, RIPPLE, NOISE_DEG = 0.1, 0.1, 0.6, 0.05     # test switches (module level)
GRID = 0.1                                                   # deg, lookup tables 0..360
TH = np.arange(0, 360, GRID)
NG = TH.size

# ---------------- trap ----------------
_nodes = np.array(G1['trap']['nodes_deg'], float)
_acc = np.array(G1['trap']['joint_run'], float)


def _fit_sin():
    m = (_nodes >= 176) & (_nodes <= 256)
    x = np.radians(_nodes[m])
    A = np.c_[np.sin(x), np.cos(x)]
    (p, q), *_ = np.linalg.lstsq(A, _acc[m], rcond=None)        # a = p sin x + q cos x = -k sin(x - x0)
    k = math.hypot(p, q)
    x0 = math.atan2(q, -p)                                       # -k sin(x - x0) = -k cos x0 sin x + k sin x0 cos x
    return k, math.degrees(x0) % 360


K_SIN, TH0_SIN = _fit_sin()


def _wrapd(d):
    return (d + 180.0) % 360.0 - 180.0


def trap_table(tin=1.0, out=1.0, ripple_rms=0.0, seed=0):
    meas = np.interp(TH, _nodes, _acc)
    outside = -K_SIN * np.sin(np.radians(TH - TH0_SIN)) * out
    if ripple_rms > 0:
        r = np.random.default_rng(1000 + seed)
        rip = sum(c * np.cos(m * np.radians(TH) + r.uniform(0, 2 * np.pi)) for m, c in ((8, 1.0), (16, 1.0)))
        outside = outside + rip * ripple_rms / np.std(rip)
    w = np.clip(np.minimum(TH - 172.0, 262.0 - TH) / 8.0, 0, 1)     # 1 inside 180-254, 0 outside 172-262
    return w * tin * meas + (1 - w) * outside


# ---------------- push ----------------
def _shape(name):
    if name == 'G1B2':
        J = G1['scaling']['G1_plus_B2']
        return list(J['coef']), [0.0, J['s_B_deg'], J['s_C_deg']]
    s = B2['shared_shape']
    c = eval(s['coef']) if isinstance(s['coef'], str) else s['coef']
    return [c['c8'], c['s8'], c['c16'], c['s16'], c['const']], [0.0, float(s['s_B_deg']), float(s['s_C_deg'])]


def push_tables(shape='G1B2', amps=(1.0, 1.0, 1.0)):
    c, sh = _shape(shape)
    out = np.empty((3, NG))
    for q in range(3):
        x = np.radians(TH - sh[q])
        out[q] = amps[q] * (c[0] * np.cos(8 * x) + c[1] * np.sin(8 * x) + c[2] * np.cos(16 * x) + c[3] * np.sin(16 * x) + c[4])
    return out


def look(tab, th):
    i = int(round((th % 360.0) / GRID)) % NG
    return tab[i]


# ---------------- one run ----------------
def run(cell, trace=False):
    (speed, direction, tin, out, f, amp, shape, C, lim, gains, seed, ped) = cell
    rng = np.random.default_rng(seed)
    trapP = trap_table(tin, out, RIPPLE, seed)
    ampq = amp * (1 + AMP_NOISE * rng.standard_normal(3))
    FP = push_tables(shape, ampq)
    trapN = trap_table(1.0, 1.0, 0.0)
    FN = push_tables('G1B2')
    fN = CTRL_F
    wn, zeta, ki_frac = gains
    Kp, Kd, Ki = wn * wn, 2 * zeta * wn, ki_frac * wn ** 3
    T_ramp, t_start, T_hold = 15.0, 2.0, 300.0
    T = t_start + T_ramp + T_hold
    w_set = direction * 2 * math.pi * speed                      # rad/s

    def ref(t):                                                  # theta_ref (deg), w_ref, alpha_ref (rad)
        if t < t_start:
            return REST, 0.0, 0.0
        s = t - t_start
        if s < T_ramp:
            al = w_set / T_ramp
            return REST + math.degrees(0.5 * al * s * s), al * s, al
        return REST + math.degrees(w_set * (s - 0.5 * T_ramp)), w_set, 0.0

    tick0 = rng.uniform(0, INTAKE)                               # GPS grid phase vs sim t = 0 (controller knows it)
    th, w = REST + rng.normal(0, 0.3), 0.0
    # pedestal applied (slowly) long before: command = low-pass state = ped, electrode level 0
    cmd_now = np.full(3, ped)                                    # applied command (plant)
    Lp = np.full(3, ped)                                         # plant low-pass state (electrode = cmd - Lp)
    Lc = np.full(3, ped)                                         # controller's copy (believes every write landed)
    cmd_ctrl_applied = np.full(3, ped)
    pending = []
    hist_t, hist_y = [], []
    integ = 0.0
    aborted = False
    err_max_hold, err_max = 0.0, 0.0
    vmax, cmdmax, stepmax = 0.0, 0.0, 0.0
    sat_n = upd_n = 0
    nfr = int(round(0.02 / DT))
    next_write = tick0 + INTAKE - 0.050
    while next_write < 0:
        next_write += INTAKE
    rec = {k: [] for k in ('t', 'th', 'ref', 'v0', 'v1', 'v2', 'c0', 'c1', 'c2')} if trace else None
    nsteps = int(T / DT)
    dec = math.exp(-DT / TAU_AC)
    for i in range(nsteps):
        t = i * DT
        if i % nfr == 0:
            hist_t.append(t); hist_y.append(th + rng.normal(0, NOISE_DEG))
            if len(hist_t) > 8:
                hist_t.pop(0); hist_y.pop(0)
        if not aborted and t >= next_write - 1e-9 and len(hist_t) >= 6:
            next_write += INTAKE
            tt = np.array(hist_t) - t
            p2 = np.polyfit(tt, np.array(hist_y), 2)
            th_e, w_e = p2[2], math.radians(p2[1])
            # controller's landing estimate: next tick after t + 15 ms
            land_c = tick0 + math.ceil((t + 0.015 - tick0) / INTAKE) * INTAKE
            tmid = land_c + INTAKE / 2
            # predict with the nominal model; the field currently commanded stays until the landing
            thp, wp, tp = th_e, w_e, t
            Lpred = Lc.copy()
            hstep = 0.01
            while tp < tmid - 1e-9:
                hs = min(hstep, tmid - tp)
                ccur = cmd_ctrl_applied if tp < land_c else None
                if ccur is None:
                    break
                v = ccur - Lpred
                x = v / 800.0
                af = sum(look(FN[q], thp) * ((1 - fN) * x[q] + fN * x[q] * x[q]) for q in range(3))
                a = look(trapN, thp) + af
                wp += a * hs; thp += math.degrees(wp * hs); tp += hs
                Lpred += (ccur - Lpred) * (hs / TAU_AC)
            # from landing to mid-hold the new command sets the motion; it is chosen so that the net acceleration is
            # the reference's, so advance with that (the trap alone here biased the speed by trap x 62 ms).
            if tp < tmid:
                hs = tmid - tp
                a = ref(tp)[2]
                thp += math.degrees(wp * hs + 0.5 * a * hs * hs); wp += a * hs
            Lland = Lpred
            r_dec = math.exp(-INTAKE / 2 / TAU_AC)
            thr, wr, alr = ref(tmid)
            e = _wrapd(thr - thp) if abs(thr - thp) < 180 else thr - thp
            e_rad = math.radians(thr - thp)
            if t > t_start:
                integ += e_rad * INTAKE
                integ = max(-0.5, min(0.5, integ))
            a_des = -look(trapN, thp) + alr + Kp * e_rad + Kd * (wr - wp) + Ki * integ
            # allocation: min |cmd|^2 s.t. sum F_q g(v_q) = a_des, v = r (cmd - Lland)
            Fq = np.array([look(FN[q], thp) for q in range(3)])
            lo = np.zeros(3); hi = np.full(3, lim)                 # amp input 0..2.1 V = 0..12800 counts (CLAUDE.md)
            if fN > 0:                                             # keep each level where (1-f)x + f x^2 still rises
                lo = np.maximum(lo, Lland - 800.0 * (1 - fN) / (2 * fN) / r_dec)
            cmd = np.clip(Lland.copy(), lo, hi)
            for _ in range(8):
                v = r_dec * (cmd - Lland); x = v / 800.0
                gval = float(np.sum(Fq * ((1 - fN) * x + fN * x * x)))
                J = Fq * ((1 - fN) + 2 * fN * x) * r_dec / 800.0
                JJ = float(J @ J)
                if JJ < 1e-14:
                    break
                resid = a_des - gval
                new = ped + J * (resid + float(J @ (cmd - ped))) / JJ      # nearest to the pedestal
                cmd = np.clip(new, lo, hi)
            sat = bool(np.any(np.isclose(cmd, lo, atol=1)) or np.any(np.isclose(cmd, hi, atol=1)))
            sat_n += sat; upd_n += 1
            cmd = np.round(cmd)
            stepmax = max(stepmax, float(np.max(np.abs(cmd - cmd_ctrl_applied))))
            cmdmax = max(cmdmax, float(np.max(np.abs(cmd))))
            # controller bookkeeping: its low-pass copy runs on what it wrote
            land_p = tick0 + math.ceil((t + C - tick0) / INTAKE) * INTAKE
            if rng.uniform() > 1 / 400:
                pending.append((land_p, cmd.copy()))
            cmd_ctrl_applied = cmd.copy()
        # controller low-pass copy advances in time with its own idea of the applied command (from its landing guess)
        Lc += (cmd_ctrl_applied - Lc) * (DT / TAU_AC) if t >= tick0 else 0.0
        while pending and pending[0][0] <= t:
            cmd_now = pending.pop(0)[1]
        Lp = cmd_now + (Lp - cmd_now) * dec
        v = cmd_now - Lp
        vmax = max(vmax, float(np.max(np.abs(v))))
        x = v / 800.0
        a_f = 0.0
        for q in range(3):
            a_f += look(FP[q], th) * ((1 - f) * x[q] + f * x[q] * x[q])
        w += (look(trapP, th) + a_f - 0.5 * GAMMA * w) * DT
        th += math.degrees(w * DT)
        thr, _, _ = ref(t)
        err = abs(th - thr)
        err_max = max(err_max, err)
        if t > t_start:
            err_max_hold = max(err_max_hold, err)
        if not aborted and err > 30.0:
            aborted = True
            pending = []; cmd_now = np.full(3, ped); cmd_ctrl_applied = np.full(3, ped)   # live: hold, then ramp down slowly
            t_abort = t
        if trace and i % nfr == 0:
            rec['t'].append(t); rec['th'].append(th); rec['ref'].append(thr)
            for q in range(3):
                rec[f'v{q}'].append(v[q]); rec[f'c{q}'].append(cmd_now[q])
        if aborted and not trace:
            break
    ok = (not aborted) and err_max_hold < 15.0
    res = dict(ped=ped, speed=speed, dir=direction, tin=tin, out=out, f=f, amp=amp, shape=shape, C_ms=round(1e3 * C), lim=lim,
               wn=wn, zeta=zeta, ki=ki_frac, seed=seed, ok=bool(ok), aborted=aborted,
               t_abort=(t_abort if aborted else None), err_max=err_max_hold, vmax=vmax, cmdmax=cmdmax, stepmax=stepmax,
               sat_frac=sat_n / max(upd_n, 1), turns=abs(th - REST) / 360.0, Vmax_volts=vmax * VPC)
    if trace:
        res['trace'] = {k: np.array(v_) for k, v_ in rec.items()}
    return res


# ---------------- scans ----------------
NOMINAL = dict(tin=1.0, out=1.0, f=0.1, amp=1.0, shape='G1B2', C=0.015, lim=12800.0, ped=6400.0)
GAINS = [(1.5, 0.8, 0.1), (2.5, 0.8, 0.1), (4.0, 0.8, 0.1), (2.5, 0.8, 0.0)]


def cell(speed, d, g, seed=0, **kw):
    p = dict(NOMINAL); p.update(kw)
    return (speed, d, p['tin'], p['out'], p['f'], p['amp'], p['shape'], p['C'], p['lim'], g, seed, p['ped'])


def gain_cells():
    out = []
    for g in GAINS:
        for speed in (0.02, 0.05):
            for d in (1, -1):
                for kw in ({}, dict(out=1.5), dict(f=0.2, amp=0.8), dict(C=0.06)):
                    out.append(cell(speed, d, g, **kw))
    return out


def robust_cells(g):
    out = []
    for speed in (0.02, 0.05, 0.2):
        for d in (1, -1):
            for tin, o in ((1.0, 1.0), (1.12, 1.0), (1.0, 1.5), (1.0, 2.0)):
                for f in (0.0, 0.1, 0.2):
                    for amp in (0.8, 1.0, 1.2):
                        for shape in ('G1B2', 'B2'):
                            for C in (0.015, 0.06):
                                out.append(cell(speed, d, g, seed=len(out) % 3, tin=tin, out=o, f=f, amp=amp,
                                                shape=shape, C=C))
    for speed in (0.02, 0.05):                       # pedestal choice, nominal plant
        for d in (1, -1):
            for o in (1.0, 1.5):
                for ped in (3200.0, 9600.0):
                    out.append(cell(speed, d, g, out=o, ped=ped))
    return out


def table(rows, keys):
    from itertools import groupby
    rows = sorted(rows, key=lambda r: tuple(r[k] for k in keys))
    L = ['| ' + ' | '.join(keys) + ' | passed | worst err (deg) | aborts | max electrode (V) | max step (counts) | sat. frac (median) |',
         '|' + '---|' * (len(keys) + 6)]
    for k, grp in groupby(rows, key=lambda r: tuple(r[k] for k in keys)):
        g = list(grp)
        L.append('| ' + ' | '.join(str(x) for x in k) +
                 f' | {sum(r["ok"] for r in g)}/{len(g)} | {max(r["err_max"] for r in g):.1f} | {sum(r["aborted"] for r in g)} | '
                 f'{max(r["Vmax_volts"] for r in g):.0f} | {max(r["stepmax"] for r in g):.0f} | '
                 f'{np.median([r["sat_frac"] for r in g]):.2f} |')
    return '\n'.join(L)


def plots(g, rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    picks = [('nominal 0.02 Hz +', cell(0.02, 1, g)), ('nominal 0.05 Hz -', cell(0.05, -1, g))]
    bad = [r for r in rows if r['speed'] in (0.02, 0.05) and not r['ok']]
    if bad:
        w = max(bad, key=lambda r: (r['out'], r['err_max']))
        picks.append((f'failing: {w["speed"]} Hz dir {w["dir"]}, trap in x{w["tin"]} out x{w["out"]}, f {w["f"]}, '
                      f'amp {w["amp"]}, {w["shape"]}, C {w["C_ms"]} ms',
                      cell(w['speed'], w['dir'], g, seed=w['seed'], tin=w['tin'], out=w['out'], f=w['f'], amp=w['amp'],
                           shape=w['shape'], C=w['C_ms'] / 1e3)))
    fig, ax = plt.subplots(len(picks), 2, figsize=(15, 3.4 * len(picks)), squeeze=False)
    for k, (lab, c) in enumerate(picks):
        r = run(c, trace=True); tr = r['trace']
        ax[k, 0].plot(tr['t'], tr['th'] - tr['ref'], lw=0.6)
        ax[k, 0].set_ylabel('theta - ref (deg)'); ax[k, 0].set_title(lab, fontsize=9)
        ax[k, 0].axhline(15, color='r', lw=0.5, ls=':'); ax[k, 0].axhline(-15, color='r', lw=0.5, ls=':')
        for q, col in enumerate(('C0', 'C1', 'C2')):
            ax[k, 1].plot(tr['t'], tr[f'v{q}'] * VPC, color=col, lw=0.5, label='ABC'[q] + ' electrode')
        ax[k, 1].set_ylabel('electrode (V, 0.0124 V/count)'); ax[k, 1].legend(fontsize=7, loc='upper right')
        ax[k, 1].set_title(f'max |electrode| {r["Vmax_volts"]:.0f} V, saturated {100 * r["sat_frac"]:.0f} % of updates',
                           fontsize=9)
    for a in ax[-1]:
        a.set_xlabel('s')
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'carry_traces.png'), dpi=90); plt.close(fig)

    # static capability vs trap
    trN = trap_table(); F = push_tables()
    fig, ax = plt.subplots(figsize=(12, 4))
    for o in (1.0, 1.5, 2.0):
        ax.plot(TH, np.abs(trap_table(1.0, o)), lw=0.8, label=f'|trap|, outside x{o} (A outside 172-262)')
    for sw in (6400, 12800):
        ax.plot(TH, np.abs(F).sum(0) * sw / 800, '--', lw=1, label=f'push capacity if linear, all 3 at +-{sw} counts')
    ax.axvspan(172, 262, color='grey', alpha=0.1)
    ax.set_xlabel('theta (deg)'); ax.set_ylabel('rad/s^2'); ax.legend(fontsize=7); ax.set_xlim(0, 360)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'carry_capacity.png'), dpi=90); plt.close(fig)


def main():
    quick = '--quick' in sys.argv
    print(f'trap outside model: k {K_SIN:.2f} rad/s^2, zero {TH0_SIN:.1f} deg')
    with ProcessPoolExecutor() as ex:
        gr = list(ex.map(run, gain_cells(), chunksize=1))
    gt = table(gr, ['wn', 'ki', 'speed'])
    print(gt)
    score = {}
    for r in gr:
        k = (r['wn'], r['zeta'], r['ki'])
        score.setdefault(k, []).append((r['ok'], -r['err_max']))
    best = max(score, key=lambda k: (sum(s[0] for s in score[k]), sum(s[1] for s in score[k])))
    print('chosen gains (wn, zeta, ki):', best)
    if quick:
        return
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(run, robust_cells(best), chunksize=2))
    json.dump(dict(gain_scan=gr, chosen=best, cells=rows, k_sin=K_SIN, th0_sin=TH0_SIN),
              open(os.path.join(HERE, 'carry_cells.json'), 'w'), indent=0)
    main_rows = [r for r in rows if r['ped'] == 6400.0]
    parts = [f'Trap outside model (A): k {K_SIN:.2f} rad/s^2, zero {TH0_SIN:.1f} deg.\n',
             '## Gain scan (nominal-ish cells)\n', gt,
             f'\nChosen (wn rad/s, zeta, ki fraction): {best}\n',
             '## By speed, direction (LIM 12800)\n', table(main_rows, ['speed', 'dir']),
             '\n## By speed and trap case\n', table(main_rows, ['speed', 'tin', 'out']),
             '\n## By speed and push scaling (f = V^2 fraction at 800 counts; amp)\n', table(main_rows, ['speed', 'f', 'amp']),
             '\n## By speed, shape, landing constant\n', table(main_rows, ['speed', 'shape', 'C_ms']),
             '\n## Pedestal (nominal plant otherwise)\n', table([r for r in rows if r['ped'] != 6400.0 or (r['tin'], r['out'], r['f'], r['amp'], r['shape'], r['C_ms']) in ((1.0, 1.0, 0.1, 1.0, 'G1B2', 15), (1.0, 1.5, 0.1, 1.0, 'G1B2', 15))], ['speed', 'out', 'ped'])]
    txt = '\n'.join(parts)
    print(txt)
    open(os.path.join(HERE, 'carry_summary.md'), 'w').write(txt + '\n')
    plots(best, rows)


if __name__ == '__main__':
    main()
