#!/usr/bin/env python3
"""ND2 interleaved run 2026-11-18/19 (nd2_run): outlier rule, drift fits, expected shift from the PD, temperature. (2026-11-19)
Mac only; reads the Dropbox tracker caches made by `coasts.py` (run it first for each night) and the run folders.

    python3 nd2_checks.py     # prints; writes nd2_checks.json

1. Outlier rule (proposed 2026-11-18 evening during the run, before pairs 25-40 were seen; Molly has not approved it):
   per coast, gamma in two fixed speed bands, h1 0.44-0.49 Hz and h2 0.38-0.43 Hz (quadratic in log f, at band centre).
   A coast is flagged if (h1 - h2) differs from that night's median (h1 - h2) by more than 15 uHz (~5x the per-half
   scatter of 2-3 uHz seen on the ND4/ND3 nights). Its pair is dropped. Applied to all three nights, blind to laser state.
2. ND2 on - off of Delta gamma = gamma(-) - gamma(+) (coasts.py values, 0.40-0.47 Hz): plain, with linear and quadratic
   drift in pair index, and ABBA blocks; all pairs and with flagged pairs dropped.
3. Expected shift: PD on - off from the 1-s trend (Y1:RDS-PD_IN1_DQ mean) over each coast window (front-end GPS from
   each coast file), the opposite state interpolated in time; 222 counts/mW; S1 = 52.2 uHz at 0.30 mW (ND1, 2026-11-16).
4. Mean gamma on - off (heating check); TSP01B air (ext_T0_C) per coast, + minus -.
Observations only.
"""
import csv
import glob
import importlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
B = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/')
NIGHTS = [('ND4', '2026-11-16', 'night_nd4_il2'), ('ND3', '2026-11-17', 'nd3_night'), ('ND2', '2026-11-18', 'nd2_run')]
BANDS = {'h1': (0.44, 0.49), 'h2': (0.38, 0.43)}
RULE = 15.0          # uHz
CPM = 222.0          # PD counts per mW
S1, P1 = 52.2, 0.30  # uHz at mW (ND1)


def meta(path):
    m = {}
    for line in open(path):
        p = line.split()
        if len(p) >= 2 and p[0] in ('field_off_host', 'coast_end_host', 'fe_gps_field_off', 'fe_gps_coast_end'):
            m[p[0]] = float(p[1])
        elif len(p) >= 2 and p[0] == 'laser':
            m['laser'] = p[1]
    return m


def band_gamma(T, F, lo, hi):
    s = (F >= lo) & (F <= hi)
    if s.sum() < 20 or F.max() < hi or F.min() > lo:
        return np.nan
    tt = T[s] - T[s][0]
    p = np.polyfit(tt, np.log(F[s]), 2)
    tm = tt[np.argmin(np.abs(F[s] - (lo + hi) / 2))]
    return -(2 * p[0] * tm + p[1]) * 1e6


def halves(day, run):
    if day == '2026-11-16':
        os.environ.pop('LASER_DIR', None)
    else:
        os.environ['LASER_DIR'] = B + day + '/laser'
    C = importlib.reload(importlib.import_module('coasts'))
    k, h, a, n = C.load_tracker(False)
    t_all = k / C.TC.FPS
    off = float(np.median(h - t_all))
    out = {}
    for p in sorted(glob.glob(os.path.join(C.D, run, 'coast_O*.txt'))):
        name = os.path.basename(p)[6:-4]
        m = meta(p)
        if 'coast_end_host' not in m:
            continue
        d = 1 if int(name[1:]) % 2 else -1
        t0, t1 = m['field_off_host'] + 5 - off, m['coast_end_host'] - 2 - off
        w = (t_all >= t0) & (t_all <= t1)
        tr = C.TC.turns(t_all[w] - t0, np.degrees(np.unwrap(np.radians(a[w]))), d, n[w] >= 0.5)
        out[name] = {kk: band_gamma(tr[:, 0], tr[:, 1], *bb) for kk, bb in BANDS.items()}
        out[name].update(m)
    return out


