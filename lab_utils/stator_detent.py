#!/usr/bin/env python3
"""Single-phase detent test through the AC-coupled HV amp: torque per electrode group.

    python3 stator_detent.py run [--counts 6400] [--cycles 4] [--outdir DIR] [--enable-outputs] [--live]
    python3 stator_detent.py analyze EVENTS.csv ANGLES.csv [--I 1.1e-11] [--amp-tau 6] [--out PREFIX]
    python3 stator_detent.py selftest

Replaces `stator_epics_drive.py detent` (deleted 2026-11-01): that never set the output
switches, so nothing reached the electrodes, and its A->B->C walk switched one phase off
and the next on in the same instant, which through the AC-coupled amp pulls both ways.

WHAT IT DOES (run). For each cycle, for A, B, C in turn (A, B, C = V2, V4, V3; channel
map from stator_osc_drive.PHASE_ELECTRODES):
  1. V{n}_TRAMP 0, V{n}_OFFSET 0 -> COUNTS: a step. The amp passes the step and it decays
     (tau_amp ~ 5-7 s, estimated, CLAUDE.md); the rotor gets a torque pulse.
  2. hold --on seconds, then V{n}_TRAMP --release, OFFSET -> 0: a slow ramp, so the
     electrode sees almost nothing on the way down (~ V * tau_amp / release).
  3. wait --gap seconds of quiet baseline.
Every event's worker2 host time and front-end GPS go to EVENTS.csv, on the same clock
as live_blob_track.py's host_time, so the analysis can line the two up.

WHAT TO EXPECT (derived, 2026-11-01). The rotor sits in a stiff trap: k = I (2 pi f0)^2
~ 1.1e-11 * (2 pi 0.31)^2 ~ 4e-11 N m/rad (f0 measured 10-30, I from DECISIONS). One
group at ~85 V gives at most ~1e-12 N m (flex_spec design figure, not measured). So the
rotor shifts ~1 deg, rings at f0 and settles back as the pulse decays: NOT visible by
eye; the tracker measures it. Not a snap to a detent.

WHAT IT MEASURES (analyze). For each switch-on, a linear fit of the tracked angle to
  free swing (const, cos w0 t, sin w0 t)  +  tau * g(t),
g = response of an undamped oscillator (w0) to a unit torque decaying as exp(-t/T),
T = amp_tau / 2 (torque ~ V^2). Gives tau per event in N m (given I), per phase mean and
scatter, and S = sqrt(2/3 * sum_n tau_n^2) per cycle: the single-phase detent torque
amplitude, independent of where the rotor sits relative to the electrodes (if the three
phases are equally strong). f0 is fitted from the data (0.2-0.45 Hz). A dead or
disconnected phase shows tau ~ 0 on every cycle while the others do not.

WHAT IT CANNOT MEASURE: the wiring ORDER. In this small-motion regime each phase's torque
is S sin(psi - 120 n) or S sin(psi + 120 n) depending on the wiring, with psi (where the
rotor sits relative to the sectors) unknown; any three numbers fit either. The order
needs large motion (a lock: drive_coupling.py) or psi from geometry.

ASSUMED: tau_amp (sets T; on synthetic data a 30% error in tau_amp moves tau by 4-5%; check with
--amp-tau), I, V/count on the _OFFSET path (unverified; 0.0134 V/count measured on _EXC).

SAFETY: refuses if the oscillator is on (DRVON or gains nonzero) or any offset is
nonzero; COUNTS <= 12800 (V{n}_LIMIT; amp input 0-2.1 V); outputs switched on only with
--enable-outputs, at zero offset, and restored at the end and on Ctrl-C (offsets ramped
down over --release first; Ctrl-C again skips that wait, and the switch then cuts a
partly ramped pedestal: a kick, not a hazard). Nothing touches hardware without --live.
"""
import argparse, csv, math, os, sys, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stator_osc_drive as osd

