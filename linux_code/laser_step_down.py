import time
from epics import caget, caput
import numpy as np

# Config
PD = 'Y1:RDS-PD' #PD: IOC prefix for photodetector module

# parameters
OUTPUT_PD = f'{PD}_OFFSET' # photodetector output (V)
DWELL_TIME = 60.0 * 5 # time (s) to step down laser power

OFFSET_VALUES = [1000, 500, 250, 100, 50, 10, 5, 1, 0] # offset values to step down through

def main():
    initial = caget(OUTPUT_PD)
    print("Beginning laser power step down...")
    print(f"Initial photodetector offset: {initial} counts")
    
    try:
        for offset in OFFSET_VALUES:
            caput(OUTPUT_PD, float(offset))
            readback = caget(OUTPUT_PD)
            print(f"Set photodetector offset to {offset} counts, readback: {readback} counts")
            time.sleep(DWELL_TIME)
        print("Laser power step down complete.")
    except KeyboardInterrupt:
        print('\nStep down stopped by user.')
    finally:
        print('Final photodetector offset set to last value.')

if __name__== '__main__':
    main()