def fits(dg, on, idx):
    """on - off of dg: plain, linear and quadratic drift in pair index, ABBA blocks of 4 consecutive pairs."""
    r = {}
    a, b = dg[on], dg[~on]
    r['plain'] = (a.mean() - b.mean(), np.hypot(a.std(ddof=1) / np.sqrt(len(a)), b.std(ddof=1) / np.sqrt(len(b))))
    for deg, key in ((1, 'linear'), (2, 'quadratic')):
        x = (idx - idx.mean()) / 10.0
        X = np.column_stack([on.astype(float), np.ones_like(x)] + [x ** j for j in range(1, deg + 1)])
        beta, res, *_ = np.linalg.lstsq(X, dg, rcond=None)
        resid = dg - X @ beta
        s2 = resid @ resid / (len(dg) - X.shape[1])
        cov = s2 * np.linalg.inv(X.T @ X)
        r[key] = (beta[0], np.sqrt(cov[0, 0]))
    blocks = []
    for b0 in range(1, int(idx.max()) + 1, 4):
        s = (idx >= b0) & (idx < b0 + 4)
        if (s & on).any() and (s & ~on).any():
            blocks.append(dg[s & on].mean() - dg[s & ~on].mean())
    blocks = np.array(blocks)
    r['abba'] = (blocks.mean(), blocks.std(ddof=1) / np.sqrt(len(blocks)))
    r['abba_blocks'] = [round(float(x), 2) for x in blocks]
    return {k_: (v if k_ == 'abba_blocks' else [round(float(v[0]), 2), round(float(v[1]), 2)]) for k_, v in r.items()}