PREFIX = osd.PREFIX
PHASES = list(zip(osd.PHASE_NAMES, osd.PHASE_ELECTRODES))     # (A,2) (B,4) (C,3)
LIMIT = 12800.0
VOLTS_PER_COUNT = osd.VOLTS_PER_COUNT
GPS_PV = 'Y1:DAQ-DC0_GPS'
TRAMP_SETTLE = 1.0      # s between a TRAMP write and the OFFSET write it is meant to shape:
                        # the front end reads settings on its own cycle, and an OFFSET change
                        # picked up first would ramp at the PREVIOUS TRAMP (a step-on turned
                        # into a 60 s ramp, or a slow release turned into a hard step).

caget = osd.caget
caput = osd.caput
sleep = time.sleep
now = time.time


def put(pv, val, dry):
    print(f'    {"[dry] " if dry else ""}{pv:<32} <- {val:g}')
    if not dry:
        caput(pv, float(val), wait=True, timeout=3.0)


# ----------------------------------------------------------------------------- run
def cmd_run(a):
    dry = not a.live
    if caget is None:
        print('! pyepics not importable.'); return 1
    if not (0 < a.counts <= LIMIT):
        print(f'! --counts must be in (0, {LIMIT:.0f}]: amp input 0-2.1 V, V{{n}}_LIMIT.'); return 1
    if a.release < 10:
        print('! --release under 10 s puts a large reverse pulse on the electrode at '
              'switch-off; that is what this test exists to avoid.'); return 1
    if not osd.check_inputs() or not osd.check_isolation():
        return 1
    drv = [caget(f'{PREFIX}_DRVON'), caget(f'{PREFIX}_DRV_SINGAIN'), caget(f'{PREFIX}_DRV_COSGAIN')]
    if any(abs(v or 0) > 1e-6 for v in drv):
        print(f'! oscillator not off (DRVON, SIN, COS = {drv}). Stop it first: '
              f'python3 stator_osc_drive.py stop --live'); return 1
    offs = {n: caget(f'{PREFIX}_V{n}_OFFSET') for n in (1, 2, 3, 4)}
    if any(abs(v or 0) > 1 for v in offs.values()):
        print(f'! offsets not zero: {offs}. Something else is driving.'); return 1

    per = a.on + a.release + 1 + a.gap
    n_ev = a.cycles * 3
    volts = a.counts * VOLTS_PER_COUNT
    print('=' * 70)
    print(f'  detent test: {a.cycles} cycles x A, B, C = {n_ev} switch-ons, {per:.0f} s each, '
          f'{n_ev * per / 60:.1f} min')
    print(f'  step {a.counts:.0f} counts ~ {volts:.0f} V at the electrode (0.0134 V/count, '
          f'measured on _EXC; _OFFSET unverified)')
    print(f'  on {a.on:g} s, ramp off over {a.release:g} s, {a.gap:g} s quiet between')
    print(f'  outputs {"ENABLED" if a.enable_outputs else "OFF -- nothing reaches the chamber"}')
    print('  expected rotor response ~1 deg (derived): not visible by eye; keep the tracker recording.')
    print('=' * 70)

    sw2_before = {n: int(caget(f'{PREFIX}_V{n}_SW2R') or 0) for n in (1, 2, 3, 4)}
    tramp_before = {n: float(caget(f'{PREFIX}_V{n}_TRAMP') or 0.0) for _, n in PHASES}
    os.makedirs(a.outdir, exist_ok=True)
    ev_path = os.path.join(a.outdir, 'detent_events_%d.csv' % int(now()))
    fh = open(ev_path, 'w', buffering=1)
    fh.write('# stator_detent.py counts=%g on=%g release=%g gap=%g live=%d outputs=%d\n' % (
        a.counts, a.on, a.release, a.gap, int(a.live), int(a.enable_outputs)))
    fh.write('event,cycle,phase,electrode,counts,host_time,fe_gps\n')

    last_release = [-1e18]          # when the most recent ramp-down was commanded

    def log(event, cycle, name, n, counts):
        if event == 'release':
            last_release[0] = now()
        g = caget(GPS_PV) if not dry else 0
        fh.write('%s,%d,%s,%d,%g,%.6f,%s\n' % (event, cycle, name, n, counts, now(), g))

    interrupted = False
    try:
        if a.enable_outputs:
            print('\n  outputs on (offsets are 0, so no step):')
            for _, n in PHASES:
                if not sw2_before[n] & osd.SW2_OUTPUT_ON:
                    put(f'{PREFIX}_V{n}_SW2S', sw2_before[n] | osd.SW2_OUTPUT_ON, dry)
        print('\n  quiet baseline %g s' % a.gap)
        if not dry: sleep(a.gap)
        for c in range(a.cycles):
            for name, n in PHASES:
                print(f'\n  cycle {c + 1}/{a.cycles}  phase {name} (V{n})')
                put(f'{PREFIX}_V{n}_TRAMP', 0, dry)
                if not dry: sleep(TRAMP_SETTLE)
                put(f'{PREFIX}_V{n}_OFFSET', a.counts, dry)
                log('on', c, name, n, a.counts)
                if not dry: sleep(a.on)
                put(f'{PREFIX}_V{n}_TRAMP', a.release, dry)
                if not dry: sleep(TRAMP_SETTLE)
                put(f'{PREFIX}_V{n}_OFFSET', 0, dry)
                log('release', c, name, n, 0)
                if not dry: sleep(a.release + 1 + a.gap)
    except KeyboardInterrupt:
        interrupted = True
        print('\n  interrupted -- tearing down.')
    finally:
        print('\n  teardown:')
        live_off = {n: caget(f'{PREFIX}_V{n}_OFFSET') for _, n in PHASES} if not dry else {}
        if any(abs(v or 0) > 0 for v in live_off.values()):
            for _, n in PHASES:
                put(f'{PREFIX}_V{n}_TRAMP', a.release, dry)
            if not dry:
                try:
                    sleep(TRAMP_SETTLE)
                except KeyboardInterrupt:
                    pass
            for _, n in PHASES:
                put(f'{PREFIX}_V{n}_OFFSET', 0, dry)
            last_release[0] = now()
        # A ramp-down commanded here or in the loop may still be running: the readback is
        # the setpoint (0), not the ramped value. Wait it out before any output switch.
        remaining = last_release[0] + a.release + 1 - now()
        if not dry and remaining > 0:
            print(f'    waiting {remaining:.0f} s for the offset ramp-down before touching the output switches'
                  f'{" (Ctrl-C again to skip: the switch then cuts a partly ramped pedestal)" if interrupted else ""}')
            try:
                sleep(remaining)
            except KeyboardInterrupt:
                print('    skipped the wait.')
        if a.enable_outputs:
            for n, v in sorted(sw2_before.items()):
                put(f'{PREFIX}_V{n}_SW2S', v, dry)
        for n, t in sorted(tramp_before.items()):
            put(f'{PREFIX}_V{n}_TRAMP', t, dry)
        fh.close()
        if not dry:
            left = {n: caget(f'{PREFIX}_V{n}_OFFSET') for n in (1, 2, 3, 4)}
            on = [n for n in (1, 2, 3, 4) if int(caget(f'{PREFIX}_V{n}_SW2R') or 0) & osd.SW2_OUTPUT_ON]
            print('  offsets', left, '| outputs on:', on or 'none')
        print(f'  events -> {ev_path}')
    return 0


