"""Offset-path volts per count from the existing W2 scope records (2026-11-03): refit each channel with SEPARATE
gains for the pedestal (V{n}_OFFSET, slow ramp) and the AWG excitation (bursts / chirp), using scope_check.py's
tau, delay and clock-rate fit. Analysis only (data in Dropbox data/feedback/waveform/).

    python3 offset_gain_refit.py
"""
import os, sys, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'lab_utils'))
import scope_check as S
from scipy.ndimage import median_filter
D=os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/feedback/waveform/')
for run in ('bburst_1793746069','bchirp_1793746531'):
    cmd,dq,sc=S.load(D+run)
    out=S.score(cmd,dq,sc,quiet=True); res=out[1] if isinstance(out,tuple) else out
    fs=float(dq['fs']); t_dq=float(dq['gps0'])+np.arange(np.asarray(dq['V2']).size)/fs
    x2=np.asarray(dq['V2'],float)
    off0,_=S.coarse_offset(t_dq,x2-x2.mean(),np.asarray(sc['CH2_t'],float),np.asarray(sc['CH2'],float))
    print(f'{run} (amp {float(cmd["amp"]):g} on pedestal {float(cmd["pedestal"]):g})')
    for n in S.ELECTRODES:
        r=res[n]; x=np.asarray(dq[f'V{n}'],float)
        if run.startswith('bburst'):
            ped=median_filter(x, size=int(0.5*fs), mode='nearest')     # bursts are 0.1 s; the median removes them
        else:
            ped=median_filter(x, size=int(3.0*fs), mode='nearest')     # chirp >= 0.1 Hz... use a long window
        ac=x-ped
        k=r['kappa']; d=-r['delay']
        ts,ys=r['ts'],r['ys']
        tm=(ts-S.TREF[0])*(1+k)+S.TREF[0]+off0+d
        hp_p=S.resample_to(t_dq,S.highpass(ped,fs,r['tau']),tm); hp_a=S.resample_to(t_dq,S.highpass(ac,fs,r['tau']),tm)
        A=np.column_stack([hp_p,hp_a,np.ones_like(ts)])
        c,*_=np.linalg.lstsq(A,ys,rcond=None); e=ys-A@c
        # uncertainty (white-noise estimate)
        cov=np.linalg.inv(A.T@A)*e.var(); se=np.sqrt(np.diag(cov))
        # how much the pedestal part varies (signal size)
        print(f'  V{n}: single-gain fit G {r["G"]:.5f} (tau {r["tau"]:.2f} s) | split: pedestal G {c[0]:.5f} +- {se[0]:.5f}, AC G {c[1]:.5f} +- {se[1]:.5f}, ratio {c[0]/c[1]:.3f}; pedestal swing at electrode {np.ptp(hp_p)*c[0]:.1f} V, AC {np.ptp(hp_a)*c[1]:.1f} V')
