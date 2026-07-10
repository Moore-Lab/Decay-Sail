#!/usr/bin/env python3
"""Configurable laser power sweep for optical sensitivity measurement.

Steps laser from --start to --stop in --step increments, dwelling --dwell
minutes at each level. Logs GPS timestamps and power to a CSV so
damping_monitor_gui.py can cross-reference τ against laser power.

Usage:
    python3 laser_power_sweep.py --start 839 --stop 0   --step 1  --dwell 90
    python3 laser_power_sweep.py --start 925 --stop 800 --step 5  --dwell 60
    python3 laser_power_sweep.py --start 850 --stop 800 --step 1  --dwell 120
"""

import argparse
import csv
import signal
import sys
import time
from epics import caput, caget
from datetime import datetime, timezone

GPS_UNIX_OFF = 315964782
CYMAC_OFFSET = 3072
OUTPUT_LASER = 'Y1:RDS-OUTS_LASER_OFFSET'

CALIBRATION = {
    1800: 15.10, 1750: 14.85, 1700: 14.26, 1600: 12.92,
    1550: 12.23, 1500: 11.46, 1450: 10.76, 1400: 10.01,
    1350:  9.33, 1300:  8.49, 1250:  7.68, 1200:  7.09,
    1150:  5.59, 1100:  4.84, 1050:  4.24, 1000:  3.41,
     950:  2.75,  900:  2.05,  850:  1.445, 800:  0.0312,
}

# ── CLI ───────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--start', type=int, required=True, help='Starting laser counts')
parser.add_argument('--stop',  type=int, required=True, help='Final laser counts (inclusive)')
parser.add_argument('--step',  type=int, default=1,     help='Step size in counts (default 1)')
parser.add_argument('--dwell', type=int, default=90,    help='Dwell time per step in minutes (default 90)')
parser.add_argument('--log',   default='',              help='CSV log path (auto-named if omitted)')
parser.add_argument('--no-zero', action='store_true',   help='Do not zero laser on Ctrl-C (leave at current level)')
args = parser.parse_args()


# ── Helpers ───────────────────────────────────────────────────────────────────
def cymac_gps_now():
    return int(time.time()) - GPS_UNIX_OFF + CYMAC_OFFSET

def power_mw(counts):
    cal = sorted(CALIBRATION)
    if counts in CALIBRATION:
        return CALIBRATION[counts]
    above = [c for c in cal if c >= counts]
    below = [c for c in cal if c <= counts]
    if above and below:
        hi, lo = min(above), max(below)
        if hi == lo:
            return CALIBRATION[hi]
        return CALIBRATION[lo] + (CALIBRATION[hi] - CALIBRATION[lo]) * (counts - lo) / (hi - lo)
    return CALIBRATION[min(above)] if above else CALIBRATION[max(below)]

def power_str(counts):
    p = power_mw(counts)
    if p < 0.001: return f'{p*1e6:.0f} nW'
    if p < 1.0:   return f'{p*1000:.1f} µW'
    return f'{p:.3f} mW'

def set_laser(counts):
    caput(OUTPUT_LASER, float(counts), wait=True, timeout=2.0)

def safe_shutdown(sig=None, frame=None):
    if not args.no_zero:
        set_laser(0)
        print('\nABORT: Laser zeroed.')
    else:
        print('\nABORT: Laser left at current level (--no-zero).')
    sys.exit(0)

signal.signal(signal.SIGINT,  safe_shutdown)
signal.signal(signal.SIGTERM, safe_shutdown)

def countdown(total_sec):
    for remaining in range(total_sec, 0, -1):
        m, s = divmod(remaining, 60)
        print(f'    Next step in {m:02d}:{s:02d} ...', end='\r', flush=True)
        time.sleep(1)
    print()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    start, stop, step = args.start, args.stop, args.step
    dwell_min = args.dwell

    direction = -1 if stop < start else 1
    steps = list(range(start, stop + direction, direction * step))
    steps = [s for s in steps if min(start, stop) <= s <= max(start, stop)]

    log_path = args.log or f'laser_sweep_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.csv'

    print(f'Laser power sweep')
    print(f'  {start} → {stop} counts  |  step={step}  |  dwell={dwell_min} min')
    print(f'  {len(steps)} steps  |  est. {len(steps) * dwell_min / 60:.1f} h')
    print(f'  Log: {log_path}')
    print(f'  Ctrl-C to abort{" (leaves laser at current level)" if args.no_zero else " and zero laser"}.\n')

    with open(log_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['step', 'total_steps', 'counts', 'power_mw',
                         'gps_step_start', 'utc_step_start',
                         'gps_step_end',   'utc_step_end'])

        for i, counts in enumerate(steps):
            gps_start = cymac_gps_now()
            utc_start = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

            set_laser(counts)
            print(f'[{i+1:3d}/{len(steps)}]  {counts:5d} counts  |  {power_str(counts):>10s}  '
                  f'|  {datetime.now().strftime("%H:%M:%S")}  |  dwell {dwell_min} min')

            countdown(dwell_min * 60)

            gps_end = cymac_gps_now()
            utc_end = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

            writer.writerow([i + 1, len(steps), counts, f'{power_mw(counts):.4f}',
                             gps_start, utc_start, gps_end, utc_end])
            f.flush()

    print(f'\nSweep complete. Laser at {steps[-1]} counts. Log → {log_path}')


if __name__ == '__main__':
    main()
