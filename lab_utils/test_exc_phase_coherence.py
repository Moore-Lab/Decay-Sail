#!/usr/bin/env python3
"""Does a multi-channel _EXC excitation hold its COMMANDED relative phase?

This is a gate, not a drive. It answers exactly one binary question:

    If we ask for three sinusoids at one frequency with relative phases
    0 / -120 / -240 deg on V2_EXC, V4_EXC, V3_EXC, do we MEASURE
    -120.0 / -120.0 at the electrodes?

Everything about the "front-end generated, therefore smooth" drive route
depends on that and nothing else does. If it passes, the AC half of the drive
moves to _EXC (front end, 2048 Hz, genuinely smooth) while the DC pedestal
stays on _OFFSET, which is the split the m=8 torque channel wants anyway
(tau_m8 ~ V_dc * V_ac). If it fails, we stay on the _OFFSET write loop with
TRAMP = 1/rate and accept a first-order hold.

WHY THIS IS IN DOUBT -- read awg.py:128 before assuming it works:

    if self.starttime == 0:
        starttime_nsec = awgbase.GPSnow() + 4*awgbase._EPOCH
        for comp in self.components:
            if comp.start == 0:
                comp.start = int(starttime_nsec)

`_EPOCH` is 1/16 s, so an excitation created with start=0 begins at "whenever
GPSnow() was when .start() happened, plus 250 ms". Three separate .start()
calls therefore pick THREE DIFFERENT start times, and the relative phase is
randomised by however long the Python interpreter took between calls. Passing
one explicit `start` to all three is what makes them coherent -- the loop above
only overwrites `comp.start` when it is 0.

AND THERE IS A CLOCK-FRAME TRAP ON TOP OF THAT. `awgbase.GPSnow()` returns
TRUE GPS; the front end runs FAST of it (8374.9 s on 2026-08-28, up from 7630 s
on 08-21 and 5836 s on 06-03 -- it drifts, so re-measure, do not reuse this
number). A start time computed from GPSnow() is therefore ~2.3 hours in the
front end's past. What the front end does with a past start is not documented
anywhere we can find, which is the whole reason this script exists rather than
an argument in a markdown file. Hence --start-mode:

    shared-true   one explicit start from GPSnow() + lead, shared by all tones.
                  In the FE's frame this is in the past.
    shared-fe     one explicit start in the FRONT END's frame (GPSnow() + the
                  measured offset + lead), so it is genuinely in the future
                  where the FE is concerned. Uses wait=False -- otherwise
                  awg.start() would sleep for the whole clock offset.
    independent   start=0 on every tone: the failure mode above, included so
                  the test can demonstrate the difference rather than assert it.

Relative phase is all that matters for a rotating field -- the absolute phase
only decides which detent the rotor lands in at t=0.

Nothing touches hardware without --live.
"""

import argparse
import math
import sys
import time

import numpy as np

try:
    from epics import caget, caput
except ImportError:
    caget = caput = None

PREFIX = 'Y1:RDS-OUTS'
DAQ_GPS_PV = 'Y1:DAQ-DC0_GPS'

# A, B, C -- same map as stator_epics_drive.py, confirmed 2026-08-24.
DEFAULT_ELECTRODES = (2, 4, 3)
PHASE_NAMES = ('A', 'B', 'C')

SW1_INPUT_ON = 4
SW2_OUTPUT_ON = 1024

NDS_HOST, NDS_PORT = 'cymac1', 8088


# ===========================================================================
def snapshot(electrodes):
    """Record everything we are about to change, so it can be put back."""
    state = {}
    for n in electrodes:
        b = f'{PREFIX}_V{n}'
        state[n] = {s: caget(f'{b}_{s}') for s in
                    ('GAIN', 'OFFSET', 'TRAMP', 'SW1R', 'SW2R')}
    return state


def setup(electrodes, state, dry):
    """Aaron's verified recipe (labutils measure_actuator_gain.py): GAIN = 1,
    module INPUT off, module OUTPUT on.

    Turning the input OFF is not incidental here. Each electrode has a signal
    summed in ahead of its filter module (V1<-LES_PIT, V2<-LES_YAW,
    V3<-LES_SUM, V4<-MON, traced from y1rds.mdl), and LES_PIT/LES_YAW are live.
    _EXC is injected at the module, so switching the input off both follows
    Aaron's recipe and keeps LES out of the measurement.
    """
    for n in electrodes:
        b = f'{PREFIX}_V{n}'
        sw1 = int(state[n]['SW1R'])
        sw2 = int(state[n]['SW2R'])
        writes = [(f'{b}_GAIN', 1.0)]
        if sw1 & SW1_INPUT_ON:
            writes.append((f'{b}_SW1S', float(sw1 & ~SW1_INPUT_ON)))
        if not sw2 & SW2_OUTPUT_ON:
            writes.append((f'{b}_SW2S', float(sw2 | SW2_OUTPUT_ON)))
        for pv, v in writes:
            print(f'    {"[dry] " if dry else ""}{pv} <- {v:g}')
            if not dry:
                caput(pv, v, wait=True, timeout=2.0)


