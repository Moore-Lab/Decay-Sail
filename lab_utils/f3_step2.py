#!/usr/bin/env python3
"""F3 step 2 (Molly OK 2026-11-10): score braking fixes in the measured-model simulator, offset route, before any run.

    python3 f3_step2.py run [--outdir DIR] [--jobs 8]      # the scan (~10 min on 8 cores), table + plots
    python3 f3_step2.py selftest

Plan: lab_utils/FEEDBACK_HANDOFF.md, "Next" 1 (branch feedback-drive); step-1 mark in docs/DECISIONS.md 2026-11-10.
Plant: f3_check.simulate_measured (11-04 joint trap fit + per-hold coupling, AC coupling tau 5.6 s, writes landing on
the 8 Hz grid), with two changes from 2026-11-10 (VOLTAGE_STEPS S1, analysis/voltage_steps_20261110_s1):
  - ROUTE: offsets (V{n}_OFFSET): no matrix ramp (mtramp 0); every update lands whole on the 8 Hz grid (measured S0,
    8/s test, S1). The matrix route (mtramp 1/16 s) runs for comparison on the baseline and the best fix.
  - TRAP rescaled by TRAP_S = (0.379 / f_sim)^2 so a +-17.5 deg free swing has the 0.379 Hz tracked after S1 (measured
    near rest only); the scan then multiplies trap and coupling strength by 0.75, 1, 1.25 (Molly OK 2026-11-10).
Unknown, scanned: extra write -> field delay (0, 30, 60, 100 ms on top of the 0-125 ms wait for the next intake),
tick phase (0, 62.5 ms), coupling model (HOLD, 010).

FIXES (handoff list; each scored in every cell):
  base      brake-only 1's live settings (horizon 0.04 s, brake_wmin 40 deg/s, full amplitude)
  H         prediction horizon = the cell's true mean delay (write + extra + half an intake period) (oracle)
  HM        H + mid-swing only: no brake push if the velocity predicted one horizon ahead (trap model) changes sign
  HMg50     HM at half amplitude
  HMg25     HM at quarter amplitude
  HMg50fix  HMg50 with the horizon FIXED at an assumed 30 ms extra delay (not the cell's truth): the realistic case
START STATES:
  A  brake 1's state (+55 deg, swing energy 0.82 of the barrier, scaled with the trap): the F3 failure
  B  today's post-S1 free swing: +-17.5 deg about equilibrium, at rest at a turning point (the first real test)
PASS (A, handoff): swing below 30 deg in the last 10 s of 60 s and never over the top, in every cell.
PASS (B, proposed by Claude, not yet agreed): swing below 5 deg in the last 10 s of 60 s, never larger than the start
  +5 deg, never over the top, in every cell.
"""
import argparse
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f3_check as F  # noqa: E402
from feedback_drive import SpeedController  # noqa: E402

F_TODAY = 0.379            # Hz, +-17.5 deg free swing after S1 (measured, analysis/voltage_steps_20261110_s1)
AMP_TODAY = 17.5
INTAKE = 0.125             # s, offsets applied every 2nd 16 Hz tick (measured)
WRITE_MS = 4.0


def free_freq(amp_deg, trap_scale=1.0, T=60.0):
    eq = equilibrium()
    dt = 1e-3; th = math.radians(eq + amp_deg); om = 0.0; prev = 0.0; cr = []
    for n in range(int(T / dt)):
        om += trap_scale * F.trap_acc(math.degrees(th)) * dt; th += om * dt
        if prev < 0 <= om:
            cr.append(n * dt)
        prev = om
    return 1.0 / np.mean(np.diff(cr))


def equilibrium():
    ph = np.linspace(-60, 60, 4801)
    a = np.array([F.trap_acc(p) for p in ph])
    return float(ph[np.argmin(np.abs(a))])


TRAP_S = (F_TODAY / free_freq(AMP_TODAY)) ** 2


