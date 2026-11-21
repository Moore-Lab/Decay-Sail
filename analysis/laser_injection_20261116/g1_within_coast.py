#!/usr/bin/env python3
"""Gate G1 (noise plan, 2026-11-21): is the coast-to-coast gamma scatter made WITHIN a coast (torque noise faster than a
coast) or set PER coast (start conditions, charge, hill)? Analysis only, Mac.

Per coast (0.40-0.47 Hz band, per-turn rates from the tracker, as night_plots.py):
  gamma_mid and its formal error (pair_plots.gamma_mid: quadratic in log f, so it assumes white per-turn noise);
  a 10-block jackknife error of the same estimator (sees correlated, i.e. slowly wandering, residuals too);
  the residuals of the fit: lag-1..lag-5 autocorrelation and an averaged periodogram (common over coasts).
Across coasts: sd of gamma per direction after removing each night's laser-state mean and a linear trend in time.
Verdict rule (set in advance): jackknife ~ coast-to-coast sd (ratio > 0.7) -> the scatter is made within the coast;
jackknife << sd (ratio < 0.4) -> set per coast; in between -> mixed.

    RUN=night_nd4_il2 python3 g1_within_coast.py
    RUN=nd3_night LASER_DIR=.../2026-11-17/laser python3 g1_within_coast.py
    RUN=nd2_run   LASER_DIR=.../2026-11-18/laser python3 g1_within_coast.py
-> g1_<RUN>.json, plots/g1_residual_psd_<RUN>.png (gitignored). Observations only.
"""
import glob
import json
import os

import numpy as np

import coasts as C
import night_plots as NP

HERE = os.path.dirname(os.path.abspath(__file__))


def coast(name, k, h, a, n):
    meta = C.read_meta(os.path.join(C.D, NP.RUN, f'coast_{name}.txt'))
    t_all = k / C.TC.FPS
    off = float(np.median(h - t_all))
    d = 1 if int(name[1:]) % 2 else -1
    t0, t1 = meta['field_off_host'] + 5 - off, meta['coast_end_host'] - 2 - off
    w = (t_all >= t0) & (t_all <= t1)
    tr = C.TC.turns(t_all[w] - t0, np.degrees(np.unwrap(np.radians(a[w]))), d, n[w] >= 0.5)
    s = (tr[:, 1] >= C.BAND[0]) & (tr[:, 1] <= C.BAND[1])
    t = tr[s, 0] - tr[s, 0][0]; f = tr[s, 1]
    g, ge = C.PP.gamma_mid(t, f)
    jk = C.PP.jk(lambda idx: C.PP.gamma_mid(t[idx], f[idx])[0], len(t))
    p = np.polyfit(t, np.log(f), 2)
    res = np.log(f) - np.polyval(p, t)
    return dict(name=name, dir=d, laser=meta.get('laser', ''), host=meta['field_off_host'], g=g, ge=ge, jk=jk,
                t=t, res=res)


def acf(x, L=5):
    x = x - x.mean()
    return [float(np.sum(x[:-l] * x[l:]) / np.sum(x * x)) for l in range(1, L + 1)]


def main():
    k, h, a, n = C.load_tracker(False)
    names = sorted(os.path.basename(p)[6:-4] for p in glob.glob(os.path.join(C.D, NP.RUN, 'coast_O*.txt'))
                   if 'coast_end_host' in C.read_meta(p))
    names = names[:len(names) // 2 * 2]
    cs = [coast(nm, k, h, a, n) for nm in names]
    out = dict(run=NP.RUN, n_coasts=len(cs))
    for d in (1, -1):
        c = [x for x in cs if x['dir'] == d]
        g = 1e6 * np.array([x['g'] for x in c]); tt = np.array([x['host'] for x in c]) / 3600
        on = np.array([x['laser'] == 'on' for x in c])
        r = g.copy()
        for s in (True, False):
            if (on == s).any():
                r[on == s] -= r[on == s].mean()
        r -= np.polyval(np.polyfit(tt - tt[0], r, 1), tt - tt[0])
        sd = float(r.std(ddof=3)); mad = float(1.4826 * np.median(np.abs(r - np.median(r))))
        jk = 1e6 * np.array([x['jk'] for x in c]); fe = 1e6 * np.array([x['ge'] for x in c])
        out[f'dir{d:+d}'] = dict(n=len(c), sd_coast_to_coast=sd, mad_sd=mad, jk_median=float(np.median(jk)),
                                 jk_rms=float(np.sqrt(np.mean(jk ** 2))), formal_median=float(np.median(fe)),
                                 ratio_jk_rms_to_sd=float(np.sqrt(np.mean(jk ** 2)) / sd),
                                 ratio_jk_rms_to_mad=float(np.sqrt(np.mean(jk ** 2)) / mad))
    out['res_acf_lag1to5_median'] = np.median(np.array([acf(x['res']) for x in cs]), axis=0).round(3).tolist()
    # averaged residual periodogram on a common grid (residuals are per turn, ~2.2 s apart; interpolate to 2 s)
    P = []
    for x in cs:
        tg = np.arange(x['t'][0], x['t'][-1], 2.0)
        y = np.interp(tg, x['t'], x['res']); y = (y - y.mean()) * np.hanning(len(y))
        F = np.abs(np.fft.rfft(y, 512)) ** 2; P.append(F)
    P = np.mean(P, axis=0); nu = np.fft.rfftfreq(512, 2.0)
    out['res_psd_low_over_high'] = float(P[(nu > 0) & (nu < 1 / 60)].mean() / P[nu > 1 / 20].mean())
    json.dump(out, open(os.path.join(HERE, f'g1_{NP.RUN}.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))
    try:
        import matplotlib
        matplotlib.use('Agg'); import matplotlib.pyplot as plt
        os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.loglog(nu[1:], P[1:]); ax.set_xlabel('frequency (Hz)'); ax.set_ylabel('residual power (arb.)')
        ax.set_title(f'{NP.RUN}: mean periodogram of per-turn fit residuals'); fig.tight_layout()
        fig.savefig(os.path.join(HERE, 'plots', f'g1_residual_psd_{NP.RUN}.png'), dpi=120)
    except Exception as e:  # plot is optional
        print('plot skipped:', e)


if __name__ == '__main__':
    main()
