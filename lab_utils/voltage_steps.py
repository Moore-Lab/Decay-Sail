#!/usr/bin/env python3
"""Fast DC voltage steps through the electrode offsets (V{n}_OFFSET): what limits them.

    python3 voltage_steps.py plan  [--patterns single,all3,stepper] [--rates 1,2,4,8,16,32] [--dur 20]
                                   [--level 3200] [--shape square|stair] [--out PLAN.csv]
    python3 voltage_steps.py run   [--plan PLAN.csv | plan options] [--outdir DIR] [--live] [--enable-outputs]
    python3 voltage_steps.py run   --preset field8 [--field-dur 240] ...   (the clean 8/s test, ~6.2 min + checks)
    python3 voltage_steps.py fetch RUNDIR            (worker2: OUT_DQ of V2, V3, V4 over the run, from NDS)
    python3 voltage_steps.py selftest                (Mac: the run loop against a mock front end)

Plan: lab_utils/VOLTAGE_STEPS_HANDOFF.md (stages S0, S1). Scorer and plots: voltage_steps_score.py.
Adapted from stator_detent.py (branch detent-test). The drive matrix, oscillator and AWG are not used.

WHAT IT DOES (run). Plays a list of (t, V2, V4, V3) offset levels in counts (A, B, C = V2, V4, V3),
block by block (one pattern at one rate per block, starting and ending at 0):
  1. V{n}_TRAMP -> 0 and read back after 1 s, at the start of EVERY block (TRAMP was found reset
     between runs). The value found is logged: that is the TRAMP-reset measurement.
  2. For each step, the channels that change are written back to back with caput(wait=False) and one
     flush, so a 3-channel change goes out as one burst. Host time before the first write and after the
     flush are logged (writes.csv). Burst length / 62.5 ms is the chance that a 16 Hz tick falls inside
     the burst, which the scorer compares against the measured split rate.
  3. V2, V3, V4 _OUTMON are monitored (EPICS callbacks, not polling): every update's host time and
     value go to outmon.csv. The scorer reads write-to-OUTMON delay from that, host side.
  4. Front-end GPS (Y1:DAQ-DC0_GPS, 1 s resolution) and host time before and after every block
     (blocks.csv); the scorer fits host -> FE time from the OUT_DQ steps themselves.
  5. At the end, and on Ctrl-C: TRAMP -> --release, wait, offsets -> 0 (a slow ramp), wait it out,
     restore TRAMP and (if changed) the output switches.

PATTERNS (plan). Level L (default 3200 counts, ~38-40 V at the electrode with the refit offset-path gain):
  single   V2 only: square 0 <-> L  (--shape stair: cycles 0, L/4 .. L, so a landed value identifies
           its write even when writes are dropped)
  all3     all three change on every step: (L, L/2, 0) -> (0, L, L/2) -> (L/2, 0, L) -> ...
  stepper  one electrode at a time, A -> B -> C -> A: (L,0,0) -> (0,L,0) -> (0,0,L); every step
           switches one electrode off as the next goes on (through the AC-coupled amp this pulls
           both ways: stator_detent.py docstring; irrelevant with outputs off).
  field    (--preset field8 only) a random field direction per step, written the way feedback would point the
           field: A, B, C = L/2 + L/2 cos(theta - 0, 120, 240 deg), theta on a 15 deg grid, every channel changing
           by >= L/10 per step. Exactly 8 steps/s for --field-dur s (240), no dither, between dithered all3
           blocks at 2 and 4/s (30 s each, before and after) that the scorer uses to line up the clocks.
Each block: --dur s at the requested rate, then back to 0 and --gap s quiet. At <= 8 steps/s each step is
dithered later by up to 125 ms (make_plan docstring; --no-dither to turn off).

WHAT S0 SEES (outputs off): OUT_DQ is upstream of the output switch (C2 11-02 and F1 saw the drive in
OUT_DQ with outputs off), so S0 measures when the front end APPLIES each write, not what leaves the box.
Whether _OUTMON follows with outputs off is not known; if it stays at 0, the host-side delay moves to S1.

AC COUPLING (S1 only, derived): a step of V at the electrode decays with tau ~ 5.6 s (~8 % in 0.5 s);
a step down gives a -V transient. stator_detent.py's "~1 deg" expectation is outdated: a held step may
move the rotor tens of degrees (handoff, derived).

SAFETY: nothing touches hardware without --live. Refuses if the oscillator is on (DRVON, SIN/COS gains),
any offset is non-zero, LES/MON is not isolated, an input or OFFSET-enable bit is off (SW1R 4 and 8;
resting value 12), or a level is outside 0..12800 (V{n}_LIMIT; amp input 0-2.1 V). Outputs stay off
unless --enable-outputs; the output bit is set as sw2 | 1024 and the pre-run SW2 restored; a whole SW2
word is never composed. Ctrl-C ramps the offsets down before the switches (Ctrl-C again skips the wait).
"""
import argparse
import csv
import math
import os
import sys
import threading
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PREFIX = 'Y1:RDS-OUTS'
CHANS = (2, 4, 3)                 # A, B, C (stator_osc_drive.PHASE_ELECTRODES)
LIMIT = 12800.0
GPS_PV = 'Y1:DAQ-DC0_GPS'
SW1_INPUT_ON, SW1_OFFSET_ON, SW2_OUTPUT_ON = 4, 8, 1024
TRAMP_SETTLE = 1.0                # s after a TRAMP write before an OFFSET write it should shape (stator_detent.py)
TICK = 1.0 / 16


