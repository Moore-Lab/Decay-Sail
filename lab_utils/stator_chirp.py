#!/usr/bin/env python3
"""Phase-continuous frequency sweep for the three-phase stator, via stepped AWG.

Two jobs, same machinery:

  down   Autoresonant PUMP. Chirp f_elec DOWNWARD from the rotor's libration
         line to drive the libration to large amplitude and over the barrier.
  up     SPIN-UP. Ramp f_elec upward once the rotor is rotating.

WHY STEPPED SEGMENTS RATHER THAN awg.SweptSine

    class SweptSine(Sine):
        def __init__(self, chan, ampl1=0, freq1=0, ..., sweeptime=0):
            Sine.__init__(self, chan, ..., duration=sweeptime, restart=sweeptime)

`restart=sweeptime` makes the sweep LOOP -- it ramps freq1->freq2 then snaps
back to freq1 and starts over. Right for DTT's repeated swept-sine measurements,
fatal for a spin-up: the snap-back is a phase discontinuity that drops the rotor.
So we build the sweep from short fixed-frequency Sine segments and carry the
phase across each boundary ourselves.

THE PHASE BOOKKEEPING

Segment k starts at T_k, runs at f_k, and is created with phase phi_k. The
instantaneous argument is 2*pi*f_k*(t - T_k) + phi_k, so continuity at the
handoff to segment k+1 requires

    phi_{k+1} = phi_k + 2*pi*f_k*(T_{k+1} - T_k)

evaluated mod 2*pi. Each phase electrode carries its own fixed 120 deg offset on
top, so the three stay locked to each other throughout. Frequency still STEPS at
each boundary -- only the phase is continuous -- so keep --step small compared
with the capture bandwidth or the rotor will not follow the jump.

WHY DOWNWARD, FOR THE PUMP

The libration well is anharmonic: measured 0.660 Hz at small amplitude and
0.25-0.33 Hz at large, i.e. the frequency FALLS as the amplitude grows, reaching
zero at the separatrix. So a fixed-frequency kick detunes itself exactly as it
starts working -- observed 2026-08-28: a 90 s kick at 0.296 Hz moved the line
0.2704 -> 0.2531 and gained only 3.5% in amplitude, ending ~15% mistuned.
Chirping DOWN follows the resonance instead of walking away from it, and the
oscillator phase-locks to the descending drive (autoresonance). With damping
times of hours there is nothing to bleed off the energy, so even a drive much
weaker than the trap can pump indefinitely -- it just takes longer.

CLOCK FRAME -- the thing that makes AWG work here at all:

    start must be in the FRONT END's frame, Y1:DAQ-DC0_GPS + lead,
    NOT awgbase.GPSnow().

The front end runs ~8376 s fast (drifting), so awg.py:128's default start of
GPSnow()+250ms lands hours in its past and the excitation silently never plays.
Re-measured every segment here, never stored.

Nothing touches hardware without --live.
"""

import argparse
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stator_awg_drive import (PREFIX, PHASE_ELECTRODES, PHASE_NAMES, M_DRIVE,
                              MAX_TOTAL_COUNTS, VOLTS_PER_COUNT,
                              snapshot, setup, restore, gps_now_fe, les_report)

try:
    from epics import caget, caput
except ImportError:
    caget = caput = None

LES_CHAN = 'Y1:RDS-LES_YAW_OUT_DQ'


def libration_freq(x, fs, lo=0.05, hi=1.5):
    ac = x - x.mean()
    X = np.abs(np.fft.rfft(ac * np.hanning(len(ac))))
    fr = np.fft.rfftfreq(len(ac), 1 / fs)
    m = (fr > lo) & (fr < hi)
    i = np.flatnonzero(m)[np.argmax(X[m])]
    y0, y1, y2 = X[i - 1], X[i], X[i + 1]
    den = y0 - 2 * y1 + y2
    d = 0.5 * (y0 - y2) / den if den else 0.0
    return fr[i] + d * (fr[1] - fr[0])


