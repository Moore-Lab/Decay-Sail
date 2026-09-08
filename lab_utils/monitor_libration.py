#!/usr/bin/env python3
"""Live monitor of rotor libration from LES PIT/YAW.

Uses cdsutils.getdata (LIGO CDS) for live streaming — no archive lag.
Each poll fetches the next WINDOW seconds of live data, so the loop
naturally advances in real time.

Reports peak frequency and RMS amplitude for each axis. Logs to a file
so an external observer can follow along.

Env vars set automatically: IFO=Y1, NDSSERVER=cymac1:8088

Ctrl-C to stop.
"""

import argparse
import os
import sys
import time
from datetime import datetime

os.environ.setdefault('IFO', 'Y1')
os.environ.setdefault('NDSSERVER', 'cymac1:8088')

import numpy as np
import cdsutils

CHANNELS = ['Y1:RDS-LES_PIT_IN1_DQ', 'Y1:RDS-LES_YAW_IN1_DQ']
WINDOW = 10.0        # seconds of data per snapshot (also poll cadence)
BAND = (0.05, 10.0)  # Hz — freq range to search for peak
LOG_PATH = '/tmp/libration_monitor.log'


def peak_and_amp(x, fs, band=BAND):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < int(2 * fs):
        return None, None, None
    ac = x - np.mean(x)
    rms = float(np.sqrt(np.mean(ac ** 2)))
    ptp = float(np.ptp(x))
    freqs = np.fft.rfftfreq(ac.size, d=1.0 / fs)
    spec = np.abs(np.fft.rfft(ac))
    mask = (freqs > band[0]) & (freqs < band[1])
    if not np.any(mask):
        return None, rms, ptp
    peak_freq = float(freqs[mask][np.argmax(spec[mask])])
    return peak_freq, rms, ptp


def format_line(data_list, gps_start):
    parts = [datetime.now().strftime('%H:%M:%S'),
             f'GPS {int(gps_start)}']
    for d in data_list:
        # channel like 'Y1:RDS-LES_PIT_IN1_DQ' → 'PIT'
        name = d.channel.split('_')[1]
        freq, rms, ptp = peak_and_amp(d.data, d.sample_rate)
        if freq is None:
            parts.append(f'{name}: n/a')
        else:
            parts.append(f'{name} f={freq:.3f}Hz rms={rms:6.1f} ptp={ptp:6.1f}')
    return ' | '.join(parts)


def main():
    global WINDOW
    p = argparse.ArgumentParser()
    p.add_argument('--window', type=float, default=WINDOW,
                   help='seconds of live data per sample (default 10)')
    p.add_argument('--log', default=LOG_PATH)
    args = p.parse_args()
    WINDOW = args.window

    print(f'Libration monitor (cdsutils live): window={WINDOW}s, log={args.log}')

    with open(args.log, 'a', buffering=1) as fh:
        fh.write(f'--- monitor started {datetime.now().isoformat()} ---\n')
        try:
            while True:
                try:
                    data = cdsutils.getdata(CHANNELS, WINDOW)
                except Exception as exc:
                    line = f'{datetime.now().strftime("%H:%M:%S")} | fetch error: {exc}'
                else:
                    gps_start = data[0].start_time
                    line = format_line(data, gps_start)
                print(line, flush=True)
                fh.write(line + '\n')
        except KeyboardInterrupt:
            print('\nMonitor stopped.')


if __name__ == '__main__':
    main()
