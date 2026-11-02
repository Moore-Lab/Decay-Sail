#!/usr/bin/env python3
"""Free-swing ring-down of the rotor (no drive), 2026-11-02: decay rate and swing frequency vs amplitude.

    python3 ringdown.py VIDEO_DIR [C2_DIR]

VIDEO_DIR holds blob_live_gps1477678308.csv (free swing, 39 min). Optional C2_DIR holds the C2
recording's blob_live_gps1477668186.csv + output_basler_gps1477668186.csv + OUT_DQ files, so the
drive-off gaps of C2 (large amplitude) can be added to the frequency-vs-amplitude curve.

Per window (WIN s, stepped by half a window): fit theta = A cos(2 pi f t + p) + c + d t by nonlinear
least squares starting from the FFT peak. Amplitude A (deg, half peak-to-peak of the fundamental) and
frequency f. Decay: straight-line fit of ln A vs t -> amplitude time constant tau_A, Q = pi f tau_A.
Analysis only.
"""
import csv, os, sys
import numpy as np
from scipy.optimize import curve_fit

WIN = 60.0
V = sys.argv[1]


def load(fn):
    rows = list(csv.DictReader(l for l in open(fn) if not l.startswith('#')))
    t = np.array([float(r['host_time']) for r in rows]); a = np.unwrap(np.deg2rad([float(r['angle_deg']) for r in rows]))
    return t - t[0], np.degrees(a), t[0]


def windows(t, th, t0=None, t1=None, win=WIN):
    t0 = t[0] if t0 is None else t0; t1 = t[-1] if t1 is None else t1
    out = []
    for s in np.arange(t0, t1 - win + 1e-9, win / 2):
        m = (t >= s) & (t < s + win); tt, y = t[m] - s, th[m]
        if len(tt) < 100: continue
        fr = np.fft.rfftfreq(4 * len(tt), tt[1] - tt[0]); sp = abs(np.fft.rfft((y - y.mean()) * np.hanning(len(y)), 4 * len(y)))
        b = (fr > 0.1) & (fr < 1.0); f0 = fr[b][np.argmax(sp[b])]
        g = lambda x, A, f, p, c, d: A * np.cos(2 * np.pi * f * x + p) + c + d * x
        try:
            P, C = curve_fit(g, tt, y, p0=[np.ptp(y) / 2, f0, 0, y.mean(), 0])
        except RuntimeError:
            continue
        A, f = abs(P[0]), P[1]; r = y - g(tt, *P)
        out.append((s + win / 2, A, f, np.sqrt(C[1, 1]), r.std()))
    return np.array(out)


t, th, T0 = load(os.path.join(V, 'blob_live_gps1477678308.csv'))
w = windows(t, th)
bad = w[:, 1] < 0.5 * np.median(w[:, 1])          # failed fits (one at 26.5 min: A 0.5 deg)
print('dropped %d failed window(s) at t = %s s' % (bad.sum(), np.round(w[bad, 0])))
w = w[~bad]
print('free swing gps1477678308: %.1f min, %d windows of %.0f s' % (t[-1] / 60, len(w), WIN))
for row in w[::8]:
    print('  t %6.0f s  A %5.1f deg  f %.4f +- %.4f Hz  resid rms %.1f deg' % tuple(row))
x, lA = w[:, 0], np.log(w[:, 1])
(sl, ic), cov = np.polyfit(x, lA, 1, cov=True)
fm = w[:, 2].mean()
tau = -1 / sl; dtau = np.sqrt(cov[0, 0]) / sl ** 2
print('decay: A %.1f -> %.1f deg; tau_A = %.0f +- %.0f s (fit, windows overlap so the error is optimistic); Q = pi f tau = %.0f'
      % (np.exp(ic + sl * x[0]), np.exp(ic + sl * x[-1]), tau, dtau, np.pi * fm * tau))
print('frequency: %.4f -> %.4f Hz over the recording (mean %.4f)' % (w[:8, 2].mean(), w[-8:, 2].mean(), fm))
c = np.polyfit(w[:, 1], w[:, 2], 1)
print('f vs A within this recording: slope %.2e Hz/deg (A and f both fall with time here)' % c[0])

if len(sys.argv) > 2:
    from types import SimpleNamespace
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'lab_utils'))
    import drive_coupling as dc
    D = sys.argv[2]; G, W = 'gps1477668186', '1477683254_1477685619'
    a = SimpleNamespace(angles=os.path.join(D, 'blob_live_%s.csv' % G), frames=os.path.join(D, 'output_basler_%s.csv' % G),
                        v2=os.path.join(D, 'Y1_RDS-OUTS_V2_OUT_DQ_%s.h5' % W), v4=os.path.join(D, 'Y1_RDS-OUTS_V4_OUT_DQ_%s.h5' % W),
                        v3=os.path.join(D, 'Y1_RDS-OUTS_V3_OUT_DQ_%s.h5' % W), tau=15368.7)
    t2, th2, phi, f2, amp = dc.load(a); th2 = np.degrees(th2)
    gaps = [(267.4, 347.1), (511.8, 591.1), (999.7, 1082.0), (1243.6, 1323.2), (1487.8, 1570.8)]
    print('\nC2 drive-off gaps (free swing, large amplitude):')
    allw = [w]
    for g0, g1 in gaps:
        ww = windows(t2, th2, g0 + 2, g1 - 2, win=40.0)
        allw.append(ww)
        print('  %6.0f-%6.0f s: A %5.1f deg  f %.4f Hz' % (g0, g1, ww[:, 1].mean(), ww[:, 2].mean()))
    W_ = np.vstack(allw)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].plot(w[:, 0] / 60, w[:, 1], '.'); ax[0].plot(x / 60, np.exp(ic + sl * x), 'r-', label='tau_A = %.0f s' % tau)
    ax[0].set_xlabel('time in gps1477678308 (min)'); ax[0].set_ylabel('swing amplitude (deg)'); ax[0].legend()
    ax[1].plot(w[:, 1], w[:, 2], '.', label='free swing 39 min')
    for ww in allw[1:]:
        ax[1].plot(ww[:, 1], ww[:, 2], 's', ms=4, color='C1')
    ax[1].plot([], [], 's', color='C1', label='C2 drive-off gaps')
    ax[1].set_xlabel('swing amplitude (deg)'); ax[1].set_ylabel('swing frequency (Hz)'); ax[1].legend()
    fig.tight_layout(); out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'plots', 'ringdown_20261102.png')
    os.makedirs(os.path.dirname(out), exist_ok=True); fig.savefig(out, dpi=110); print('plot', os.path.abspath(out))
