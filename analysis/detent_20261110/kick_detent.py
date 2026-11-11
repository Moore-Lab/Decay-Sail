"""Field-driven angular acceleration at each switch-on (derived), 2026-11-10 detent runs.

    python3 kick_detent.py DATA_DIR
Free trap acc(theta) is binned (1 deg) from the field-off free swing after run 2 (from 25 s after the
C2 ramp end, when the derived AC-coupled residual is < 2 % of the step, to the end of the video;
covers ~145-294 deg). acc from a Savitzky-Golay fit (15 frames, cubic) of the tracked angle.
Residual = measured acc - trap(theta) over the first 0.6 s after each switch-on (derived field
fraction ~1.0-0.9 of the step there). Also the swing-energy change: E = 1/2 omega^2 + U(theta),
U from integrating the binned trap; dE across each step (hold+ramp+gap) in (rad/s)^2.
Writes kick_detent.csv and plots/detent_kick_residual.png.
"""
import sys, os, glob, numpy as np, pandas as pd, matplotlib
from scipy.signal import savgol_filter
matplotlib.use('Agg'); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); D = sys.argv[1]
d = pd.read_csv(os.path.join(HERE, 'rotor_angle_detent.csv'))
t = d.host_time_cam.values; a = d.angle_deg.values; dt = np.median(np.diff(t))
w = savgol_filter(a, 15, 3, deriv=1, delta=dt); acc = savgol_filter(a, 15, 3, deriv=2, delta=dt)  # deg/s, deg/s^2
ev = pd.concat([pd.read_csv(f, comment='#') for f in sorted(glob.glob(os.path.join(D, 'detent_events_*.csv')))], ignore_index=True)
on = ev[ev.event == 'on'].reset_index(drop=True); rel = ev[ev.event == 'release'].reset_index(drop=True)
free = t > rel.host_time.iloc[-1] + 30 + 25
bins = np.arange(140, 300.1, 1.0); c = (bins[1:] + bins[:-1]) / 2
ib = np.digitize(a[free], bins) - 1
trap = np.array([np.median(acc[free][ib == k]) if (ib == k).sum() >= 5 else np.nan for k in range(len(c))])
nb = np.array([(ib == k).sum() for k in range(len(c))])
ok = np.isfinite(trap); trapf = lambda th: np.interp(th, c[ok], trap[ok])
# zero of trap acc (stable point) for reference
U = -np.cumsum(np.where(ok, trap, 0)) * 1.0   # deg^2/s^2 per deg-bin, potential up to const
Uf = lambda th: np.interp(th, c, U)
E = 0.5 * w ** 2 + Uf(a)
rows = []
f, ax = plt.subplots(1, 2, figsize=(13, 4.5))
COL = {'A': '#2a78d6', 'B': '#eb6834', 'C': '#1baf7a'}
for n, r in on.iterrows():
    lab = '%s%d' % (r.phase, 1 if r.counts == 3200 else 2)
    m = (t >= r.host_time) & (t < r.host_time + 0.6)
    res = acc[m] - trapf(a[m])
    pre = (t >= r.host_time - 5) & (t < r.host_time)
    res_pre = acc[pre] - trapf(a[pre])
    e0 = np.median(E[(t > r.host_time - 3) & (t < r.host_time)])
    nxt = on.host_time[n + 1] if n + 1 < len(on) else rel.host_time.iloc[-1] + 40
    e1 = np.median(E[(t > nxt - 3) & (t < nxt)])
    rows.append(dict(step=lab, counts=r.counts, angle_range='%.1f-%.1f' % (a[m].min(), a[m].max()),
                     res_acc_mean_dps2=res.mean(), res_acc_rad_s2=np.deg2rad(res.mean()),
                     pre_res_rms_dps2=res_pre.std(), E_before=e0, E_after=e1))
    ls = '-' if r.counts == 3200 else '--'
    ax[0].plot(a[m], np.deg2rad(res), ls, color=COL[r.phase], label=lab, lw=1.5)
ax[0].axhline(0, color='#6b6a63', lw=0.6); ax[0].set_xlabel('rotor angle (deg)'); ax[0].set_ylabel('acc − free trap (rad/s²)')
ax[0].set_title('residual acceleration, first 0.6 s after switch-on (derived)', loc='left', fontsize=10); ax[0].legend(fontsize=8, frameon=False)
ax[1].plot(c, np.deg2rad(trap), color='#1f1f1e'); ax[1].axhline(0, color='#6b6a63', lw=0.6)
ax[1].set_xlabel('rotor angle (deg)'); ax[1].set_ylabel('free acc (rad/s²)'); ax[1].set_title('free trap acc, field-off swing after run 2 (measured)', loc='left', fontsize=10)
for x in ax: x.grid(color='#e4e3dd', lw=0.6)
f.savefig(os.path.join(HERE, 'plots', 'detent_kick_residual.png'), dpi=120, bbox_inches='tight')
k = pd.DataFrame(rows); k.to_csv(os.path.join(HERE, 'kick_detent.csv'), index=False, float_format='%.3f')
print(k.round(2).to_string())
zc = c[ok][np.where(np.diff(np.sign(trap[ok])) < 0)[0]]
print('free trap stable zeros (acc + to -):', zc, ' bins with data:', ok.sum(), 'min count', nb[ok].min())
print('trap acc rad/s2 at 192..208 step 4:', np.round(np.deg2rad(trapf(np.arange(186, 212, 4))), 2))