class BrakeController(SpeedController):
    """SpeedController + mid-swing gate: brake only if the velocity predicted `margin` horizons ahead keeps its sign
    (trap model -w0sq sin(theta - rest)), so a push near a turning point, where it would pump, is skipped."""

    def __init__(self, midswing=False, margin=1.5, **kw):
        super().__init__(**kw)
        self.midswing, self.margin = midswing, margin

    def update(self, t, theta_deg):
        psi = super().update(t, theta_deg)
        if psi is None or not self.midswing or self.action > 0:
            return psi
        w = math.radians(self.w)
        a = -self.w0sq * math.sin(math.radians(self.th - self.rest))
        if np.sign(w + a * self.latency * self.margin) != np.sign(w):
            self.on = False
            return None
        return psi


FIXES = {
    'base': dict(horizon='live', midswing=False, amp=1.0),
    'H': dict(horizon='true', midswing=False, amp=1.0),
    'HM': dict(horizon='true', midswing=True, amp=1.0),
    'HMg50': dict(horizon='true', midswing=True, amp=0.5),
    'HMg25': dict(horizon='true', midswing=True, amp=0.25),
    'HMg50fix': dict(horizon=0.030, midswing=True, amp=0.5),
    # brake_wmin 40 deg/s (live 2) is about the PEAK speed of a +-17.5 deg swing at 0.379 Hz (41.7 deg/s, derived), so it
    # all but switches the brake off for start B. The mid-swing gate does the job brake_wmin was for, so lower it:
    'HMw': dict(horizon='true', midswing=True, amp=1.0, wmin=10.0),
    'HMwfix': dict(horizon=0.030, midswing=True, amp=1.0, wmin=10.0),
    'HMwg50fix': dict(horizon=0.030, midswing=True, amp=0.5, wmin=10.0),
}


def start_state(which, trap_scale):
    eq = equilibrium()
    if which == 'B':
        return eq + AMP_TODAY, 0.0
    U = lambda p: trap_scale * F.trap_U(p)
    E_bar = max(U(p) for p in range(-180, 180)) - U(eq)
    E0 = 0.82 * E_bar
    phi0 = F.BRAKE1_START['phi0']
    w0 = -math.degrees(math.sqrt(max(2 * (E0 - (U(phi0) - U(eq))), 0.0)))
    return phi0, w0


def one(cell):
    fix, start, route, extra, tick, cpl, ts, cs = cell
    fx = FIXES[fix]
    mtramp = 0.0 if route == 'offsets' else 0.0625
    write_ms = WRITE_MS + 1e3 * extra
    true_mean = write_ms / 1e3 + INTAKE / 2 + mtramp / 2
    if fx['horizon'] == 'live':
        lat = 0.04 + mtramp / 2
    elif fx['horizon'] == 'true':
        lat = true_mean
    else:
        lat = WRITE_MS / 1e3 + fx['horizon'] + INTAKE / 2 + mtramp / 2
    trap_scale = TRAP_S * ts
    ctrl = BrakeController(midswing=fx['midswing'], target_rev=0.0, push_pos=-88.0, push_neg=167.0,
                           w0sq=4.94 * TRAP_S, push_max=0.4, brake_wmin=fx.get('wmin', 40.0), rest_deg=F.REST_F3, sign=-1, m=8,
                           latency=lat, vmin=6.0)
    phi0, w0 = start_state(start, trap_scale)
    t, ph, on, E = F.simulate_measured(T=60.0, phi0=phi0, w0=w0, ctrl=ctrl, coupling=cpl_of(cpl), amp_scale=fx['amp'],
                                       write_ms=write_ms, tick_phase=tick, mtramp=mtramp, trap_scale=trap_scale,
                                       cpl_scale=cs, seed=0)
    eq = equilibrium()
    tc, dc = F.turns(t, ph)
    end = t > t[-1] - 10
    final = float(np.ptp(ph[end]) / 2)
    peak = float(np.max(np.abs(ph - eq)))
    over = bool(tc.size)
    if start == 'A':
        ok = (not over) and final < 30
    else:
        ok = (not over) and final < 5 and peak <= AMP_TODAY + 5
    return dict(fix=fix, start=start, route=route, extra_ms=1e3 * extra, tick=tick, cpl=cpl, trap=ts, cs=cs,
                final=final, peak=peak, over=over, on=float(on.mean()), ok=bool(ok), lat=lat)


