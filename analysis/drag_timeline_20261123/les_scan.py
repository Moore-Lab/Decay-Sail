#!/usr/bin/env python3
"""Sept/Oct LES h5: decimate to 8 Hz (cached in plots/, gitignored) and print a coarse 2f-ridge time series to find free coasts."""
import os, sys, glob
import h5py, numpy as np
from scipy import signal
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data')
FILES = ['LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_1472933400_1472935200.h5','LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_1473029300_1473037100.h5',
 'LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_1473050000_1473053600.h5','LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_1473065000_1473068600.h5',
 'LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_1473191140_1473191740.h5','LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_1473192742_1473194400.h5',
 'LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_1473204000_1473376497.h5','LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_1473375897_1473435502.h5',
 'LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_1475632200_1475769325.h5','LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_1475768725_1475784000.h5']
def dec8(rel):
    out = os.path.join(HERE, 'plots', 'dec8_' + os.path.basename(rel).replace('.h5', '.npz'))
    if os.path.exists(out):
        z = np.load(out); return float(z['g0']), z['y']
    with h5py.File(os.path.join(DATA, rel), 'r') as f:
        fs = float(f.attrs['sample_rate']); s = f['segments']; g0 = float(s['gps_start'][0]); n = len(f['data'])
        ns = len(s['gps_start'])
        ys = []
        CH = 1024 * 3600
        for i in range(0, n, CH):
            x = np.asarray(f['data'][i:i + CH], float); x = x - x.mean()
            for q in (8, 8, 2):
                x = signal.decimate(x, q, ftype='fir', zero_phase=True)
            ys.append(x)
    y = np.concatenate(ys)
    np.savez(out, g0=g0, y=y, segs=ns, fs=fs)
    return g0, y
if __name__ == '__main__':
    for rel in FILES:
        g0, y = dec8(rel)
        print(rel, 'g0', g0, 'dur_h', len(y) / 8 / 3600)
        W = 120 * 8; step = 600 * 8; rows = []
        for i in range(0, len(y) - W, step):
            x = y[i:i + W]; X = np.abs(np.fft.rfft(x * np.hanning(W), 16 * W)) ** 2; fr = np.fft.rfftfreq(16 * W, 1 / 8)
            m = (fr > 0.3) & (fr < 2.0); j = np.flatnonzero(m)[np.argmax(X[m])]
            nz = np.median(X[(fr > 0.3) & (fr < 2.0)])
            rows.append((i / 8 / 3600, fr[j], X[j] / nz))
        print(' '.join(f'{h:.1f}:{f:.2f}/{s:.0f}' for h, f, s in rows))
