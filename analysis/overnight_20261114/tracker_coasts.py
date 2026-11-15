#!/usr/bin/env python3
"""Overnight coast series 2026-11-14/15: damping per coast from the TRACKER, compared coast by coast with the LES.
Mac only, reads Dropbox.

    python3 tracker_coasts.py      # needs les_coasts.json (run les_coasts.py first) -> tracker_coasts.json/.csv,
                                   # plots/tracker_vs_les.png

Data: Dropbox spinup/2026-11-14/overnight/tracker/blob_live_gps1478746563.csv (one tracker run all night, 50 fps,
0 BlockID gaps) and series/coast_On.txt (field_off_host, coast_end_host: worker2 host clock, as the tracker's
host_time).

Method: as analysis/coast_pairs_20261112/coast_pairs.py (the 11-12 coast pairs).
 - Time = frame index x 20 ms (camera isochronous at 50 fps); host time only to place the coast windows (median
   host - frame time offset over the whole run).
 - Window [field off + 5 s, coast end - 2 s] (the same as les_coasts.py). Frames with ncc < 0.5 dropped; turns
   spanning a dropped frame discarded.
 - Per-turn rates from interpolated 360 deg crossings in the commanded direction. Fit f(t) = f0 exp(-t/tau)
   (log-linear least squares) over the whole coast and over the COMMON band 0.40-0.47 Hz (the band of les_coasts.py).
 - Coasts that les_coasts.py calls swings (not rotating) are skipped; whole-coast summaries use coasts starting
   >= 0.48 Hz, as there.
Summaries as les_coasts.py: per direction mean, sd, trend; - minus + pair differences. Plus tracker minus LES per coast.
"""
import csv
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-14/overnight')
CSV = os.path.join(D, 'tracker', 'blob_live_gps1478746563.csv')
FPS = 50.0
BAND = (0.40, 0.47)


def load():
    cache = os.path.join(HERE, 'plots', 'tracker_cache.npz')            # gitignored with plots/
    if os.path.exists(cache):
        z = np.load(cache)
        return z['k'], z['h'], z['a'], z['n']
    k, h, a, n = [], [], [], []
    with open(CSV) as fh:
        for r in csv.DictReader(l for l in fh if not l.startswith('#')):
            k.append(int(r['frame'])); h.append(float(r['host_time'])); a.append(float(r['angle_deg']))
            n.append(float(r['ncc']))
    k, h, a, n = np.array(k), np.array(h), np.array(a), np.array(n)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    np.savez(cache, k=k, h=h, a=a, n=n)
    return k, h, a, n


def turns(t, th, d, good):
    """Per-turn (t_mid, rate) from interpolated crossings; drop turns containing bad frames (coast_pairs.py)."""
    x = d * (th - th[0])
    n = np.floor(x / 360.0)
    idx = np.where(np.diff(n) > 0)[0]
    tc = np.array([t[i] + (360.0 * n[i + 1] - x[i]) / (x[i + 1] - x[i]) * (t[i + 1] - t[i]) for i in idx])
    bad_t = t[~good]
    out = []
    for j in range(1, len(tc)):
        if bad_t.size and np.any((bad_t >= tc[j - 1]) & (bad_t <= tc[j])):
            continue
        out.append((0.5 * (tc[j] + tc[j - 1]), 1.0 / (tc[j] - tc[j - 1])))
    return np.array(out).reshape(-1, 2)


def fit_tau(tm, f):
    return -1.0 / np.polyfit(tm, np.log(f), 1)[0] / 60.0


def summarise(rows, key, hours):
    out = {}
    for d in (1, -1):
        v = [(hours[r['name']], r[key]) for r in rows if r['dir'] == d and r.get(key) is not None]
        if len(v) < 3:
            continue
        x, y = np.array(v).T
        p, cov = np.polyfit(x, y, 1, cov=True)
        out[f'dir{d:+d}'] = dict(n=len(y), mean=float(y.mean()), sd=float(y.std(ddof=1)),
                                 sem=float(y.std(ddof=1) / np.sqrt(len(y))), slope_min_per_h=float(p[0]),
                                 slope_err=float(np.sqrt(cov[0, 0])))
    by = {r['name']: r for r in rows}
    diffs = []
    for i in range(1, 200, 2):
        a, b = by.get(f'O{i:02d}'), by.get(f'O{i + 1:02d}')
        if a and b and a.get(key) is not None and b.get(key) is not None:
            diffs.append((f'O{i:02d}', 100 * (b[key] / a[key] - 1)))
    if diffs:
        dv = np.array([x[1] for x in diffs])
        out['pairs'] = dict(n=len(dv), mean_pct=float(dv.mean()), sd_pct=float(dv.std(ddof=1)),
                            sem_pct=float(dv.std(ddof=1) / np.sqrt(len(dv))), n_positive=int((dv > 0).sum()),
                            per_pair={k: round(v, 3) for k, v in diffs})
    return out