def cpl_of(name):
    return F.COUPLING_HOLD if name == 'HOLD' else F.COUPLING_010


def cells(fixes, starts, routes=('offsets',)):
    out = []
    for fix in fixes:
        for st in starts:
            for r in routes:
                for ex in (0.0, 0.03, 0.06, 0.10):
                    for tk in (0.0, 0.0625):
                        for cp in ('HOLD', '010'):
                            for ts in (0.75, 1.0, 1.25):
                                for cs in (0.75, 1.0, 1.25):
                                    out.append((fix, st, r, ex, tk, cp, ts, cs))
    return out


def summarise(rows):
    S = {}
    for r in rows:
        k = (r['fix'], r['start'], r['route'])
        S.setdefault(k, []).append(r)
    lines = ['| fix | start | route | cells passed | worst final swing (deg) | over the top | pass by extra delay 0/30/60/100 ms |',
             '|---|---|---|---|---|---|---|']
    for (fix, st, rt), rr in S.items():
        byd = []
        for ex in (0.0, 30.0, 60.0, 100.0):
            q = [x for x in rr if abs(x['extra_ms'] - ex) < 1]
            byd.append(f'{sum(x["ok"] for x in q)}/{len(q)}')
        lines.append(f'| {fix} | {st} | {rt} | {sum(x["ok"] for x in rr)}/{len(rr)} | {max(x["final"] for x in rr):.1f} | '
                     f'{sum(x["over"] for x in rr)} | {" ".join(byd)} |')
    return '\n'.join(lines)


def run(outdir, jobs):
    os.makedirs(outdir, exist_ok=True)
    print(f'trap rescale {TRAP_S:.3f} (free swing +-{AMP_TODAY} deg: {free_freq(AMP_TODAY):.3f} Hz in the 11-04 fit, '
          f'{free_freq(AMP_TODAY, TRAP_S):.3f} Hz rescaled; measured {F_TODAY})')
    only = os.environ.get('STEP2_FIXES')
    if only:                                   # rerun a subset, merging into the saved cells
        cl = cells(only.split(','), ('A', 'B'))
    else:
        cl = cells(list(FIXES), ('A', 'B')) + cells(['base', 'HMg50fix'], ('A', 'B'), routes=('matrix',))
    with ProcessPoolExecutor(jobs) as ex:
        rows = list(ex.map(one, cl, chunksize=4))
    fn = os.path.join(outdir, 'step2_cells.json')
    if only and os.path.exists(fn):
        keep = [r for r in json.load(open(fn)) if r['fix'] not in only.split(',')]
        rows = keep + rows
    json.dump(rows, open(fn, 'w'), indent=0)
    tab = summarise(rows)
    print(tab)
    open(os.path.join(outdir, 'step2_summary.md'), 'w').write(
        f'Trap rescale {TRAP_S:.3f}; {len(rows)} cells; pass A: < 30 deg, B (proposed): < 5 deg, no growth.\n\n' + tab + '\n')
    plots(rows, outdir)
    return rows