def restore(state, dry):
    for n, s in state.items():
        b = f'{PREFIX}_V{n}'
        for key, pv in (('GAIN', f'{b}_GAIN'), ('OFFSET', f'{b}_OFFSET'),
                        ('TRAMP', f'{b}_TRAMP'), ('SW1R', f'{b}_SW1S'),
                        ('SW2R', f'{b}_SW2S')):
            if s[key] is None:
                continue
            if not dry:
                caput(pv, float(s[key]), wait=True, timeout=2.0)
    print('  module state restored.')


# ===========================================================================
def fit_phase(x, fs, freq):
    """Least-squares fit of A*cos + B*sin at one frequency.

    A single-bin FFT would leak unless the capture is an exact integer number
    of cycles, and at 0.16 Hz over ~60 s it never is. The fit does not care.
    Returns (amplitude, phase_deg) with phase measured on cos.
    """
    t = np.arange(len(x)) / fs
    w = 2 * math.pi * freq
    M = np.column_stack([np.cos(w * t), np.sin(w * t), np.ones_like(t)])
    a, b, _ = np.linalg.lstsq(M, x, rcond=None)[0]
    return math.hypot(a, b), math.degrees(math.atan2(-b, a))


def capture(electrodes, gps_start, seconds):
    import nds2
    chans = [f'{PREFIX}_V{n}_OUT_DQ' for n in electrodes]
    conn = nds2.connection(NDS_HOST, NDS_PORT)
    conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')
    out = {}
    for buf in conn.fetch(int(gps_start), int(gps_start + seconds), chans):
        n = int(buf.channel.name.split('_V')[1].split('_')[0])
        out[n] = (np.array(buf.data, dtype=float), float(buf.channel.sample_rate))
    return out


