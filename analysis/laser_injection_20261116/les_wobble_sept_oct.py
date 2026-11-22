#!/usr/bin/env python3
"""Within-coast speed wobble, September/October (better damping) vs November, on the SAME readout (LES) and estimator.
Analysis only, Mac. Asked by Molly 2026-11-21.

Estimator (as les_vs_tracker.py / G1): LES 2f line tracked with overnight_20261114/les_coasts.track (rotor f per window),
gamma_mid over the 0.40-0.47 Hz band (pair_plots), 10-block jackknife error = the within-coast wobble.
A torque noise of fixed spectral density gives a jackknife error ~ 1/sqrt(time in band), and the September coasts spend
~2x longer in the band (lower drag), so the comparison column is sigma_jk x sqrt(T_band / 600 s) ("wobble at 10 min").

Sept/Oct coasts: free spin-downs from the slide "Spindown: laser off" (CCW 09-13, CW 10-11), LES_YAW only (PIT not
fetched then). November: the ND4 night 11-16/17 (LES PIT/YAW, the better channel per coast, as les_vs_tracker.py).
    python3 les_wobble_sept_oct.py   # -> les_wobble_sept_oct.json
"""
import glob
import json
import os
import sys

import h5py
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'overnight_20261114'))
import les_coasts as L   # noqa: E402
import pair_plots as PP  # noqa: E402

DATA = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data')
OLD = {'CCW 2026-09-13': 'LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_1473375897_1473435502.h5',
       'CW 2026-10-11': 'LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_1475768725_1475784000.h5'}


def load_h5(p):
    with h5py.File(p, 'r') as f:
        y = np.asarray(f['data'], float); fs = float(f.attrs['sample_rate']); s = f['segments']
        g0, i0, n = s['gps_start'][:], s['index_start'][:], s['length'][:]
    assert fs == L.FS
    if len(g0) > 1:
        gap = np.abs(np.diff(g0) - n[:-1] / fs).max()
        assert gap < 1e-3, f'{p}: gap {gap}'
    return float(g0[0]), y


def coarse_line(y, i, n=120 * 1024):
    x = y[i:i + n] - y[i:i + n].mean()
    X = np.abs(np.fft.rfft(x * np.hanning(len(x)), 8 * len(x))); fr = np.fft.rfftfreq(8 * len(x), 1 / L.FS)
    m = (fr > 0.3) & (fr < 2.2)
    return fr[np.flatnonzero(m)[np.argmax(X[m])]]


def band_stats(v):
    s = (v[:, 1] >= PP.BAND[0]) & (v[:, 1] <= PP.BAND[1])
    t, f = v[s, 0], v[s, 1]
    if s.sum() < 15:
        return None
    g = PP.gamma_mid(t, f)[0]
    jk = PP.jk(lambda idx: PP.gamma_mid(t[idx], f[idx])[0], len(t))
    T = float(t[-1] - t[0])
    return dict(gamma_uHz=1e6 * g, jk_uHz=1e6 * jk, T_band_s=T, wobble10_uHz=1e6 * jk * np.sqrt(T / 600.0),
                snr=float(np.median(v[s, 2])), n_win=int(s.sum()))


def old_coasts():
    out = {}
    for lab, rel in OLD.items():
        g0, y = load_h5(os.path.join(DATA, rel))
        # start where the rotor has slowed to ~0.5 Hz (LES line < 1.0 Hz) on the first coast-down
        step = 60 * 1024; i = 0; prev = None
        while i + 120 * 1024 < len(y):
            ln = coarse_line(y, i)
            if prev is not None and ln < 1.0 and prev >= 0.9:
                break
            prev = ln; i += step
        v = L.track(y[i:i + 3600 * 1024], 0.0)          # one hour from there covers 0.5 -> ~0.35 Hz
        r = band_stats(v)
        r['start_fe_gps'] = g0 + i / L.FS
        out[lab] = r
        print(lab, {k: round(x, 2) if isinstance(x, float) else x for k, x in r.items()})
    return out


def nov_coasts():
    import les_vs_tracker as V
    g0, pit, yaw = V.load_les()
    g1 = g0 + len(pit) / L.FS
    rows = []
    for p in sorted(glob.glob(os.path.join(V.D, 'night_nd4_il2', 'coast_O*.txt'))):
        m = V.meta(p)
        if 'fe_gps_coast_end' not in m or 'fe_gps_field_off' not in m:
            continue
        a, b = m['fe_gps_field_off'] + 5, m['fe_gps_coast_end'] - 2
        if a < g0 or b > g1:
            continue
        i0, i1 = int((a - g0) * L.FS), int((b - g0) * L.FS)
        best = None
        for x in (pit, yaw):
            v = L.track(x[i0:i1], 0.0)
            if v.size and v[0, 1] >= PP.BAND[1]:
                r = band_stats(v)
                if r and (best is None or r['snr'] > best['snr']):
                    best = r
        if best:
            rows.append(best)
    a = lambda k: np.array([r[k] for r in rows])
    s = dict(n=len(rows), gamma_uHz=float(np.median(a('gamma_uHz'))), jk_rms_uHz=float(np.sqrt(np.mean(a('jk_uHz') ** 2))),
             T_band_s=float(np.median(a('T_band_s'))), wobble10_rms_uHz=float(np.sqrt(np.mean(a('wobble10_uHz') ** 2))),
             wobble10_min_max=[float(a('wobble10_uHz').min()), float(a('wobble10_uHz').max())], snr=float(np.median(a('snr'))))
    print('ND4 2026-11-16/17', {k: (round(x, 2) if isinstance(x, float) else x) for k, x in s.items()})
    return s


if __name__ == '__main__':
    res = dict(old=old_coasts(), nov_nd4=nov_coasts())
    json.dump(res, open(os.path.join(HERE, 'les_wobble_sept_oct.json'), 'w'), indent=1)
