from epics import caput, caget

# Config
OUTPUT_LASER = 'Y1:RDS-OUTS_LASER_OFFSET'

caput(OUTPUT_LASER, 0.0, wait=True, timeout=2.0)
readback = caget(OUTPUT_LASER)
print(f'Laser OFF: readback {readback} counts')