# ------------------------------------------------------------------------------------------- plan
def states(pattern, shape, L):
    if pattern == 'single':
        if shape == 'stair':
            lv = [L * k / 4 for k in (1, 2, 3, 4, 3, 2, 1, 0)]
        else:
            lv = [L, 0.0]
        return [(v, 0.0, 0.0) for v in lv]
    if pattern == 'all3':
        h = L / 2
        return [(L, h, 0.0), (0.0, L, h), (h, 0.0, L)]
    if pattern == 'stepper':
        return [(L, 0.0, 0.0), (0.0, L, 0.0), (0.0, 0.0, L)]
    raise ValueError(pattern)


def make_plan(patterns, rates, dur, level, shape='square', gap=2.0, lead=2.0, dither=True, seed=0):
    """Rows: block, pattern, rate, step, t (s from run start), V2, V4, V3. Each block ends at 0.

    dither: at rates <= 8/s each step is moved later by a random 0..125 ms (0..62.5 ms at 8/s; fixed seed, so
    the plan is reproducible), so the writes sample every phase of the 16 Hz tick, and of a 2-tick cycle. Without it, a regular schedule keeps
    nearly one phase against the ticks for a whole block (host and FE clocks differ by only ~1 ms/s), and
    the delay spread, the drift fit and the chance of a split are biased by that one phase.
    """
    rng = np.random.default_rng(seed)
    rows, t, b = [], lead, 0
    for p in patterns:
        seq = states(p, shape, level)
        for r in rates:
            n = max(2, int(round(dur * r)))
            for k in range(n):
                v = seq[k % len(seq)]
                dt = rng.random() * min(2 * TICK, 0.5 / r) if (dither and r <= 8 and 0 < k) else 0.0
                rows.append(dict(block=b, pattern=p, rate=r, step=k, t=round(t + k / r + dt, 6),
                                 V2=v[0], V4=v[1], V3=v[2]))
            rows.append(dict(block=b, pattern=p, rate=r, step=n, t=round(t + n / r, 6), V2=0.0, V4=0.0, V3=0.0))
            t += n / r + gap
            b += 1
    return rows


def field_states(n, L, rng, step_deg=15.0, min_change=0.1):
    """n random field directions, as feedback would write them: electrode k (A, B, C) = L/2 + L/2 cos(theta - k 120 deg),
    so 0..L. theta on a step_deg grid (a short list of values per channel, so the scorer can snap each OUT_DQ level to a
    commanded one). Every channel changes by >= min_change * L from one state to the next, so each update is visible on
    all three channels. Returns [(V2, V4, V3)], plus the angles."""
    grid = np.arange(0.0, 360.0, step_deg)
    def volts(th):
        return tuple(float(round(L / 2 + L / 2 * math.cos(math.radians(th - 120.0 * k)))) for k in range(3))
    out, ang, prev = [], [], None
    while len(out) < n:
        th = float(rng.choice(grid))
        v = volts(th)
        if prev is not None and min(abs(a - b) for a, b in zip(v, prev)) < min_change * L:
            continue
        out.append(v); ang.append(th); prev = v
    return out, ang