# ------------------------------------------------------------------------- analyze
def unit_response(t, w0, T):
    """theta(t) for theta'' + w0^2 theta = exp(-t/T)  (unit torque/I), theta(0)=theta'(0)=0."""
    C = 1.0 / (w0 ** 2 + T ** -2)
    g = C * (np.exp(-t / T) - np.cos(w0 * t) + np.sin(w0 * t) / (w0 * T))
    return np.where(t > 0, g, 0.0)


def fit_event(t, th, w0, T, pre=8.0, post=15.0):
    m = (t > -pre) & (t < post)
    tt, y = t[m], th[m]
    X = np.c_[np.ones_like(tt), np.cos(w0 * tt), np.sin(w0 * tt), unit_response(tt, w0, T)]
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ coef
    cov = np.linalg.pinv(X.T @ X) * (r @ r) / max(1, len(y) - 4)
    return coef, math.sqrt(cov[3, 3]), r, (tt, y, X @ coef)


def analyze(events, t_ang, theta_rad, I, amp_tau, f0=None):
    """events: list of (cycle, phase, t_on). Returns (f0, rows)."""
    T = amp_tau / 2.0
    def total_res(f):
        w0 = 2 * np.pi * f
        return sum(float(fit_event(t_ang - te, theta_rad, w0, T)[2] @ fit_event(t_ang - te, theta_rad, w0, T)[2])
                   for _, _, te in events)
    if f0 is None:
        fs = np.arange(0.20, 0.45, 0.002)
        f0 = float(fs[int(np.argmin([total_res(f) for f in fs]))])
    w0 = 2 * np.pi * f0
    rows = []
    for c, ph, te in events:
        coef, se, r, curves = fit_event(t_ang - te, theta_rad, w0, T)
        tau = coef[3] * I; tau_se = se * I
        rows.append(dict(cycle=c, phase=ph, t_on=te, tau=tau, tau_se=tau_se,
                         static_deg=np.rad2deg(tau / (I * w0 ** 2)),
                         resid_deg=np.rad2deg(r.std()), curves=curves))
    return f0, rows


