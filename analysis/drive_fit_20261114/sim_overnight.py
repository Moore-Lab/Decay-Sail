#!/usr/bin/env python3
"""G1 step 3: simulate the 11-14/15 reversal spin-ups with the plant fitted from that night's logs, and compare with the
live phase times. Then the same with the angle errors removed. Mac only.

    python3 sim_overnight.py      # needs drive_fit.json (corrected-centre fit) -> sim_overnight.json, stdout table

Plant (derived, drive_fit.py 'grid' fit, corrected angles): trap T(theta) (Fourier m <= 24, mean removed), push map per
phase (Fourier m 0/8/16, rad/s^2 at 800 counts, linear in level), damping 1/tau, tau 34 min; writes land on an 8 Hz
grid of random phase and act 10 ms after the tick (measured, drive_fit.py); angle noise 0.05 deg per frame.
Start: rotating at 0.37 Hz against DIR (the coast end speed), random angle. Up to 360 s, as the live runs.
Controller: the live brake_offsets.choose_spin (voltage-steps), level 800, --w-push-max 120, --tol 0.05,
stop on target = 3 consecutive turns within 1 % of 0.5 Hz.
Cases:
  live     the controller sees the angle about the OLD tracker centre (131.03, 178.79): theta + up to +-7 deg, and uses
           the G1 map (as run)
  centre   true angle; controller map shifted by the fitted offsets (-2.50, -2.45, -1.50 deg)
  sync     as centre, and the controller predicts to the actual middle of the hold its write lands in (tick phase
           known) instead of a fixed 155 ms
  *_1600   the same at level 1600
Phase times per run as phases.py (live logs): t_rev (last time moving against DIR), reversed -> 0.45 Hz, 0.45 -> 0.49,
0.49 -> stop; 'stall' = no turn along DIR by 360 s.
"""
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.expanduser('~/Desktop/VSCode/decay_sail_wt_vs/lab_utils'))
sys.path.insert(0, HERE)
import drive_fit as DF  # noqa: E402

TICK, DELTA, TAU = 0.125, 0.010, 34 * 60.0
MAPSHIFT = (-2.50, -2.45, -1.50)
LIVE = {1: dict(rev=70, to45=28, to49=58, stop=17, total=199, n=29, stall=0),      # phases.py, on-target runs; stalls
        -1: dict(rev=31, to45=25, to49=59, stop=30, total=158, n=20, stall=4)}       # from all 30 per direction


def plant():
    o = json.load(open(os.path.join(HERE, 'drive_fit.json')))
    b = np.array(o['grid_b']); nT = 1 + 2 * DF.MT
    th = np.radians(np.arange(0, 360, 0.25))
    T = DF.fourier(th, range(0, DF.MT + 1)) @ b[:nT]
    T = T - T.mean()
    P = np.array([DF.fourier(th, DF.MSET) @ b[nT + 5 * q:nT + 5 * q + 5] for q in range(3)])
    return T, P


def look(tab, th_deg):
    x = (th_deg % 360.0) * 4.0
    i = int(x); f = x - i
    return tab[i % 1440] * (1 - f) + tab[(i + 1) % 1440] * f


def distort(th_deg):
    """Angle the overnight tracker reported (old centre) for a true angle (corrected frame)."""
    ex, ey = DF.SHIFT_PX
    a = math.radians(th_deg)
    return math.degrees(math.atan2(DF.R_PX * math.sin(a) + ey, DF.R_PX * math.cos(a) + ex))


