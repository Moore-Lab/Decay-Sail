#!/usr/bin/env python3
"""Phase C simulator (own copy of analysis/spinup_spin_20261111/spin_sim.run; sim only, Mac only, no hardware).
Differences from spin_sim.run: (1) field off and stop when the live stop rule fires (B.TurnTimer.on_target, 50 fps frame times),
(2) plant knobs (trap scale, push scale, damping, latency C, trap shift) and controller knobs (f_against span) as arguments,
(3) pluggable controller (variants.py), (4) trace + per-run reversal metrics (rotation-stop, brake end, rest, first turn).
brake_offsets is imported from ~/Desktop/VSCode/decay_sail_wt_vs/lab_utils (identical to branch laser-interleave, diff checked)."""
import json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SPIN = os.path.join(HERE, '..', 'spinup_spin_20261111')
sys.path.insert(0, os.path.expanduser('~/Desktop/VSCode/decay_sail_wt_vs/lab_utils'))
sys.path.insert(0, os.path.join(SPIN, '..', 'carry_sim_20261111'))
import carry_sim as CS  # noqa: E402
import brake_offsets as B  # noqa: E402

REST = 208.5
INTAKE = 0.125
COAST = json.load(open(os.path.join(SPIN, 'coast_trap.json')))
VARIANTS = ((1.0, 0.1, 1.0), (0.9, 0.0, 0.75), (1.1, 0.2, 1.25))     # (trap x, f, push x) as Phase A
DEF = dict(wpm=140.0, level=1600.0, tol=0.1, stop_tol=0.01, stop_n=3, ca=0.030, minp=0.15, f_t=0.5, start_f=0.44,
           span_ag=30.0, variant='live', gamma=3.5e-4, trap_x=1.0, push_x=1.0, C=None, T=300.0, w_cap=500.0, lag_s=0.0, vparams={})


def cells(n=12):
    """Phase A cell list: 3 plant variants x C 15/30 ms x dir +-1 = 12 cells; seed alternating 0/1."""
    out = []
    for d in (1, -1):
        for tin, f, ps in VARIANTS:
            for C in (0.015, 0.03):
                out.append(dict(d=d, tin=tin, f=f, ps=ps, C=C, seed=len(out) % 2))
    return out[:n]


def _turn_time(trapP, w0, gamma, sg, dt=0.004):
    """time for one full turn of a free coast starting at REST with speed w0 (rad/s) in direction sg (+1/-1)"""
    th, w, t = REST, sg * w0, 0.0
    while sg * (th - REST) < 360.0 and t < 40:
        w += (CS.look(trapP, th) - 0.5 * gamma * w) * dt; th += math.degrees(w * dt); t += dt
        if sg * w < 0.05: return 99.0
    return t


def coast_start(trapP, f, gamma, d, u):
    """free coast (no field, same trap) in direction -d whose turn time from REST is 1/f; then advance by phase u of that turn.
    Returns (angle, w rad/s). The speed at the trap bottom is then ~1.3-1.5x the mean rate (the old start used 1.08x)."""
    sg = -d
    lo, hi = 2 * math.pi * f, 2 * math.pi * f * 2.5
    for _ in range(14):
        mid = 0.5 * (lo + hi)
        if _turn_time(trapP, mid, gamma, sg) > 1.0 / f: lo = mid
        else: hi = mid
    w0 = 0.5 * (lo + hi); T = _turn_time(trapP, w0, gamma, sg)
    th, w, t, dt = REST, sg * w0, 0.0, 0.002
    while t < u * T:
        w += (CS.look(trapP, th) - 0.5 * gamma * w) * dt; th += math.degrees(w * dt); t += dt
    return th, w


