#!/usr/bin/env python3
"""Measure the stator's angular stiffness against whatever else traps the rotor.

WHY THIS IS THE NUMBER THAT MATTERS (2026-08-28)

With every electrode grounded, the rotor still librates -- 0.25-0.33 Hz all day,
with the line at SNR ~100 in LES. So something holds it angularly that is NOT
the stator. Turning the drive on shifts that line, and the shift is the stator's
own contribution:

    k_stator / k_intrinsic = (f_on^2 - f_off^2) / f_off^2

First measurement, --amp 6400 (maximum, optimal dc=amp split):
    f_off = 0.2704 Hz,  f_on = 0.2923 Hz  ->  f_stator = 0.111 Hz
    k_intrinsic / k_stator ~ 6

i.e. at full power the stator is about SIX TIMES weaker than the trap already
holding the rotor. That is why it will not spin, and it is not a waveform, phase
or capture-bandwidth problem -- all of which were real bugs, and all of which
were fixed today without the rotor caring.

The ratio is (f_on^2 - f_off^2)/f_off^2, a ratio of frequencies squared, so it
does NOT depend on the moment of inertia. That matters here: I = 1.88e-11 kg m^2
is assumed and has never been measured, and it contaminates every torque and
capture number in CLAUDE.md. This one is clean.

WHAT THIS SCRIPT ADDS

One on/off pair is not enough, because the libration frequency drifts on its own
(0.2531 -> 0.2704 -> 0.2923 -> 0.3300 over a few hours, partly with amplitude
since the well is anharmonic). A single before/after can be swamped by that
drift. So this alternates ON and OFF segments and pairs each ON against its
neighbouring OFFs, which cancels drift to first order.

THE TEST IT EXISTS FOR: stator stiffness must scale as V^2. Halving --amp from
6400 to 3200 should quarter (f_on^2 - f_off^2). If it does, the picture is
sound. If it does not, the "intrinsic trap" reading is wrong and the ~6x should
not be built on.

Predicted at --amp 3200, from the 6400 measurement: f_stator ~ 0.0555 Hz, so
with f_off ~ 0.253 the shift is only ~0.006 Hz. That is small against the drift,
which is exactly why the pairing matters -- use --cycles 3 or more.

Nothing touches hardware without --live.
"""

import argparse
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stator_awg_drive import (PREFIX, DAQ_GPS_PV, PHASE_ELECTRODES, M_DRIVE,
                              snapshot, setup, restore, build, gps_now_fe)

try:
    from epics import caget, caput
except ImportError:
    caget = caput = None

LES_CHAN = 'Y1:RDS-LES_YAW_OUT_DQ'


def libration_freq(x, fs, lo=0.10, hi=1.20):
    """Dominant line, with parabolic interpolation for sub-bin precision.

    Sub-bin matters: a 90 s segment has 0.011 Hz bins, and the shift we are
    chasing at --amp 3200 is ~0.006 Hz. Interpolation typically gets an order of
    magnitude inside the bin for a clean line, and this line sits at SNR ~100.
    """
    ac = x - x.mean()
    X = np.abs(np.fft.rfft(ac * np.hanning(len(ac))))
    fr = np.fft.rfftfreq(len(ac), 1 / fs)
    m = (fr > lo) & (fr < hi)
    i = np.flatnonzero(m)[np.argmax(X[m])]
    y0, y1, y2 = X[i - 1], X[i], X[i + 1]
    den = y0 - 2 * y1 + y2
    d = 0.5 * (y0 - y2) / den if den else 0.0
    return fr[i] + d * (fr[1] - fr[0]), X[i]


def fetch(gps_a, gps_b):
    import nds2
    conn = nds2.connection('cymac1', 8088)
    conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')
    buf = conn.fetch(int(gps_a), int(gps_b), [LES_CHAN])[0]
    return np.array(buf.data, float), float(buf.channel.sample_rate)


