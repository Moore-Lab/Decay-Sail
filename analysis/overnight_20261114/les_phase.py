#!/usr/bin/env python3
"""LES phase readout of the overnight coasts: per-turn rates from the phase of the 2 f_rot LES line, compared with the
tracker per turn, and the per-pair asymmetry from each readout and from both combined. Mac only, reads Dropbox.

    python3 les_phase.py     # needs les_coasts.json, pair_table.csv (pair_plots.py) -> les_phase.json, les_phase_pairs.csv,
                             # plots/les_phase_*.png

Method per coast (windows and channel choice from les_coasts.py; rotating coasts that start >= 0.47 Hz):
 1. LES (1024 Hz, front-end clock) over [field off + 5 s, coast end - 2 s]; mean removed; decimated to 32 Hz.
 2. Zero-phase band-pass 0.65-1.05 Hz (Butterworth, order 4: holds the 2 f_rot line for f_rot 0.33-0.52 Hz; the 1 f and
    3 f lines are outside); analytic signal; unwrapped phase phi. Rotor angle = phi / 2 (CLAUDE.md: rotating, the LES line
    is 2 f_rot). One turn = 4 pi of phi; crossing times interpolated -> per-turn rates, as the tracker's.
 3. Front-end clock -> real seconds: t / (1 + R), R = +0.1234 % (README, measured from the overnight GPS reads).
 4. Band 0.40-0.47 Hz, tau by log-linear fit (formal error from the per-turn scatter); pairs as pair_plots.py (ratio and
    the joint fit d|f|/dt = -|f|/tau +- b).
Noise test: per-turn residuals from each coast's exponential fit IN THE BAND, LES and tracker, averaged in 20 s bins; their correlation
(lag scanned +-5 s to absorb the 1 s resolution of the front-end window times). Correlated = real speed jitter (neither
readout can remove it); uncorrelated = readout noise (combining helps).
Combined: per pair, the inverse-variance mean of the LES and tracker b (formal per-pair errors), and the pair-to-pair sd.
"""
import csv
import glob
import json
import os

import numpy as np
from scipy import signal

import pair_plots as PP

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(PP.TC.D, 'les')
R = 0.001234
FS_D = 32.0


class LES:
    def __init__(self):
        self.ch = []
        for f in sorted(glob.glob(os.path.join(D, 'les_*.npz'))):
            z = np.load(f)
            self.ch.append((float(z['gps0']), float(z['gps1']), f))
        self.cache = {}

    def get(self, ch, g0, g1):
        out = []
        for a, b, f in self.ch:
            if b <= g0 or a >= g1:
                continue
            if f not in self.cache:
                z = np.load(f); self.cache = {f: {'pit': z['pit'], 'yaw': z['yaw']}}
            x = self.cache[f][ch]
            i0 = int(round((max(g0, a) - a) * 1024)); i1 = int(round((min(g1, b) - a) * 1024))
            out.append(x[i0:i1])
        return np.concatenate(out)


def les_turns(x):
    x = x - x.mean()
    y = signal.decimate(signal.decimate(x, 8, ftype='fir'), 4, ftype='fir')
    sos = signal.butter(4, [0.65, 1.05], btype='band', fs=FS_D, output='sos')
    z = signal.hilbert(signal.sosfiltfilt(sos, y))
    phi = np.unwrap(np.angle(z))
    t = np.arange(len(phi)) / FS_D
    s = np.sign(phi[-1] - phi[0])
    x = s * (phi - phi[0])
    n = np.floor(x / (4 * np.pi))
    idx = np.where(np.diff(n) > 0)[0]
    tc = np.array([t[i] + (4 * np.pi * n[i + 1] - x[i]) / (x[i + 1] - x[i]) * (t[i + 1] - t[i]) for i in idx])
    tc = tc / (1 + R)
    tc = tc[(tc > 3) & (tc < t[-1] / (1 + R) - 3)]                  # drop filter edges
    return np.c_[0.5 * (tc[1:] + tc[:-1]), 1.0 / np.diff(tc)]


def band(tr):
    s = (tr[:, 1] >= PP.BAND[0]) & (tr[:, 1] <= PP.BAND[1])
    return tr[s, 0], tr[s, 1]


