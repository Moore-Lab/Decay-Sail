#!/usr/bin/env python3
"""Overnight coast series 2026-11-14/15: per-pair CW/CCW coast plots (style of the Oct spindown slide), per-pair numbers,
and the + / - asymmetry expressed as an equivalent constant torque, for comparison with the 212Pb recoil signal.
Mac only, reads Dropbox (tracker CSV via tracker_coasts.py's cache).

    python3 pair_plots.py      # -> pair_table.csv, pair_summary.json, plots/pair_*.png (gitignored)

Readout: tracker per-turn rates (tracker_coasts.py, coast_pairs.py method), window field off + 5 s to coast end - 2 s,
band 0.40-0.47 Hz (covered by every coast starting >= 0.47 Hz). Time axis: since entering the band.
Per coast: tau from f = f0 exp(-t/tau) (log-linear least squares). 1-sigma: formal, from the per-turn residual scatter
(used in plots; matches the observed coast-to-coast scatter); a delete-one-block jackknife (10 blocks) is also tabulated:
it is ~4x larger because the decay is not exactly exponential (tau depends on speed), the same in every coast.
Per back-to-back pair (+ then -, as run):
  ratio      tau(-)/tau(+) - 1
  joint fit  d|f|/dt = -|f|/tau + s b,  s = +1 for the + coast, -1 for the - coast, common tau and b, separate f0:
             |f|(t) = (f0 - s b tau) exp(-t/tau) + s b tau.  b (Hz/s) = the constant angular acceleration (/2 pi) that
             would produce the pair's asymmetry; f_eq = b tau = the steady frequency shift it corresponds to.
  A constant torque N gives b = N / (2 pi I). Any direction-dependent drag is also absorbed into b here (one pair cannot
  separate them); b is the quantity a source would change.
Signal scale: torque N = 1.1e-18 N m (Molly's slide: 20 kBq, F0 0.81 fN at r 1.38 mm), I = 1.1e-11 kg m^2 (DECISIONS
2026-09-30, +-10 %): b_signal = N / (2 pi I) = 1.6e-8 Hz/s, independent of the damping. The slide's 78 uHz steady shift
is b_signal x tau with tau ~79 min (analysis/noise_budget_20261009.ipynb: gamma = I / tau_mech = 2.32e-15 N m s); at the
current tau (~34 min) the same torque gives ~32 uHz.
"""
import csv
import json
import os

import numpy as np
from scipy.optimize import curve_fit

import tracker_coasts as TC

HERE = os.path.dirname(os.path.abspath(__file__))
BAND = (0.40, 0.47)
N_SIG, I_ROT = 1.1e-18, 1.1e-11
B_SIG = N_SIG / (2 * np.pi * I_ROT)


def coast_turns():
    les = {c['name']: c for c in json.load(open(os.path.join(HERE, 'les_coasts.json')))['coasts']}
    k, h, a, n = TC.load()
    t_all = k / TC.FPS
    off = float(np.median(h - t_all))
    out = {}
    for name in sorted(les):
        L = les[name]
        if not L.get('rotating'):
            continue
        meta = {}
        for line in open(os.path.join(TC.D, 'series', f'coast_{name}.txt')):
            p = line.split()
            if len(p) >= 2 and p[0] in ('field_off_host', 'coast_end_host'):
                meta[p[0]] = float(p[1])
        t0, t1 = meta['field_off_host'] + 5 - off, meta['coast_end_host'] - 2 - off
        w = (t_all >= t0) & (t_all <= t1)
        tr = TC.turns(t_all[w] - t0, np.degrees(np.unwrap(np.radians(a[w]))), int(L['dir']), n[w] >= 0.5)
        out[name] = dict(dir=int(L['dir']), tr=tr, host_off=meta['field_off_host'])
    return out


def fit_tau(t, f):
    p = np.polyfit(t, np.log(f), 1)
    return -1.0 / p[0], np.exp(p[1])


def fit_tau_err(t, f):
    """Formal 1-sigma on tau from the residual scatter of the log-linear fit (per-turn noise)."""
    p, cov = np.polyfit(t, np.log(f), 1, cov=True)
    return float(np.sqrt(cov[0, 0]) / p[0] ** 2)


F_MID = 0.435


def gamma_mid(t, f):
    """gamma = -dlnf/dt (1/s) where f crosses F_MID, from log f = a + b t + c t^2 over the band (the curvature common
    to all coasts is modelled, so the formal error reflects the per-turn noise only)."""
    p, cov = np.polyfit(t, np.log(f), 2, cov=True)
    tm = t[np.argmin(np.abs(f - F_MID))]
    J = np.array([2 * tm, 1.0, 0.0])
    return float(-(J @ p)), float(np.sqrt(J @ cov @ J))


