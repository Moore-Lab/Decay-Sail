"""Interactive laser step-down for PD -> mW power-meter calibration.

Steps the laser offset through a list of levels; at each level, waits a settle
time, then prompts for the power-meter reading and records everything to a
timestamped CSV. Keep the DAQ running throughout -- the PD trace in the frames
plus this CSV's timestamps is the calibration dataset (commanded counts +
PD counts + metered power, aligned by time).

Level list design (see analysis/laser_stepdown_*.ipynb for why):
  - full span 1800 -> 800 (PD ~240 -> ~25, the range used in the July run)
  - dense below 1000 counts, where the old log's mW values were least reliable
  - both 1600 and 1550 (the run showed PD RISING 167 -> 186 across this
    commanded power DROP -- the meter arbitrates)
  - dark points (0 counts) at start and end, anchoring PD0
  - repeats on the way back up (1000/1400/1800) for drift + hysteresis +
    top-end PD saturation check

Usage:  python3 laser_power_calibration.py
  - Enter meter readings in mW (e.g. "0.031" for 31 uW). Blank entry skips a
    level but still logs the timestamps. Ctrl-C zeroes the laser and exits.
"""

import csv
import os
import sys
import time
from datetime import datetime, timezone

from epics import caget, caput

LASER = 'Y1:RDS-OUTS_LASER'
OUTPUT_LASER = f'{LASER}_OFFSET'

SETTLE_S = 60.0
OUT_DIR = os.path.expanduser("~/laser_calibration")

LEVELS = [
    0,                                          # dark reference
    1800, 1700, 1600, 1550, 1500, 1400, 1300,   # top span incl. the 1600/1550 pair
    1200, 1100, 1000,
    975, 950, 925, 900, 875, 850,               # dense low end
    840, 830, 820, 810, 800,
    0,                                          # dark again
    1000, 1400, 1800,                            # repeats going up: drift/hysteresis/saturation
    0,                                          # end dark / laser effectively off
]


def safe_shutdown():
    caput(OUTPUT_LASER, 0)
    print('\nABORT: laser offset set to 0.')


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')
    out_path = os.path.join(OUT_DIR, f'laser_pd_calibration_{stamp}.csv')

    session_note = input("Session note (meter model, meter position, wavelength setting): ").strip()

    with open(out_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow([f'# laser PD->mW calibration  {stamp} UTC  note: {session_note}'])
        w.writerow(['level_counts', 'readback_counts',
                    't_set_utc', 't_set_unix', 't_read_utc', 't_read_unix',
                    'power_mw', 'note'])

    print(f"\n{len(LEVELS)} levels, settle {SETTLE_S:.0f} s each  ->  ~{len(LEVELS)*(SETTLE_S+30)/60:.0f} min total")
    print(f"Recording to {out_path}")
    print("Make sure the DAQ is running (PD channel) before starting. Ctrl-C aborts + zeroes laser.\n")
    input("Press Enter to start...")

    try:
        for i, level in enumerate(LEVELS):
            t_set = datetime.now(timezone.utc)
            caput(OUTPUT_LASER, float(level), wait=True, timeout=2.0)
            readback = caget(OUTPUT_LASER)
            print(f"\n[{i+1}/{len(LEVELS)}] >>> LEVEL CHANGED to {level} counts "
                  f"(readback {readback}) <<<")
            remaining = SETTLE_S
            while remaining > 0:
                chunk = min(15.0, remaining)
                print(f"    settling... {remaining:.0f} s left", flush=True)
                time.sleep(chunk)
                remaining -= chunk
            print(f"\a  READY -- read the meter now ({level} counts)")

            entry = input(f"  power reading in mW (blank = skip, 'q' = finish early): ").strip()
            if entry.lower() == 'q':
                print("Finishing early.")
                break
            note = input("  optional note (blank = none): ").strip()
            t_read = datetime.now(timezone.utc)

            power_mw = ''
            if entry:
                try:
                    power_mw = f"{float(entry):.6g}"
                except ValueError:
                    note = (note + ' | ' if note else '') + f'UNPARSED ENTRY: {entry!r}'
                    print(f"  (could not parse {entry!r} as mW -- stored in note column)")

            with open(out_path, 'a', newline='') as f:
                csv.writer(f).writerow([
                    level, readback,
                    t_set.isoformat(), f'{t_set.timestamp():.3f}',
                    t_read.isoformat(), f'{t_read.timestamp():.3f}',
                    power_mw, note,
                ])
    except KeyboardInterrupt:
        safe_shutdown()
        print(f"Partial data saved to {out_path}")
        sys.exit(1)

    caput(OUTPUT_LASER, 0)
    print(f"\nDone. Laser offset left at 0. Data: {out_path}")


if __name__ == '__main__':
    main()