def plots(rows, outdir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(outdir, 'plots'), exist_ok=True)
    # example traces: each fix, nominal cell and its worst cell, both starts (offsets)
    for st in ('A', 'B'):
        fig, ax = plt.subplots(len(FIXES), 1, figsize=(12, 2.2 * len(FIXES)), sharex=True)
        for k, fix in enumerate(FIXES):
            rr = [r for r in rows if r['fix'] == fix and r['start'] == st and r['route'] == 'offsets']
            worst = max(rr, key=lambda r: (r['over'], r['final']))
            for r, col, lab in ((dict(rr[0], extra_ms=30.0, tick=0.0, cpl='HOLD', trap=1.0, cs=1.0), 'C0', 'nominal (30 ms, HOLD, x1)'),
                                (worst, 'C3', f'worst ({worst["extra_ms"]:.0f} ms, {worst["cpl"]}, trap x{worst["trap"]}, cpl x{worst["cs"]})')):
                cell = (fix, st, 'offsets', r['extra_ms'] / 1e3, r['tick'], r['cpl'], r['trap'], r['cs'])
                t, ph = trace(cell)
                ax[k].plot(t, ph, color=col, lw=0.8, label=lab)
            ax[k].axhline(30 if st == 'A' else 5, color='grey', ls=':', lw=0.8); ax[k].axhline(-(30 if st == 'A' else 5), color='grey', ls=':', lw=0.8)
            ax[k].set_ylabel(f'{fix}\ndeg'); ax[k].legend(fontsize=7, loc='upper right')
        ax[-1].set_xlabel('s')
        fig.suptitle(f'F3 step 2, start {st}: rotor angle from rest (simulated, offset route)', fontsize=11)
        fig.tight_layout(); fig.savefig(os.path.join(outdir, 'plots', f'step2_traces_{st}.png'), dpi=100); plt.close(fig)


def trace(cell):
    fix, start, route, extra, tick, cpl, ts, cs = cell
    fx = FIXES[fix]
    mtramp = 0.0 if route == 'offsets' else 0.0625
    write_ms = WRITE_MS + 1e3 * extra
    lat = {'live': 0.04 + mtramp / 2, 'true': write_ms / 1e3 + INTAKE / 2 + mtramp / 2}.get(
        fx['horizon'], WRITE_MS / 1e3 + (fx['horizon'] if not isinstance(fx['horizon'], str) else 0) + INTAKE / 2 + mtramp / 2)
    ctrl = BrakeController(midswing=fx['midswing'], target_rev=0.0, push_pos=-88.0, push_neg=167.0, w0sq=4.94 * TRAP_S,
                           push_max=0.4, brake_wmin=fx.get('wmin', 40.0), rest_deg=F.REST_F3, sign=-1, m=8, latency=lat, vmin=6.0)
    phi0, w0 = start_state(start, TRAP_S * ts)
    t, ph, on, E = F.simulate_measured(T=60.0, phi0=phi0, w0=w0, ctrl=ctrl, coupling=cpl_of(cpl), amp_scale=fx['amp'],
                                       write_ms=write_ms, tick_phase=tick, mtramp=mtramp, trap_scale=TRAP_S * ts,
                                       cpl_scale=cs, seed=0)
    return t, ph - equilibrium()


def selftest():
    ok = True
    f = free_freq(AMP_TODAY, TRAP_S)
    print(f'rescaled trap: +-{AMP_TODAY} deg swing at {f:.3f} Hz (want {F_TODAY}); scale {TRAP_S:.3f}')
    ok &= abs(f - F_TODAY) < 0.003
    # no drive: a free swing from B keeps its amplitude (Q None), so B cannot pass without braking
    r = one(('base', 'B', 'offsets', 0.0, 0.0, 'HOLD', 1.0, 0.0))     # coupling x0 = field has no effect
    print(f'B with the field disconnected: final swing {r["final"]:.1f} deg (want ~{AMP_TODAY}), pass {r["ok"]}')
    ok &= abs(r['final'] - AMP_TODAY) < 1.5 and not r['ok']
    r = one(('base', 'A', 'offsets', 0.0, 0.0, 'HOLD', 1.0, 0.0))
    print(f'A with the field disconnected: final swing {r["final"]:.1f} deg, over the top {r["over"]} (want large, no)')
    ok &= r['final'] > 100 and not r['over']
    print('SELFTEST', 'PASSED' if ok else 'FAILED')
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('cmd', choices=('run', 'selftest'))
    p.add_argument('--outdir', default='f3_step2_out')
    p.add_argument('--jobs', type=int, default=os.cpu_count())
    a = p.parse_args()
    if a.cmd == 'selftest':
        return selftest()
    run(a.outdir, a.jobs)
    return 0


if __name__ == '__main__':
    sys.exit(main())
