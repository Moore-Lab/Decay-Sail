#!/usr/bin/env python3
"""Checks on the 2026-11-02 C2 holds beyond drive_coupling.py's table (analysis only).

    python3 c2_checks.py DATA_DIR      (DATA_DIR holds the gps1477668186 files, see README)

1. Wobble significance: angle at 1x/2x the drive in each third of a hold (amplitude and phase
   vs the drive), and the whole hold with the drive phase detuned by +-0.02 Hz. A real
   drive-locked wobble keeps its phase across thirds and drops when detuned.
2. Off-line amplitude floor: single-frequency fit (quadratic baseline) over 0.03-1.2 Hz,
   excluding +-0.02 Hz of k*f (k=1..4) and the 0.2-0.45 Hz swing band.
3. Swing amplitude (sqrt2 * rms of the linearly detrended angle) before and after each
   drive on/off (drive amplitude crossing 0.5).
4. Step 0 no-glide: field frequency in V2..V4_OUT_DQ during the outputs-off test.
5. Pedestal (DC) step vs oscillation: angle in 2 s windows around hold 1 on, hold 4 on, hold 3 off.
6. Every drive start: pedestal stagger between phases, differential field during the ramp, AC rise time.
6. Every drive start: pedestal stagger between phases, differential field during the ramp, AC rise time.
"""
import os, sys
import numpy as np
from types import SimpleNamespace
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'lab_utils'))
import drive_coupling as dc

D = sys.argv[1]
G, W = 'gps1477668186', '1477683254_1477685619'
a = SimpleNamespace(angles=os.path.join(D, 'blob_live_%s.csv' % G), frames=os.path.join(D, 'output_basler_%s.csv' % G),
                    v2=os.path.join(D, 'Y1_RDS-OUTS_V2_OUT_DQ_%s.h5' % W), v4=os.path.join(D, 'Y1_RDS-OUTS_V4_OUT_DQ_%s.h5' % W),
                    v3=os.path.join(D, 'Y1_RDS-OUTS_V3_OUT_DQ_%s.h5' % W), tau=15368.7)
t, th, phi, f, amp = dc.load(a)
thd = np.degrees(th)
HOLDS = [(107.3, 263.1), (354.5, 507.5), (598.5, 751.5), (842.4, 995.3), (1086.3, 1239.2), (1330.6, 1483.4), (1575.2, 1728.1)]


def fit(tt, y, ph):
    x = tt - tt.mean(); X = np.c_[np.cos(ph), np.sin(ph), np.ones_like(x), x, x * x]
    c, *_ = np.linalg.lstsq(X, y, rcond=None); return (180 / np.pi) * (c[0] + 1j * c[1])


