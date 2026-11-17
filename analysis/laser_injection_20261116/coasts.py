#!/usr/bin/env python3
"""Laser injection 2026-11-16: gamma per coast and Delta gamma per pair, same method as the 11-14/15 overnight series.
Mac only, reads Dropbox spinup/2026-11-16/laser/ (tracker CSV + each run folder's coast_On.txt).

    python3 coasts.py                 # every run folder found (off1, on, night_*, ...)
    python3 coasts.py --no-cache      # re-read the tracker CSV (it grows during the night)

Method (identical to analysis/overnight_20261114/pair_plots.py, whose functions are imported):
 - tracker per-turn rates, window field off + 5 s to coast end - 2 s, frames ncc < 0.5 dropped (tracker_coasts.turns)
 - band 0.40-0.47 Hz; coasts starting below 0.47 Hz skipped
 - gamma = -d ln f/dt at f = 0.435 Hz from a quadratic in log f (pair_plots.gamma_mid), formal 1-sigma
 - Delta gamma = gamma(-) - gamma(+) per back-to-back pair (O01/O02, O03/O04, ... within each run folder)
 - direction: odd step = +1, even = -1 (coast_series convention)
 - interleaved runs (coast_series --laser-pattern): each coast file's 'laser on/off' line labels the pair; per run,
   on minus off = mean Delta gamma(on pairs) - mean Delta gamma(off pairs), error from the scatter of each set
Baseline: the 24 overnight pairs (analysis/overnight_20261114/pair_table.csv).
Writes coasts_table.csv, coasts_summary.json; plots/laser_pairs.png (gitignored).
"""
import argparse
import csv
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ON = os.path.join(HERE, '..', 'overnight_20261114')
sys.path.insert(0, ON)
import tracker_coasts as TC   # noqa: E402
import pair_plots as PP       # noqa: E402

D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-16/laser')
BAND, F_MID = PP.BAND, PP.F_MID


def load_tracker(no_cache):
    csvs = sorted(glob.glob(os.path.join(D, 'tracker', 'blob_live_gps*.csv')))
    if not csvs:
        sys.exit(f'no tracker CSV in {D}/tracker')
    cache = os.path.join(HERE, 'plots', 'tracker_cache.npz')
    if os.path.exists(cache) and not no_cache:
        z = np.load(cache)
        return z['k'], z['h'], z['a'], z['n']
    k, h, a, n = [], [], [], []
    for path in csvs:
        with open(path) as fh:
            for r in csv.DictReader(l for l in fh if not l.startswith('#')):
                try:
                    k.append(int(r['frame'])); h.append(float(r['host_time'])); a.append(float(r['angle_deg']))
                    n.append(float(r['ncc']))
                except (ValueError, TypeError, KeyError):
                    continue   # partial or empty-field rows (lost dot, last line of a growing file)
    k, h, a, n = map(np.array, (k, h, a, n))
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    np.savez(cache, k=k, h=h, a=a, n=n)
    return k, h, a, n


def read_meta(path):
    meta = {}
    for line in open(path):
        p = line.split()
        if len(p) >= 2 and p[0] in ('field_off_host', 'coast_end_host'):
            meta[p[0]] = float(p[1])
        elif len(p) >= 2 and p[0] == 'laser':                     # interleaved runs (--laser-pattern)
            meta['laser'] = p[1]
    return meta


