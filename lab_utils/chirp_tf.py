#!/usr/bin/env python3
"""W2 bchirp: amplifier response vs frequency at the electrodes (scope / OUT_DQ), per band.
Run 2026-11-03 bchirp_1793743924 (paths below). Complex gain per band from a local fit
scope = a + b*t + Re(H) * x + Im-part * hilbert(x); kappa = FE/scope clock-rate difference from W2 bburst.
Inter-electrode timing = phase of H3/H2 (same scope clock, so robust). Absolute phase is NOT reported as a
result: it depends on the arbitrary scope-clock alignment and kappa.
"""
import sys, numpy as np
sys.path.insert(0, '/Users/mollywatts/Desktop/VSCode/decay_sail_wt_wave/lab_utils')
import scope_check as S
from scipy.signal import hilbert
D='/Users/mollywatts/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/feedback/waveform/bchirp_1793743924'
cmd=dict(np.load(D+'/command.npz')); dq=dict(np.load(D+'/out_dq.npz')); sc=dict(np.load(D+'/scope_1793744239_w2_complete.npz'))
fs=float(dq['fs']); t_dq=float(dq['gps0'])+np.arange(dq['V2'].size)/fs; start=float(cmd['start_gps'])
x2=dq['V2'].astype(float)
off0,_=S.coarse_offset(t_dq, x2-x2.mean(), sc['CH2_t'].astype(float), sc['CH2'].astype(float))
print('coarse offset', off0)
kappa=0.001233; tref=start+30-off0
def fe_time(ts): return (ts-tref)*(1+kappa)+tref+off0
bands=[0.3,0.5,0.7,1,1.5,2,3,5,7,10]
T=60.0; f1,f2=0.1,12.0
def tf(n, ch):
    x=dq['V%d'%n].astype(float); xh=np.imag(hilbert(x-np.median(x)))
    ts=sc[ch+'_t'].astype(float); y=sc[ch].astype(float); tf_=fe_time(ts)
    out=[]
    for fb in bands:
        tc=start+T*np.log(fb/f1)/np.log(f2/f1)
        half=max(2.0/fb,0.5)
        m=(tf_>tc-half)&(tf_<tc+half)
        xm=np.interp(tf_[m],t_dq,x); xhm=np.interp(tf_[m],t_dq,xh)
        A=np.column_stack([np.ones(m.sum()), tf_[m]-tc, xm-np.median(xm), xhm])
        c,*_=np.linalg.lstsq(A,y[m],rcond=None)
        H=c[2]-1j*c[3]
        r=y[m]-A@c
        out.append((fb,H,r.std()))
    return out
res={n:tf(n,ch) for n,ch in ((2,'CH2'),(3,'CH3'),(4,'CH4'))}
# fit a pure delay to V2 phase after removing one-pole high-pass lead with tau=5.6
f=np.array(bands)
for n in (2,3,4):
    H=np.array([h for _,h,_ in res[n]])
    print(f'V{n}: |H| V/count:', ' '.join(f'{fb:g}Hz {abs(h):.5f}' for fb,h in zip(f,H)))
H2=np.array([h for _,h,_ in res[2]]); H3=np.array([h for _,h,_ in res[3]])
ph2=np.unwrap(np.angle(H2)); lead=np.arctan(1/(2*np.pi*f*5.6))
dt=np.polyfit(2*np.pi*f, -(ph2-lead), 1)[0]
print('V2 phase - one-pole(5.6 s) lead, after best pure delay %.2f ms (arbitrary scope clock):'%(1e3*dt),
      ' '.join(f'{fb:g}:{np.degrees(p-l+2*np.pi*fb*dt):+.1f}' for fb,p,l in zip(f,ph2,lead)))
rel=np.degrees(np.angle(H3/H2)); print('V3 vs V2 phase deg:', ' '.join(f'{fb:g}:{r:+.2f}' for fb,r in zip(f,rel)))
print('  -> V3 vs V2 timing ms (+ = V3 later):', ' '.join(f'{fb:g}:{-1e3 * r / 360 / fb:+.3f}' for fb, r in zip(f, rel)))
print('residual V:', ' '.join(f'{r:.2f}' for _,_,r in res[2]))