print('1-2. wobble vs drive phase (deg)')
grid = np.arange(0.03, 1.2, 0.0025)
for i, (t0, t1) in enumerate(HOLDS, 1):
    m = (t >= t0 + 1) & (t <= t1 - 1); tt, y, ph = t[m], th[m], phi[m]; fe = abs(f[m].mean()); n = len(tt)
    s = []
    for k in (1, 2):
        z = [fit(tt[j * n // 3:(j + 1) * n // 3], y[j * n // 3:(j + 1) * n // 3], k * ph[j * n // 3:(j + 1) * n // 3]) for j in range(3)]
        det = [abs(fit(tt, y, k * (ph + np.sign(f[m].mean()) * 2 * np.pi * d * (tt - tt[0])))) for d in (-0.02, 0.02)]
        s.append('k%d thirds %s, phase %s; detuned %.1f/%.1f' % (k, '/'.join('%.1f' % abs(q) for q in z),
                 '/'.join('%.0f' % np.degrees(np.angle(q)) for q in z), *det))
    spec = np.array([abs(fit(tt, y, 2 * np.pi * g * (tt - tt.mean()))) for g in grid])
    ok = (grid < 0.2) | (grid > 0.45)
    for k in (1, 2, 3, 4): ok &= abs(grid - k * fe) > 0.02
    print('hold %d f=%.3f | %s | floor median %.2f, 95%% %.2f' % (i, fe, ' | '.join(s), np.median(spec[ok]), np.percentile(spec[ok], 95)))


def sw(t0, t1):
    m = (t >= t0) & (t < t1); x = t[m] - t[m].mean(); y = thd[m]; r = y - np.polyval(np.polyfit(x, y, 1), x)
    return np.sqrt(2) * r.std()


print('\n3. swing amplitude (deg) around drive on/off')
on = amp > 0.5
for i in np.flatnonzero(np.diff(on.astype(int))):
    tc = t[i]
    print('%s %7.1f s: [-15,-3] %5.1f -> [+3,+15] %5.1f -> [+15,+30] %5.1f' % (
        'ON ' if on[i + 1] else 'OFF', tc, sw(tc - 15, tc - 3), sw(tc + 3, tc + 15), sw(tc + 15, tc + 30)))


# 4. step 0 no-glide: field frequency of V2..V4_OUT_DQ in the outputs-off test (FE 1477683385-407)
import h5py
ph = []
for c in ('V2', 'V4', 'V3'):
    with h5py.File(os.path.join(D, 'Y1_RDS-OUTS_%s_OUT_DQ_%s.h5' % (c, W))) as h:
        ph.append(h['data'][:].astype(float)); fs = h.attrs['sample_rate']; g0 = h['segments/gps_start'][0]
i0, i1 = int((1477683380 - g0) * fs), int((1477683412 - g0) * fs)
z = sum(x[i0:i1] * np.exp(2j * np.pi * k / 3) for k, x in enumerate(ph))   # common pedestal cancels
k = np.flatnonzero(abs(z) > 0.5 * abs(z).max()); tk = g0 + (i0 + k) / fs; pk = np.unwrap(np.angle(z[k]))
inst = np.diff(pk) * fs / 2 / np.pi
print('\n4. step 0: drive above half amplitude FE %.2f-%.2f; f over first 2/5/10 s %s Hz; instantaneous f, first 1 s, %.4f-%.4f Hz'
      % (tk[0], tk[-1], '/'.join('%.4f' % (np.polyfit(tk[tk < tk[0] + w], pk[tk < tk[0] + w], 1)[0] / 2 / np.pi) for w in (2, 5, 10)),
         inst[:int(fs)].min(), inst[:int(fs)].max()))


# 5. pedestal (DC, common mode) vs oscillation timing at hold 1 on, hold 4 on, hold 3 off:
#    angle range in 2 s windows, with the pedestal and drive amplitude at each window's centre
# The video's first-frame true GPS, as drive_coupling.load computes it (its printed value):
ts_ = np.genfromtxt(a.frames, delimiter=',', names=True)
cam_ = (ts_['cam_timestamp_ns'] - ts_['cam_timestamp_ns'][0]) * 1e-9; host_ = ts_['host_time'] - ts_['host_time'][0]
c_, *_ = np.linalg.lstsq(np.c_[np.ones(len(cam_)), cam_], host_, rcond=None)
t_true0 = ts_['host_time'][0] - dc.GPS_UNIX_OFF + c_[0] + (host_ - c_[0] - c_[1] * cam_).min()
cm = sum(x[:min(map(len, ph))] for x in ph) / 3
td = g0 + np.arange(len(cm)) / fs - a.tau - t_true0
print('\n5. pedestal vs oscillation (2 s windows; angle min..max deg; pedestal counts; drive amplitude fraction)')
for name, (lo, hi) in (('hold 1 on', (95, 125)), ('hold 4 on', (830, 860)), ('hold 3 off', (745, 775))):
    m = (td > lo) & (td < hi); up = np.flatnonzero(np.diff((cm[m] > 3200).astype(int)))
    print('  %s: pedestal crosses half at %s s' % (name, np.round(td[m][up], 2)))
    for s0 in np.arange(lo, hi, 2.0):
        k = (t >= s0) & (t < s0 + 2)
        print('    %6.1f-%6.1f s  %7.2f..%7.2f  pedestal %5.0f  amp %.2f' % (
            s0, s0 + 2, thd[k].min(), thd[k].max(), np.interp(s0 + 1, td, cm), np.interp(s0 + 1, t, amp)))

# 6. every drive start: do the three pedestals ramp together, how big is the differential field
#    during the ramp, and does the AC ramp in (DRV_TRAMP) or step?
n6 = min(map(len, ph)); A6 = np.abs(sum(x[:n6] * np.exp(2j * np.pi * k / 3) for k, x in enumerate(ph)) * 2 / 3)
cm6 = sum(x[:n6] for x in ph) / 3; t6 = g0 + np.arange(n6) / fs
print('\n6. drive starts (0 = step-0 outputs-off test, 1-7 = holds); phases V2, V4, V3')
for j, i in enumerate(np.flatnonzero(np.diff((cm6 > 3200).astype(int)) == 1)):
    tc = t6[i]; m = (t6 > tc - 2) & (t6 < tc + 20); tt, aa = t6[m], A6[m]
    cr = [t6[np.flatnonzero((x[:n6] > 3200) & (t6 > tc - 2))[0]] - tc for x in ph]
    aft = tt > tc + 1.0
    i10 = np.flatnonzero((aa > 640) & aft)[0]; i90 = np.flatnonzero((aa > 5760) & aft)[0]
    print('  %d FE %.2f: pedestal half-crossings %s s; differential |z| max in ramp %4.0f counts; AC 10->90%% rise %.2f s'
          % (j, tc, ' '.join('%+.3f' % c for c in cr), aa[tt < tc + 1.0].max(), tt[i90] - tt[i10]))
