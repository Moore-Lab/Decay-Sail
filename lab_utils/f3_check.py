#!/usr/bin/env python3
"""Gate F3 (Molly OK 2026-11-04): spin up from rest, hold a mean rotation rate, brake to rest. Simulator + scorer.

    python3 f3_check.py sim [--push-max 0.3] [--target 0.5] [--amp 4000] [--mtramp 0.0625]   # one simulated run
    python3 f3_check.py score BLOB_LIVE.csv FEEDBACK_LOG.csv [--rest-deg R]                   # a real run
    python3 f3_check.py selftest

Pass mark (Molly 2026-11-04): the rotor goes over the top from rest; then for 60 s every full turn's mean rate
is within 0.5 rev/s +-20 % (0.4..0.6) with no reversal; then the brake brings it back to a swing below 30 deg.

The simulator is EPICS-realistic (assumptions labelled):
  rotor    theta'' = -w0sq sin(theta) - (w0/Q) theta' + drive,  w0sq 4.94 rad/s^2 (F2 1x term, measured;
           the 2x-4x terms, ~15-20 % each, are left out), Q 1e4
  camera   50 fps, 0.3 deg noise (assumed), frame timestamp exact
  writes   at most --rate per s (10, as F2), each landing on the next 1/16 s front-end tick (measured, F1b)
           3 ms after the write (assumed); the matrix then ramps linearly over --mtramp to the new field
  amp      each phase AC-coupled, tau 5.6 s (measured W2 2026-11-03)
  drive    linear-in-V term acc_lin * E * sin(psi_e - psi_r) and V^2 term acc_v2 * E^2 * sin(2 (psi_e - psi_r)),
           psi_r = -8 theta; at amp 5000 F2 measured 1.52 and 1.79 rad/s^2, scaled to --amp (lin ~ V, V^2 ~ V^2).
           With this model the push angles are +90 (accelerate +) and -90 (accelerate -); the real ones (F2 fit)
           are -88 / +167 and are what the live run uses.
"""
import csv
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feedback_drive import SpeedController   # noqa: E402

LO, HI = 0.4, 0.6


def simulate(T_spin=180.0, T_hold=60.0, T_brake=90.0, amp=4000.0, push_max=0.3, target=0.5, mtramp=0.0625,
             rate=10.0, latency=0.07, seed=0, w0sq=4.94, Q=1e4, noise=0.3, tau_ac=5.6, rate0=0.0, brake_only=False,
             ctrl_w0sq=None, brake_wmin=0.0, upd_every=1):
    rng = np.random.default_rng(seed)
    acc_lin = 1.52 * amp / 5000.0
    acc_v2 = 1.79 * (amp / 5000.0) ** 2
    w0 = math.sqrt(w0sq)
    ctrl = SpeedController(target_rev=0.0 if brake_only else target, push_pos=90.0, push_neg=-90.0,
                           w0sq=ctrl_w0sq or w0sq, push_max=push_max, latency=latency + mtramp / 2, sign=-1, m=8,
                           brake_wmin=brake_wmin, rest_deg=0.0)
    dt = 1e-3
    th, om = math.radians(0.5), 0.0
    if rate0:                                     # start rotating with the energy of mean rate rate0 (rev/s), at the bottom
        from feedback_drive import energy_for_rate
        om = math.copysign(math.sqrt(2 * energy_for_rate(abs(rate0), w0sq)), rate0)
    ang = np.radians([0.0, -120.0, -240.0])
    hp_in = np.zeros(3); hp_out = np.zeros(3); a_hp = tau_ac / (tau_ac + dt)
    applied = np.zeros(2); ramp_from = np.zeros(2); ramp_to = np.zeros(2); ramp_t0 = -1.0
    pending = []                                    # (land_time, (x, y))
    last_write = -1.0
    phase = 'brake' if brake_only else 'spin'; t_phase = 0.0; t_over = None
    if brake_only:
        T_spin = T_hold = 0.0
    out_t, out_th, phases = [], [], []
    T = T_spin + T_hold + T_brake
    n = int(T / dt)
    for i in range(n):
        t = i * dt
        # phases: spin-up until rotating steadily (or T_spin), hold, brake
        if phase == 'spin':
            if t_over is None and ctrl.E > 2 * w0sq * 1.02:
                t_over = t
            if (t_over is not None and t - t_over > 20.0) or t > T_spin:
                phase, t_phase = 'hold', t
        elif phase == 'hold' and t - t_phase >= T_hold:
            phase, t_phase = 'brake', t; ctrl.set_target(0.0)
        elif phase == 'brake' and t - t_phase >= T_brake:
            break
        if i % 20 == 0:                              # camera frame
            meas = math.degrees(th) + rng.normal(0, noise)
            psi = ctrl.update(t, meas)
            out_t.append(t); out_th.append(math.degrees(th)); phases.append(phase)
            if t - last_write >= 1.0 / rate - 1e-9:
                last_write = t
                xy = np.zeros(2) if psi is None else np.array([math.cos(math.radians(psi)), math.sin(math.radians(psi))])
                land = math.ceil((t + 0.003) * 16 / upd_every) * upd_every / 16   # upd_every 2: loads only every 2nd tick (pre-flights)
                pending.append((land, xy))
        while pending and pending[0][0] <= t:
            _, xy = pending.pop(0)
            ramp_from = applied.copy(); ramp_to = xy; ramp_t0 = t
        if ramp_t0 >= 0:
            f = 1.0 if mtramp <= 0 else min(1.0, (t - ramp_t0) / mtramp)
            applied = ramp_from + f * (ramp_to - ramp_from)
        x, y = applied
        v_in = x * np.cos(ang) - y * np.sin(ang)
        hp_out = a_hp * (hp_out + v_in - hp_in); hp_in = v_in
        z = np.sum(hp_out * np.exp(-1j * ang)) * 2 / 3
        E = abs(z); psi_e = np.angle(z)
        d = psi_e - (-8 * th)
        tq = acc_lin * E * math.sin(d) + acc_v2 * E * E * math.sin(2 * d)
        om += (-w0sq * math.sin(th) - w0 / Q * om + tq) * dt
        th += om * dt
    return np.array(out_t), np.array(out_th), np.array(phases), t_over


