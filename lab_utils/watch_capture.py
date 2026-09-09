#!/usr/bin/env python3
"""Watch a free-spinning rotor and catch the moment it is captured into libration.

The capture frequency is the trap frequency, and it is the number that settles
the open question in apparatus_log.md -- so it is worth catching as it happens
rather than reconstructing afterwards.

HOW IT TELLS THE TWO STATES APART.  Waveform shape, not frequency. Measured
2026-09-09 on Y1:RDS-LES_YAW_IN1_DQ:

                    kurtosis    skew    frac>mean
    rotating          -1.43     +0.05     0.503
    librating         +0.92     -0.75     0.587
    (pure sine)       -1.50      0.00     0.500

A rotating rotor projects as a sinusoid. A librating one folds about its
turning points, giving cusps at the centre crossings -- positive kurtosis and
strong negative skew. The gap is 2.3 in kurtosis with nothing in between, so
the call is not marginal.

THE DIVISOR CHANGES AT CAPTURE, AND THAT IS AN ARTEFACT, NOT PHYSICS:

    rotating   mechanical = dominant line / 4   (sail is 2-fold; the 4x line
                                                 -- its 2nd harmonic -- is
                                                 strongest)
    librating  mechanical = dominant line / 2   (LES rectifies: it responds to
                                                 |theta|, one cycle per one-way
                                                 swing)

So the apparent mechanical frequency JUMPS 2x at capture from the change of
interpretation alone. A tracker that does not know this records a sudden
speed-up; that is what made the last point of the 2026-09-08 spindown
meaningless. Both readings are printed at every sample so the jump is visible
rather than silent.

Read-only. Touches no hardware, only NDS and one EPICS read for the clock.
"""

import argparse
import csv
import math
import os
import sys
import time

import numpy as np

try:
    from epics import caget
except ImportError:
    caget = None

CHAN = 'Y1:RDS-LES_YAW_IN1_DQ'
NDS_HOST, NDS_PORT = 'cymac1', 8088
NDS_LAG = 40.0                 # s of write lag to stay clear of
ROT_DIVISOR = 4.0
LIB_DIVISOR = 2.0

# Kurtosis thresholds. Rotating sits near -1.43, librating near +0.92, so
# anything above -0.5 is well clear of the rotating population.
KURT_CAPTURED = -0.5
CONFIRM_N = 2                  # consecutive samples before declaring capture


def fetch(gps_a, gps_b):
    import nds2
    conn = nds2.connection(NDS_HOST, NDS_PORT)
    buf = conn.fetch(int(gps_a), int(gps_b), [CHAN])[0]
    return np.array(buf.data, float), float(buf.channel.sample_rate)


