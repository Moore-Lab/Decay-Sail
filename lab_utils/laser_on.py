from epics import caput, caget

# Config
OUTPUT_LASER = 'Y1:RDS-OUTS_LASER_OFFSET'
COUNTS = 800  # <-- edit this to set laser power

caput(OUTPUT_LASER, float(COUNTS), wait=True, timeout=2.0)
readback = caget(OUTPUT_LASER)
print(f'Laser ON: set {COUNTS} counts, readback {readback} counts')
print("Press Ctrl+C or type 'q' + Enter to turn laser off...")

try:
    while True:
        if input().strip().lower() == 'q':
            break
except KeyboardInterrupt:
    pass

caput(OUTPUT_LASER, 0.0, wait=True, timeout=2.0)
print(f'Laser OFF: readback {caget(OUTPUT_LASER)} counts')