def resid_bins(t, f, t0, w=20.0):
    tau, f0 = PP.fit_tau(t - t0, f)
    r = f - f0 * np.exp(-(t - t0) / tau)
    k = ((t - t0) // w).astype(int)
    return np.array([[t0 + w * (j + 0.5), r[k == j].mean()] for j in np.unique(k) if (k == j).sum() >= 4])


def main():
    les_c = {c['name']: c for c in json.load(open(os.path.join(HERE, 'les_coasts.json')))['coasts']}
    TCo = PP.coast_turns()
    L = LES()
    per = {}
    corr = []
    for name in sorted(TCo):
        c = les_c[name]
        if not c.get('rotating') or TCo[name]['tr'][0, 1] < PP.BAND[1]:
            continue
        g0, g1 = c['fe_off'] + 5, c['fe_end'] - 2
        trL = les_turns(L.get(c['channel'], g0, g1))
        trT = TCo[name]['tr']                         # tracker: t from field off + 5 s (host)
        tL, fL = band(trL); tT, fT = band(trT)
        # per coast tau, each readout
        tauL, _ = PP.fit_tau(tL - tL[0], fL); eL = PP.fit_tau_err(tL - tL[0], fL)
        tauT, _ = PP.fit_tau(tT - tT[0], fT); eT = PP.fit_tau_err(tT - tT[0], fT)
        # residual correlation: align by lag scan (front-end window start known to 1 s)
        rT = resid_bins(tT, fT, 0.0, 20.0)
        best = None
        for lag in np.arange(-5, 5.01, 0.25):
            rL = resid_bins(tL + lag, fL, 0.0, 20.0)
            common = np.intersect1d(np.round(rT[:, 0], 3), np.round(rL[:, 0], 3))
            if len(common) < 10:
                continue
            a = rT[np.isin(np.round(rT[:, 0], 3), common), 1]; b = rL[np.isin(np.round(rL[:, 0], 3), common), 1]
            cc = np.corrcoef(a, b)[0, 1]
            if best is None or cc > best[0]:
                best = (cc, lag, a, b)
        rmsL = float(np.std(fL - np.exp(np.polyval(np.polyfit(tL, np.log(fL), 1), tL))))
        rmsT = float(np.std(fT - np.exp(np.polyval(np.polyfit(tT, np.log(fT), 1), tT))))
        per[name] = dict(dir=TCo[name]['dir'], tauL=tauL, eL=eL, tauT=tauT, eT=eT, nL=len(tL), nT=len(tT),
                         rms_turn_L_mHz=1e3 * rmsL, rms_turn_T_mHz=1e3 * rmsT, corr20=best[0], lag=best[1],
                         rms20_T=1e3 * float(np.std(best[2])), rms20_L=1e3 * float(np.std(best[3])),
                         tL=tL - tL[0], fL=fL, tT=tT - tT[0], fT=fT)
        corr.append((best[2], best[3]))
        print(f"{name} {per[name]['dir']:+d} tau LES {tauL / 60:.3f}±{eL / 60:.3f} trk {tauT / 60:.3f}±{eT / 60:.3f} | per-turn rms "
              f"LES {1e3 * rmsL:.3f} trk {1e3 * rmsT:.3f} mHz | 20 s resid corr {best[0]:+.2f} (lag {best[1]:+.2f} s)")
    A = np.concatenate([a for a, b in corr]); B = np.concatenate([b for a, b in corr])
    # pairs
    rows = []
    for i in range(1, 61, 2):
        a, b = f'O{i:02d}', f'O{i + 1:02d}'
        if a not in per or b not in per:
            continue
        P, M = per[a], per[b]
        r = dict(pair=f'{a}/{b}')
        for k, tk, fk, ek in (('les', 'tL', 'fL', None), ('trk', 'tT', 'fT', None)):
            p, cov, _ = PP.joint(P[tk], P[fk], M[tk], M[fk])
            r[f'b_{k}'] = p[3]; r[f'b_{k}_err'] = float(np.sqrt(cov[3, 3]))
            tp = P['tauL'] if k == 'les' else P['tauT']; tm = M['tauL'] if k == 'les' else M['tauT']
            r[f'diff_{k}_pct'] = 100 * (tm / tp - 1)
        w1, w2 = 1 / r['b_les_err'] ** 2, 1 / r['b_trk_err'] ** 2
        r['b_comb'] = (r['b_les'] * w1 + r['b_trk'] * w2) / (w1 + w2); r['b_comb_err'] = (w1 + w2) ** -0.5
        rows.append(r)
    bs = PP.B_SIG
    summ = dict(n_coasts=len(per), n_pairs=len(rows),
                per_turn_rms_mHz=dict(les=float(np.median([p['rms_turn_L_mHz'] for p in per.values()])),
                                      trk=float(np.median([p['rms_turn_T_mHz'] for p in per.values()]))),
                tau_err_formal_min=dict(les=float(np.median([p['eL'] for p in per.values()]) / 60),
                                        trk=float(np.median([p['eT'] for p in per.values()]) / 60)),
                resid20_corr_all=float(np.corrcoef(A, B)[0, 1]), resid20_rms_mHz=dict(trk=1e3 * 0 + float(np.std(A) * 1e3),
                                                                                     les=float(np.std(B) * 1e3)),
                tau_scatter_min={k: {d: float(np.std([p[t] for p in per.values() if p['dir'] == d], ddof=1) / 60)
                                     for d in (1, -1)} for k, t in (('les', 'tauL'), ('trk', 'tauT'))},
                tau_mean_min={k: {d: float(np.mean([p[t] for p in per.values() if p['dir'] == d]) / 60)
                                  for d in (1, -1)} for k, t in (('les', 'tauL'), ('trk', 'tauT'))})
    for k in ('les', 'trk', 'comb'):
        v = np.array([r[f'b_{k}'] for r in rows]); e = np.median([r[f'b_{k}_err'] for r in rows])
        summ[f'b_{k}'] = dict(mean=float(v.mean()), sd=float(v.std(ddof=1)), sem=float(v.std(ddof=1) / np.sqrt(len(v))),
                              formal_per_pair=float(e), sd_over_signal=float(v.std(ddof=1) / bs),
                              pairs_for_1sigma=float((v.std(ddof=1) / bs) ** 2))
    for k in ('les', 'trk'):
        v = np.array([r[f'diff_{k}_pct'] for r in rows])
        summ[f'diff_{k}_pct'] = dict(mean=float(v.mean()), sd=float(v.std(ddof=1)), n_pos=int((v > 0).sum()))
    summ['b_les_minus_trk_sd'] = float(np.std([r['b_les'] - r['b_trk'] for r in rows], ddof=1))
    summ['b_les_trk_corr'] = float(np.corrcoef([r['b_les'] for r in rows], [r['b_trk'] for r in rows])[0, 1])
    print(json.dumps(summ, indent=1))
    json.dump(dict(summary=summ, coasts={k: {kk: vv for kk, vv in v.items() if kk not in ('tL', 'fL', 'tT', 'fT')}
                                         for k, v in per.items()}, pairs=rows),
              open(os.path.join(HERE, 'les_phase.json'), 'w'), indent=1, default=float)
    with open(os.path.join(HERE, 'les_phase_pairs.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader()
        for r in rows:
            w.writerow({k: (f'{v:.6g}' if isinstance(v, float) else v) for k, v in r.items()})
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))
    nm = 'O29'
    p = per[nm]
    for tk, fk, col, lab in (('tT', 'fT', 'C0', 'tracker'), ('tL', 'fL', 'C3', 'LES phase')):
        t, f = p[tk], p[fk]
        ax[0].plot(t / 60, 1e3 * (f - np.exp(np.polyval(np.polyfit(t, np.log(f), 1), t))), '.', ms=3, color=col, label=lab)
    ax[0].set_xlabel('min in band'); ax[0].set_ylabel('per-turn rate − exponential fit (mHz)'); ax[0].legend(frameon=False)
    ax[0].set_title(f'{nm}: per-turn residuals, both readouts', fontsize=10)
    ax[1].plot(1e3 * A, 1e3 * B, '.', ms=3, color='k')
    ax[1].set_xlabel('tracker residual, 20 s mean (mHz)'); ax[1].set_ylabel('LES residual, 20 s mean (mHz)')
    ax[1].set_title(f'all coasts: correlation {summ["resid20_corr_all"]:+.2f}', fontsize=10)
    for k, col, off in (('trk', 'C0', -0.15), ('les', 'C3', 0.0), ('comb', 'k', 0.15)):
        v = np.array([r[f'b_{k}'] for r in rows]) / bs
        ax[2].plot(np.arange(len(rows)) + off, v, 'o', ms=4, color=col, label=f"{k}: mean {v.mean():.0f}, sd {v.std(ddof=1):.0f}")
    ax[2].axhline(0, color='0.5', lw=0.8); ax[2].set_xlabel('pair'); ax[2].set_ylabel('b / expected signal')
    ax[2].legend(frameon=False, fontsize=8); ax[2].set_title('per-pair asymmetry, by readout', fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'les_phase_compare.png'), dpi=120)


if __name__ == '__main__':
    main()
