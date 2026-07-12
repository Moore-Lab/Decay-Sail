#!/usr/bin/env python3

import time
from epics import caget, caput
import numpy as np

# Config electrode module
V_CHANS = ['Y1:RDS-OUTS_V1',
           'Y1:RDS-OUTS_V2',
           'Y1:RDS-OUTS_V3',
           'Y1:RDS-OUTS_V4']

ELECTRODE_OFFSETS = {'Y1:RDS-OUTS_V1':6400.0,
           'Y1:RDS-OUTS_V2': 6400.0,
           'Y1:RDS-OUTS_V3': 6400.0,
           'Y1:RDS-OUTS_V4': 6400.0}

def set_electrode_offsets(offsets):
    for chan in V_CHANS:
        caput(f'{chan}_OFFSET', float(offsets[chan]), wait=True, timeout=2.0)
        print(f'Set {chan} OFFSET to {offsets[chan]} counts')

def zero_electrodes():
    zeros = {ch: 0.0 for ch in V_CHANS}
    set_electrode_offsets(zeros)

# DRIVE module
PV = 'Y1:RDS-OUTS_DRV'
PV_ON = 'Y1:RDS-OUTS_DRVON'

GAIN = 6400
DWELL_TIME = 1.0

# sweep parameters
f_start = 0.1
f_stop = 4.0
f_step = 0.2
shutdown_after = False

# kick parameters
KICK_GAIN = 6400
KICK_FREQ = 0.6
KICK_DURATION = 1 * 1
kick_only = False

FREQ_PV  = f'{PV}_FREQ'
TRAMP_PV = f'{PV}_TRAMP'
SIN_PV   = f'{PV}_SINGAIN'
COS_PV   = f'{PV}_COSGAIN'

def kick():
    caput(SIN_PV,  KICK_GAIN)
    caput(COS_PV, -KICK_GAIN)  # negated for reverse direction
    print(f"Kick: driving at {KICK_FREQ} Hz for {KICK_DURATION} s (reverse direction)...")
    caput(FREQ_PV, float(KICK_FREQ))
    time.sleep(KICK_DURATION)
    caput(SIN_PV,  GAIN)
    caput(COS_PV, -GAIN)       # negated for reverse direction
    print("Kick complete.")

def shutdown():
    zero_electrodes()
    caput(PV_ON, 0)
    caput(SIN_PV, 0)
    caput(COS_PV, 0)
    caput(FREQ_PV, 0.0)

    sin_after = caget(SIN_PV)
    cos_after = caget(COS_PV)
    print(f'After zeroing, SIN gain: {sin_after} counts, COS gain: {cos_after} counts')
    print('\nOscillator disabled, outputs zeroed')

def main():
    caput(TRAMP_PV, 0.0)
    caput(FREQ_PV, f_start)
    time.sleep(1.5)
    set_electrode_offsets(ELECTRODE_OFFSETS)
    caput(TRAMP_PV, 100)
    caput(PV_ON, 1)
    caput(SIN_PV,  GAIN)
    caput(COS_PV, -GAIN)       # negated for reverse direction
    print(f"Gains set to SIN=+{GAIN}, COS=-{GAIN} (reverse). Press Ctrl-C to stop.")

    do_shutdown = False

    try:
        kick()

        if kick_only:
            return

        print("Begin sweep...")
        for freq in np.arange(f_start, f_stop + 1e-6, f_step):
            caput(FREQ_PV, float(freq))
            print(f"Frequency = {freq:.2f} Hz, dwell = {DWELL_TIME:.1f} s")
            time.sleep(DWELL_TIME)
        print("Sweep complete")

        if shutdown_after:
            do_shutdown = True
        else:
            print('Oscillator left enabled at last frequency.')

    except KeyboardInterrupt:
        print('\nStopped by user.')
        do_shutdown = True
    finally:
        if do_shutdown:
            shutdown()

if __name__ == '__main__':
    main()
