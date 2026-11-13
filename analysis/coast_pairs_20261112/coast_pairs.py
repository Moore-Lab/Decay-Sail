#!/usr/bin/env python3
"""CW/CCW damping from the 2026-11-12 coast pairs (C1 +1, C2 -1, C3 +1 to the camera move). Mac only.

    python3 coast_pairs.py      # -> coast_pairs.json, plots/coast_pairs.png, printed table

Per coast (field off, no writes; windows from coast_C*.txt, C3 cut 5 s before the camera move at host 1794511172.9):
 1. Per-turn rates: unwrapped angle, crossings of each 360 deg interpolated between frames, time = frame index x 20 ms
    (camera isochronous at 50 fps; the scoring method, DECISIONS 2026-11-12). Frames with ncc < 0.5 dropped (C2: a
    7-frame dot loss at coast+34.3 s); turns spanning a dropped stretch are discarded.
    Fit f(t) = f0 exp(-t/tau) by least squares, (a) over each whole window and (b) over the COMMON band 0.44-0.49 Hz
    (covered by all three) and C1/C2 also over 0.38-0.49 Hz.
 2. Energy (trap included): E = 1/2 w^2 + U(theta) with U from S1's coast (analysis/spinup_spin_20261111/coast_trap.json),
    per frame; average E and w^2 over each turn; fit dE/dt = -c <w^2> turn by turn (viscous c; for a free rotor
    tau = 1/c). Same bands.
Errors: 1-sigma, delete-one-block jackknife over 10 contiguous blocks of turns.
"""
import json
import os

import numpy as np
from scipy.signal import savgol_filter

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-12/coast')
CT = json.load(open(os.path.join(HERE, '..', 'spinup_spin_20261111', 'coast_trap.json')))
FPS = 50.0
MOVE = 1794511172.9
COASTS = [('C1', +1, 'tracker_1/blob_live_gps1478544406.csv'), ('C2', -1, 'tracker_1/blob_live_gps1478544406.csv'),
          ('C3', +1, 'tracker_2/blob_live_gps1478545917.csv'),
          ('C3b', +1, 'tracker_3/blob_live_gps1478549385.csv'), ('C4', -1, 'tracker_3/blob_live_gps1478549385.csv'),
          ('C5', +1, 'tracker_4/blob_live_gps1478550935.csv'), ('C6', -1, 'tracker_4/blob_live_gps1478550935.csv')]
PAIRS = [('C1', 'C2'), ('C3b', 'C4'), ('C5', 'C6')]         # back-to-back +/- pairs (C3 partial: extra)
BANDS = {'common 0.44-0.49': (0.44, 0.49), 'full 0.38-0.49': (0.38, 0.49)}


def meta(name):
    m = {}
    for line in open(os.path.join(D, f'coast_{name}.txt')):
        p = line.split()
        if len(p) >= 2 and p[0] in ('field_off_host', 'coast_end_host'):
            m[p[0]] = float(p[1])
    return m


def load(fn):
    import csv
    rows = [r for r in csv.DictReader(l for l in open(os.path.join(D, fn)) if not l.startswith('#'))]
    k = np.array([int(r['frame']) for r in rows]); h = np.array([float(r['host_time']) for r in rows])
    a = np.array([float(r['angle_deg']) for r in rows]); n = np.array([float(r['ncc']) for r in rows])
    t = k / FPS
    off = np.median(h - t)
    return t, off, a, n


def turns(t, th, d, good):
    """Per-turn (t_mid, rate) from interpolated crossings; drop turns containing bad frames."""
    x = d * (th - th[0])
    n = np.floor(x / 360.0)
    idx = np.where(np.diff(n) > 0)[0]
    tc, ok = [], []
    for i in idx:
        frac = (360.0 * n[i + 1] - x[i]) / (x[i + 1] - x[i])
        tc.append(t[i] + frac * (t[i + 1] - t[i])); ok.append(i)
    tc = np.array(tc)
    bad_t = t[~good]
    out = []
    for j in range(1, len(tc)):
        if bad_t.size and np.any((bad_t >= tc[j - 1]) & (bad_t <= tc[j])):
            continue
        out.append((0.5 * (tc[j] + tc[j - 1]), 1.0 / (tc[j] - tc[j - 1]), tc[j - 1], tc[j]))
    return np.array(out)


def fit_tau(tm, f):
    p = np.polyfit(tm, np.log(f), 1)
    return -1.0 / p[0] / 60.0                                  # minutes


def energy_turns(t, th, good, tr):
    th_r = np.radians(th)
    w = np.radians(savgol_filter(th, 9, 3, deriv=1, delta=1 / FPS))
    U = np.interp(np.mod(th, 360.0), CT['theta_deg'], CT['U'], period=360.0)
    E = 0.5 * w ** 2 + U
    out = []
    for tmid, f, t0, t1 in tr:
        m = (t >= t0) & (t < t1) & good
        if m.sum() < 20:
            continue
        out.append((tmid, f, E[m].mean(), (w[m] ** 2).mean()))
    return np.array(out)


def fit_c(et):
    # dE/dt between consecutive turns against the mean <w^2>
    dt = np.diff(et[:, 0]); dE = np.diff(et[:, 2]); w2 = 0.5 * (et[1:, 3] + et[:-1, 3])
    return float(-np.sum(dE * w2 / dt) / np.sum(w2 * w2))     # least squares for dE/dt = -c w2