def main():
    p = argparse.ArgumentParser(
        description="Measure the stator's angular stiffness vs the intrinsic trap.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--live', action='store_true')
    p.add_argument('--amp', type=float, default=3200.0,
                   help='AC amplitude per phase, counts (default 3200). dc = amp.')
    p.add_argument('--cycles', type=int, default=3,
                   help='ON/OFF pairs (default 3). More beats down the drift.')
    p.add_argument('--seg', type=float, default=90.0,
                   help='seconds per segment (default 90)')
    p.add_argument('--lead', type=float, default=8.0)
    p.add_argument('--nds-lag', type=float, default=35.0)
    args = p.parse_args()

    dry = not args.live
    dc = args.amp
    electrodes = list(PHASE_ELECTRODES)

    if caget is None:
        print('! pyepics not importable.')
        return 1

    # Match the drive to the CURRENT libration line -- it drifts, so a value
    # measured an hour ago is not good enough for a resonance.
    print('Measuring the current libration line...')
    fe0 = gps_now_fe()
    try:
        x, fs = fetch(fe0 - 215, fe0 - 15)
        f_lib, _ = libration_freq(x, fs)
    except Exception as err:
        print(f'! could not read LES ({err}); pass a frequency by hand.')
        return 1
    print(f'  f_libration = {f_lib:.4f} Hz  ->  driving f_elec = {f_lib:.4f} Hz '
          f'(f_rotor = {f_lib / M_DRIVE:.5f} Hz)')
    print(f'  {args.cycles} ON/OFF pairs of {args.seg:.0f} s at amp {args.amp:.0f} '
          f'(dc {dc:.0f})\n')

    if dry:
        print('DRY RUN -- pass --live to drive.')
        total = 2 * args.cycles * args.seg
        print(f'  would take {total / 60:.1f} min plus {args.nds_lag:.0f} s of NDS lag.')
        return 0

    state = snapshot(electrodes)
    setup(electrodes, state, dc, 'leave', dry)
    marks = []                      # (kind, gps_start, gps_end)
    import awg
    try:
        for cyc in range(args.cycles):
            start_ns = int((gps_now_fe() + args.lead) * 1e9)
            exc = build(electrodes, args.amp, f_lib, None,
                        args.seg + args.lead, start_ns, False)
            for e in exc:
                e.start(ramptime=0, wait=False)
            t_on = start_ns / 1e9
            print(f'  cycle {cyc + 1}/{args.cycles}  ON  at FE {t_on:.0f}')
            time.sleep(args.lead + args.seg + 2)
            for e in exc:
                try:
                    e.stop(ramptime=0, wait=True)
                except Exception as err:
                    print(f'    ! stop: {err}')
            awg.awg_cleanup()
            marks.append(('ON', t_on + 5, t_on + args.seg - 3))
            t_off = gps_now_fe()
            print(f'  cycle {cyc + 1}/{args.cycles}  OFF at FE {t_off:.0f}')
            time.sleep(args.seg)
            marks.append(('OFF', t_off + 5, t_off + args.seg - 3))
    except KeyboardInterrupt:
        print('\n  interrupted.')
    finally:
        try:
            awg.awg_cleanup()
        except Exception:
            pass
        restore(state, dry)

    print(f'\n  waiting {args.nds_lag:.0f} s for NDS frames...')
    time.sleep(args.nds_lag)

    print(f'\n  {"seg":>5} {"kind":>5} {"f (Hz)":>10} {"rms":>10}')
    res = {'ON': [], 'OFF': []}
    for i, (kind, a, b) in enumerate(marks):
        try:
            x, fs = fetch(a, b)
        except Exception as err:
            print(f'  {i:5d} {kind:>5}  fetch failed: {err}')
            continue
        f, _ = libration_freq(x, fs)
        res[kind].append(f)
        print(f'  {i:5d} {kind:>5} {f:10.4f} {x.std():10.1f}')

    if len(res['ON']) and len(res['OFF']):
        f_on = float(np.mean(res['ON']))
        f_off = float(np.mean(res['OFF']))
        print(f'\n  mean f_on  = {f_on:.4f} Hz  (n={len(res["ON"])})')
        print(f'  mean f_off = {f_off:.4f} Hz  (n={len(res["OFF"])})')
        d2 = f_on ** 2 - f_off ** 2
        if d2 > 0:
            f_stator = math.sqrt(d2)
            print(f'  f_stator   = {f_stator:.4f} Hz')
            print(f'  k_intrinsic / k_stator = {f_off ** 2 / d2:.2f}')
            print(f'\n  Compare with --amp 6400: f_stator was 0.111 Hz.')
            print(f'  Stiffness goes as V^2, so half the amplitude should give '
                  f'HALF f_stator\n  (0.0555 Hz at 3200). Measured {f_stator:.4f}.')
        else:
            print('  f_on <= f_off -- no measurable stiffening. Either the drive '
                  'is not\n  coupling, or the drift swamped it: try more --cycles '
                  'or a larger --amp.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
