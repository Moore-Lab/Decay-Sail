#!/usr/bin/env python3
"""Tier 2 (CODE CHANGE to the controller; would need a branch + worker2 test before live use; sim only).
choose_spin_avg: same as brake_offsets.choose_spin (same prediction, same want logic, same min_push) except the
|w_p| < w_push_max gate is replaced by choosing the phase whose push, AVERAGED over the angular span the 125 ms hold
will sweep (th_p +- w_p*INTAKE/2, 9 samples), is largest along the wanted direction. So it can push at any speed.
Usage: VARIANT=avg python3 phaseA.py a1 0.55 grid=...   (phaseA.work picks this up)."""
import math
import numpy as np


def choose_spin_avg(hist, t_now, level, d, f_mean, f_target, tol=0.05, w_push_max=1e9, c_assumed=0.030, min_push=0.15,
                    f_against=0.0, f_rev=0.05, nsamp=9, B=None):
    INTAKE = B.INTAKE
    tt = np.array([h[0] for h in hist]) - t_now; yy = np.array([h[1] for h in hist])
    p2 = np.polyfit(tt, yy, 2)
    th_e, w_e, al = p2[2], p2[1], 2 * p2[0]
    h = c_assumed + INTAKE
    th_p = th_e + w_e * h + 0.5 * al * h * h; w_p = w_e + al * h
    want = 1 if f_mean < f_target * (1 - tol / 2) else (-1 if f_mean > f_target * (1 + tol / 2) else 0)
    if f_against > f_rev:
        want = -1
    out = [0.0, 0.0, 0.0]; bq = None
    if want != 0 and abs(w_p) < w_push_max:
        sgn = d if want > 0 else -math.copysign(1.0, w_p)
        if want > 0 and w_p * d <= 0:
            sgn = 0.0                                  # as the live rule: pump only while moving along d
        if sgn != 0.0:
            span = np.linspace(-0.5, 0.5, nsamp) * w_p * INTAKE
            vals = [sgn * float(np.mean([B.push(q, th_p + s) for s in span])) for q in range(3)]
            bq = int(np.argmax(vals))
            if vals[bq] > min_push:
                out[bq] = level
            else:
                bq = None
    return tuple(out), dict(th=th_e, w_dps=w_e, th_p=th_p, q=-1 if bq is None else bq, want=want)
