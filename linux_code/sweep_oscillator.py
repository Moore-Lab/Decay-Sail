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
PV = 'Y1:RDS-OUTS_DRV' #PV: IOC prefix for oscillator module
PV_ON = 'Y1:RDS-OUTS_DRVON'

GAIN = 6400
# DWELL_TIME = 10.0 # time (s) to hold each frequency step
N_CYCLES = 60 # dwell, 60 cycles foreach frequency step

# sweep parameters
f_start = 0.7 #0.2 # Hz
f_stop = 8.0 # Hz
f_step = 0.0025 # Hz
shutdown_after = False # if True, turn off oscillator at end of sweep

# kick parameters
KICK_GAIN = 6400
KICK_FREQ = 0.7  # Hz - fixed drive frequency before sweep (ideally near resonance)
KICK_DURATION = 45.0  # seconds
kick_only = True # if True, kick and stop without sweeping

# associated EPICS record variable names
#ENABLE_PV = f'{PV_ON}' # Drive on/off [0,1] 
FREQ_PV = f'{PV}_FREQ' # frequency (Hz)
TRAMP_PV = f'{PV}_TRAMP' # ramp time for freq and/or gain (s)
SIN_PV = f'{PV}_SINGAIN' # sin gain (counts)
COS_PV = f'{PV}_COSGAIN' # cos gain (counts)

def dwell_time(freq_hz):
    return N_CYCLES / freq_hz

def kick():
    caput(SIN_PV, KICK_GAIN)
    caput(COS_PV, KICK_GAIN)
    print(f"Kick: driving at {KICK_FREQ} Hz for {KICK_DURATION} s to establish rotation...")
    caput(FREQ_PV, float(KICK_FREQ))
    time.sleep(KICK_DURATION)
    caput(SIN_PV, GAIN)
    caput(COS_PV, GAIN)
    print("Kick complete.")

def shutdown():
    caput(PV_ON, 0)
    caput(SIN_PV, 0)
    caput(COS_PV, 0)
    caput(FREQ_PV, 0.0)

    sin_after = caget(SIN_PV)
    cos_after = caget(COS_PV)
    print(f'After zeroing, SIN gain: {sin_after} counts, COS gain: {cos_after} counts')
    print('\nOscillator disabled, outputs zeroed')

def main():
    # turn on ramping for smoothly modulating to next f_step
    caput(TRAMP_PV, 0.0) # set to 0 initially to set phase to 0
    caput(FREQ_PV, f_start) # set initial frequency
    time.sleep(1.5) # short delay to ensure freq is set before enabling
    set_electrode_offsets(ELECTRODE_OFFSETS)
    caput(TRAMP_PV, 1) # ramp time (s) for freq and/or gain changes
    caput(PV_ON, 1)
    # set gains
    caput(SIN_PV, GAIN)
    caput(COS_PV, GAIN)
    print(f"Gains set to +/-{GAIN:.1f} counts. Press Ctrl-C to stop.")
    kick()
    if kick_only:
        if shutdown_after:
            shutdown()
            zero_electrodes()
        return
    print("Begin sweep...")
    # freq sweep
    try:
        for freq in np.arange(f_start, f_stop + 1e-6, f_step):
            caput(FREQ_PV, float(freq))
            dt = dwell_time(freq)
            print(f"Frequency = {freq:.2f} Hz, dwell = {dt:.1f} s")
            time.sleep(dt)
        print(f"Sweep complete")
    except KeyboardInterrupt:
        print('\nSweep stopped by user.')
    finally:
        zero_electrodes()
        if shutdown_after:
            shutdown()
        else:
            print('Oscillator left enabled at last frequency.')

if __name__== '__main__':
    main()
