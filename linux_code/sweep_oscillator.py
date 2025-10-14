#!/usr/bin/env python3

import time
from epics import caget, caput
import numpy as np

# Config
PV = 'Y1:RDS-OUTS_DRV' #PV: IOC prefix for oscillator module
PV_ON = 'Y1:RDS-OUTS_DRVON'

GAIN = 6000
DWELL_TIME = 30.0 # time (s) to hold each frequency step?
# sweep parameters
f_start = 0.8 #0.2 # Hz
f_stop = 2.0 # Hz
f_step = 0.05 # Hz
shutdown_after = True # if True, turn off oscillator at end of sweep

# associated EPICS record variable names
#ENABLE_PV = f'{PV_ON}' # Drive on/off [0,1] 
FREQ_PV = f'{PV}_FREQ' # frequency (Hz)
TRAMP_PV = f'{PV}_TRAMP' # ramp time for freq and/or gain (s)
SIN_PV = f'{PV}_SINGAIN' # sin gain (counts)
COS_PV = f'{PV}_COSGAIN' # cos gain (counts)

def shutdown():
    caput(PV_ON, 0)
    caput(SIN_PV, 0)
    caput(COS_PV, 0)
    caput(FREQ_PV, 0.0)
    print('\nOscillator disabled, outputs zeroed')

def main():
    # turn on ramping for smoothly modulating to next f_step
    caput(PV_ON, 1)
    caput(TRAMP_PV, 100.0)
    # set gains
    caput(SIN_PV, GAIN)
    caput(COS_PV, GAIN)
    print(f"Gains set to +/-{GAIN:.1f} counts.Press Ctrl-C to stop.  Begin sweep...")
    # freq sweep
    try:
        for freq in np.arange(f_start, f_stop + 1e-6, f_step):
            caput(FREQ_PV, float(freq))
            print(f"Frequency = {freq:.2f} Hz")
            time.sleep(DWELL_TIME)
        print("Sweep complete")
    except KeyboardInterrupt:
        print('\nSweep stopped by user.')
    finally:
        if shutdown_after:
            shutdown()
        else:
            print('Oscillator left enabled at last frequency.')

if __name__== '__main__':
    main()
