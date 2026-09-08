#!/usr/bin/env python3
"""Track the rotation frequency after the drive stops. Read-only (NDS)."""
import time, sys, numpy as np, nds2
from epics import caget
STOP = 1472934149          # FE GPS when the drive ended
BLK  = 90                  # s per estimate
LOG  = '/home/controls/spindown_20260908.csv'

def peak(x, fs, lo=0.05, hi=3.0):
    ac = x - x.mean()
    X = np.abs(np.fft.rfft(ac * np.hanning(len(ac))))
    fr = np.fft.rfftfreq(len(ac), 1 / fs)
    m = (fr > lo) & (fr < hi)
    i = np.flatnonzero(m)[np.argmax(X[m])]
    y0, y1, y2 = X[i-1], X[i], X[i+1]
    den = y0 - 2*y1 + y2
    return fr[i] + (0.5*(y0-y2)/den if den else 0)*(fr[1]-fr[0])

with open(LOG, 'a', buffering=1) as fh:
    fh.write('# gps_mid, t_since_stop_s, f3_hz, f_rot_hz, rms\n')
    print(f'{"t-stop":>8} {"3x line":>9} {"rotation":>9} {"rms":>8}')
    while True:
        fe = caget('Y1:DAQ-DC0_GPS')
        a = int(fe - BLK - 25); b = int(fe - 25)
        if a < STOP:
            time.sleep(10); continue
        try:
            c = nds2.connection('cymac1', 8088)
            c.set_parameter('ALLOW_DATA_ON_TAPE', '1')
            x = np.array(c.fetch(a, b, ['Y1:RDS-LES_YAW_OUT_DQ'])[0].data, float)
        except Exception as e:
            print(f'  fetch: {e}'); time.sleep(15); continue
        f3 = peak(x, 1024.0, 0.30, 1.2)     # the strong 3x line
        frot = f3 / 3.0
        t = (a + b) / 2 - STOP
        print(f'{t:8.0f} {f3:9.4f} {frot:9.4f} {x.std():8.0f}', flush=True)
        fh.write(f'{(a+b)/2:.0f},{t:.0f},{f3:.5f},{frot:.5f},{x.std():.1f}\n')
        time.sleep(BLK)
