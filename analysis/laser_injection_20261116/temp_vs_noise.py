#!/usr/bin/env python3
"""Does the coast noise follow the air temperature? ND3 night (11-17/18) and ND2 run (11-18/19). Analysis only, Mac.

Air: TSP01B ext_T0_C, one probe hanging in air near the table (outside the chamber); host clock, same as the coast
metadata. Per coast (0.40-0.47 Hz band, estimators of g1_within_coast.py): gamma, its 10-block jackknife (the
within-coast slow-torque noise, "wobble"), and over the coast window: mean T, dT/dt (linear fit, mK/min) and the rms of
T about that line (mK). gamma residual = gamma minus the mean of its direction x laser state (removes the +/- offset and
the laser push) minus a linear trend in time per direction.
Tests (decided in advance, 6 per night): Spearman of gamma residual vs T, vs dT/dt; jackknife vs T, vs |dT/dt|, vs
T rms; pair delta-gamma residual vs (T- - T+). Report rho and p; with 12 tests, p < 0.004 (Bonferroni 0.05) to count.
    RUN=nd3_night LASER_DIR=.../2026-11-17/laser python3 temp_vs_noise.py    # -> temp_noise_nd3_night.json
    RUN=nd2_run   LASER_DIR=.../2026-11-18/laser python3 temp_vs_noise.py    # -> temp_noise_nd2_run.json
    python3 temp_vs_noise.py --plot   # -> plots/temp_vs_noise.png, plots/temp_pair_dgamma.png, temp_pairs_summary.json
"""
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TSP = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-17/env/tsp01b_host1794956558.csv')
RUNS = [('nd3_night', 'ND3 night, 11-17/18'), ('nd2_run', 'ND2 run, 11-18/19')]


def load_T():
    T = np.genfromtxt((l for l in open(TSP) if not l.startswith('#')), delimiter=',', names=True)
    return T['unix'], T['ext_T0_C']


