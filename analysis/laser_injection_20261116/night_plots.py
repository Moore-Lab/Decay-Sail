#!/usr/bin/env python3
"""Laser injection, overnight ND4 interleaved run 2026-11-16/17 (night_nd4_il2): the 14-15 Nov notes' analysis for
this night. Mac only; uses coasts.py's tracker loader (run `python3 coasts.py --no-cache` first) and pair_plots.py.

    python3 night_plots.py    # -> night_summary.json, night_pairs.csv; plots/night_pair_grid.png,
                              #    night_pair_example.png, night_pair_vs_time.png (plots gitignored)

Per coast: per-turn rates (tracker_coasts.turns), gamma at 0.435 Hz (pair_plots.gamma_mid, 0.40-0.47 Hz band),
single-exponential tau in the band (pair_plots.fit_tau), local tau per 0.02 Hz slice 0.37-0.49 Hz (as local_tau.py).
Laser state per pair from the 'laser on/off' line in each coast file. Observations only.
"""
import csv
import glob
import json
import os

import numpy as np

import coasts as C

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.environ.get('RUN', 'night_nd4_il2')   # RUN=nd3_night LASER_DIR=... for later nights
LABEL = os.environ.get('LABEL', 'ND4 interleaved night 2026-11-16/17')
TAG = '' if RUN == 'night_nd4_il2' else f'_{RUN}'   # later nights write their own files
SIG = 0.073          # expected recoil change in delta gamma (uHz), derived (N 1.1e-18 N m, I 1.1e-11 kg m^2)
EDGES = np.arange(0.37, 0.495, 0.02)


def coast_turns(name, k, h, a, n):
    meta = C.read_meta(os.path.join(C.D, RUN, f'coast_{name}.txt'))
    t_all = k / C.TC.FPS
    off = float(np.median(h - t_all))
    d = 1 if int(name[1:]) % 2 else -1
    t0, t1 = meta['field_off_host'] + 5 - off, meta['coast_end_host'] - 2 - off
    w = (t_all >= t0) & (t_all <= t1)
    tr = C.TC.turns(t_all[w] - t0, np.degrees(np.unwrap(np.radians(a[w]))), d, n[w] >= 0.5)
    s = (tr[:, 1] >= C.BAND[0]) & (tr[:, 1] <= C.BAND[1])
    t = tr[s, 0] - tr[s, 0][0]; f = tr[s, 1]
    g, ge = C.PP.gamma_mid(t, f)
    tau, f0 = C.PP.fit_tau(t, f)
    loc = []
    for lo, hi in zip(EDGES[:-1], EDGES[1:]):
        m = (tr[:, 1] >= lo) & (tr[:, 1] < hi)
        loc.append(C.PP.fit_tau(tr[m, 0], tr[m, 1])[0] / 60 if m.sum() >= 15 and tr[0, 1] >= 0.485 else np.nan)
    return dict(name=name, dir=d, laser=meta.get('laser', ''), host=meta['field_off_host'], t=t, f=f, g=g, ge=ge,
                tau=tau, f0=f0, loc=np.array(loc))