# ===========================================================================
def main():
    p = argparse.ArgumentParser(
        description='Test whether multi-channel _EXC holds commanded relative phase.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--live', action='store_true',
                   help='actually drive (default is a dry run)')
    p.add_argument('--electrodes', default=','.join(map(str, DEFAULT_ELECTRODES)),
                   help='comma-separated V{n} for phases A,B,C '
                        f'(default {",".join(map(str, DEFAULT_ELECTRODES))})')
    p.add_argument('--freq', type=float, default=0.16,
                   help='ELECTRICAL frequency, Hz (default 0.16 = the 08-24 run)')
    p.add_argument('--ampl', type=float, default=500.0,
                   help='amplitude per channel, counts (default 500 ~ 6.7 V, '
                        'deliberately far below the 6400/85 V working point -- '
                        'this measures phase, it is not a torque test)')
    p.add_argument('--duration', type=float, default=120.0,
                   help='injection length, s (default 120)')
    p.add_argument('--start-mode', default='shared-fe',
                   choices=('shared-fe', 'shared-true', 'independent'),
                   help='how the excitation start time is chosen (see module '
                        'docstring). Default shared-fe.')
    p.add_argument('--lead', type=float, default=5.0,
                   help='seconds of lead before the shared start (default 5)')
    p.add_argument('--nds-lag', type=float, default=30.0,
                   help='seconds to wait after the run before fetching, so the '
                        'DAQ has written the frames (default 30)')
    p.add_argument('--settle', type=float, default=10.0,
                   help='seconds to skip at each end before fitting (default 10)')
    args = p.parse_args()

    electrodes = [int(s) for s in args.electrodes.split(',')]
    if len(electrodes) < 2:
        raise SystemExit('need at least two electrodes to measure a relative phase')
    commanded = [0.0, -120.0, -240.0][:len(electrodes)]
    dry = not args.live

    print('DRY RUN -- no hardware will be touched. Pass --live to drive.\n' if dry
          else 'LIVE\n')
    print('=' * 70)
    for name, n, ph in zip(PHASE_NAMES, electrodes, commanded):
        print(f'  phase {name}  V{n}_EXC   {args.ampl:.0f} counts   '
              f'commanded {ph:+.1f} deg')
    print(f'  f_elec {args.freq} Hz  ->  f_mech {args.freq / 8:.5f} Hz  '
          f'(rotor speed = f_elec / 8)')
    print(f'  duration {args.duration:.0f} s   start-mode {args.start_mode}')
    print('=' * 70)

    if caget is None:
        print('! pyepics not importable -- cannot read or drive.')
        return 1

    import awg, awgbase

    true_gps = awgbase.GPSnow() / 1e9
    fe_gps = caget(DAQ_GPS_PV)
    offset = fe_gps - true_gps
    print(f'\n  true GPS (awgbase)  {true_gps:.3f}')
    print(f'  front-end GPS       {fe_gps:.3f}')
    print(f'  front end is        {offset:+.1f} s ahead  '
          f'(re-measured now; it drifts -- do not reuse a stored value)')

    state = snapshot(electrodes)
    print('\n  module state before:')
    for n in electrodes:
        s = state[n]
        print(f'    V{n}: GAIN {s["GAIN"]:g}  OFFSET {s["OFFSET"]:g}  '
              f'TRAMP {s["TRAMP"]:g}  SW1R {s["SW1R"]:.0f}  SW2R {s["SW2R"]:.0f}')

    print('\n  setup:')
    setup(electrodes, state, dry)

    if args.start_mode == 'independent':
        start_ns = 0
    elif args.start_mode == 'shared-true':
        start_ns = int((true_gps + args.lead) * 1e9)
    else:                                   # shared-fe
        start_ns = int((true_gps + offset + args.lead) * 1e9)
    print(f'\n  start (ns, 0 = each tone picks its own): {start_ns}')

    exc = [awg.Sine(f'{PREFIX}_V{n}_EXC', ampl=args.ampl, freq=args.freq,
                    phase=math.radians(ph), start=start_ns,
                    duration=args.duration)
           for n, ph in zip(electrodes, commanded)]

    capture_start = None
    try:
        if dry:
            print('\n  [dry-run] would start '
                  f'{len(exc)} excitations and capture {args.duration:.0f} s.')
            print('  Re-run with --live to actually measure.')
            return 0

        print('\n  starting excitations...')
        for e in exc:
            # wait=False: with shared-fe the start is ~offset seconds in the
            # future by GPSnow()'s reckoning, so waiting would sleep for hours.
            e.start(ramptime=0, wait=False)
        capture_start = caget(DAQ_GPS_PV) + args.settle
        print(f'  running {args.duration:.0f} s '
              f'(capture from front-end GPS {capture_start:.0f})')
        time.sleep(args.duration + 2)
    finally:
        for e in exc:
            try:
                e.stop(ramptime=0, wait=False)
            except Exception as err:
                print(f'  ! stopping excitation: {err}')
        restore(state, dry)

    span = args.duration - 2 * args.settle
    # NDS writes frames behind real time (~15 s observed). The last sample we
    # want is only ~12 s old when the run ends, so fetching immediately races
    # the frame writer and returns a gap or an error. Wait it out, then retry.
    print(f'\n  waiting {args.nds_lag:.0f} s for NDS frames to land...')
    time.sleep(args.nds_lag)
    data = {}
    for attempt in range(1, 5):
        try:
            data = capture(electrodes, capture_start, span)
            break
        except Exception as err:
            print(f'  fetch attempt {attempt} failed ({err}); retrying in 15 s')
            time.sleep(15)
    if not data:
        print('! could not fetch the capture. The excitation ran and the module\n'
              f'  state is restored -- re-fetch by hand from front-end GPS '
              f'{capture_start:.0f} for {span:.0f} s.')
        return 1

    print(f'\n  {"chan":>6} {"amplitude":>12} {"phase":>10} '
          f'{"rel":>10} {"commanded":>11} {"error":>9}')
    ref_phase = ref_amp = None
    errors = []
    for name, n, cmd in zip(PHASE_NAMES, electrodes, commanded):
        if n not in data:
            print(f'    V{n}: no data returned')
            continue
        x, fs = data[n]
        amp, ph = fit_phase(x, fs, args.freq)
        if ref_phase is None:
            ref_phase, ref_amp = ph, amp
        rel = (ph - ref_phase + 180) % 360 - 180
        err = (rel - cmd + 180) % 360 - 180
        errors.append(err)
        print(f'  {name} V{n} {amp:12.1f} {ph:+9.2f}d {rel:+9.2f}d '
              f'{cmd:+10.1f}d {err:+8.2f}d')

    if ref_amp:
        spread = max(abs(fit_phase(data[n][0], data[n][1], args.freq)[0] / ref_amp - 1)
                     for n in electrodes if n in data)
        print(f'\n  amplitude spread {100 * spread:.2f}%')
    worst = max(abs(e) for e in errors) if errors else None
    if worst is not None:
        print(f'  worst phase error {worst:.2f} deg')
        print('\n  ' + ('PASS -- relative phase is controlled; the _EXC route works.'
                        if worst < 5.0 else
                        'FAIL -- commanded relative phase did not survive. Try a '
                        'different\n  --start-mode before concluding the route is '
                        'dead.'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