def run(cell, P, trace=False, dt=0.002):
    P = {**DEF, **P}
    rng = np.random.default_rng(cell['seed'])
    B.set_map('g1')
    d, tin, f, pscale = cell['d'], cell['tin'], cell['f'], cell['ps']
    C = P['C'] if P['C'] is not None else cell['C']
    trapP = P['trap_x'] * tin * np.interp(CS.TH, COAST['theta_deg'], COAST['acc'], period=360.0)
    trapP = trapP - trapP.mean()
    FP = CS.push_tables('G1B2', pscale * P['push_x'] * (1 + 0.1 * rng.standard_normal(3)))
    level = P['level']
    x = level / 800.0
    g = (1 - f) * x + f * x * x
    if P.get('start_mode', 'coast') == 'coast':      # start state = free coast of the same trap at mean rate start_f, random phase
        th, w = coast_start(trapP, P['start_f'], P['gamma'], d, rng.uniform())
    else:
        th, w = REST + rng.uniform(-2, 2), -d * 2 * math.pi * P['start_f'] * 1.08
    tick0 = rng.uniform(0, INTAKE)
    hist, trail, pending = [], [], []
    cmd = np.zeros(3, bool)
    last_write = -1.0
    nfr = int(round(0.02 / dt))
    ext = d * th
    f_mean = f_ag = 0.0
    TT = B.TurnTimer(d)
    field_on = True
    import variants
    ctrl = variants.get(P['variant'], P['vparams'])
    rec = {k: [] for k in ('t', 'th', 'f', 'fa', 'q', 'on')}
    t_stop, reason, kfr = None, 'T', 0
    state = {}
    for i in range(int(P['T'] / dt)):
        t = i * dt
        if i % nfr == 0:
            hist.append((t, th + rng.normal(0, 0.05))); hist = hist[-8:]
            if not trail or t - trail[-1][0] >= 0.1:
                trail.append((t, hist[-1][1]))
            trail = [p for p in trail if t - p[0] <= 30.0]
            f_mean = B.mean_rate(trail, t, hist[-1][1], d)
            f_ag = B.mean_rate(trail, t, hist[-1][1], -d, span=P['span_ag'])
            kfr += 1
            if len(hist) >= 5:
                wf = float(np.polyfit([h[0] for h in hist[-8:]], [h[1] for h in hist[-8:]], 1)[0])
                if abs(wf) > P['w_cap']:
                    reason = 'w-cap'; t_stop = t; break
            TT.add(kfr, hist[-1][1])
            if TT.on_target(P['f_t'], P['stop_tol'], P['stop_n']):
                reason = 'target'; t_stop = t; break
            if t - last_write >= INTAKE - 1e-9 and len(hist) >= 5:
                last_write = t
                o, est = ctrl(hist, t, level, d, f_mean, P['f_t'], P['tol'], P['wpm'], c_assumed=P['ca'], min_push=P['minp'],
                              f_against=f_ag, state=state, trail=trail, w_cap=P['w_cap'])
                land = math.ceil((t + C - tick0) / INTAKE) * INTAKE + tick0
                if rng.uniform() > 1 / 400:
                    pending.append((land, np.array(o) > 0))
                rec['q'].append((t, est.get('q', -1)))
            rec['t'].append(t); rec['th'].append(th); rec['f'].append(f_mean); rec['fa'].append(f_ag); rec['on'].append(int(cmd.any()))
        while pending and pending[0][0] <= t:
            cmd = pending.pop(0)[1]
        a_f = 0.0
        for q in range(3):
            if cmd[q]:
                a_f += CS.look(FP[q], th) * g
        w += (CS.look(trapP, th) + a_f - 0.5 * P['gamma'] * w) * dt
        th += math.degrees(w * dt)
    r = summarize(rec, t_stop, reason, d, P, cell)
    r['rates_stop'] = [float(x) for x in TT.rates[-P['stop_n']:]]
    return r


def summarize(rec, t_stop, reason, d, P, cell):
    t = np.array(rec['t']); th = np.array(rec['th']); fm = np.array(rec['f']); fa = np.array(rec['fa'])
    n = min(len(t), len(th), len(fm), len(fa)); t, th, fm, fa = t[:n], th[:n], fm[:n], fa[:n]
    x = d * th
    wd = np.convolve(d * np.gradient(th, t), np.ones(25) / 25, mode='same')
    neg = np.where(wd < -30)[0]
    iz = int(neg[0] + np.argmax(wd[neg[0]:] > 0)) if neg.size and (wd[neg[0]:] > 0).any() else 0
    big = np.where(fa > 0.05)[0]
    if big.size and (fa[big[0]:] <= 0.05).any():
        ibe = int(big[0] + np.argmax(fa[big[0]:] <= 0.05))
    else:
        ibe = len(t) - 1 if big.size else 0
    base = np.minimum.accumulate(x); ok1 = (x - base >= 360)
    i1 = int(np.argmax(ok1)) if ok1.any() else None
    okr = np.abs(fm / P['f_t'] - 1) < 0.05
    ir = int(np.argmax(okr & (np.arange(n) > (i1 or 0)))) if (okr & (np.arange(n) > (i1 or 0))).any() else None
    ws = np.convolve(np.abs(np.gradient(th, t)), np.ones(50) / 50, mode='same')
    seg = slice(ibe, min(n, ibe + 1000))
    rest_min = float(ws[seg].min()) if ibe < n - 1 else None
    r = dict(cell=cell, t_stop=t_stop, reason=reason, t_rot_stop=float(t[iz]), t_brake_end=float(t[ibe]),
             over_brake=float(t[ibe] - t[iz]), t_first_turn=None if i1 is None else float(t[i1]),
             t_reach=None if ir is None else float(t[ir]), rest_min_w=rest_min,
             hunt=None if (t_stop is None or ir is None) else float(t_stop - t[ir]),
             gap=None if i1 is None else float(t[i1] - t[ibe]), peak_f=float(fm.max()),
             peak_w=float(np.abs(np.gradient(th, t)).max()))
    r['t_stop_s'] = t_stop if reason == 'target' else None
    r['rec'] = dict(t=t[::5], th=th[::5], f=fm[::5], fa=fa[::5])
    return r