def boot(fn, arr, nb=10):
    """1-sigma from a delete-one-block jackknife over nb contiguous blocks of turns (keeps turn order, so time
    differences stay valid; also allows for correlated residuals between neighbouring turns)."""
    edges = np.linspace(0, len(arr), nb + 1).astype(int)
    v = [fn(np.concatenate([arr[:edges[j]], arr[edges[j + 1]:]])) for j in range(nb)]
    return float(np.sqrt((nb - 1) / nb * np.sum((np.array(v) - np.mean(v)) ** 2)))


def main():
    res = {}
    traces = {}
    for name, d, fn in COASTS:
        m = meta(name)
        t, off, a, n = load(fn)
        t0 = m['field_off_host'] + 5 - off
        t1 = (min(m['coast_end_host'], MOVE - 5) if name == 'C3' else m['coast_end_host']) - off
        w = (t >= t0) & (t <= t1)
        tt, aa, nn = t[w], a[w], n[w]
        th = np.degrees(np.unwrap(np.radians(aa)))
        good = nn >= 0.5
        tr = turns(tt, th, d, good)
        tr[:, 0] -= t0; tr[:, 2] -= t0; tr[:, 3] -= t0
        tt0 = tt - t0
        et = energy_turns(tt0, th, good, tr)
        traces[name] = tr
        r = {'dir': d, 'n_turns': int(len(tr)), 'f_start': float(tr[0, 1]), 'f_end': float(tr[-1, 1]),
             'dropped_frames': int((~good).sum()), 'window_s': float(t1 - t0)}
        r['tau_whole_min'] = fit_tau(tr[:, 0], tr[:, 1])
        r['tau_whole_err'] = boot(lambda x: fit_tau(x[:, 0], x[:, 1]), tr)
        r['c_whole'] = fit_c(et); r['c_whole_err'] = boot(fit_c, et)
        for bn, (lo, hi) in BANDS.items():
            if bn.startswith('full') and name == 'C3':
                continue
            s = (tr[:, 1] >= lo) & (tr[:, 1] <= hi)
            se = (et[:, 1] >= lo) & (et[:, 1] <= hi)
            if s.sum() < 10:
                continue
            r[f'tau {bn}'] = fit_tau(tr[s, 0], tr[s, 1]); r[f'tau {bn} err'] = boot(lambda x: fit_tau(x[:, 0], x[:, 1]), tr[s])
            r[f'c {bn}'] = fit_c(et[se]); r[f'c {bn} err'] = boot(fit_c, et[se])
            r[f'n {bn}'] = int(s.sum())
        res[name] = r
    for name, r in res.items():
        print(name, {k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()})
    # CW/CCW comparisons
    print()
    out = {}
    for bn in BANDS:
        for q in ('tau', 'c'):
            k, ke = f'{q} {bn}', f'{q} {bn} err'
            diffs = []
            for p_, m_ in PAIRS:
                a1, e1 = res[p_][k], res[p_][ke]; a2, e2 = res[m_][k], res[m_][ke]
                diffs.append((100 * (a2 / a1 - 1), 100 * np.hypot(e1 / a1, e2 / a2)))
            dv = np.array(diffs)
            wts = 1 / dv[:, 1] ** 2
            mean = float(np.sum(dv[:, 0] * wts) / np.sum(wts)); err = float(1 / np.sqrt(np.sum(wts)))
            chi2 = float(np.sum((dv[:, 0] - mean) ** 2 * wts))
            plus = [res[n_][k] for n_ in ('C1', 'C3b', 'C5')]; minus = [res[n_][k] for n_ in ('C2', 'C4', 'C6')]
            out[k] = dict(pairs=diffs, weighted_mean_pct=mean, err_pct=err, chi2=chi2, plus=plus, minus=minus)
            print(f'{k}: pair diffs (- vs +, %): ' + ', '.join(f'{d:+.2f}±{e:.2f}' for d, e in diffs)
                  + f' | weighted mean {mean:+.2f} ± {err:.2f} % (chi2 {chi2:.1f}/2) | + values '
                  + ', '.join(f'{v:.5g}' for v in plus) + ' | - values ' + ', '.join(f'{v:.5g}' for v in minus))
    json.dump(dict(per_coast=res, comparison=out), open(os.path.join(HERE, 'coast_pairs.json'), 'w'), indent=1)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig, ax = plt.subplots(1, 2, figsize=(14, 4.6))
    for name, col in (('C1', 'C0'), ('C3b', 'C9'), ('C5', 'C2'), ('C2', 'C3'), ('C4', 'C1'), ('C6', 'C6')):
        tr = traces[name]
        lab = f'{name} ({"+" if res[name]["dir"] > 0 else "-"}1): tau {res[name]["tau_whole_min"]:.1f} min'
        ax[0].plot(tr[:, 0] / 60, tr[:, 1], '.', ms=2, color=col, label=lab)
        ax[1].plot(tr[:, 1], np.gradient(np.log(tr[:, 1]), tr[:, 0]) * -60, '.', ms=2, color=col, alpha=0.4)
    ax[0].set_xlabel('min after field off'); ax[0].set_ylabel('per-turn rate (Hz)'); ax[0].legend(fontsize=8)
    ax[0].set_title('coasts (field off), per-turn rate', fontsize=10)
    ax[1].set_xlabel('rate (Hz)'); ax[1].set_ylabel('local 1/tau (1/min)'); ax[1].set_ylim(0, 0.08)
    ax[1].set_title('local decay rate vs speed (noisy per turn)', fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'coast_pairs.png'), dpi=95)


if __name__ == '__main__':
    main()