def main():
    k, h, a, n = C.load_tracker(False)
    names = sorted(os.path.basename(p)[6:-4] for p in glob.glob(os.path.join(C.D, RUN, 'coast_O*.txt'))
                   if 'coast_end_host' in C.read_meta(p))   # skip a coast still running (mid-night snapshot)
    names = names[:len(names) // 2 * 2]                           # whole pairs only
    cs = [coast_turns(nm, k, h, a, n) for nm in names]
    t_first = cs[0]['host']
    pairs = []
    for P, M in zip(cs[0::2], cs[1::2]):
        assert P['dir'] == 1 and M['dir'] == -1 and P['laser'] == M['laser']
        pairs.append(dict(pair=f"{P['name']}/{M['name']}", laser=P['laser'], hour=(P['host'] - t_first) / 3600,
                          gp=1e6 * P['g'], gpe=1e6 * P['ge'], gm=1e6 * M['g'], gme=1e6 * M['ge'],
                          dg=1e6 * (M['g'] - P['g']), dge=1e6 * float(np.hypot(P['ge'], M['ge'])),
                          taup=P['tau'] / 60, taum=M['tau'] / 60, P=P, M=M))
    with open(os.path.join(HERE, f'night_pairs{TAG}.csv'), 'w', newline='') as fh:
        cols = ['pair', 'laser', 'hour', 'gp', 'gpe', 'gm', 'gme', 'dg', 'dge', 'taup', 'taum']
        w = csv.writer(fh); w.writerow(cols)
        for p in pairs:
            w.writerow([p['pair'], p['laser']] + [f'{p[c]:.4f}' for c in cols[2:]])
    S = {}
    on = np.array([p['laser'] == 'on' for p in pairs])
    dg = np.array([p['dg'] for p in pairs])
    for lab, m in (('off', ~on), ('on', on), ('all', np.ones_like(on))):
        x = dg[m]
        S[lab] = dict(n=int(m.sum()), dg_mean=float(x.mean()), dg_sd=float(x.std(ddof=1)),
                      dg_sem=float(x.std(ddof=1) / np.sqrt(m.sum())),
                      gp=float(np.mean([p['gp'] for p, mm in zip(pairs, m) if mm])),
                      gm=float(np.mean([p['gm'] for p, mm in zip(pairs, m) if mm])),
                      taup=float(np.mean([p['taup'] for p, mm in zip(pairs, m) if mm])),
                      taum=float(np.mean([p['taum'] for p, mm in zip(pairs, m) if mm])),
                      taup_sd=float(np.std([p['taup'] for p, mm in zip(pairs, m) if mm], ddof=1)),
                      taum_sd=float(np.std([p['taum'] for p, mm in zip(pairs, m) if mm], ddof=1)))
    S['on_minus_off'] = S['on']['dg_mean'] - S['off']['dg_mean']
    S['on_minus_off_err'] = float(np.hypot(S['on']['dg_sem'], S['off']['dg_sem']))
    rat = np.array([p['taum'] / p['taup'] - 1 for p in pairs]) * 100
    S['tau_ratio_pct'] = dict(mean=float(rat.mean()), sd=float(rat.std(ddof=1)), sem=float(rat.std(ddof=1) / np.sqrt(len(rat))),
                              n_pos=int((rat > 0).sum()), n=len(rat))
    S['gamma_sd_plus'] = float(np.std([p['gp'] for p in pairs], ddof=1))
    S['gamma_sd_minus'] = float(np.std([p['gm'] for p in pairs], ddof=1))
    S['dge_median'] = float(np.median([p['dge'] for p in pairs]))
    S['lag1'] = float(np.corrcoef(dg[:-1], dg[1:])[0, 1])
    hv = np.array([p['hour'] for p in pairs])
    c, cov = np.polyfit(hv, dg, 1, cov=True)
    S['dg_trend_uHz_per_h'] = [float(c[0]), float(np.sqrt(cov[0, 0]))]
    loc = []
    for j, (lo, hi) in enumerate(zip(EDGES[:-1], EDGES[1:])):
        r = dict(band=f'{lo:.2f}-{hi:.2f}')
        for d in (1, -1):
            v = np.array([c_['loc'][j] for c_ in cs if c_['dir'] == d]); v = v[np.isfinite(v)]
            r[f'tau{d:+d}'] = float(v.mean()); r[f'sd{d:+d}'] = float(v.std(ddof=1)); r[f'n{d:+d}'] = int(v.size)
        r['pct'] = 100 * (r['tau-1'] / r['tau+1'] - 1)
        r['pct_err'] = 100 * np.hypot(r['sd+1'] / np.sqrt(r['n+1']), r['sd-1'] / np.sqrt(r['n-1'])) / r['tau+1']
        loc.append(r)
    S['local_tau'] = loc
    json.dump(S, open(os.path.join(HERE, f'night_summary{TAG}.json'), 'w'), indent=1)
    print(json.dumps({k_: v for k_, v in S.items() if k_ != 'local_tau'}, indent=1))
    for r in loc:
        print(f"{r['band']}  +{r['tau+1']:.2f} (sd {r['sd+1']:.2f}, n {r['n+1']})  -{r['tau-1']:.2f} (sd {r['sd-1']:.2f}, "
              f"n {r['n-1']})  {r['pct']:+.2f} +- {r['pct_err']:.2f} %")
    plots(pairs, S)


def plots(pairs, S):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    cp, cm, con = '#1f3b73', '#4a90a4', '#c0392b'
    plt.rcParams.update({'font.family': 'sans-serif', 'axes.spines.top': False, 'axes.spines.right': False})

    def panel(ax, p, big=False):
        for S_, col, lab in ((p['P'], cp, '+'), (p['M'], cm, '−')):
            bb = C.PP.binned(S_['t'], S_['f'])
            ax.plot(bb[:, 0] / 60, bb[:, 1], 'o', ms=4 if big else 2.5, color=col)
            tt = np.linspace(0, S_['t'][-1], 200)
            ax.plot(tt / 60, S_['f0'] * np.exp(-tt / S_['tau']), '-', lw=1.6 if big else 1, color=col,
                    label=(f"{lab} ({S_['name']}):  γ = {1e3 * S_['g']:.4f} ± {1e3 * S_['ge']:.4f} mHz" if big
                           else f"{lab} γ {1e3 * S_['g']:.4f}±{1e3 * S_['ge']:.4f}"))
        ax.grid(alpha=0.3)
        tag = 'laser ON' if p['laser'] == 'on' else 'laser off'
        if big:
            ax.legend(frameon=False, fontsize=10, loc='upper right')
            ax.text(0.01, 0.03, f"{tag}.  γ(−) − γ(+) = {p['dg']:+.2f} ± {p['dge']:.2f} µHz at {C.PP.F_MID} Hz "
                    f"({p['hour']:.1f} h into the night).  Expected recoil: {SIG} µHz", transform=ax.transAxes, fontsize=10)
        else:
            ax.set_title(f"{p['pair']}  {p['hour']:.1f} h  {tag}  Δγ {p['dg']:+.2f}±{p['dge']:.2f} µHz", fontsize=8,
                         color=con if p['laser'] == 'on' else 'k')
            ax.legend(frameon=False, fontsize=6, loc='upper right')
            ax.tick_params(labelsize=6)
            if p['laser'] == 'on':
                ax.set_facecolor('#fbeeee')

    j = int(np.argsort([p['dg'] for p in pairs])[len(pairs) // 2])
    fig, ax = plt.subplots(figsize=(10, 5.6))
    panel(ax, pairs[j], big=True)
    ax.set_xlabel('time since entering the band (min)'); ax.set_ylabel('rotor frequency (Hz)')
    ax.set_title(f'Free coast-down, + vs −, {C.BAND[0]:.2f}–{C.BAND[1]:.2f} Hz band (tracker, per turn; 1-min means shown)',
                 fontsize=12)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', f'night_pair_example{TAG}.png'), dpi=150)

    nc = 6; nr = int(np.ceil(len(pairs) / nc))
    fig, axs = plt.subplots(nr, nc, figsize=(18, 3 * nr), sharex=True, sharey=True)
    for ax, p in zip(axs.flat, pairs):
        panel(ax, p)
    fig.supxlabel('time since entering the band (min)'); fig.supylabel('rotor frequency (Hz)')
    fig.suptitle(f'All {len(pairs)} pairs, {LABEL}, {C.BAND[0]:.2f}–{C.BAND[1]:.2f} Hz '
                 f'(tracker; dark = +, light = −; red title and shading = 660 nm laser on); γ in mHz at {C.PP.F_MID} Hz, '
                 f'Δγ = γ(−) − γ(+)')
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', f'night_pair_grid{TAG}.png'), dpi=110)

    hv = np.array([p['hour'] for p in pairs]); on = np.array([p['laser'] == 'on' for p in pairs])
    dg = np.array([p['dg'] for p in pairs]); de = np.array([p['dge'] for p in pairs])
    fig, ax = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
    for m, mfc, lab in ((~on, 'white', 'laser off'), (on, None, 'laser on')):
        ax[0].errorbar(hv[m], [p['gp'] for p, mm in zip(pairs, m) if mm], [p['gpe'] for p, mm in zip(pairs, m) if mm],
                       fmt='o', color=cp, mfc=mfc, ms=5, capsize=2, label=f'+, {lab}')
        ax[0].errorbar(hv[m] + 0.08, [p['gm'] for p, mm in zip(pairs, m) if mm], [p['gme'] for p, mm in zip(pairs, m) if mm],
                       fmt='s', color=cm, mfc=mfc, ms=5, capsize=2, label=f'−, {lab}')
    ax[0].set_ylabel('γ at 0.435 Hz (µHz)'); ax[0].legend(frameon=False, ncol=2, fontsize=9); ax[0].grid(alpha=0.3)
    ax[0].set_title(f"γ per coast (± formal, median per pair {S['dge_median']:.2f} µHz; sd between coasts "
                    f"{S['gamma_sd_plus']:.1f} (+) and {S['gamma_sd_minus']:.1f} (−) µHz); filled = laser on", fontsize=10)
    for m, col, lab in ((~on, '0.45', 'off'), (on, con, 'on')):
        ax[1].errorbar(hv[m], dg[m], de[m], fmt='o', color=col, ms=6, capsize=2, label=f"laser {lab}: mean "
                       f"{S[lab]['dg_mean']:+.2f} ± {S[lab]['dg_sem']:.2f} µHz (sd {S[lab]['dg_sd']:.2f}, {S[lab]['n']} pairs)")
        ax[1].axhline(S[lab]['dg_mean'], color=col, lw=1, ls='--')
    ax[1].axhline(0, color='0.5', lw=0.8)
    ax[1].set_ylabel('Δγ = γ(−) − γ(+) (µHz)'); ax[1].legend(frameon=False, fontsize=9, loc='lower right'); ax[1].grid(alpha=0.3)
    ax[1].set_title(f"Pair difference (± formal per pair); on − off = {S['on_minus_off']:+.2f} ± {S['on_minus_off_err']:.2f} µHz "
                    f"(expected at ND4 ≈ +0.05)", fontsize=10)
    ax[2].errorbar(hv, dg - S['all']['dg_mean'], de, fmt='o', color='k', ms=5, capsize=2, label='Δγ minus the night mean, per pair')
    ax[2].axhspan(-SIG, SIG, color='C2', alpha=0.35, label=f'± expected recoil change in Δγ ({SIG} µHz)')
    ax[2].axhline(0, color='0.5', lw=0.8)
    ax[2].set_ylabel('µHz'); ax[2].legend(frameon=False, fontsize=9, loc='upper left'); ax[2].grid(alpha=0.3)
    ax[2].set_title('Pair-to-pair variation vs the signal (assumed N 1.1e-18 N m, I 1.1e-11 kg m²)', fontsize=10)
    ax[2].set_xlabel('hours after the first coast (19:52 EST, 11-16)')
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', f'night_pair_vs_time{TAG}.png'), dpi=130)


if __name__ == '__main__':
    main()
