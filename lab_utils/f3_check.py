#!/usr/bin/env python3
"""Gate F3 (Molly OK 2026-11-04): spin up from rest, hold a mean rotation rate, brake to rest. Simulator + scorer.

    python3 f3_check.py sim [--push-max 0.3] [--target 0.5] [--amp 4000] [--mtramp 0.0625]   # one simulated run
    python3 f3_check.py score BLOB_LIVE.csv FEEDBACK_LOG.csv [--rest-deg R]                   # a real run
    python3 f3_check.py selftest
    python3 f3_check.py repro [--coupling hold|010]                                           # brake-only 1, measured model

repro (2026-11-04 evening): simulate_measured() = joint-fit trap (TRAP_CU) + a fitted coupling + loads every 2nd
1/16 s tick, with brake-only 1's live controller settings, from brake 1's start state. Open-loop checks of the same
plant against the measured field: ../analysis/f3_20261104/outdq_replay.py (main).

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


# ------------------------------------------------------------- measured-model simulator (2026-11-04 evening)
# All from today's data, analysis/f3_20261104/push_angles.py (main):
#  TRAP_CU: U(phi) - const (rad^2/s^2 per unit I), phi = angle from rest (229.8), harmonics 1..4 as
#           [c0, cos1, sin1, cos2, sin2, ...]. Joint fit (2026-11-04 evening) of the two field-off data sets:
#           live-2 coasting (U from energy per turn, 5 deg bins; residual 0.27 rms) and brake-1's free swing in
#           the 11 s before its loop (energy a free parameter; spread along the swing 0.11 rad^2/s^2, vs ~0.35
#           with the live-2-only fit). Barrier 9.61 at -160 deg. The live-2-only fit (push_angles.py cU)
#           put the + turning point of brake-1's swing ~10 deg past the measured +144.
#  COUPLING_010: residual angular acceleration (rad/s^2) at amp 4000 vs D = psi_field + 8*theta_abs (deg),
#           fitted as [c0, cos D, sin D, cos 2D, sin 2D] with the command delayed by 0.10 s (R^2 0.63, 1097
#           field-on frames of live 2 + brake 1). Applied here to the SIMULATED field angle, whose own lag
#           (loads every 2nd 1/16 s tick + the 1/16 s matrix ramp) makes up the 0.10 s (derived: mean wait for
#           an even tick 62.5 ms + half ramp 31 ms + write ~4 ms = 0.098 s). c0 (-0.53) is kept, scaled by
#           the field size; it is a fit term, not understood.
TRAP_CU = [4.9151, -4.5469, -0.7612, -0.0749, 0.4721, -0.0949, 0.0676, -0.0822, 0.0597]
COUPLING_010 = [-0.533, 2.211, -1.754, -0.573, -0.491]
#  COUPLING_HOLD (2026-11-04 evening, analysis/f3_20261104/outdq_replay.py): fitted per constant-field hold
#           (~125 ms) against the MEASURED field (OUT_DQ, aligned by command matching + 0.075 s, the shift
#           that maximises the fit): dw - int(trap) = int(coupling) dt. Live 2, 146 holds, R^2 0.41; held-out
#           brake 1, 20 holds, R^2 0.38. A c0 term adds nothing (R^2 0.42, c0 -0.8), so it is 0. The
#           commanded-angle fit above underestimates the 2x term: the acceleration is smoothed over 0.42 s
#           while the field steps every 125 ms.
COUPLING_HOLD = [0.0, 2.42, -1.05, -1.73, 0.25]
REST_F3 = 229.8
# brake-only 1 (21:01Z 11-04, FE 1477876900): state at loop start. phi +55 deg (tracker, measured); w set so the
# energy is the free swing's 7.92 rad^2/s^2 (joint fit; 0.82 of the barrier). The tracker's savgol w there is
# -205 deg/s; that reads 0.5 high in energy, about the trap model's error at +55.
BRAKE1_START = dict(phi0=55.0, w0=-194.3)


def trap_acc(phi_deg, cU=TRAP_CU):
    """-dU/dphi (rad/s^2) at phi deg from rest."""
    r = math.radians(phi_deg); out = 0.0
    for n in range(1, 5):
        a, b = cU[2 * n - 1], cU[2 * n]
        out -= -n * a * math.sin(n * r) + n * b * math.cos(n * r)
    return out


def trap_U(phi_deg, cU=TRAP_CU):
    r = math.radians(phi_deg)
    return sum(cU[2 * n - 1] * math.cos(n * r) + cU[2 * n] * math.sin(n * r) for n in range(1, 5))


def simulate_measured(T=30.0, phi0=BRAKE1_START['phi0'], w0=BRAKE1_START['w0'], ctrl=None, ctrl_kw=None,
                      coupling=COUPLING_010, amp_scale=1.0, rate=20.0, write_ms=4.0, upd_every=2, tick_phase=0.0,
                      mtramp=0.0625, tau_ac=5.6, frame=0.02, noise=0.3, Q=None, seed=0, rest=REST_F3, replay=None):
    """One run from the state (phi0 deg from rest, w0 deg/s) with the measured trap and coupling.
    ctrl: a SpeedController (default: brake-only 1's live settings, built from ctrl_kw overrides).
    Writes: the first frame >= 1/rate after the last write; lands write_ms later on the next front-end tick
    that is a multiple of upd_every (tick_phase: s offset of the tick grid, unknown, scan it), then the matrix
    ramps over mtramp. amp_scale: coupling scale (linear 1x, quadratic 2x terms ~ V^2 (assumed)).
    replay: (write_times s, psi deg or <0 for off) from a live log, played open loop instead of the controller's
    writes (tests the plant model: trap + coupling + load timing).
    Returns t, phi (deg from rest, unwrapped), field-on flag per frame, controller E per frame."""
    rng = np.random.default_rng(seed)
    if ctrl is None:
        kw = dict(target_rev=0.0, push_pos=-88.0, push_neg=167.0, w0sq=4.94, push_max=0.4, brake_wmin=40.0,
                  rest_deg=rest, sign=-1, m=8, latency=0.04 + mtramp / 2, vmin=6.0)
        kw.update(ctrl_kw or {})
        ctrl = SpeedController(**kw)
    dt = 1e-3
    ph, om = math.radians(phi0), math.radians(w0)
    ang = np.radians([0.0, -120.0, -240.0])
    hp_in = np.zeros(3); hp_out = np.zeros(3); a_hp = tau_ac / (tau_ac + dt)
    applied = np.zeros(2); ramp_from = np.zeros(2); ramp_to = np.zeros(2); ramp_t0 = -1.0
    pending = []; last_write = -1e9; ri = 0
    c0, c1, s1, c2, s2 = coupling
    k1, k2 = amp_scale, amp_scale ** 2
    out_t, out_ph, out_on, out_E = [], [], [], []
    tick = 1.0 / 16 * upd_every
    nf = int(round(frame / dt))
    for i in range(int(T / dt)):
        t = i * dt
        if i % nf == 0:
            meas = rest + math.degrees(ph) + rng.normal(0, noise)
            psi = ctrl.update(t, meas)
            out_t.append(t); out_ph.append(math.degrees(ph)); out_E.append(ctrl.E)
            out_on.append(psi is not None)
            if replay is None and t - last_write >= 1.0 / rate - 1e-9:
                last_write = t
                xy = np.zeros(2) if psi is None else np.array([math.cos(math.radians(psi)), math.sin(math.radians(psi))])
                land = math.ceil((t + write_ms / 1e3 - tick_phase) / tick) * tick + tick_phase
                pending.append((land, xy))
        if replay is not None:
            while ri < len(replay[0]) and replay[0][ri] <= t:
                p = replay[1][ri]; ri += 1
                xy = np.zeros(2) if p < 0 else np.array([math.cos(math.radians(p)), math.sin(math.radians(p))])
                pending.append((math.ceil((t + write_ms / 1e3 - tick_phase) / tick) * tick + tick_phase, xy))
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
        E = abs(z)
        tq = 0.0
        if E > 1e-6:
            D = np.angle(z) + 8 * (math.radians(rest) + ph)
            tq = k1 * E * (c0 + c1 * math.cos(D) + s1 * math.sin(D)) + k2 * E * E * (c2 * math.cos(2 * D) + s2 * math.sin(2 * D))
        damp = 0.0 if Q is None else math.sqrt(4.94) / Q * om
        om += (trap_acc(math.degrees(ph)) - damp + tq) * dt
        ph += om * dt
    return np.array(out_t), np.array(out_ph), np.array(out_on), np.array(out_E)


def swing_extremes(t, phi):
    """Turning points (time, phi) of a swing; a full turn has none for that stretch."""
    w = np.gradient(phi, t)
    idx = np.where(np.sign(w[1:]) != np.sign(w[:-1]))[0]
    return [(round(float(t[k]), 2), round(float(phi[k]), 1)) for k in idx]


def end_rate(t, phi, last=10.0):
    m = t > t[-1] - last
    return (phi[m][-1] - phi[m][0]) / (t[m][-1] - t[m][0]) / 360.0


def repro_brake1(T=30.0, n_seeds=4, phases=(0.0, 0.03125, 0.0625, 0.09375), quiet=False, **kw):
    """Brake-only 1 measured: from (+55 deg, ~-200 deg/s) the swing peaks went -118 / +156, then over the top
    negative at ~5.6 s, then coasted at -0.55..-0.65 rev/s (field off above 0.4 rev/s). Runs the measured model
    over tick phases x noise seeds; returns the fraction that went over the top negative and coasted below -0.4."""
    E_bar = max(trap_U(p) for p in range(-180, 180)) - trap_U(0.0)
    E0 = 0.5 * math.radians(BRAKE1_START['w0']) ** 2 + trap_U(BRAKE1_START['phi0']) - trap_U(0.0)
    if not quiet:
        print(f'start: phi {BRAKE1_START["phi0"]:+.0f} deg, w {BRAKE1_START["w0"]:+.0f} deg/s: energy {E0:.2f} rad^2/s^2 '
              f'= {E0 / E_bar:.2f} of the measured barrier {E_bar:.2f}')
    n_rep = 0; n = 0
    for tp in phases:
        for s in range(n_seeds):
            t, ph, on, E = simulate_measured(T=T, tick_phase=tp, seed=s, **kw)
            r = end_rate(t, ph)
            tc, dc = turns(t, ph)
            over_neg = tc.size > 0 and dc[0] < 0
            rep = over_neg and r < -0.4
            n += 1; n_rep += rep
            if not quiet:
                ex = [e for e in swing_extremes(t, ph) if e[0] < (tc[0] if tc.size else T)][:4]
                print(f'  tick phase {tp:.3f} seed {s}: over the top {"-" if over_neg else ("+" if tc.size else "no")}'
                      f'{"" if not tc.size else f" at {tc[0]:.1f} s"}, end rate {r:+.2f} rev/s, field on {on.mean():.0%}'
                      f' of frames; first turning points {ex}')
    if not quiet:
        print(f'reproduces brake-only 1 (over the top negative, then coasting faster than 0.4 rev/s): {n_rep}/{n}')
    return n_rep / n


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
    if len(sys.argv) > 1 and sys.argv[1] == 'repro':
        cp = COUPLING_010 if '--coupling' in sys.argv and sys.argv[sys.argv.index('--coupling') + 1] == '010' else COUPLING_HOLD
        repro_brake1(T=20.0, n_seeds=3, coupling=cp)
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