def summarize(f0, rows, I):
    k = I * (2 * np.pi * f0) ** 2
    print(f'trap f0 fitted {f0:.3f} Hz -> k = I w0^2 = {k:.2e} N m/rad (I = {I:.2e}, assumed)')
    if f0 < 0.205 or f0 > 0.445:
        print('! f0 is at the edge of the 0.20-0.45 Hz scan: the fit did not find the trap. '
              'Pass --f0 from the drive-off swing, or check the recording.')
    print('%5s %5s %12s %10s %10s %9s' % ('cycle', 'phase', 'tau (N m)', '+-', 'static deg', 'resid deg'))
    for r in rows:
        print('%5d %5s %+12.3e %10.1e %+10.3f %9.2f' % (r['cycle'], r['phase'], r['tau'], r['tau_se'],
                                                        r['static_deg'], r['resid_deg']))
    out = {}
    for ph in ('A', 'B', 'C'):
        v = np.array([r['tau'] for r in rows if r['phase'] == ph])
        if len(v):
            out[ph] = (v.mean(), v.std(ddof=1) / math.sqrt(len(v)) if len(v) > 1 else float('nan'))
            print(f'  phase {ph}: mean tau {out[ph][0]:+.3e} +- {out[ph][1]:.1e} N m (n={len(v)}, scatter)')
    S = []
    for c in sorted(set(r['cycle'] for r in rows)):
        v = [r['tau'] for r in rows if r['cycle'] == c]
        if len(v) == 3:
            S.append(math.sqrt(2.0 / 3.0 * sum(x * x for x in v)))
    if S:
        S = np.array(S)
        print(f'  detent torque amplitude S = {S.mean():.3e} +- '
              f'{(S.std(ddof=1) / math.sqrt(len(S)) if len(S) > 1 else float("nan")):.1e} N m '
              f'over {len(S)} cycles (assumes equal phases; independent of rotor position)')
    return out, S


def load_events(path):
    rows = list(csv.DictReader(l for l in open(path) if not l.startswith('#')))
    return [(int(r['cycle']), r['phase'], float(r['host_time'])) for r in rows if r['event'] == 'on']


def load_angles(path):
    rows = list(csv.DictReader(l for l in open(path) if not l.startswith('#')))
    t = np.array([float(r['host_time']) for r in rows])
    th = np.unwrap(np.deg2rad([float(r['angle_deg']) for r in rows]))
    return t, th


def cmd_analyze(a):
    ev = load_events(a.events)
    t, th = load_angles(a.angles)
    ev = [e for e in ev if t[0] + 8 < e[2] < t[-1] - 15]
    if not ev:
        print('! no switch-on events inside the angle recording'); return 2
    f0, rows = analyze(ev, t, th, a.I, a.amp_tau, a.f0)
    summarize(f0, rows, a.I)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    n = len(rows); cols = 3; nr = int(math.ceil(n / cols))
    fig, axs = plt.subplots(nr, cols, figsize=(4 * cols, 2.4 * nr), squeeze=False)
    for ax, r in zip(axs.ravel(), rows):
        tt, y, yf = r['curves']
        ax.plot(tt, np.rad2deg(y - y[tt < 0].mean()), lw=0.6, color='0.5')
        ax.plot(tt, np.rad2deg(yf - y[tt < 0].mean()), lw=1.2, color='C3')
        ax.axvline(0, color='k', lw=0.5)
        ax.set_title('cycle %d %s: tau %+.2e N m' % (r['cycle'], r['phase'], r['tau']), fontsize=8)
        ax.set_xlabel('s from switch-on', fontsize=7); ax.set_ylabel('deg', fontsize=7)
    for ax in axs.ravel()[n:]:
        ax.axis('off')
    fig.tight_layout(); fig.savefig(a.out + '.png', dpi=100)
    print('figure:', a.out + '.png')
    return 0