def read_les(gps_a, gps_b):
    import nds2
    conn = nds2.connection('cymac1', 8088)
    conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')
    buf = conn.fetch(int(gps_a), int(gps_b), [LES_CHAN])[0]
    return np.array(buf.data, float), float(buf.channel.sample_rate)


def phase_offsets(reverse):
    """A/B/C offsets. Negated relative to the intuitive order because awg's
    `phase` enters with the opposite sign to the _OFFSET path -- measured
    2026-08-28, see stator_awg_drive.build()."""
    return [0.0, 4 * math.pi / 3, 2 * math.pi / 3] if reverse else \
           [0.0, 2 * math.pi / 3, 4 * math.pi / 3]


def run_sweep(electrodes, amp, f_start, f_end, total, step_s, lead, reverse, dry):
    """Walk f_elec from f_start to f_end in phase-continuous segments."""
    import awg
    offs = phase_offsets(reverse)
    n = max(1, int(round(total / step_s)))
    freqs = np.linspace(f_start, f_end, n)
    print(f'\n  {n} segments of {step_s:.1f} s, f_elec {f_start:.4f} -> {f_end:.4f} Hz')
    print(f'  step size {abs(freqs[1] - freqs[0]) if n > 1 else 0:.5f} Hz per segment')
    if dry:
        print(f'  [dry] would run {total / 60:.1f} min.')
        return None, None

    phi = 0.0                       # accumulated phase of the reference channel
    t_prev = None
    first_start = None
    live = []
    try:
        for k, f in enumerate(freqs):
            t_k = gps_now_fe() + lead
            if t_prev is not None:
                # carry the phase across the boundary
                phi = (phi + 2 * math.pi * freqs[k - 1] * (t_k - t_prev)) % (2 * math.pi)
            t_prev = t_k
            if first_start is None:
                first_start = t_k
            start_ns = int(t_k * 1e9)
            exc = [awg.Sine(f'{PREFIX}_V{e}_EXC', ampl=amp, freq=float(f),
                            phase=phi + o, start=start_ns,
                            duration=step_s + lead + 1)
                   for e, o in zip(electrodes, offs)]
            for x in exc:
                x.start(ramptime=0, wait=False)
            # overlap the previous segment out only after the new one is armed,
            # so the electrodes are never unpowered mid-sweep
            for x in live:
                try:
                    x.stop(ramptime=0, wait=True)
                except Exception:
                    pass
            live = exc
            if k % max(1, n // 12) == 0 or k == n - 1:
                print(f'    seg {k + 1:3d}/{n}  f_elec {f:.4f} Hz  '
                      f'(rotor {f / M_DRIVE:.5f} Hz)  phi {math.degrees(phi):6.1f} deg')
            time.sleep(lead + step_s)
    except KeyboardInterrupt:
        print('\n  interrupted.')
    finally:
        for x in live:
            try:
                # wait=True RELEASES the AWG slot. wait=False leaks it, and
                # leaked slots hit MAX_NUM_AWG=9 and make later runs fail in
                # confusing ways.
                x.stop(ramptime=0, wait=True)
            except Exception as err:
                print(f'  ! stop: {err}')
        try:
            awg.awg_cleanup()
        except Exception:
            pass
    return first_start, gps_now_fe()


def main():
    p = argparse.ArgumentParser(
        description='Phase-continuous stator frequency sweep (stepped AWG).',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('mode', choices=('down', 'up'),
                   help="'down' = autoresonant pump toward escape; "
                        "'up' = spin-up ramp once rotating")
    p.add_argument('--live', action='store_true')
    p.add_argument('--amp', type=float, default=6400.0,
                   help='AC amplitude per phase, counts (default 6400 = max)')
    p.add_argument('--dc', type=float, default=None, help='default = --amp')
    p.add_argument('--from-elec', type=float, default=None,
                   help='start f_elec in Hz. Default: the measured libration '
                        'line (down) -- which is the whole point, so it tracks '
                        'the drift rather than using a stale number.')
    p.add_argument('--to-elec', type=float, default=None,
                   help='end f_elec in Hz. Default: 0.5x the start for `down`, '
                        '4x for `up`.')
    p.add_argument('--minutes', type=float, default=15.0,
                   help='sweep duration (default 15)')
    p.add_argument('--step', type=float, default=8.0,
                   help='seconds per segment (default 8). Smaller = finer '
                        'frequency steps but more AWG churn.')
    p.add_argument('--lead', type=float, default=4.0,
                   help='arming lead per segment, s (default 4). Counts toward '
                        'each segment, so --step 8 --lead 4 spends a third of '
                        'the time arming.')
    p.add_argument('--reverse', action='store_true')
    p.add_argument('--verify', action='store_true',
                   help='LES before/after, to see whether the libration moved')
    args = p.parse_args()

    dry = not args.live
    dc = args.dc if args.dc is not None else args.amp
    electrodes = list(PHASE_ELECTRODES)

    if dc + args.amp > MAX_TOTAL_COUNTS:
        print(f'! dc + amp = {dc + args.amp:.0f} exceeds the LIMIT of '
              f'{MAX_TOTAL_COUNTS:.0f} counts.')
        return 1
    if caget is None:
        print('! pyepics not importable.')
        return 1

    fe0 = gps_now_fe()
    f_start = args.from_elec
    if f_start is None:
        try:
            x, fs = read_les(fe0 - 215, fe0 - 15)
            f_start = libration_freq(x, fs)
            print(f'  measured libration line: {f_start:.4f} Hz  '
                  f'(it drifts -- measured now, not stored)')
        except Exception as err:
            print(f'! could not measure the libration line ({err}); '
                  f'pass --from-elec.')
            return 1
    f_end = args.to_elec
    if f_end is None:
        f_end = 0.5 * f_start if args.mode == 'down' else 4.0 * f_start

    print('=' * 72)
    print(f'  mode      {args.mode}   '
          f'{"(autoresonant pump toward escape)" if args.mode == "down" else "(spin-up ramp)"}')
    for name, e in zip(PHASE_NAMES, electrodes):
        print(f'  phase {name}   V{e}: EXC {args.amp:.0f} cts, OFFSET {dc:.0f} cts')
    print(f'  f_elec    {f_start:.4f} -> {f_end:.4f} Hz over {args.minutes:.1f} min')
    print(f'  rotor     {f_start / M_DRIVE:.5f} -> {f_end / M_DRIVE:.5f} Hz')
    print(f'  peak      {dc + args.amp:.0f} counts ~ '
          f'{(dc + args.amp) * VOLTS_PER_COUNT:.0f} V')
    print('=' * 72)

    state = snapshot(electrodes)
    print('\n  setup:')
    setup(electrodes, state, dc, 'leave', dry)

    a = b = None
    try:
        a, b = run_sweep(electrodes, args.amp, f_start, f_end,
                         args.minutes * 60.0, args.step, args.lead,
                         args.reverse, dry)
    finally:
        restore(state, dry)

    if args.verify and not dry and a:
        span = min(200.0, b - a - 20)
        les_report(fe0 - span - 20, span, f_start / M_DRIVE, 'BEFORE sweep')
        print('\n  waiting 35 s for NDS frames...')
        time.sleep(35)
        try:
            x, fs = read_les(b - span - 10, b - 10)
            print(f'  AFTER sweep: libration line {libration_freq(x, fs):.4f} Hz, '
                  f'rms {x.std():.1f}')
            print(f'  (started at {f_start:.4f} Hz. A line that has moved DOWN '
                  f'means the\n   libration grew -- closer to escape. Watch the '
                  f'camera for actual rotation.)')
        except Exception as err:
            print(f'  after-sweep LES fetch failed: {err}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
