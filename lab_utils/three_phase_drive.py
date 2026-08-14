#!/usr/bin/env python3
"""Three-phase sinusoidal electrode drive on V1, V2, V3 -> a rotating electric field.

Writes three sinusoids 120 deg apart to the V1/V2/V3 OFFSET channels, which makes a
field pattern that rotates at --freq and can drive/spin the rotor. Software-generated,
so it is practical only up to a few Hz (you want many updates per cycle: keep
--rate >> 20*--freq). Unlike arcade_mode.py this uses only EPICS, so NO sudo/keyboard.

  V1 = dc + amp*sin(w t)
  V2 = dc + amp*sin(w t - 120 deg)
  V3 = dc + amp*sin(w t - 240 deg)      (--reverse flips the sense of rotation)

DC / unipolar note: the electrodes were found sitting at 12000 counts, and HV amps are
usually unipolar (can't go negative). So by default DC = amp, i.e. each channel swings
between 0 and 2*amp (never negative). If your amp is bipolar, pass --dc 0 for a pure
+/-amp swing about zero. V4 is left untouched.

On Ctrl-C (or when --duration elapses) the amplitude is ramped back down and all three
channels are set to 0 -- a known safe state.
"""
import argparse
import math
import signal
import sys
import time
from datetime import datetime, timezone

from epics import PV

_GPS_UNIX_OFFSET = 315964800 - 18


def gps_now():
    return int(time.time()) - _GPS_UNIX_OFFSET


p = argparse.ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--electrodes', type=str, default='1,2,3',
               help='the 3 electrodes to drive as phases A,B,C, comma-separated '
                    '(default 1,2,3; e.g. 2,3,4). Electrodes not listed are left untouched.')
p.add_argument('--freq', type=float, default=1.0, help='rotation frequency in Hz (default 1.0)')
p.add_argument('--amp', type=float, default=6000.0, help='peak amplitude in counts (default 6000)')
p.add_argument('--dc', type=float, default=None,
               help='DC offset in counts (default = amp, keeps the drive >= 0 for a '
                    'unipolar amp; pass 0 for a bipolar +/-amp swing about zero)')
p.add_argument('--rate', type=float, default=200.0, help='update rate in Hz (default 200)')
p.add_argument('--ramp', type=float, default=2.0,
               help='amplitude ramp up/down time in s, avoids a jolt (default 2.0)')
p.add_argument('--duration', type=float, default=0.0,
               help='run time in s (default 0 = until Ctrl-C)')
p.add_argument('--reverse', action='store_true', help='reverse the sense of rotation')
args = p.parse_args()

enums = [int(x) for x in args.electrodes.split(',')]
if len(enums) != 3 or len(set(enums)) != 3 or any(n < 1 or n > 4 for n in enums):
    sys.exit(f"--electrodes must be 3 distinct numbers from 1-4, got '{args.electrodes}'")
CHANS = [f"Y1:RDS-OUTS_V{n}_OFFSET" for n in enums]

dc = args.amp if args.dc is None else args.dc

# 120-degree phase offsets; reversing the order reverses the field rotation.
phases = [0.0, -2 * math.pi / 3, -4 * math.pi / 3]
if args.reverse:
    phases = [-ph for ph in phases]

if args.rate < 20 * args.freq:
    print(f"WARNING: --rate {args.rate} Hz is < 20x --freq; the sinusoid will be coarse. "
          f"Raise --rate or lower --freq.")

# connect
pvs = [PV(c) for c in CHANS]
for pv in pvs:
    pv.wait_for_connection(timeout=5.0)
bad = [pv.pvname for pv in pvs if not pv.connected]
if bad:
    sys.exit(f"ERROR: could not connect to: {', '.join(bad)}")


def write(values):
    for pv, v in zip(pvs, values):
        pv.put(float(v), wait=False)


def sample(t, amp):
    return [dc + amp * math.sin(2 * math.pi * args.freq * t + ph) for ph in phases]


running = {'go': True}
def _stop(sig, frame):
    running['go'] = False
signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)

print("3-phase electrode drive")
print(f"  channels : {', '.join(CHANS)}   (V4 untouched)")
print(f"  freq={args.freq} Hz  amp={args.amp}  dc={dc}  -> swing [{dc-args.amp:.0f}, {dc+args.amp:.0f}]")
print(f"  rate={args.rate} Hz  ramp={args.ramp}s  {'REVERSE' if args.reverse else 'forward'}"
      f"  duration={'until Ctrl-C' if not args.duration else str(args.duration)+'s'}")
print(f"  GPS start {gps_now()}  ({datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC)")
print("  Ctrl-C to stop (ramps down + zeros V1-V3).")

dt = 1.0 / args.rate
t0 = time.monotonic()
n = 0
try:
    while running['go']:
        t = time.monotonic() - t0
        env = min(1.0, t / args.ramp) if args.ramp > 0 else 1.0
        write(sample(t, args.amp * env))
        if args.duration and t >= args.duration:
            break
        n += 1
        s = (t0 + n * dt) - time.monotonic()
        if s > 0:
            time.sleep(s)
finally:
    # ramp amplitude down from wherever we are, then zero
    rd0 = time.monotonic()
    while args.ramp > 0:
        e = (time.monotonic() - rd0) / args.ramp
        if e >= 1.0:
            break
        t = time.monotonic() - t0
        write(sample(t, args.amp * (1.0 - e)))
        time.sleep(dt)
    write([0.0, 0.0, 0.0])
    time.sleep(0.1)
    print(f"\nStopped; V1-V3 zeroed. GPS end {gps_now()}")