def run(cell):
    import brake_offsets as B
    case, d, seed, T_, P_ = cell
    B.set_map('g1')
    level = 1600.0 if case.endswith('1600') else 800.0
    kind = case.split('_')[0]
    if kind != 'live':
        B.SHIFT = tuple(s + m for s, m in zip(B.SHIFT, MAPSHIFT))
    rng = np.random.default_rng(seed)
    dt = 0.002; nfr = 10
    th = rng.uniform(0, 360); w = -d * 2 * math.pi * 0.37 * 1.08
    tick0 = rng.uniform(0, TICK)
    hist, trail, pending = [], [], []
    cmd = np.zeros(3, bool); last_write = -1.0; u = level / 800.0
    prev_obs = None
    turns = []; ext = d * th; next_turn = 1
    t_last_against = 0.0; stop_t = None
    for i in range(int(360.0 / dt)):
        t = i * dt
        if i % nfr == 0:
            ob = th if kind != 'live' else th + ((distort(th % 360.0) - (th % 360.0) + 180) % 360 - 180)
            ob += rng.normal(0, 0.05)
            if prev_obs is not None:
                ob = prev_obs + ((ob - prev_obs + 180) % 360 - 180)
            prev_obs = ob
            hist.append((t, ob)); hist = hist[-8:]
            if not trail or t - trail[-1][0] >= 0.1:
                trail.append((t, ob))
            trail = [p for p in trail if t - p[0] <= 30.0]
            f_mean = B.mean_rate(trail, t, ob, d); f_ag = B.mean_rate(trail, t, ob, -d)
            if t - last_write >= TICK - 1e-9 and len(hist) >= 5:
                last_write = t
                land = math.ceil((t - tick0) / TICK) * TICK + tick0 + DELTA
                c_ass = 0.030 if kind != 'sync' else (land - t) - TICK / 2 + 0.0   # h = c + TICK -> middle of hold
                o, _ = B.choose_spin(hist, t, level, d, f_mean, 0.5, 0.05, 120.0, c_assumed=c_ass, f_against=f_ag)
                pending.append((land, np.array(o) > 0))
        while pending and pending[0][0] <= t:
            cmd = pending.pop(0)[1]
        a = look(T_, th) - w / TAU
        for q in range(3):
            if cmd[q]:
                a += u * look(P_[q], th)
        w += a * dt
        th += math.degrees(w * dt)
        if w * d < 0:
            t_last_against = t
        ext = min(ext, d * th)
        if d * th - ext >= 360.0 * next_turn:
            turns.append(t); next_turn += 1
        else:
            if d * th - ext < 360.0 * (next_turn - 1) - 1e-9:           # went back: restart counting from new extreme
                pass
        if len(turns) >= 4 and stop_t is None:
            r = 1.0 / np.diff(turns[-4:])
            if np.all(np.abs(r / 0.5 - 1) < 0.01):
                stop_t = t
                break
    tt = np.array(turns); rates = 1.0 / np.diff(tt) if tt.size >= 2 else np.array([])
    def first(x):
        k = np.where(rates >= x)[0]
        return float(tt[k[0] + 1]) if k.size else None
    return dict(case=case, dir=d, seed=seed, t_rev=t_last_against, t45=first(0.45), t49=first(0.49), t48=first(0.48),
                stop=stop_t, stall=len(turns) == 0, n_turns=len(turns))


def main():
    T_, P_ = plant()
    cases = ['live', 'centre', 'sync', 'centre_1600', 'sync_1600']
    cells = [(c, d, s, T_, P_) for c in cases for d in (1, -1) for s in range(24)]
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(run, cells, chunksize=4))
    print('median s (live logs in brackets for the "live" case) | reached 0.48 Hz | stop on target | stalls')
    out = {}
    for c in cases:
        for d in (1, -1):
            R = [r for r in rows if r['case'] == c and r['dir'] == d]
            ok = [r for r in R if r['stop'] is not None and r['t45'] is not None]
            med = lambda k: float(np.median([r[k] for r in ok])) if ok else float('nan')
            rev = med('t_rev'); t45 = med('t45'); t49 = med('t49'); st = med('stop')
            t48 = [r['t48'] for r in R if r['t48'] is not None]
            L = LIVE[d]
            extra = (f'  [live {L["rev"]} / {L["to45"]} / {L["to49"]} / {L["stop"]} / {L["total"]}, stalls {L["stall"]}/30]'
                     if c == 'live' else '')
            print(f'{c:12s} {d:+d}: rev {rev:5.0f}  ->0.45 {t45 - rev:4.0f}  0.45->0.49 {t49 - t45:4.0f}  ->stop {st - t49:4.0f}  '
                  f'total {st:5.0f} | 0.48 Hz by median {np.median(t48) if t48 else float("nan"):4.0f} s ({len(t48)}/{len(R)}) | '
                  f'stop {len(ok)}/{len(R)} | stalls {sum(r["stall"] for r in R)}' + extra)
            out[f'{c} {d:+d}'] = dict(rev=rev, t45=t45, t49=t49, stop=st, t48_median=float(np.median(t48)) if t48 else None,
                                      n_t48=len(t48), n_stop=len(ok), n=len(R), stalls=int(sum(r['stall'] for r in R)))
    json.dump(dict(summary=out, rows=rows), open(os.path.join(HERE, 'sim_overnight.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