def turns(t, th_deg):
    """Times of completed full turns (crossings of rest + 180 + k*360, i.e. over the top) and their direction."""
    u = (th_deg - 180.0) / 360.0
    k = np.floor(u)
    idx = np.where(np.diff(k) != 0)[0]
    return t[idx + 1], np.sign(np.diff(k)[idx])


def score(t, th, phases, quiet=False):
    """t, th (deg, unwrapped, 0 = rest), phases ('spin'/'hold'/'brake' per sample)."""
    tc, dc = turns(t, th)
    over = tc.size > 0
    hold = phases == 'hold'
    res = dict(over=over)
    if not hold.any():
        if not quiet:
            print('! no hold phase')
        return False, res
    h0, h1 = t[hold][0], t[hold][-1]
    sel = (tc >= h0) & (tc <= h1)
    th_h = tc[sel]; d_h = dc[sel]
    rates = 1.0 / np.diff(th_h) if th_h.size > 1 else np.array([])
    rev = np.any(d_h != d_h[0]) if d_h.size else True
    in_band = rates.size > 0 and np.all((rates >= LO) & (rates <= HI))
    br = phases == 'brake'
    end = t > t[-1] - 10
    final_swing = np.ptp(th[end]) / 2 if br.any() else np.nan
    final_wrapped = np.ptp(((th[end] + 180) % 360) - 180) / 2
    ok = over and in_band and not rev and (final_swing < 30)
    res.update(rates=rates, reversal=rev, final_swing=final_swing, n_turns=th_h.size)
    if not quiet:
        print(f'F3: over the top {over}; hold {h1 - h0:.0f} s: {th_h.size} turns, per-turn rate '
              f'{(rates.min() if rates.size else np.nan):.3f}..{(rates.max() if rates.size else np.nan):.3f} rev/s '
              f'(mean {(rates.mean() if rates.size else np.nan):.3f}), reversal {rev}; after the brake: swing '
              f'+-{final_swing:.1f} deg (wrapped +-{final_wrapped:.1f})')
        print(f'  F3 (mark: over the top; every turn 0.4-0.6 rev/s, no reversal, 60 s; brake to < 30 deg): '
              f'{"PASS" if ok else "not met"}')
    return ok, res


def read_blob(fn):
    rows = list(csv.DictReader(l for l in open(fn) if not l.startswith('#')))
    t = np.array([float(r['host_time']) for r in rows])
    a = np.degrees(np.unwrap(np.radians([float(r['angle_deg']) for r in rows])))
    return t, a


def read_phases(fn, t):
    """Phase per tracker sample from the feedback log's '# phase NAME host_time' lines."""
    marks = []
    for line in open(fn):
        if line.startswith('# phase'):
            _, _, name, ht = line.split()[:4]
            marks.append((float(ht), name))
    ph = np.array(['none'] * t.size, dtype=object)
    for k, (ht, name) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else np.inf
        ph[(t >= ht) & (t < end)] = name
    return ph.astype(str)


def selftest():
    print('-- simulated F3, push only below 0.3 rev/s, matrix ramp 1/16 s, amp 4000:')
    t, th, ph, tov = simulate()
    ok1, _ = score(t, th, ph)
    print(f'   over the top after {tov if tov is None else round(tov, 1)} s')
    print('-- scorer must fail a run that never goes over the top (amp 500):')
    t, th, ph, _ = simulate(amp=500.0, T_spin=60, T_hold=20, T_brake=20)
    ok2, _ = score(t, th, ph)
    good = ok1 and not ok2
    print('SELFTEST', 'PASSED' if good else 'FAILED')
    return 0 if good else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        sys.exit(selftest())
    if len(sys.argv) > 1 and sys.argv[1] == 'sim':
        kw = {}
        for k, typ in (('push-max', float), ('target', float), ('amp', float), ('mtramp', float), ('seed', int)):
            if f'--{k}' in sys.argv:
                v = sys.argv[sys.argv.index(f'--{k}') + 1]
                kw[k.replace('-', '_')] = None if v == 'none' else typ(v)
        t, th, ph, tov = simulate(**kw)
        print(f'over the top after {tov} s')
        score(t, th, ph)
        return
    if len(sys.argv) > 3 and sys.argv[1] == 'score':
        t, a = read_blob(sys.argv[2])
        ph = read_phases(sys.argv[3], t)
        # rest angle: --rest-deg (the tracker's angle at rest, same value given to feedback_drive), else the first
        # 50 frames (only right if the run started from rest)
        if '--rest-deg' in sys.argv:
            r0 = float(sys.argv[sys.argv.index('--rest-deg') + 1])
            rest = r0 + 360.0 * np.round((np.median(a[:50]) - r0) / 360.0)
        else:
            rest = np.median(a[:50])
        ok, _ = score(t, a - rest, ph)
        sys.exit(0 if ok else 1)
    sys.exit(__doc__)


if __name__ == '__main__':
    main()