def main():
    les = {c['name']: c for c in json.load(open(os.path.join(HERE, 'les_coasts.json')))['coasts']}
    k, h, a, n = load()
    t_all = k / FPS
    off = float(np.median(h - t_all))
    rows = []
    for name in sorted(les):
        L = les[name]
        if not L.get('rotating'):
            print(f'{name} {L["dir"]:+d} swing (LES), skipped'); continue
        meta = {}
        for line in open(os.path.join(D, 'series', f'coast_{name}.txt')):
            p = line.split()
            if len(p) >= 2 and p[0] in ('field_off_host', 'coast_end_host'):
                meta[p[0]] = float(p[1])
        t0, t1 = meta['field_off_host'] + 5 - off, meta['coast_end_host'] - 2 - off
        w = (t_all >= t0) & (t_all <= t1)
        tt = t_all[w] - t0
        th = np.degrees(np.unwrap(np.radians(a[w])))
        good = n[w] >= 0.5
        d = int(L['dir'])
        tr = turns(tt, th, d, good)
        r = dict(name=name, dir=d, n_turns=int(len(tr)), dropped=int((~good).sum()), ncc_min=float(n[w].min()),
                 f_start=float(tr[0, 1]), f_end=float(tr[-1, 1]), tau_whole_min=None, tau_band_min=None,
                 les_band_min=L.get('tau_band_min'), les_whole_min=L.get('tau_whole_min'))
        if r['f_start'] >= 0.48:
            r['tau_whole_min'] = float(fit_tau(tr[:, 0], tr[:, 1]))
        s = (tr[:, 1] >= BAND[0]) & (tr[:, 1] <= BAND[1])
        if r['f_start'] >= BAND[1] and s.sum() >= 10:
            r['tau_band_min'] = float(fit_tau(tr[s, 0], tr[s, 1])); r['n_band'] = int(s.sum())
        if r['tau_band_min'] and r['les_band_min']:
            r['band_trk_minus_les_pct'] = 100 * (r['tau_band_min'] / r['les_band_min'] - 1)
        rows.append(r)
        print(f'{name} {d:+d} turns {r["n_turns"]} drop {r["dropped"]} ncc_min {r["ncc_min"]:.3f} f {r["f_start"]:.3f}->'
              f'{r["f_end"]:.3f} band trk {r["tau_band_min"] or float("nan"):.2f} les {r["les_band_min"] or float("nan"):.2f}'
              f' whole trk {r["tau_whole_min"] or float("nan"):.2f} les {r["les_whole_min"] or float("nan"):.2f}')
    t_first = min(les[x]['host_off'] for x in les)
    hours = {x: (les[x]['host_off'] - t_first) / 3600 for x in les}
    summ = {key: summarise(rows, key, hours) for key in ('tau_band_min', 'tau_whole_min')}
    dv = np.array([r['band_trk_minus_les_pct'] for r in rows if 'band_trk_minus_les_pct' in r])
    summ['band_trk_minus_les_pct'] = dict(n=len(dv), mean=float(dv.mean()), sd=float(dv.std(ddof=1)),
                                          min=float(dv.min()), max=float(dv.max()))
    for kk, v in summ.items():
        print(kk, json.dumps({a_: b_ for a_, b_ in v.items() if a_ != 'pairs'} if isinstance(v, dict) else v))
        if isinstance(v, dict) and 'pairs' in v:
            print('  pairs', json.dumps({a_: b_ for a_, b_ in v['pairs'].items() if a_ != 'per_pair'}))
    json.dump(dict(band=BAND, time_offset_host_minus_frame=off, summary=summ, coasts=rows),
              open(os.path.join(HERE, 'tracker_coasts.json'), 'w'), indent=1)
    keys = list(rows[0].keys()) + ['n_band', 'band_trk_minus_les_pct']
    with open(os.path.join(HERE, 'tracker_coasts.csv'), 'w', newline='') as fh:
        wr = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(keys)), extrasaction='ignore'); wr.writeheader()
        wr.writerows(rows)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
    for d, col in ((1, 'C0'), (-1, 'C3')):
        q = [r for r in rows if r['dir'] == d and r['tau_band_min'] and r['les_band_min']]
        x = [hours[r['name']] for r in q]
        ax[0].plot(x, [r['tau_band_min'] for r in q], 'o', color=col, label=f'tracker {d:+d}')
        ax[0].plot(x, [r['les_band_min'] for r in q], 'x', color=col, label=f'LES {d:+d}')
        ax[1].plot(x, [r['band_trk_minus_les_pct'] for r in q], 'o', color=col, label=f'{d:+d}')
    ax[0].set_xlabel('h after first coast (23:11 EST)'); ax[0].set_ylabel('tau, 0.40-0.47 Hz (min)'); ax[0].legend(fontsize=8)
    ax[1].set_xlabel('h after first coast'); ax[1].set_ylabel('tracker / LES - 1 (%)'); ax[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'tracker_vs_les.png'), dpi=95)


if __name__ == '__main__':
    main()
