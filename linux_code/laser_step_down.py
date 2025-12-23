import time
from epics import caget, caput
import numpy as np

# Config
LASER = 'Y1:RDS-OUTS_LASER' #LASER: IOC prefix for laser module

# parameters
OUTPUT_LASER = f'{LASER}_OFFSET' # photodetector output (V)
DWELL_TIME = 10.0 # * 60.0 # time (s) to step down laser power

OFFSET_VALUES = [1800, 1750, 1700, 1650, 1600, 1550, 1500, 1450, 1400, 
                 1350, 1300, 1250, 1200, 1100, 1050, 1000, 950, 900, 850, 
                 800, 500, 0] # offset values to step down through; make sure to correspond to 25 - 55 mA or

def safe_shutdown():
    caput(OUTPUT_LASER, 0)
    print('\nABORT: Laser power set to zero for safe shutdown.')

def main():
    initial = caget(OUTPUT_LASER)
    print("Beginning laser power step down...")
    print(f"Initial photodetector offset: {initial} counts")
    
    try:
        for offset in OFFSET_VALUES:
            caput(OUTPUT_LASER, float(offset), wait=True, timeout=2.0)
            readback = caget(OUTPUT_LASER)
            print(f"Set photodetector offset to {offset} counts, readback: {readback} counts")
            time.sleep(DWELL_TIME)
        print("Laser power step down complete.")
    except KeyboardInterrupt:
        print('\nStep down stopped by user.')
        safe_shutdown()
    finally:
        print('Final photodetector offset set to last value.')

if __name__== '__main__':
    main()