# ------------------------------------------------------------------------ selftest
def selftest():
    global caget, caput, sleep, now
    ok = True
    def check(name, cond):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + name); ok &= bool(cond)

    # 1. hardware ordering against a fake EPICS
    import tempfile
    tmp = tempfile.mkdtemp(prefix='detent_selftest_')
    for scenario in ('normal', 'interrupt', 'interrupt_on', 'osc_on', 'offset_on'):
        state, log, clock = {}, [], [0.0]
        for n in (1, 2, 3, 4):
            state.update({f'{PREFIX}_V{n}_SW1R': 4, f'{PREFIX}_V{n}_SW2R': 768,
                          f'{PREFIX}_V{n}_OFFSET': 0.0, f'{PREFIX}_V{n}_TRAMP': 1.0})
        state.update({f'{PREFIX}_DRVON': 0, f'{PREFIX}_DRV_SINGAIN': 0.0, f'{PREFIX}_DRV_COSGAIN': 0.0, GPS_PV: 1})
        for s in ('LES_PIT', 'LES_YAW', 'LES_SUM', 'MON'):
            state.update({f'Y1:RDS-{s}_GAIN': 1.0, f'Y1:RDS-{s}_SW2R': 0})
        if scenario == 'osc_on': state[f'{PREFIX}_DRVON'] = 1
        if scenario == 'offset_on': state[f'{PREFIX}_V2_OFFSET'] = 500.0
        def fget(pv): return state.get(pv, 0.0)
        def fput(pv, v, wait=True, timeout=3.0):
            log.append((clock[0], pv, v, dict(state)))
            if pv.endswith('_SW2S'): state[pv[:-1] + 'R'] = int(v)
            else: state[pv] = v
        n_sleep = [0]
        def fsleep(s):
            n_sleep[0] += 1
            # sleeps: baseline, settle, on, settle, release+gap ...
            if scenario == 'interrupt' and n_sleep[0] == 5: raise KeyboardInterrupt
            if scenario == 'interrupt_on' and n_sleep[0] == 3: raise KeyboardInterrupt
            clock[0] += s
        caget = osd.caget = fget; caput = osd.caput = fput; sleep = fsleep; now = lambda: clock[0]
        args = argparse.Namespace(counts=6400, cycles=2, on=8, release=60, gap=10, live=True,
                                  enable_outputs=True, outdir=os.path.join(tmp, scenario))
        rc = cmd_run(args)
        if scenario in ('osc_on', 'offset_on'):
            check(f'{scenario}: refuses with no writes', rc == 1 and not log); continue
        ons = [(i, x) for i, x in enumerate(log) if x[1].endswith('_OFFSET') and x[2] > 0]
        ev_files = [f for f in os.listdir(os.path.join(tmp, scenario)) if f.startswith('detent_events')]
        ev_loaded = load_events(os.path.join(tmp, scenario, ev_files[0])) if ev_files else []
        check(f'{scenario}: events CSV round-trips (one "on" row per switch-on)',
              len(ev_loaded) == len(ons) and all(p in 'ABC' for _, p, _ in ev_loaded))
        check(f'{scenario}: every switch-on is a step (TRAMP 0)',
              all(x[3][x[1].replace('OFFSET', 'TRAMP')] == 0 for _, x in ons))
        offs = [x for x in log if x[1].endswith('_OFFSET') and x[2] == 0]
        check(f'{scenario}: every switch-off ramps over --release',
              all(x[3][x[1].replace('OFFSET', 'TRAMP')] == 60 for x in offs))
        first_sw = min(i for i, x in enumerate(log) if x[1].endswith('_SW2S'))
        check(f'{scenario}: outputs enabled before any offset, at offset 0',
              all(x[3][f'{PREFIX}_V{n}_OFFSET'] == 0 for x in log[:first_sw + 1] for n in (2, 3, 4))
              and first_sw < (ons[0][0] if ons else 1e9))
        check(f'{scenario}: order A(V2), B(V4), C(V3)',
              [x[1] for _, x in ons][:3] == [f'{PREFIX}_V{n}_OFFSET' for n in (2, 4, 3)] or scenario.startswith('interrupt'))
        check(f'{scenario}: end state offsets 0, SW2 768, TRAMP 1.0',
              all(state[f'{PREFIX}_V{n}_OFFSET'] == 0 and state[f'{PREFIX}_V{n}_SW2R'] == 768 for n in (1, 2, 3, 4))
              and all(state[f'{PREFIX}_V{n}_TRAMP'] == 1.0 for n in (2, 3, 4)))
        if scenario.startswith('interrupt'):
            last_off = max(i for i, x in enumerate(log) if x[1].endswith('_OFFSET'))
            sw_after = [x for i, x in enumerate(log) if i > last_off and x[1].endswith('_SW2S')]
            check(f'{scenario}: outputs restored only after the ramp-down wait',
                  sw_after and sw_after[0][0] - log[last_off][0] >= 60)
    caget = osd.caget = None; caput = osd.caput = None

    # 2. analysis recovers a known torque
    rng = np.random.default_rng(1)
    I, f0, amp_tau = 1.1e-11, 0.30, 6.0
    w0, T = 2 * np.pi * f0, amp_tau / 2
    t = np.arange(0, 12 * 80, 0.02); th = np.deg2rad(1.0) * np.sin(w0 * t + 0.3)   # 1 deg free swing
    events, truth = [], {}
    S, psi = 1.0e-12, 0.7
    for c in range(4):
        for i, ph in enumerate('ABC'):
            te = 20 + (3 * c + i) * 80; tau = S * math.sin(psi - 2 * np.pi / 3 * i)
            th += tau / I * unit_response(t - te, w0, T); events.append((c, ph, te)); truth[ph] = tau
    th += np.deg2rad(0.7) * rng.normal(size=len(t))                                  # tracker noise
    f_fit, rows = analyze(events, t, th, I, amp_tau)
    out, Sfit = summarize(f_fit, rows, I)
    check('analysis: f0 within 0.01 Hz', abs(f_fit - f0) < 0.01)
    check('analysis: per-phase tau within 15% of truth (or 0.1e-12)',
          all(abs(out[p][0] - truth[p]) < max(0.15 * abs(truth[p]), 0.1e-12) for p in 'ABC'))
    check('analysis: S within 10%', abs(Sfit.mean() - S) < 0.1 * S)
    print('SELFTEST %s' % ('PASSED' if ok else 'FAILED'))
    return ok


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run')
    r.add_argument('--counts', type=float, default=6400.0)
    r.add_argument('--cycles', type=int, default=4)
    r.add_argument('--on', type=float, default=8.0, help='s held before the ramp-down (default 8)')
    r.add_argument('--release', type=float, default=60.0, help='ramp-down time, s (default 60)')
    r.add_argument('--gap', type=float, default=10.0, help='quiet s between steps (default 10)')
    r.add_argument('--outdir', default=os.path.expanduser('~/stator_detent'),
                   help='events CSV goes here (default ~/stator_detent, outside the repo)')
    r.add_argument('--enable-outputs', action='store_true')
    r.add_argument('--live', action='store_true')
    z = sub.add_parser('analyze')
    z.add_argument('events'); z.add_argument('angles')
    z.add_argument('--I', type=float, default=1.1e-11, help='moment of inertia, kg m^2 (DECISIONS)')
    z.add_argument('--amp-tau', type=float, default=6.0, help='amp AC-coupling time constant, s (estimate)')
    z.add_argument('--f0', type=float, default=None, help='trap frequency, Hz (default: fit)')
    z.add_argument('--out', default='detent')
    sub.add_parser('selftest')
    a = p.parse_args()
    if a.cmd == 'selftest':
        return 0 if selftest() else 1
    return cmd_run(a) if a.cmd == 'run' else cmd_analyze(a)


if __name__ == '__main__':
    sys.exit(main())