def make_field_plan(level, field_dur=240.0, cal_dur=30.0, cal_rates=(2.0, 4.0), gap=2.0, lead=2.0, seed=0):
    """The clean 8/s test (handoff, "8/s field test"): one block of random field directions on all three electrodes at
    exactly 8 steps/s, no dither, between dithered all3 calibration blocks at cal_rates (before, and reversed after).
    The calibration blocks fit host -> FE time (scorer); the host and FE clocks differ by ~1.2 ms/s (S0), so over
    field_dur = 240 s the writes slide ~0.3 s, i.e. through every position in the 125 ms intake window ~2 times."""
    rng = np.random.default_rng(seed)
    rows, t, b = [], lead, 0
    specs = [('all3', r, cal_dur, True) for r in cal_rates] + [('field', 8.0, field_dur, False)] + \
            [('all3', r, cal_dur, True) for r in cal_rates[::-1]]
    for p, r, dur, dith in specs:
        n = max(2, int(round(dur * r)))
        seq = field_states(n, level, rng)[0] if p == 'field' else states(p, 'square', level)
        for k in range(n):
            v = seq[k % len(seq)]
            dt = rng.random() * min(2 * TICK, 0.5 / r) if (dith and 0 < k) else 0.0
            rows.append(dict(block=b, pattern=p, rate=r, step=k, t=round(t + k / r + dt, 6), V2=v[0], V4=v[1], V3=v[2]))
        rows.append(dict(block=b, pattern=p, rate=r, step=n, t=round(t + n / r, 6), V2=0.0, V4=0.0, V3=0.0))
        t += n / r + gap
        b += 1
    return rows


def build_plan(a):
    if getattr(a, 'preset', None) == 'field8':
        return make_field_plan(a.level, field_dur=a.field_dur)
    return make_plan(a.patterns.split(','), [float(x) for x in a.rates.split(',')], a.dur, a.level, a.shape, a.gap,
                     dither=not a.no_dither)


