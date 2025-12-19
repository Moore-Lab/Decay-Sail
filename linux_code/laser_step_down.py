import time
from epics import caget, caput
import numpy as np

# Config
LASER = 'Y1:RDS-OUTS_LASER' #LASER: IOC prefix for laser module

# parameters
OUTPUT_LASER = f'{LASER}_OFFSET' # photodetector output (V)
DWELL_TIME = 60.0 * 5 # time (s) to step down laser power

OFFSET_VALUES = [100, 50, 0 ] # offset values to step down through; make sure to correspond to 25 - 55 mA or 

def main():
    initial = caget(OUTPUT_LASER)
    print("Beginning laser power step down...")
    print(f"Initial photodetector offset: {initial} counts")
    
    try:
        for offset in OFFSET_VALUES:
            caput(OUTPUT_LASER, float(offset))
            readback = caget(OUTPUT_LASER)
            print(f"Set photodetector offset to {offset} counts, readback: {readback} counts")
            time.sleep(DWELL_TIME)
        print("Laser power step down complete.")
    except KeyboardInterrupt:
        print('\nStep down stopped by user.')
    finally:
        print('Final photodetector offset set to last value.')

if __name__== '__main__':
    main()