def analyse(x, fs):
    """Return (dominant line Hz, kurtosis, skew, frac>mean, rms)."""
    from scipy.signal import decimate, welch
    from scipy.stats import skew, kurtosis
    x = x - x.mean()
    y = decimate(decimate(x, 8, ftype='fir'), 8, ftype='fir')
    fsd = fs / 64.0
    f, P = welch(y, fsd, nperseg=len(y), noverlap=0)
    m = np.where((f > 0.03) & (f < 3.0))[0]
    if len(m) < 3:
        return None
    k = m[np.argmax(P[m])]
    # parabolic interpolation in log power for a sub-bin peak
    if 0 < k < len(P) - 1:
        a_, b_, c_ = np.log(P[k - 1]), np.log(P[k]), np.log(P[k + 1])
        den = a_ - 2 * b_ + c_
        d = 0.5 * (a_ - c_) / den if den != 0 else 0.0
    else:
        d = 0.0
    line = f[k] + d * (f[1] - f[0])
    return line, kurtosis(y), skew(y), float(np.mean(y > 0)), float(y.std())


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--t-off', type=float, default=None,
                   help='front-end GPS at drive-off, for the elapsed column')
    p.add_argument('--interval', type=float, default=300.0,
                   help='seconds between samples (default 300)')
    p.add_argument('--window', type=float, default=240.0,
                   help='seconds of data per sample. Longer resolves the line '
                        'better but smears it while the rate is falling '
                        '(default 240)')
    p.add_argument('--out', default=None, help='append rows to this CSV')
    p.add_argument('--max-hours', type=float, default=12.0)
    args = p.parse_args()

    if caget is None:
        print('! pyepics not importable', file=sys.stderr)
        return 1

    w = csv.writer(open(args.out, 'a', newline='')) if args.out else None
    if w and os.path.getsize(args.out) == 0:
        w.writerow(['gps_mid', 't_since_off_s', 'line_hz', 'f_rot_hz',
                    'f_lib_hz', 'kurtosis', 'skew', 'frac_above', 'rms',
                    'state'])

    print(f'watching {CHAN}')
    print(f'  window {args.window:.0f} s every {args.interval:.0f} s, '
          f'up to {args.max_hours:g} h')
    print(f'  capture declared when kurtosis > {KURT_CAPTURED} for '
          f'{CONFIRM_N} consecutive samples\n')
    hdr = (f'{"elapsed":>9} {"line":>8} {"rot Hz":>8} {"turn s":>7} '
           f'{"kurt":>7} {"skew":>7} {"rms":>7}  state')
    print(hdr); print('-' * len(hdr))

    t_end = time.time() + args.max_hours * 3600
    run, declared = 0, False
    while time.time() < t_end:
        try:
            fe = float(caget('Y1:DAQ-DC0_GPS', timeout=5))
            b = fe - NDS_LAG
            a = b - args.window
            x, fs = fetch(a, b)
            r = analyse(x, fs)
            if r is None:
                print('  (no usable spectrum)'); time.sleep(args.interval); continue
            line, kurt, sk, frac, rms = r
            f_rot, f_lib = line / ROT_DIVISOR, line / LIB_DIVISOR
            el = (a + b) / 2 - args.t_off if args.t_off else float('nan')

            if kurt > KURT_CAPTURED:
                run += 1
            else:
                run = 0
            state = 'librating' if run >= CONFIRM_N else (
                'CAPTURING?' if run else 'rotating')

            print(f'{el:9.0f} {line:8.4f} {f_rot:8.4f} {1/f_rot:7.2f} '
                  f'{kurt:+7.3f} {sk:+7.3f} {rms:7.0f}  {state}')
            if w:
                w.writerow([f'{(a+b)/2:.0f}', f'{el:.0f}', f'{line:.5f}',
                            f'{f_rot:.5f}', f'{f_lib:.5f}', f'{kurt:.4f}',
                            f'{sk:.4f}', f'{frac:.4f}', f'{rms:.1f}', state])

            if run >= CONFIRM_N and not declared:
                declared = True
                print('\n' + '=' * 72)
                print('  CAPTURED INTO LIBRATION')
                print(f'    at front-end GPS  {(a+b)/2:.0f}'
                      + (f'   ({el:.0f} s after drive-off)' if args.t_off else ''))
                print(f'    kurtosis {kurt:+.3f}, skew {sk:+.3f} '
                      f'(rotating was about -1.43 / +0.05)')
                print(f'    dominant line {line:.4f} Hz')
                print(f'    -> libration {f_lib:.4f} Hz  (divisor 2, rectified)')
                print(f'    the last ROTATION rate before this was the capture')
                print(f'       rate; the trap frequency is {f_lib:.4f} Hz.')
                print('    NOTE the 2x jump in apparent mechanical frequency '
                      'here is\n    the divisor changing, NOT the rotor '
                      'speeding up.')
                print('=' * 72 + '\n')
        except KeyboardInterrupt:
            print('\ninterrupted.'); return 0
        except Exception as err:
            print(f'  ! {type(err).__name__}: {err}')
        time.sleep(args.interval)
    print('\nreached --max-hours; stopping.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
