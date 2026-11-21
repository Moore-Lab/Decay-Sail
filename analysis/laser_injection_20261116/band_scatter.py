#!/usr/bin/env python3
"""Pair scatter against speed, within the existing coast-pair nights (analysis only, Mac).

Question: does the pair-to-pair scatter of delta-gamma fall as the rotor speed rises (0.37 -> 0.49 Hz), as it would if
the hill (stronger at low speed) or the low-speed CW/CCW mismatch set it?

Per coast: gamma = 1/tau from a log-linear fit in each of three 0.04 Hz bands (formal error from the fit residuals).
Per pair: delta-gamma_b = gamma(-) - gamma(+). The laser-state mean is subtracted per band (removes the laser push and
the offset), then the sd across pairs is taken. A constant torque gives delta-gamma ~ 1/f, so the column 'sd x f/0.435'
compares torque-equivalent scatter across bands. MAD-based sd shown as well (robust to single pairs such as O39).

    RUN=night_nd4_il2 python3 band_scatter.py
    RUN=nd3_night LASER_DIR=~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-17/laser python3 band_scatter.py
    RUN=nd2_run   LASER_DIR=~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-18/laser python3 band_scatter.py
-> band_scatter_<RUN>.json. Observations only.
"""
import glob
import json
import os

import numpy as np

import coasts as C
import night_plots as NP

HERE = os.path.dirname(os.path.abspath(__file__))
BANDS = [(0.37, 0.41), (0.41, 0.45), (0.45, 0.49)]


def band_gamma(t, f, lo, hi):
    m = (f >= lo) & (f < hi)
    if m.sum() < 15:
        return np.nan, np.nan
    p, cov = np.polyfit(t[m], np.log(f[m]), 1, cov=True)
    return -p[0], np.sqrt(cov[0, 0])


def coast(name, k, h, a, n):
    meta = C.read_meta(os.path.join(C.D, NP.RUN, f'coast_{name}.txt'))
    t_all = k / C.TC.FPS
    off = float(np.median(h - t_all))
    d = 1 if int(name[1:]) % 2 else -1
    t0, t1 = meta['field_off_host'] + 5 - off, meta['coast_end_host'] - 2 - off
    w = (t_all >= t0) & (t_all <= t1)
    tr = C.TC.turns(t_all[w] - t0, np.degrees(np.unwrap(np.radians(a[w]))), d, n[w] >= 0.5)
    started_high = tr[0, 1] >= 0.49   # band 0.45-0.49 needs the coast to start above it
    g = [band_gamma(tr[:, 0], tr[:, 1], lo, hi) if started_high else (np.nan, np.nan) for lo, hi in BANDS]
    return dict(name=name, dir=d, laser=meta.get('laser', ''), g=np.array([x[0] for x in g]), ge=np.array([x[1] for x in g]))


def main():
    k, h, a, n = C.load_tracker(False)
    names = sorted(os.path.basename(p)[6:-4] for p in glob.glob(os.path.join(C.D, NP.RUN, 'coast_O*.txt'))
                   if 'coast_end_host' in C.read_meta(p))
    names = names[:len(names) // 2 * 2]
    cs = [coast(nm, k, h, a, n) for nm in names]
    P, M = cs[0::2], cs[1::2]
    assert all(p['dir'] == 1 and m['dir'] == -1 for p, m in zip(P, M))
    dg = 1e6 * np.array([m['g'] - p['g'] for p, m in zip(P, M)])            # pairs x bands, uHz
    dge = 1e6 * np.array([np.hypot(p['ge'], m['ge']) for p, m in zip(P, M)])
    gp = 1e6 * np.array([p['g'] for p in P]); gm = 1e6 * np.array([m['g'] for m in M])
    on = np.array([p['laser'] == 'on' for p in P])
    res = dict(run=NP.RUN, n_pairs=len(P), bands=[])
    print(f'{NP.RUN}: {len(P)} pairs')
    print(f"{'band':>10} {'f_mid':>6} {'n':>3} {'gamma':>7} {'mean dg off':>11} {'sd dg':>6} {'MADsd':>6} {'sd x f/.435':>11} "
          f"{'fit err':>7} {'sd g+':>6} {'sd g-':>6}")
    resid = np.full_like(dg, np.nan)
    for j, (lo, hi) in enumerate(BANDS):
        x = dg[:, j]; ok = np.isfinite(x)
        r = x.copy()
        for s in (True, False):
            mm = ok & (on == s)
            if mm.any():
                r[mm] = x[mm] - x[mm].mean()
        resid[:, j] = r
        rr = r[ok]
        sd = float(rr.std(ddof=len({bool(v) for v in on[ok]})))
        mad = float(1.4826 * np.median(np.abs(rr - np.median(rr))))
        fm = (lo + hi) / 2
        gpr = gp[ok, j] - np.nanmean(gp[ok, j]); gmr = gm[ok, j] - np.nanmean(gm[ok, j])
        b = dict(band=f'{lo:.2f}-{hi:.2f}', f_mid=fm, n=int(ok.sum()), gamma_mean=float(np.nanmean(np.r_[gp[ok, j], gm[ok, j]])),
                 dg_off_mean=float(np.nanmean(x[ok & ~on])), sd=sd, mad_sd=mad, sd_torque_equiv=sd * fm / 0.435,
                 fit_err_median=float(np.nanmedian(dge[ok, j])), sd_gplus=float(gpr.std(ddof=1)), sd_gminus=float(gmr.std(ddof=1)))
        res['bands'].append(b)
        print(f"{b['band']:>10} {fm:6.2f} {b['n']:3d} {b['gamma_mean']:7.1f} {b['dg_off_mean']:11.2f} {sd:6.2f} {mad:6.2f} "
              f"{b['sd_torque_equiv']:11.2f} {b['fit_err_median']:7.2f} {b['sd_gplus']:6.2f} {b['sd_gminus']:6.2f}")
    ok = np.all(np.isfinite(resid), axis=1)
    cc = np.corrcoef(resid[ok].T)
    res['band_corr'] = cc.round(3).tolist()
    print('correlation of pair residuals between bands (low, mid, high):')
    print(np.array2string(cc, precision=2))
    json.dump(res, open(os.path.join(HERE, f'band_scatter_{NP.RUN}.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