def compute():
    from scipy.stats import spearmanr
    import coasts as C
    import night_plots as NP
    import g1_within_coast as G
    tu, tc = load_T()
    k, h, a, n = C.load_tracker(False)
    names = sorted(os.path.basename(p)[6:-4] for p in glob.glob(os.path.join(C.D, NP.RUN, 'coast_O*.txt'))
                   if 'coast_end_host' in C.read_meta(p))
    names = names[:len(names) // 2 * 2]
    rows = []
    for nm in names:
        x = G.coast(nm, k, h, a, n)
        m = C.read_meta(os.path.join(C.D, NP.RUN, f'coast_{nm}.txt'))
        s = (tu >= m['field_off_host']) & (tu <= m['coast_end_host'])
        if s.sum() < 5:
            continue
        tt = (tu[s] - tu[s][0]) / 60; p = np.polyfit(tt, tc[s], 1)
        rows.append(dict(name=nm, dir=x['dir'], laser=x['laser'], host=x['host'], gamma=1e6 * x['g'], jk=1e6 * x['jk'],
                         T=float(tc[s].mean()), dTdt=1e3 * p[0], Trms=1e3 * float(np.std(tc[s] - np.polyval(p, tt)))))
    g = np.array([r['gamma'] for r in rows]); hh = np.array([r['host'] for r in rows]) / 3600
    res = g.copy()
    for d in (1, -1):
        for L in ('on', 'off'):
            s = np.array([r['dir'] == d and r['laser'] == L for r in rows])
            if s.any():
                res[s] -= res[s].mean()
        s = np.array([r['dir'] == d for r in rows])
        res[s] -= np.polyval(np.polyfit(hh[s] - hh[0], res[s], 1), hh[s] - hh[0])
    for r, v in zip(rows, res):
        r['gamma_res'] = float(v)
    A = lambda key: np.array([r[key] for r in rows])
    tests = {'gamma_res vs T': (A('gamma_res'), A('T')), 'gamma_res vs dT/dt': (A('gamma_res'), A('dTdt')),
             'jk vs T': (A('jk'), A('T')), 'jk vs |dT/dt|': (A('jk'), np.abs(A('dTdt'))), 'jk vs T rms': (A('jk'), A('Trms'))}
    by = {r['name']: r for r in rows}
    pairs = [(by[f'O{i:02d}'], by[f'O{i + 1:02d}']) for i in range(1, 200, 2) if f'O{i:02d}' in by and f'O{i + 1:02d}' in by]
    dg = np.array([q['gamma'] - p['gamma'] for p, q in pairs]); on = np.array([p['laser'] == 'on' for p, _ in pairs])
    for L in (True, False):
        if (on == L).any():
            dg[on == L] -= dg[on == L].mean()
    tests['pair dg_res vs (T- - T+)'] = (dg, np.array([q['T'] - p['T'] for p, q in pairs]))
    out = dict(run=NP.RUN, n_coasts=len(rows), n_pairs=len(pairs),
               T_range=[float(A('T').min()), float(A('T').max())], dTdt_abs_median_mK_per_min=float(np.median(np.abs(A('dTdt')))),
               tests={}, coasts=rows)
    for kk, (y, xx) in tests.items():
        rho, pv = spearmanr(y, xx)
        out['tests'][kk] = dict(rho=round(float(rho), 3), p=float(pv), n=len(y))
        print(f'{NP.RUN:10s} {kk:28s} rho {rho:+.2f}  p {pv:.3f}  n {len(y)}')
    json.dump(out, open(os.path.join(HERE, f'temp_noise_{NP.RUN}.json'), 'w'), indent=1)


EXCL = {'nd2_run': ('O39', 'O59', 'O60', 'O61', 'O62'), 'nd3_night': ()}   # O39 outlier pair; 17.6 C dip (O59-O62)


def pairs(run):
    """Pair delta-gamma (laser-state mean removed) vs the air-temperature difference of its two coasts (T- - T+)."""
    c = json.load(open(os.path.join(HERE, f'temp_noise_{run}.json')))['coasts']; by = {r['name']: r for r in c}
    P = [(by[f'O{i:02d}'], by[f'O{i + 1:02d}']) for i in range(1, 200, 2) if f'O{i + 1:02d}' in by]
    P = [(p, q) for p, q in P if p['name'] not in EXCL[run] and q['name'] not in EXCL[run]]
    on = np.array([p['laser'] == 'on' for p, _ in P])
    dg = np.array([q['gamma'] - p['gamma'] for p, q in P]); dT = np.array([q['T'] - p['T'] for p, q in P])
    for L in (True, False):
        dg[on == L] -= dg[on == L].mean()
    h = np.array([p['host'] for p, _ in P]); h = (h - h[0]) / 3600
    return dg, dT, h


def pair_fit(dg, dT):
    from scipy.stats import pearsonr
    b, cov = np.polyfit(dT, dg, 1, cov=True); r, p = pearsonr(dT, dg)
    return dict(n=len(dg), r=round(float(r), 3), p=float(p), slope_uHz_per_K=round(float(b[0]), 2),
                slope_err=round(float(np.sqrt(cov[0, 0])), 2), sd_dT_mK=round(1e3 * float(dT.std()), 0),
                sd_dg=round(float(dg.std(ddof=2)), 2), sd_dg_after_T=round(float((dg - np.polyval(b, dT)).std(ddof=3)), 2))


def plot():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    tu, tc = load_T()
    CP, CM, INK, MUTED, GRID = '#2a78d6', '#eb6834', '#1f1f1e', '#6b6a63', '#e4e3dd'
    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED,
                         'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, ax = plt.subplots(3, 2, figsize=(10, 7), sharex='col', gridspec_kw=dict(height_ratios=[1.1, 1, 1]))
    for j, (run, title) in enumerate(RUNS):
        d = json.load(open(os.path.join(HERE, f'temp_noise_{run}.json')))
        run = run; c = d['coasts']; t0 = min(r['host'] for r in c) - 1800
        t1 = max(r['host'] for r in c) + 3600
        s = (tu >= t0) & (tu <= t1)
        ax[0, j].plot((tu[s] - t0) / 3600, tc[s], color=INK, lw=1.2)
        ax[0, j].set_title(title, color=INK, loc='left', fontsize=10)
        for row, key, lab in [(1, 'gamma_res', 'γ residual per coast (µHz)'), (2, 'jk', 'within-coast noise (µHz)')]:
            for dd, col, nm in [(1, CP, '+ direction'), (-1, CM, '− direction')]:
                x = [(r['host'] - t0) / 3600 for r in c if r['dir'] == dd]; y = [r[key] for r in c if r['dir'] == dd]
                ax[row, j].plot(x, y, 'o', ms=4.5, color=col, mec='white', mew=0.8, label=nm)
            ax[row, j].set_ylabel(lab if j == 0 else '')
        ax[1, j].axhline(0, color=MUTED, lw=0.8)
        tx = d['tests']
        ax[2, j].set_title('within-coast noise vs |dT/dt|: Spearman ρ = {:+.2f} (p {:.2f})'.format(
            tx['jk vs |dT/dt|']['rho'], tx['jk vs |dT/dt|']['p']), fontsize=8, color=MUTED, loc='left')
        if run == 'nd2_run':
            ax[1, j].set_ylim(-12, 12)
            ax[1, j].annotate('O39: +43 µHz (off scale)', xy=(0.45, 0.97), xycoords='axes fraction', fontsize=8,
                              color=MUTED, va='top')
        ax[2, j].set_xlabel('hours from run start')
        for a in ax[:, j]:
            a.grid(True, color=GRID, lw=0.6); a.set_axisbelow(True)
    ax[0, 0].set_ylabel('air temperature near table (°C)')
    ax[1, 0].legend(frameon=False, fontsize=8, loc='lower left')
    fig.suptitle('Coast noise vs air temperature (TSP01B probe outside the chamber; 0.40–0.47 Hz band)', x=0.01, ha='left',
                 color=INK, fontsize=11)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    p = os.path.join(HERE, 'plots', 'temp_vs_noise.png'); fig.savefig(p, dpi=150); print(p)

    # figure 2: pair delta-gamma vs the temperature difference between its two coasts
    fig, ax = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    summ = {}
    for j, (run, title) in enumerate(RUNS):
        dg, dT, h = pairs(run)
        groups = [('hours 0-7: air cycling ~1 K', h < 7, CP), ('hours 7+: air steady', h >= 7, CM)] if run == 'nd2_run' \
            else [('all pairs', np.ones(len(dg), bool), CP)]
        summ[run] = dict(all=pair_fit(dg, dT))
        for lab, s_, col in groups:
            f = pair_fit(dg[s_], dT[s_]); summ[run][lab] = f
            ax[j].plot(1e3 * dT[s_], dg[s_], 'o', ms=6, color=col, mec='white', mew=0.8,
                       label=f"{lab}: r = {f['r']:+.2f}, n = {f['n']}")
        f = summ[run]['all']; xx = np.linspace(dT.min(), dT.max(), 2)
        ax[j].plot(1e3 * xx, f['slope_uHz_per_K'] * xx, color=INK, lw=1)
        ax[j].set_title(f"{title}: slope {f['slope_uHz_per_K']:+.1f} ± {f['slope_err']:.1f} µHz/K; "
                        f"scatter {f['sd_dg']:.1f} → {f['sd_dg_after_T']:.1f} µHz", fontsize=9, color=INK, loc='left')
        ax[j].axhline(0, color=MUTED, lw=0.8); ax[j].axvline(0, color=MUTED, lw=0.8)
        ax[j].grid(True, color=GRID, lw=0.6); ax[j].set_axisbelow(True)
        ax[j].set_xlabel('air temperature, − coast minus + coast (mK)')
        ax[j].legend(frameon=False, fontsize=8, loc='upper right')
    ax[0].set_ylabel('pair Δγ, laser-state mean removed (µHz)')
    fig.suptitle('Pair Δγ vs air-temperature difference between its two coasts (ND2: O39 and the 17.6 °C dip excluded)',
                 x=0.01, ha='left', color=INK, fontsize=10)
    fig.tight_layout()
    p = os.path.join(HERE, 'plots', 'temp_pair_dgamma.png'); fig.savefig(p, dpi=150); print(p)
    json.dump(summ, open(os.path.join(HERE, 'temp_pairs_summary.json'), 'w'), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == '__main__':
    plot() if '--plot' in sys.argv else compute()
