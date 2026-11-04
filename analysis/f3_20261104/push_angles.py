import csv, glob, numpy as np
from scipy.signal import medfilt, savgol_filter
B='/Users/mollywatts/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/feedback/f3/'
REST=229.8
def load(run):
    rows=list(csv.DictReader(l for l in open(glob.glob(B+run+'/blob_live_*.csv')[0]) if not l.startswith('#')))
    t=np.array([float(r['host_time']) for r in rows]); a=np.degrees(np.unwrap(np.radians([float(r['angle_deg']) for r in rows])))
    lg=list(csv.DictReader(l for l in open(glob.glob(B+run+'/feedback_*.csv')[0]) if not l.startswith('#')))
    lt=np.array([float(r['host_time']) for r in lg]); ps=np.array([float(r['psi_deg']) for r in lg])
    return t,a,lt,ps
# trap acceleration from the live2 coasting (U from energy conservation), as a function of angle from rest
t,a,lt,ps=load('live2')
w=savgol_filter(medfilt(a,5),15,3,deriv=1,delta=np.median(np.diff(t)))
phi=((a-REST+180)%360)-180
hold=(t>t[0]+30)&(t<t[0]+90)
ke=0.5*np.radians(w[hold])**2
tid=np.floor((a[hold]-REST+180)/360)
U=np.full(ke.size,np.nan)
for k in np.unique(tid):
    m=tid==k; b=np.abs(phi[hold][m])<10
    if m.sum()>50 and b.any(): U[m]=np.median(ke[m][b])-ke[m]
bins=np.arange(-180,181,5); Ub=np.array([np.nanmedian(U[(phi[hold]>=x)&(phi[hold]<x+5)]) for x in bins[:-1]]); cb=bins[:-1]+2.5
# smooth periodic fit of U with harmonics 1..4
X=np.column_stack([np.ones_like(cb)]+[f(np.radians(n*cb)) for n in range(1,5) for f in (np.cos,np.sin)])
cU,*_=np.linalg.lstsq(X[np.isfinite(Ub)],Ub[np.isfinite(Ub)],rcond=None)
def a_trap(phideg):   # -dU/dphi (rad/s^2)
    r=np.radians(phideg); out=np.zeros_like(r); k=1
    for n in range(1,5):
        out+= -(-n*cU[k]*np.sin(n*r)+n*cU[k+1]*np.cos(n*r)); k+=2
    return out
print('trap harmonics (U coeffs, rad^2/s^2):', np.round(cU,3))
# residual acceleration in field-on windows, vs field-rotor angle
res_all=[]
for run in ('live2','brake1'):
    t,a,lt,ps=load(run)
    dt=np.median(np.diff(t))
    asm=savgol_filter(medfilt(a,5),21,3)
    w=savgol_filter(asm,21,3,deriv=1,delta=dt); al=savgol_filter(asm,21,3,deriv=2,delta=dt)
    phi=((a-REST+180)%360)-180
    ar=np.radians(al)-a_trap(phi)
    res_all.append((run,t,a,ar,w,lt,ps))
for d in (0.0,0.05,0.07,0.1,0.15,0.2):
    D=[];R=[];W=[]
    for run,t,a,ar,w,lt,ps in res_all:
        j=np.searchsorted(lt+d,t)-1; ok=j>=0
        pc=np.where(ok,ps[np.clip(j,0,None)],-1)
        on=ok&(pc>=0)&(np.abs(ar)<20)
        Dl=((pc[on]+8*a[on])+180)%360-180   # field - rotor pattern (-8 theta): psi - (-8 theta)
        D.append(Dl); R.append(ar[on]); W.append(w[on])
    D=np.concatenate(D); R=np.concatenate(R)
    X=np.column_stack([np.ones_like(D),np.cos(np.radians(D)),np.sin(np.radians(D)),np.cos(np.radians(2*D)),np.sin(np.radians(2*D))])
    c,*_=np.linalg.lstsq(X,R,rcond=None); r2=1-np.var(R-X@c)/np.var(R)
    th=np.linspace(-180,180,721); f=np.column_stack([np.ones_like(th),np.cos(np.radians(th)),np.sin(np.radians(th)),np.cos(np.radians(2*th)),np.sin(np.radians(2*th))])@c
    print(f'delay {d:.2f}: n {D.size}, R2 {r2:.3f}, best + accel at {th[np.argmax(f)]:+.0f} ({f.max():.2f} rad/s2), best - at {th[np.argmin(f)]:+.0f} ({f.min():.2f}); at -88: {np.interp(-88,th,f):+.2f}, at +167: {np.interp(167,th,f):+.2f}')
# baseline: field-off residual spread
for run,t,a,ar,w,lt,ps in res_all:
    j=np.searchsorted(lt,t)-1; off=(j>=0)&(ps[np.clip(j,0,None)]<0)&(np.abs(ar)<20)
    print(run,'field-off residual accel: mean %.2f, std %.2f rad/s2'%(ar[off].mean(),ar[off].std()))
