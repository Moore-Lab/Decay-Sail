#!/usr/bin/env python3
"""ND4 night 2026-11-16/17: delta gamma per pair against the laser pickoff PD measured during that pair. Mac only.
Needs night_pairs.csv (night_plots.py), coasts_table.csv (coasts.py) and Dropbox pd_trend/pd_trend_1s.csv.

    python3 pd_vs_dgamma.py   # -> plots/pd_vs_dgamma.png (gitignored); prints correlations

PD per pair = mean of the 1-s PD trend over that pair's two coasts (field off to coast end, 600 s each).
Power = counts / 222 counts per mW; includes the PD dark offset. Observations only.
"""
import csv
import os

import numpy as np
from scipy import stats

import coasts as C

HERE = os.path.dirname(os.path.abspath(__file__))
K = 222.0
HOST = 315947891.97


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    z = np.genfromtxt(os.path.join(C.D, 'pd_trend', 'pd_trend_1s.csv'), delimiter=',', names=True)
    th, uw = z['gps'] + HOST, z['pd_mean'] / K * 1e3
    co = {r['name']: float(r['host_off']) for r in csv.DictReader(open(os.path.join(HERE, 'coasts_table.csv')))
          if r['run'] == 'night_nd4_il2'}
    P = list(csv.DictReader(open(os.path.join(HERE, 'night_pairs.csv'))))
    t0 = co['O01']
    rows = []
    for p in P:
        a, b = p['pair'].split('/')
        m = ((th >= co[a]) & (th <= co[a] + 600)) | ((th >= co[b]) & (th <= co[b] + 600))
        rows.append(dict(h=(co[a] - t0) / 3600, on=p['laser'] == 'on', dg=float(p['dg']), dge=float(p['dge']),
                         gmean=(float(p['gp']) + float(p['gm'])) / 2, pd=uw[m].mean(), pde=uw[m].std() / np.sqrt(m.sum() / 60)))
    on = np.array([r['on'] for r in rows]); pd = np.array([r['pd'] for r in rows]); dg = np.array([r['dg'] for r in rows])
    gm = np.array([r['gmean'] for r in rows]); h = np.array([r['h'] for r in rows])
    for lab, s in (('off', ~on), ('on', on)):
        r1, p1 = stats.pearsonr(pd[s], dg[s]); r2, p2 = stats.pearsonr(pd[s], gm[s])
        print(f'laser {lab}: PD {pd[s].mean():.3f} uW (sd {pd[s].std(ddof=1):.3f}); r(PD, dgamma) {r1:+.2f} (p {p1:.2f}); '
              f'r(PD, mean gamma) {r2:+.2f} (p {p2:.2f})')
    # within-state PD residuals pooled
    res_pd = pd - np.where(on, pd[on].mean(), pd[~on].mean()); res_dg = dg - np.where(on, dg[on].mean(), dg[~on].mean())
    r, pv = stats.pearsonr(res_pd, res_dg); print(f'pooled within-state: r(PD, dgamma) {r:+.2f} (p {pv:.2f}), n {len(dg)}')

    fig, ax = plt.subplots(3, 1, figsize=(11, 11), gridspec_kw=dict(height_ratios=[3, 2, 2.4]))
    a = ax[0]
    m = (th >= t0 - 300) & (th <= t0 + 10.2 * 3600)
    k = ((th[m] - t0) // 60).astype(int)
    kk = np.unique(k); pm = np.array([uw[m][k == j].mean() for j in kk])
    a2 = a.twinx()
    a2.plot(kk / 60, pm, '-', lw=0.8, color='#e6a23c', alpha=0.9, label='PD at the pickoff (1-min means)')
    a2.set_ylabel('measured power at the pickoff (µW)\n(includes PD dark offset)', color='#b07a1a'); a2.tick_params(axis='y', colors='#b07a1a')
    for s, col, lab in ((~on, '0.35', 'laser off'), (on, '#c0392b', 'laser on')):
        a.errorbar(h[s] + 0.2, dg[s], [r['dge'] for r, ss in zip(rows, s) if ss], fmt='o', ms=7, color=col, capsize=2,
                   label=f'Δγ per pair, {lab}', zorder=3)
    a.set_ylabel('Δγ = γ(−) − γ(+) (µHz)'); a.grid(alpha=0.3); a.set_zorder(a2.get_zorder() + 1); a.patch.set_visible(False)
    l1, n1 = a.get_legend_handles_labels(); l2, n2 = a2.get_legend_handles_labels()
    a.legend(l1 + l2, n1 + n2, frameon=False, fontsize=9, loc='lower right')
    a.set_xlabel('hours after the first coast (19:52, 16 Nov); each point at the middle of its pair')
    a.set_title('ND4 night: Δγ per pair (points) and the laser pickoff PD (line)', fontsize=11)
    b = ax[1]
    for s, col in ((~on, '0.35'), (on, '#c0392b')):
        b.plot(h[s] + 0.2, gm[s], 'o', color=col, ms=6)
    b.set_ylabel('mean γ of the pair (µHz)'); b.grid(alpha=0.3); b.set_xlabel('hours after the first coast')
    b.set_title('Pair-mean γ (a heating or drag change would show here)', fontsize=10)
    c = ax[2]
    for s, col, lab in ((~on, '0.35', 'off'), (on, '#c0392b', 'on')):
        r1, p1 = stats.pearsonr(pd[s], dg[s])
        c.errorbar(pd[s], dg[s], xerr=pd[s] * 0 + np.array([r['pde'] for r, ss in zip(rows, s) if ss]), fmt='o', color=col,
                   ms=6, capsize=2, label=f'laser {lab}: r = {r1:+.2f} (p {p1:.2f}, 12 pairs)')
    c.set_xlabel('PD averaged over the pair (µW at the pickoff)'); c.set_ylabel('Δγ (µHz)'); c.grid(alpha=0.3)
    c.legend(frameon=False, fontsize=9)
    c.set_title(f'Δγ against the measured power per pair; pooled within-state r = {r:+.2f} (p {pv:.2f})', fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'pd_vs_dgamma.png'), dpi=130)


if __name__ == '__main__':
    main()