def jk(fn, n, nb=10):
    e = np.linspace(0, n, nb + 1).astype(int)
    v = np.array([fn(np.r_[0:e[j], e[j + 1]:n]) for j in range(nb)])
    return float(np.sqrt((nb - 1) / nb * np.sum((v - v.mean()) ** 2)))


def joint(tp, fp, tm, fm):
    t = np.r_[tp, tm]; s = np.r_[np.ones_like(tp), -np.ones_like(tm)]; f = np.r_[fp, fm]
    def model(X, f0p, f0m, tau, b):
        tt, ss = X
        f0 = np.where(ss > 0, f0p, f0m)
        return (f0 - ss * b * tau) * np.exp(-tt / tau) + ss * b * tau
    p, cov = curve_fit(model, (t, s), f, p0=(fp[0], fm[0], 2040.0, 0.0))
    return p, cov, model


def main():
    C = coast_turns()
    t_first = min(c['host_off'] for c in C.values())
    rows, panels = [], []
    names = sorted(C)
    for i in range(1, 61, 2):
        a, b_ = f'O{i:02d}', f'O{i + 1:02d}'
        if a not in C or b_ not in C:
            continue
        seg = {}
        for nm in (a, b_):
            tr = C[nm]['tr']
            if tr[0, 1] < BAND[1]:
                break
            s = (tr[:, 1] >= BAND[0]) & (tr[:, 1] <= BAND[1])
            t = tr[s, 0] - tr[s, 0][0]; f = tr[s, 1]
            tau, f0 = fit_tau(t, f)
            err_jk = jk(lambda ix: fit_tau(t[ix], f[ix])[0], len(t))
            err = fit_tau_err(t, f)
            g, ge = gamma_mid(t, f)
            seg[nm] = dict(t=t, f=f, tau=tau, f0=f0, err=err, err_jk=err_jk, g=g, ge=ge, n=len(t), dir=C[nm]['dir'],
                           hour=(C[nm]['host_off'] - t_first) / 3600)
        if len(seg) < 2:
            continue
        P, M = seg[a], seg[b_]
        p, cov, model = joint(P['t'], P['f'], M['t'], M['f'])
        e = np.sqrt(np.diag(cov))
        res = np.r_[P['f'] - model((P['t'], np.ones_like(P['t'])), *p), M['f'] - model((M['t'], -np.ones_like(M['t'])), *p)]
        r = dict(pair=f'{a}/{b_}', hour=round(P['hour'], 3),
                 tau_plus_min=P['tau'] / 60, tau_plus_err_min=P['err'] / 60, tau_minus_min=M['tau'] / 60,
                 tau_minus_err_min=M['err'] / 60, tau_plus_err_jk_min=P['err_jk'] / 60,
                 tau_minus_err_jk_min=M['err_jk'] / 60, gamma_plus_e4=1e4 / P['tau'], gamma_minus_e4=1e4 / M['tau'],
                 diff_pct=100 * (M['tau'] / P['tau'] - 1),
                 diff_err_pct=100 * np.hypot(P['err'] / P['tau'], M['err'] / M['tau']),
                 n_turns_plus=P['n'], n_turns_minus=M['n'], band_time_plus_min=P['t'][-1] / 60,
                 band_time_minus_min=M['t'][-1] / 60,
                 joint_tau_min=p[2] / 60, b_Hz_per_s=p[3], b_err_formal=e[3], f_eq_uHz=1e6 * p[3] * p[2],
                 resid_rms_mHz=1e3 * float(np.std(res)),
                 gamma_plus_mHz=1e3 * P['g'], gamma_plus_err_mHz=1e3 * P['ge'], gamma_minus_mHz=1e3 * M['g'],
                 gamma_minus_err_mHz=1e3 * M['ge'], dgamma_uHz=1e6 * (M['g'] - P['g']),
                 dgamma_err_uHz=1e6 * float(np.hypot(P['ge'], M['ge'])))
        rows.append(r); panels.append((r, P, M, p, model))
    # summary
    bv = np.array([r['b_Hz_per_s'] for r in rows]); dv = np.array([r['diff_pct'] for r in rows])
    hv = np.array([r['hour'] for r in rows]); fe = np.array([r['f_eq_uHz'] for r in rows])
    b_sig = B_SIG
    tau_now = np.mean([r['joint_tau_min'] for r in rows]) * 60
    pb = np.polyfit(hv, bv, 1, cov=True)
    summ = dict(n_pairs=len(rows), band=BAND,
                diff_pct_mean=float(dv.mean()), diff_pct_sd=float(dv.std(ddof=1)), diff_pct_sem=float(dv.std(ddof=1) / np.sqrt(len(dv))),
                b_mean=float(bv.mean()), b_sd=float(bv.std(ddof=1)), b_sem=float(bv.std(ddof=1) / np.sqrt(len(bv))),
                b_trend_per_h=float(pb[0][0]), b_trend_err=float(np.sqrt(pb[1][0, 0])),
                f_eq_uHz_mean=float(fe.mean()), f_eq_uHz_sd=float(fe.std(ddof=1)),
                signal_assumed=dict(N=N_SIG, I=I_ROT, b_Hz_per_s=b_sig, f_eq_at_79min_uHz=1e6 * b_sig * 79 * 60,
                                    f_eq_at_current_tau_uHz=1e6 * b_sig * tau_now),
                ratio_b_mean_to_signal=float(bv.mean() / b_sig), ratio_b_sd_to_signal=float(bv.std(ddof=1) / b_sig),
                pairs_for_1sigma_signal=float((bv.std(ddof=1) / b_sig) ** 2),
                b_change_over_night=float(pb[0][0] * (hv.max() - hv.min())),
                b_err_formal_median=float(np.median([r['b_err_formal'] for r in rows])),
                gamma_mid_Hz=F_MID,
                dgamma_uHz_mean=float(np.mean([r['dgamma_uHz'] for r in rows])),
                dgamma_uHz_sd=float(np.std([r['dgamma_uHz'] for r in rows], ddof=1)),
                dgamma_uHz_sem=float(np.std([r['dgamma_uHz'] for r in rows], ddof=1) / np.sqrt(len(rows))),
                dgamma_err_uHz_median=float(np.median([r['dgamma_err_uHz'] for r in rows])),
                gamma_err_mHz_median=float(np.median([r['gamma_plus_err_mHz'] for r in rows] + [r['gamma_minus_err_mHz'] for r in rows])),
                dgamma_signal_uHz=1e6 * 2 * b_sig / F_MID)
    with open(os.path.join(HERE, 'pair_table.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader()
        for r in rows:
            w.writerow({k: (f'{v:.6g}' if isinstance(v, float) else v) for k, v in r.items()})
    json.dump(summ, open(os.path.join(HERE, 'pair_summary.json'), 'w'), indent=1)
    print(json.dumps(summ, indent=1))
    for r in rows:
        print(f"{r['pair']} h{r['hour']:5.2f}  tau+ {r['tau_plus_min']:.2f}±{r['tau_plus_err_min']:.2f}  tau- {r['tau_minus_min']:.2f}"
              f"±{r['tau_minus_err_min']:.2f}  diff {r['diff_pct']:+.2f}±{r['diff_err_pct']:.2f} %  b {r['b_Hz_per_s']:.3e}  "
              f"f_eq {r['f_eq_uHz']:.0f} uHz  resid {r['resid_rms_mHz']:.2f} mHz")
    plots(panels, rows, summ)


def binned(t, f, w=60.0):
    k = (t // w).astype(int)
    return np.array([[t[k == j].mean(), f[k == j].mean()] for j in np.unique(k) if (k == j).sum() >= 5])


def plots(panels, rows, summ):
    """gamma = 1/tau shown in mHz (1 mHz = 1e-3 /s), taken at the band-centre speed F_MID with the curvature modelled;
    +- = formal error from the per-turn noise. The expected recoil changes gamma(-) - gamma(+) by 2 b_signal / F_MID."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    cp, cm = '#1f3b73', '#4a90a4'
    plt.rcParams.update({'font.family': 'sans-serif', 'axes.spines.top': False, 'axes.spines.right': False})
    sig = summ['dgamma_signal_uHz']

    def panel(ax, r, P, M, big=False):
        for S, col, lab, nm in ((P, cp, '+', r['pair'].split('/')[0]), (M, cm, '−', r['pair'].split('/')[1])):
            bb = binned(S['t'], S['f'])
            ax.plot(bb[:, 0] / 60, bb[:, 1], 'o', ms=4 if big else 2.5, color=col)
            tt = np.linspace(0, S['t'][-1], 200)
            ax.plot(tt / 60, S['f0'] * np.exp(-tt / S['tau']), '-', lw=1.6 if big else 1, color=col,
                    label=(f"{lab} ({nm}):  γ = {1e3 * S['g']:.4f} ± {1e3 * S['ge']:.4f} mHz  (1/γ = {1 / S['g'] / 60:.2f} min)"
                           if big else f"{lab} γ {1e3 * S['g']:.4f}±{1e3 * S['ge']:.4f}"))
        ax.grid(alpha=0.3)
        if big:
            ax.legend(frameon=False, fontsize=10, loc='upper right')
            ax.text(0.01, 0.03, f"γ(−) − γ(+) = {r['dgamma_uHz']:+.2f} ± {r['dgamma_err_uHz']:.2f} µHz at {F_MID} Hz "
                    f"({r['hour']:.1f} h into the night).  Expected recoil: {sig:.3f} µHz", transform=ax.transAxes, fontsize=10)
        else:
            ax.set_title(f"{r['pair']}  {r['hour']:.1f} h  Δγ {r['dgamma_uHz']:+.2f}±{r['dgamma_err_uHz']:.2f} µHz", fontsize=8)
            ax.legend(frameon=False, fontsize=6, loc='upper right')
            ax.tick_params(labelsize=6)

    j = int(np.argsort([r['dgamma_uHz'] for r in rows])[len(rows) // 2])
    r, P, M, _, _ = panels[j]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    panel(ax, r, P, M, big=True)
    ax.set_xlabel('time since entering the band (min)'); ax.set_ylabel('rotor frequency (Hz)')
    ax.set_title(f'Free coast-down, + vs −, {BAND[0]:.2f}–{BAND[1]:.2f} Hz band (tracker, per turn; 1-min means shown)', fontsize=12)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'pair_example.png'), dpi=150)

    n = len(panels); nc = 6; nr = int(np.ceil(n / nc))
    fig, axs = plt.subplots(nr, nc, figsize=(18, 3 * nr), sharex=True, sharey=True)
    for ax, (r, P, M, _, _) in zip(axs.flat, panels):
        panel(ax, r, P, M)
    for ax in list(axs.flat)[n:]:
        ax.axis('off')
    fig.supxlabel('time since entering the band (min)'); fig.supylabel('rotor frequency (Hz)')
    fig.suptitle(f'All {n} back-to-back pairs, 2026-11-14/15, {BAND[0]:.2f}–{BAND[1]:.2f} Hz (tracker; dark = +, light = −); '
                 f'γ in mHz at {F_MID} Hz, Δγ = γ(−) − γ(+)')
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'pair_grid.png'), dpi=110)

    hv = np.array([r['hour'] for r in rows])
    dg = np.array([r['dgamma_uHz'] for r in rows]); de = np.array([r['dgamma_err_uHz'] for r in rows])
    fig, ax = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
    ax[0].errorbar(hv, [r['gamma_plus_mHz'] for r in rows], [r['gamma_plus_err_mHz'] for r in rows], fmt='o', color=cp, ms=5, capsize=2, label='+')
    ax[0].errorbar(hv + 0.2, [r['gamma_minus_mHz'] for r in rows], [r['gamma_minus_err_mHz'] for r in rows], fmt='o', color=cm, ms=5, capsize=2, label='−')
    ax[0].set_ylabel('γ = 1/τ at 0.435 Hz (mHz)'); ax[0].legend(frameon=False); ax[0].grid(alpha=0.3)
    ax[0].set_title(f"γ per coast (± formal, median {summ['gamma_err_mHz_median'] * 1e3:.2f} µHz; "
                    f"sd between coasts ~2 µHz)", fontsize=10)
    ax[1].errorbar(hv, dg, de, fmt='o', color='k', ms=5, capsize=2)
    ax[1].axhline(summ['dgamma_uHz_mean'], color='C3', lw=1, ls='--',
                  label=f"mean {summ['dgamma_uHz_mean']:+.2f} µHz (sd {summ['dgamma_uHz_sd']:.2f}, sem {summ['dgamma_uHz_sem']:.2f})")
    ax[1].axhline(0, color='0.5', lw=0.8)
    ax[1].set_ylabel('Δγ = γ(−) − γ(+) (µHz)'); ax[1].legend(frameon=False); ax[1].grid(alpha=0.3)
    ax[1].set_title('Pair difference in γ (± formal per pair)', fontsize=10)
    ax[2].errorbar(hv, dg - dg.mean(), de, fmt='o', color='k', ms=5, capsize=2, label='Δγ minus its mean, per pair')
    ax[2].axhspan(-sig, sig, color='C2', alpha=0.35, label=f'± expected recoil change in Δγ ({sig:.3f} µHz)')
    ax[2].axhline(0, color='0.5', lw=0.8)
    ax[2].set_ylabel('µHz'); ax[2].legend(frameon=False, fontsize=9, loc='lower left'); ax[2].grid(alpha=0.3)
    ax[2].set_title(f"Pair-to-pair variation vs the signal (signal = 2 N/(2πI) / f at {F_MID} Hz; assumed N 1.1e-18 N m, "
                    f"I 1.1e-11 kg m²)", fontsize=10)
    ax[2].set_xlabel('hours after the first coast (23:11 EST, 11-14)')
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'pair_vs_time.png'), dpi=130)


if __name__ == '__main__':
    main()