def main():
    S = {'rule_uHz': RULE, 'nights': {}}
    H = {}
    for lab, day, run in NIGHTS:
        H[lab] = hv = halves(day, run)
        d = np.array([v['h1'] - v['h2'] for v in hv.values()])
        med = float(np.nanmedian(d))
        dev = {nm: v['h1'] - v['h2'] - med for nm, v in hv.items()}
        flag = sorted(nm for nm, x in dev.items() if np.isfinite(x) and abs(x) > RULE)
        sd = float(np.nanstd(d, ddof=1))
        rest = np.array([abs(x) for nm, x in dev.items() if np.isfinite(x) and nm not in flag])
        nan = sorted(nm for nm, x in dev.items() if not np.isfinite(x))
        print(f'{lab}: {len(hv)} coasts, median(h1-h2) {med:+.1f} uHz, sd {sd:.1f}; flagged {flag} '
              f'({", ".join(f"{dev[f]:+.1f}" for f in flag)}); largest unflagged |dev| {rest.max():.1f}; no halves: {nan}')
        S['nights'][lab] = dict(median=round(med, 2), sd=round(sd, 2), flagged={f: round(float(dev[f]), 1) for f in flag},
                                max_unflagged=round(float(rest.max()), 1), no_halves=nan)

    # ND2 pairs from coasts.py's table
    rows = [r for r in csv.DictReader(open(os.path.join(HERE, 'coasts_table_2026-11-18.csv'))) if r['run'] == 'nd2_run']
    g = {r['name']: r for r in rows}
    hv = H['ND2']
    flag = set(S['nights']['ND2']['flagged'])
    P = []
    for i in range(1, 81, 2):
        pn, mn = f'O{i:02d}', f'O{i + 1:02d}'
        gp, gm = float(g[pn]['gamma_mHz']), float(g[mn]['gamma_mHz'])
        scale = 1e3                                # mHz -> uHz
        P.append(dict(pair=(i + 1) // 2, pn=pn, mn=mn, on=hv[pn]['laser'] == 'on', dg=(gm - gp) * scale,
                      mean=(gm + gp) / 2 * scale, flag=pn in flag or mn in flag,
                      t0=hv[pn]['fe_gps_field_off'], gps=[(hv[c]['fe_gps_field_off'], hv[c]['fe_gps_coast_end']) for c in (pn, mn)]))
    idx = np.array([p['pair'] for p in P], float)
    on = np.array([p['on'] for p in P])
    dg = np.array([p['dg'] for p in P])
    mg = np.array([p['mean'] for p in P])
    keep = ~np.array([p['flag'] for p in P])
    S['nd2_all'] = fits(dg, on, idx)
    S['nd2_rule'] = fits(dg[keep], on[keep], idx[keep])
    S['nd2_dropped_pairs'] = [p['pair'] for p in P if p['flag']]
    S['mean_gamma_on_minus_off'] = fits(mg[keep], on[keep], idx[keep])['plain']
    S['dg_sd_rule'] = {'on': round(float(dg[keep & on].std(ddof=1)), 2), 'off': round(float(dg[keep & ~on].std(ddof=1)), 2)}
    print(f'\nND2 dropped pairs: {S["nd2_dropped_pairs"]}')
    for key in ('nd2_all', 'nd2_rule'):
        print(key, json.dumps(S[key]))
    print('mean gamma on - off (rule):', S['mean_gamma_on_minus_off'], ' Delta-gamma sd (rule):', S['dg_sd_rule'])

    # PD from the 1-s trend
    z = np.genfromtxt(B + '2026-11-18/laser/pd_trend/pd_trend_1s.csv', delimiter=',', names=True)
    lvl = []
    for p in P:
        s = np.zeros(len(z), bool)
        for a_, b_ in p['gps']:
            s |= (z['gps'] >= a_) & (z['gps'] <= b_)
        lvl.append(float(z['pd_mean'][s].mean()))
    lvl = np.array(lvl)
    tt = np.array([p['t0'] for p in P])
    step = np.array([lvl[i] - np.interp(tt[i], tt[on != on[i]], lvl[on != on[i]]) for i in range(len(P))])
    step = np.where(on, step, -step)
    mstep = float(step.mean())
    exp = S1 * (mstep / CPM) / P1
    S['pd'] = dict(on_mean=round(float(lvl[on].mean()), 3), off_mean=round(float(lvl[~on].mean()), 3),
                   step_mean=round(mstep, 3), step_min=round(float(step.min()), 3), step_max=round(float(step.max()), 3),
                   power_uW=round(mstep / CPM * 1e3, 1), expected_uHz=round(exp, 2))
    print('\nPD (1-s trend, coast windows):', S['pd'])

    # TSP01B air temperature per coast (host clock)
    tf = glob.glob(B + '2026-11-17/env/tsp01b_host*.csv')[0]
    T = np.genfromtxt((l for l in open(tf) if not l.startswith('#')), delimiter=',', names=True)
    def tmean(nm):
        m = hv[nm]
        s = (T['unix'] >= m['field_off_host']) & (T['unix'] <= m['coast_end_host'])
        return float(T['ext_T0_C'][s].mean()) if s.any() else np.nan
    tp = np.array([tmean(p['pn']) for p in P]); tm = np.array([tmean(p['mn']) for p in P])
    dT = tm - tp
    ok = np.isfinite(dT) & keep
    r = float(np.corrcoef(dT[ok], dg[ok] - np.where(on[ok], dg[ok & on].mean(), dg[ok & ~on].mean()))[0, 1]) if ok.sum() > 3 else np.nan
    S['air'] = dict(range=[round(float(np.nanmin(np.r_[tp, tm])), 2), round(float(np.nanmax(np.r_[tp, tm])), 2)],
                    plus_minus_minus=round(float(np.nanmean(-dT)), 3), sem=round(float(np.nanstd(dT, ddof=1) / np.sqrt(np.isfinite(dT).sum())), 3),
                    r_dT_dg=round(r, 2), n=int(ok.sum()))
    print('air (ext_T0_C):', S['air'])
    json.dump(S, open(os.path.join(HERE, 'nd2_checks.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