def coast(run, name, k, h, a, n):
    meta = read_meta(os.path.join(D, run, f'coast_{name}.txt'))
    if 'coast_end_host' not in meta:
        return None
    t_all = k / TC.FPS
    off = float(np.median(h - t_all))
    d = 1 if int(name[1:]) % 2 else -1
    t0, t1 = meta['field_off_host'] + 5 - off, meta['coast_end_host'] - 2 - off
    w = (t_all >= t0) & (t_all <= t1)
    if w.sum() < 100:
        return None
    tr = TC.turns(t_all[w] - t0, np.degrees(np.unwrap(np.radians(a[w]))), d, n[w] >= 0.5)
    out = dict(run=run, name=name, dir=d, host_off=meta['field_off_host'], n_turns_all=len(tr), laser=meta.get('laser', ''),
               f_start=float(tr[0, 1]) if len(tr) else None, f_end=float(tr[-1, 1]) if len(tr) else None)
    if len(tr) < 20 or tr[0, 1] < BAND[1]:
        out['note'] = 'did not start above the band'
        return out
    s = (tr[:, 1] >= BAND[0]) & (tr[:, 1] <= BAND[1])
    if s.sum() < 20 or tr[:, 1].min() > BAND[0]:
        out['note'] = 'did not cover the band (0.40-0.47 Hz)'
        return out
    t = tr[s, 0] - tr[s, 0][0]; f = tr[s, 1]
    g, ge = PP.gamma_mid(t, f)
    tau, _ = PP.fit_tau(t, f)
    out.update(gamma_mHz=1e3 * g, gamma_err_mHz=1e3 * ge, tau_min=tau / 60, n_band=int(s.sum()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-cache', action='store_true')
    args = ap.parse_args()
    k, h, a, n = load_tracker(args.no_cache)
    runs = sorted({os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(D, '*', 'coast_O*.txt'))})
    rows = []
    for run in runs:
        for p in sorted(glob.glob(os.path.join(D, run, 'coast_O*.txt'))):
            c = coast(run, os.path.basename(p)[6:-4], k, h, a, n)
            if c:
                rows.append(c)
    by = {(r['run'], r['name']): r for r in rows}
    pairs = []
    for r in rows:
        i = int(r['name'][1:])
        if i % 2 == 0:
            continue
        m = by.get((r['run'], f'O{i + 1:02d}'))
        if m and 'gamma_mHz' in r and 'gamma_mHz' in m:
            pairs.append(dict(run=r['run'], pair=f"{r['name']}/{m['name']}", host=r['host_off'], laser=r['laser'],
                              gamma_plus_mHz=r['gamma_mHz'], gamma_minus_mHz=m['gamma_mHz'],
                              dgamma_uHz=1e3 * (m['gamma_mHz'] - r['gamma_mHz']),
                              dgamma_err_uHz=1e3 * float(np.hypot(r['gamma_err_mHz'], m['gamma_err_mHz'])),
                              tau_plus_min=r['tau_min'], tau_minus_min=m['tau_min']))
    base = [float(x['dgamma_uHz']) for x in csv.DictReader(open(os.path.join(ON, 'pair_table.csv')))]
    bm, bs = float(np.mean(base)), float(np.std(base, ddof=1))
    print(f'baseline 11-14/15: Delta gamma {bm:+.2f} uHz, sd {bs:.2f}, n {len(base)}')
    print('\ncoasts:')
    for r in rows:
        g = f"gamma {r['gamma_mHz']:.4f} +- {r['gamma_err_mHz']:.4f} mHz, tau {r['tau_min']:.2f} min" \
            if 'gamma_mHz' in r else r.get('note', '')
        print(f"  {r['run']:>12} {r['name']} dir {r['dir']:+d}  f {r['f_start']:.4f} -> {r['f_end']:.4f} Hz  {g}")
    print('\npairs (Delta gamma = gamma(-) - gamma(+)):')
    for p in pairs:
        z = (p['dgamma_uHz'] - bm) / bs
        print(f"  {p['run']:>12} {p['pair']}  {p['dgamma_uHz']:+8.2f} +- {p['dgamma_err_uHz']:.2f} uHz   "
              f"vs baseline {p['dgamma_uHz'] - bm:+8.2f} uHz ({z:+.1f} baseline sd)")
    for run in sorted({p['run'] for p in pairs if p['laser']}):              # interleaved: on minus off
        v = {st: np.array([p['dgamma_uHz'] for p in pairs if p['run'] == run and p['laser'] == st]) for st in ('on', 'off')}
        if len(v['on']) >= 2 and len(v['off']) >= 2:
            d = v['on'].mean() - v['off'].mean()
            e = np.sqrt(v['on'].var(ddof=1) / len(v['on']) + v['off'].var(ddof=1) / len(v['off']))
            print(f"\n{run}: on {v['on'].mean():+.2f} (sd {v['on'].std(ddof=1):.2f}, n {len(v['on'])}), "
                  f"off {v['off'].mean():+.2f} (sd {v['off'].std(ddof=1):.2f}, n {len(v['off'])}); "
                  f"on - off = {d:+.2f} +- {e:.2f} uHz (error from the pair scatter)")
    with open(os.path.join(HERE, 'coasts_table.csv'), 'w', newline='') as fh:
        keys = sorted({kk for r in rows for kk in r})
        w = csv.DictWriter(fh, keys); w.writeheader(); w.writerows(rows)
    json.dump(dict(baseline=dict(mean_uHz=bm, sd_uHz=bs, n=len(base)), pairs=pairs),
              open(os.path.join(HERE, 'coasts_summary.json'), 'w'), indent=1)
    plot(rows, pairs, bm, bs)


def plot(rows, pairs, bm, bs):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ok = [r for r in rows if 'gamma_mHz' in r]
    if not ok:
        return
    t0 = min(r['host_off'] for r in ok)
    fig, ax = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    for d, c, lab in ((1, '#26357a', '+'), (-1, '#5f9aa8', '−')):
        s = [r for r in ok if r['dir'] == d]
        ax[0].errorbar([(r['host_off'] - t0) / 3600 for r in s], [r['gamma_mHz'] for r in s],
                       [r['gamma_err_mHz'] for r in s], fmt='o', color=c, label=lab)
    ax[0].set_ylabel('γ at 0.435 Hz (mHz)'); ax[0].legend()
    ax[1].axhspan(bm - bs, bm + bs, color='0.85', label=f'11-14/15 off: {bm:.2f} ± {bs:.2f} (sd) µHz')
    runs = sorted({p['run'] for p in pairs})
    for i, run in enumerate(runs):
        s = [p for p in pairs if p['run'] == run]
        ax[1].errorbar([(p['host'] - t0) / 3600 for p in s], [p['dgamma_uHz'] for p in s],
                       [p['dgamma_err_uHz'] for p in s], fmt='o', color=f'C{i}', label=run)
    ax[1].axhline(0, color='0.5', lw=0.8)
    ax[1].set_ylabel('Δγ = γ(−) − γ(+) (µHz)'); ax[1].set_xlabel('hours since first coast'); ax[1].legend(fontsize=8)
    fig.suptitle('Laser injection 2026-11-16: per coast and per pair (tracker, 0.40-0.47 Hz)')
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'laser_pairs.png'), dpi=130)


if __name__ == '__main__':
    main()
