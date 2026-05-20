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
DWELL_TIME = 100.0 # time (s) to hold each frequency step
# N_CYCLES = 20  # dwell, 20 cycles for each frequency step

# sweep parameters
f_start = 0.13 #0.2 # Hz
f_stop = 4.0 # Hz
f_step = 0.05# Hz
shutdown_after = True # if True, turn off oscillator at end of sweep

# kick parameters
KICK_GAIN = 6400
KICK_FREQ = 0.13 # Hz - fixed drive frequency before sweep (ideally near resonance)
KICK_DURATION = 60 * 5 # seconds
kick_only = False # if True, kick and stop without sweeping

# associated EPICS record variable names
#ENABLE_PV = f'{PV_ON}' # Drive on/off [0,1] 
FREQ_PV = f'{PV}_FREQ' # frequency (Hz)
TRAMP_PV = f'{PV}_TRAMP' # ramp time for freq and/or gain (s)
SIN_PV = f'{PV}_SINGAIN' # sin gain (counts)
COS_PV = f'{PV}_COSGAIN' # cos gain (counts)

# def dwell_time(freq_hz):
#     return N_CYCLES / freq_hz

def kick():
    caput(SIN_PV, KICK_GAIN)
    caput(COS_PV, -KICK_GAIN)
    print(f"Kick: driving at {KICK_FREQ} Hz for {KICK_DURATION} s to establish rotation...")
    caput(FREQ_PV, float(KICK_FREQ))
    time.sleep(KICK_DURATION)
    caput(SIN_PV, GAIN)
    caput(COS_PV, -GAIN)
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
    caput(TRAMP_PV, 0.0)
    caput(FREQ_PV, f_start)
    time.sleep(1.5)
    set_electrode_offsets(ELECTRODE_OFFSETS)
    caput(TRAMP_PV, 100) # trying 100 like previous script; but could go back to 1
    caput(PV_ON, 1)
    caput(SIN_PV, GAIN)
    caput(COS_PV, -GAIN)
    print(f"Gains set to +/-{GAIN:.1f} counts. Press Ctrl-C to stop.")

    do_shutdown = False  # false only when sweep completes normally with shutdown_after=False

    try:
        kick()

        if kick_only:
            return

        print("Begin sweep...")
        for freq in np.arange(f_start, f_stop + 1e-6, f_step):
            caput(FREQ_PV, float(freq))
            # dt = dwell_time(freq)
            # print(f"Frequency = {freq:.2f} Hz, dwell = {dt:.1f} s")
            print(f"Frequency = {freq:.2f} Hz, dwell = {DWELL_TIME:.1f} s")
            time.sleep(DWELL_TIME)
        print("Sweep complete")

        if not shutdown_after:
            do_shutdown = False
            print('Oscillator left enabled at last frequency.')

    except KeyboardInterrupt:
        print('\nStopped by user.')
    finally:
        if do_shutdown:
            zero_electrodes()
            shutdown()

if __name__== '__main__':
    main()