def write_plan(rows, path):
    with open(path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def read_plan(path):
    rows = []
    for r in csv.DictReader(open(path)):
        rows.append(dict(block=int(r['block']), pattern=r['pattern'], rate=float(r['rate']), step=int(r['step']),
                         t=float(r['t']), V2=float(r['V2']), V4=float(r['V4']), V3=float(r['V3'])))
    return rows


def check_plan(rows):
    bad = [r for r in rows if any(not (0 <= r[f'V{n}'] <= LIMIT) for n in CHANS)]
    if bad:
        return f'{len(bad)} rows outside 0..{LIMIT:.0f} counts (first: {bad[0]})'
    if any(rows[i + 1]['t'] <= rows[i]['t'] for i in range(len(rows) - 1)):
        return 'times not increasing'
    return None


# ------------------------------------------------------------------------------------ EPICS layer
class Epics:
    """Thin pyepics wrapper; the mock below has the same interface."""

    def __init__(self):
        import epics
        self.e = epics
        self.now = time.time
        self.mons = []

    def get(self, pv):
        return self.e.caget(pv, timeout=3.0, use_monitor=False)   # fresh read, not a monitor cache

    def put(self, pv, val, wait=True):
        self.e.caput(pv, float(val), wait=wait, timeout=3.0)

    def flush(self):
        self.e.ca.flush_io()

    def sleep(self, s):
        if s > 0:
            time.sleep(s)

    def monitor(self, pv, cb):
        p = self.e.PV(pv, auto_monitor=True)
        if not p.wait_for_connection(timeout=3.0):
            print(f'  ! {pv} did not connect: no OUTMON record for it')
        p.add_callback(lambda value=None, **kw: cb(pv, self.now(), value))
        self.mons.append(p)

    def stop_monitors(self):
        for p in self.mons:
            p.clear_callbacks()


# --------------------------------------------------------------------------------------- run
def preflight(ep, rows):
    """Returns a list of refusals (empty = OK)."""
    no = []
    err = check_plan(rows)
    if err:
        no.append('plan: ' + err)
    drv = [ep.get(f'{PREFIX}_DRVON'), ep.get(f'{PREFIX}_DRV_SINGAIN'), ep.get(f'{PREFIX}_DRV_COSGAIN')]
    if any(v is None for v in drv) or any(abs(v) > 1e-6 for v in drv):
        no.append(f'oscillator not off (DRVON, SIN, COS = {drv}): python3 stator_osc_drive.py stop --live')
    offs = {n: ep.get(f'{PREFIX}_V{n}_OFFSET') for n in (1, 2, 3, 4)}
    if any(v is None or abs(v) > 1 for v in offs.values()):
        no.append(f'offsets not zero: {offs}. Something else is driving.')
    for n in CHANS:
        sw1 = ep.get(f'{PREFIX}_V{n}_SW1R')
        if sw1 is None or not (int(sw1) & SW1_INPUT_ON and int(sw1) & SW1_OFFSET_ON):
            no.append(f'V{n} SW1R = {sw1}: needs input (4) and OFFSET (8) on; resting value is 12')
        lim = ep.get(f'{PREFIX}_V{n}_LIMIT')
        if lim is None or abs(lim - LIMIT) > 1:
            no.append(f'V{n}_LIMIT = {lim}, expected {LIMIT:.0f}')
    for n, src in {2: 'LES_YAW', 3: 'LES_SUM', 4: 'MON'}.items():
        g, sw2 = ep.get(f'Y1:RDS-{src}_GAIN'), ep.get(f'Y1:RDS-{src}_SW2R')
        if g is None or sw2 is None or (abs(g) > 1e-6 and int(sw2) & SW2_OUTPUT_ON):
            no.append(f'V{n} <- {src} not isolated (GAIN {g}, SW2R {sw2}): switch its output off')
    return no


def cmd_run(a, ep=None):
    rows = read_plan(a.plan) if a.plan else build_plan(a)
    blocks = sorted({r['block'] for r in rows})
    T = rows[-1]['t']
    print('=' * 72)
    print(f'  voltage steps: {len(blocks)} blocks, {len(rows)} steps, {T / 60:.1f} min of stepping '
          f'+ {len(blocks) * TRAMP_SETTLE:.0f} s TRAMP checks + {a.release + 1:.0f} s ramp-down')
    for b in blocks:
        rb = [r for r in rows if r['block'] == b]
        print(f'    block {b:2d}  {rb[0]["pattern"]:8s} {rb[0]["rate"]:5g} steps/s  {len(rb):4d} steps  '
              f'max {max(max(r["V2"], r["V4"], r["V3"]) for r in rb):.0f} counts')
    print(f'  outputs {"ENABLED: steps reach the electrodes" if a.enable_outputs else "OFF: nothing reaches the chamber"}')
    print('=' * 72)
    if ep is None:
        if not a.live:
            err = check_plan(rows)
            print(f'  ! plan: {err}' if err else '  plan OK. Dry run: nothing written. Add --live to run.')
            return 0 if not err else 1
        try:
            ep = Epics()
        except ImportError:
            print('! pyepics not importable.'); return 1
    if a.release < 10:
        print('! --release under 10 s puts a large reverse pulse on the electrodes at the end.'); return 1
    no = preflight(ep, rows)
    if no:
        print('! refusing:\n    ' + '\n    '.join(no)); return 1

    os.makedirs(a.outdir, exist_ok=True)
    stamp = int(ep.now())
    rd = os.path.join(a.outdir, f'vsteps_{stamp}')
    os.makedirs(rd, exist_ok=True)
    write_plan(rows, os.path.join(rd, 'plan.csv'))
    meta = dict(level=a.level, release=a.release, outputs=int(a.enable_outputs), live=1, stamp=stamp)
    sw2_before = {n: int(ep.get(f'{PREFIX}_V{n}_SW2R') or 0) for n in (1, 2, 3, 4)}
    tramp_before = {n: float(ep.get(f'{PREFIX}_V{n}_TRAMP') or 0.0) for n in CHANS}
    with open(os.path.join(rd, 'meta.csv'), 'w') as fh:
        fh.write('key,value\n')
        for k, v in list(meta.items()) + [(f'sw2_before_V{n}', s) for n, s in sw2_before.items()] + \
                [(f'tramp_before_V{n}', s) for n, s in tramp_before.items()]:
            fh.write(f'{k},{v}\n')

    lock = threading.Lock()
    om = []
    def on_mon(pv, t, v):
        with lock:
            om.append((t, pv, v))
    for n in CHANS:
        ep.monitor(f'{PREFIX}_V{n}_OUTMON', on_mon)

    wf = open(os.path.join(rd, 'writes.csv'), 'w', buffering=1)
    wf.write('block,step,t_plan,host_t0,host_t1,late_ms,chans,V2,V4,V3,rb_ok\n')
    bf = open(os.path.join(rd, 'blocks.csv'), 'w', buffering=1)
    bf.write('block,pattern,rate,edge,host_a,fe_gps,host_b,tramp_found_V2,tramp_found_V4,tramp_found_V3\n')

    def gps_mark(b, rb, edge, found=('', '', '')):
        ha = ep.now(); g = ep.get(GPS_PV); hb = ep.now()
        bf.write(f'{b},{rb["pattern"]},{rb["rate"]},{edge},{ha:.6f},{g},{hb:.6f},{found[0]},{found[1]},{found[2]}\n')

    cur = {n: 0.0 for n in CHANS}
    interrupted = False
    try:
        if a.enable_outputs:
            print('\n  outputs on (offsets at 0, so no step):')
            for n in CHANS:
                if not sw2_before[n] & SW2_OUTPUT_ON:
                    ep.put(f'{PREFIX}_V{n}_SW2S', sw2_before[n] | SW2_OUTPUT_ON)
        t_start = ep.now() - rows[0]['t'] + 2.0     # first row starts 2 s after the first TRAMP check
        for b in blocks:
            rb = [r for r in rows if r['block'] == b]
            found = [float(ep.get(f'{PREFIX}_V{n}_TRAMP') or 0.0) for n in CHANS]
            if any(abs(x) > 1e-9 for x in found):
                for n in CHANS:
                    ep.put(f'{PREFIX}_V{n}_TRAMP', 0)
            ep.sleep(TRAMP_SETTLE)
            rb_tr = [float(ep.get(f'{PREFIX}_V{n}_TRAMP') or 0.0) for n in CHANS]
            if any(abs(x) > 1e-9 for x in rb_tr):
                print(f'  ! TRAMP reads {rb_tr} after setting 0: stopping.'); break
            # keep the plan's spacing but never start a block before its TRAMP check is done
            t_start = max(t_start, ep.now() + 0.5 - rb[0]['t'])
            gps_mark(b, rb[0], 'start', found)
            print(f'  block {b:2d}  {rb[0]["pattern"]:8s} {rb[0]["rate"]:5g}/s  TRAMP found {found}')
            for r in rb:
                due = t_start + r['t']
                ep.sleep(due - ep.now())
                ch = [n for n in CHANS if r[f'V{n}'] != cur[n]]
                t0 = ep.now()
                for n in ch:
                    ep.put(f'{PREFIX}_V{n}_OFFSET', r[f'V{n}'], wait=False)
                ep.flush()
                t1 = ep.now()
                for n in ch:
                    cur[n] = r[f'V{n}']
                ok = all(abs((ep.get(f'{PREFIX}_V{n}_OFFSET') or 0) - cur[n]) < 0.5 for n in ch)
                wf.write(f'{b},{r["step"]},{r["t"]:.6f},{t0:.6f},{t1:.6f},{1e3 * (t0 - due):.2f},'
                         f'{"".join(str(n) for n in ch)},{r["V2"]:g},{r["V4"]:g},{r["V3"]:g},{int(ok)}\n')
            gps_mark(b, rb[0], 'end')
    except KeyboardInterrupt:
        interrupted = True
        print('\n  interrupted: tearing down.')
    finally:
        print('\n  teardown:')
        # let the last writes be applied before any TRAMP change: S0 (11-09) showed writes applied on an 8 Hz grid,
        # and a TRAMP restore landing in the same applied tick as the final 0-write turned that step into a 1 s ramp
        ep.sleep(0.5)
        live = {n: ep.get(f'{PREFIX}_V{n}_OFFSET') for n in CHANS}
        t_rel = -1e18
        if any(abs(v or 0) > 0 for v in live.values()):
            for n in CHANS:
                ep.put(f'{PREFIX}_V{n}_TRAMP', a.release)
            try:
                ep.sleep(TRAMP_SETTLE)
            except KeyboardInterrupt:
                pass
            for n in CHANS:
                ep.put(f'{PREFIX}_V{n}_OFFSET', 0)
            t_rel = ep.now()
            remaining = t_rel + a.release + 1 - ep.now()
            print(f'    offsets ramping to 0 over {a.release:g} s; waiting before any switch'
                  f'{" (Ctrl-C again to skip: the switch then cuts a partly ramped offset)" if interrupted else ""}')
            try:
                ep.sleep(remaining)
            except KeyboardInterrupt:
                print('    skipped the wait.')
        if a.enable_outputs:
            for n in CHANS:     # restore only the output bit, from the live word
                sw2 = int(ep.get(f'{PREFIX}_V{n}_SW2R') or 0)
                want = (sw2 & ~SW2_OUTPUT_ON) | (sw2_before[n] & SW2_OUTPUT_ON)
                if want != sw2:
                    ep.put(f'{PREFIX}_V{n}_SW2S', want)
        for n, t in sorted(tramp_before.items()):
            ep.put(f'{PREFIX}_V{n}_TRAMP', t)
        ep.sleep(1.0)
        ep.stop_monitors()
        wf.close(); bf.close()
        with lock, open(os.path.join(rd, 'outmon.csv'), 'w') as fh:
            fh.write('host_t,chan,value\n')
            for t, pv, v in om:
                fh.write(f'{t:.6f},{pv.split("_V")[1].split("_")[0]},{v}\n')
        left = {n: ep.get(f'{PREFIX}_V{n}_OFFSET') for n in (1, 2, 3, 4)}
        on = [n for n in (1, 2, 3, 4) if int(ep.get(f'{PREFIX}_V{n}_SW2R') or 0) & SW2_OUTPUT_ON]
        tr = {n: ep.get(f'{PREFIX}_V{n}_TRAMP') for n in CHANS}
        print(f'  offsets {left} | outputs on: {on or "none"} | TRAMP restored {tr}')
        print(f'  run dir -> {rd}\n  next: python3 voltage_steps.py fetch {rd}   (after ~2 min, for frames)')
    return 0 if not interrupted else 1


# ------------------------------------------------------------------------------------- fetch
def cmd_fetch(a):
    """OUT_DQ of V2, V3, V4 over the run (FE GPS from blocks.csv, padded 30 s) -> RUNDIR/out_dq.npz."""
    import nds2
    g = [float(r['fe_gps']) for r in csv.DictReader(open(os.path.join(a.rundir, 'blocks.csv')))
         if r['fe_gps'] not in ('', 'None')]
    if not g:
        sys.exit('! no front-end GPS readings in blocks.csv: read Y1:DAQ-DC0_GPS by hand and fetch over the run')
    s, e = int(min(g)) - 30, int(max(g)) + 30
    conn = nds2.connection('cymac1', 8088)
    conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')
    conn.set_parameter('GAP_HANDLER', 'STATIC_HANDLER_NAN')
    d = {}
    for buf in conn.fetch(s, e, [f'{PREFIX}_V{n}_OUT_DQ' for n in CHANS]):
        n = int(buf.channel.name.split('_V')[1].split('_')[0])
        d[f'V{n}'] = np.asarray(buf.data, float)
        fs = float(buf.channel.sample_rate)
        g0 = float(buf.gps_seconds) + buf.gps_nanoseconds * 1e-9
    out = os.path.join(a.rundir, 'out_dq.npz')
    np.savez(out, gps0=g0, fs=fs, **d)
    print(f'  OUT_DQ V2, V3, V4 FE {s}-{e} ({fs:g} Hz) -> {out}')
    return 0


# ------------------------------------------------------------------------------- mock front end
class MockFE:
    """Virtual-time front end: EPICS writes are applied at 16 Hz ticks of the FE clock.

    modes: 'tick' (every tick), 'every2' (every 2nd tick, F3's behaviour), 'late3' (V3 lands one tick
    after the others). FE time = host - GPS_UNIX + offset, running `drift` fast. OUTMON updates at
    each tick that changes the value, `epics_ms` later in host time. Writes cost put_ms each.
    """
    GPS_UNIX = 315964800 - 18

    def __init__(self, mode='tick', seed=0, offset=15380.9, drift=1.1e-3, latency=0.004, put_ms=0.35,
                 jitter_ms=1.5, epics_ms=3.0, ring=True):
        self.rng = np.random.default_rng(seed)
        self.mode, self.offset, self.drift, self.lat, self.ring = mode, offset, drift, latency, ring
        self.put_s, self.jit, self.ep_s = put_ms * 1e-3, jitter_ms * 1e-3, epics_ms * 1e-3
        self.t = 1793650000.0 + self.rng.random()
        self.h0 = self.t
        self.phase = self.rng.random() * TICK         # tick phase in FE time
        self.pv = {f'{PREFIX}_DRVON': 0, f'{PREFIX}_DRV_SINGAIN': 0, f'{PREFIX}_DRV_COSGAIN': 0, GPS_PV: 0}
        for n in (1, 2, 3, 4):
            self.pv.update({f'{PREFIX}_V{n}_OFFSET': 0.0, f'{PREFIX}_V{n}_SW1R': 12, f'{PREFIX}_V{n}_SW2R': 1792,
                            f'{PREFIX}_V{n}_TRAMP': 1.0, f'{PREFIX}_V{n}_LIMIT': LIMIT})
        for s in ('LES_YAW', 'LES_SUM', 'MON'):
            self.pv.update({f'Y1:RDS-{s}_GAIN': 1.0, f'Y1:RDS-{s}_SW2R': 768})
        self.writes = []          # (host_t, chan, value)
        self.cb = []

    def fe(self, h):
        return (h - self.GPS_UNIX + self.offset) + self.drift * (h - self.h0)

    def host(self, f):
        # inverse of fe() (linear)
        return (f - self.offset + self.GPS_UNIX + self.drift * self.h0) / (1 + self.drift)

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += max(s, 0) + self.rng.random() * self.jit

    def get(self, pv):
        self.t += 0.0005
        if pv == GPS_PV:
            return float(math.floor(self.fe(self.t)))
        return self.pv.get(pv)

    def put(self, pv, val, wait=True):
        self.t += self.put_s
        if pv.endswith('_SW2S'):
            pv = pv[:-1] + 'R'
        self.pv[pv] = val
        if pv.endswith('_OFFSET'):
            self.writes.append((self.t, int(pv.split('_V')[1].split('_')[0]), float(val)))

    def flush(self):
        self.t += 0.0002

    def monitor(self, pv, cb):
        self.cb.append((pv, cb))

    def stop_monitors(self):
        """Emit the OUTMON updates the run would have seen (from the applied series)."""
        for pv, cb in self.cb:
            n = int(pv.split('_V')[1].split('_')[0])
            for f, v in self.applied(n):
                cb(pv, self.host(f) + self.ep_s, v)

    def _tick_after(self, f, n):
        k = math.ceil((f - self.phase) / TICK)
        if self.mode == 'every2' and k % 2:
            k += 1
        if self.mode == 'late3' and n == 3:
            k += 1
        return self.phase + k * TICK

    def applied(self, n):
        """(FE time, value) at each tick where channel n's applied value changes; last write before a tick wins."""
        out, last = [], 0.0
        ws = [(self._tick_after(self.fe(h) + self.lat, n), v) for h, c, v in self.writes if c == n]
        i = 0
        while i < len(ws):
            j = i
            while j + 1 < len(ws) and ws[j + 1][0] == ws[i][0]:
                j += 1
            if ws[j][1] != last:
                out.append((ws[j][0], ws[j][1])); last = ws[j][1]
            i = j + 1
        return out

    def out_dq(self, fs=1024.0, pad=5.0):
        f0 = math.floor(self.fe(self.h0)) - pad
        n = int((self.fe(self.t) + pad - f0) * fs)
        tf = f0 + np.arange(n) / fs
        d = {}
        for c in CHANS:
            ap = self.applied(c)
            x = np.zeros(n)
            for f, v in ap:
                x[tf >= f - 1e-9] = v
            d[f'V{c}'] = np.convolve(x, np.diff(self.step_resp(), prepend=0.0))[:n] if self.ring else x
        return dict(gps0=f0, fs=fs, **d)

    @staticmethod
    def step_resp():
        """OUT_DQ step response measured 2026-11-09 (S0, V2's first 0 -> 800 edge, normalised): ~18 % overshoot,
        alternating ringing, settled to < 0.1 % after ~35 samples. Assumed to be the DQ decimation filter, i.e. a
        recording artefact: whether the DAC/electrode edge rings is for the S1 scope to show."""
        return np.array([0.0272, 0.4596, 1.1806, 1.0174, 0.9521, 1.0710, 0.9298, 1.0549, 0.9606, 1.0266, 0.9833, 1.0088,
                         0.9976, 0.9969, 1.0072, 0.9898, 1.0117, 0.9879, 1.0113, 0.9901, 1.0078, 0.9943, 1.0035, 0.9984,
                         0.9998, 1.0014, 0.9976, 1.0029, 0.9969, 1.0029, 0.9973, 1.0022, 0.9983, 1.0011, 0.9994, 1.0001,
                         1.0002, 0.9994, 1.0007, 0.9992, 1.0007, 0.9993, 1.0006, 0.9995, 1.0003, 0.9998] + [1.0] * 18)


def mock_run(rundir, mode='tick', patterns='single,all3,stepper', rates='1,2,4,8,16,32', dur=8.0, shape='square',
             seed=0, level=3200.0, preset=None, field_dur=240.0):
    """Run cmd_run against MockFE; write out_dq.npz. Returns the run dir."""
    fe = MockFE(mode, seed)
    a = argparse.Namespace(plan=None, patterns=patterns, rates=rates, dur=dur, level=level, shape=shape, gap=2.0,
                           outdir=rundir, live=True, enable_outputs=False, release=20.0, no_dither=False,
                           preset=preset, field_dur=field_dur)
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        cmd_run(a, ep=fe)
    rd = sorted(d for d in os.listdir(rundir) if d.startswith('vsteps_'))[-1]
    rd = os.path.join(rundir, rd)
    np.savez(os.path.join(rd, 'out_dq.npz'), **fe.out_dq())
    return rd, fe


def selftest():
    import tempfile
    ok = True
    rows = make_plan(['single', 'all3', 'stepper'], [1, 2, 4, 8, 16, 32], 20, 3200)
    T = rows[-1]['t']
    print(f'default plan: {len(rows)} steps, {T / 60:.1f} min; check_plan -> {check_plan(rows)}')
    ok &= check_plan(rows) is None and 6 < T / 60 < 8
    ok &= check_plan(make_plan(['single'], [1], 4, 13000)) is not None
    fr = make_field_plan(3200)
    fb = [r for r in fr if r['pattern'] == 'field']
    dts = np.diff([r['t'] for r in fb])
    chg = min(min(abs(fb[i + 1][f'V{n}'] - fb[i][f'V{n}']) for n in CHANS) for i in range(len(fb) - 2))
    print(f'field8 plan: {len(fr)} steps, {fr[-1]["t"] / 60:.1f} min; field block {len(fb)} steps, spacing '
          f'{dts.min() * 1e3:.3f}-{dts.max() * 1e3:.3f} ms, smallest per-channel change {chg:.0f} counts; check_plan -> {check_plan(fr)}')
    ok &= check_plan(fr) is None and np.allclose(dts, 0.125) and chg >= 320 and len(fb) == 1921
    fe = MockFE()
    fe.pv[f'{PREFIX}_V3_SW1R'] = 4
    fe.pv[f'{PREFIX}_DRVON'] = 1
    no = preflight(fe, rows)
    print(f'preflight with DRVON=1 and V3 OFFSET bit off -> {len(no)} refusals')
    ok &= len(no) == 2
    with tempfile.TemporaryDirectory() as d:
        rd, fe = mock_run(d)
        w = list(csv.DictReader(open(os.path.join(rd, 'writes.csv'))))
        bl = list(csv.DictReader(open(os.path.join(rd, 'blocks.csv'))))
        om = list(csv.DictReader(open(os.path.join(rd, 'outmon.csv'))))
        late = max(float(r['late_ms']) for r in w)
        burst = np.median([1e3 * (float(r['host_t1']) - float(r['host_t0'])) for r in w if len(r['chans']) == 3])
        print(f'mock run: {len(w)} write bursts, {len(bl)} block marks, {len(om)} OUTMON updates, '
              f'max lateness {late:.1f} ms, 3-channel burst {burst:.2f} ms; offsets at end {[fe.pv[f"{PREFIX}_V{n}_OFFSET"] for n in CHANS]}, '
              f'TRAMP restored {[fe.pv[f"{PREFIX}_V{n}_TRAMP"] for n in CHANS]}')
        ok &= len(bl) == 36 and late < 10 and all(fe.pv[f'{PREFIX}_V{n}_OFFSET'] == 0 for n in CHANS)
        ok &= all(fe.pv[f'{PREFIX}_V{n}_TRAMP'] == 1.0 for n in CHANS) and all(r['rb_ok'] == '1' for r in w)
        st = [r['tramp_found_V2'] for r in bl if r['edge'] == 'start']
        print(f'TRAMP found at block starts: {st[0]} then {set(st[1:])} (mock keeps 0 once set)')
        ok &= st[0] == '1.0' and set(st[1:]) == {'0.0'}
    print('SELFTEST %s' % ('PASSED' if ok else 'FAILED'))
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sp = p.add_subparsers(dest='cmd', required=True)

    def plan_opts(q):
        q.add_argument('--patterns', default='single,all3,stepper')
        q.add_argument('--rates', default='1,2,4,8,16,32', help='requested steps/s')
        q.add_argument('--dur', type=float, default=20.0, help='s per block')
        q.add_argument('--level', type=float, default=3200.0, help='counts')
        q.add_argument('--shape', default='square', choices=('square', 'stair'), help='single-electrode pattern')
        q.add_argument('--gap', type=float, default=2.0, help='s at 0 between blocks')
        q.add_argument('--no-dither', action='store_true', help='regular schedule at <= 8 steps/s too')
        q.add_argument('--preset', choices=('field8',), help='field8: the clean 8/s test (random field directions, '
                       'all three electrodes, exactly 8/s, between dithered all3 calibration blocks); ignores '
                       '--patterns/--rates/--dur/--shape/--gap')
        q.add_argument('--field-dur', type=float, default=240.0, help='s, field8 only: length of the 8/s block')
    q = sp.add_parser('plan'); plan_opts(q); q.add_argument('--out', default='voltage_steps_plan.csv')
    q = sp.add_parser('run'); plan_opts(q)
    q.add_argument('--plan', help='plan CSV (overrides the plan options)')
    q.add_argument('--outdir', default='voltage_steps_runs')
    q.add_argument('--release', type=float, default=20.0, help='s, end-of-run offset ramp (>= 10)')
    q.add_argument('--live', action='store_true')
    q.add_argument('--enable-outputs', action='store_true')
    q = sp.add_parser('fetch'); q.add_argument('rundir')
    sp.add_parser('selftest')
    a = p.parse_args()
    if a.cmd == 'plan':
        rows = build_plan(a)
        err = check_plan(rows)
        if err:
            sys.exit('! ' + err)
        write_plan(rows, a.out)
        print(f'{len(rows)} steps, {rows[-1]["t"] / 60:.1f} min -> {a.out}')
        return 0
    if a.cmd == 'run':
        return cmd_run(a)
    if a.cmd == 'fetch':
        return cmd_fetch(a)
    return selftest()


if __name__ == '__main__':
    sys.exit(main())
