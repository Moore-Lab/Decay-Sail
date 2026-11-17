#!/usr/bin/env python3
"""ND4 night 2026-11-16/17: is delta gamma per pair correlated with the measured pickoff power after a delay or a
thermal lag? (Molly's question: a heated surface could push through a radiometric effect.) Mac only.
Needs night_pairs.csv, coasts_table.csv and Dropbox pd_trend/pd_trend_1s.csv.

    python3 pd_lag.py    # -> plots/pd_lag.png (gitignored); prints the best lag/tau and a shuffle-based p

Two models of the power each pair "feels" (PD averaged over the pair's two coasts):
  delay:  PD shifted earlier by L (0..4 h)
  thermal: PD through a first-order low-pass with time constant tau (1 min..5 h)
r(model power, delta gamma) for each L / tau. Only PD after ND4 went in (19:31 local, FE GPS 1478928000 + margin) is
used: a delayed window that would reach into the afternoon's mW light drops that pair (>= 12 pairs kept), and the
low-pass starts at the ND4 level. The afternoon light (ND1/no filter, until 19:31) is discussed, not fitted. Significance: the largest |r| over all L and tau,
compared with the same scan on circularly shifted PD series (keeps the autocorrelation of both series).
Observations only; 24 points, neighbouring pairs correlated (lag-1 r 0.36).
"""
import csv
import os

import numpy as np

import coasts as C

HERE = os.path.dirname(os.path.abspath(__file__))
K, HOST = 222.0, 315947891.97
LAGS = np.arange(0, 4.01, 1 / 12) * 3600
TAUS = np.geomspace(60, 5 * 3600, 40)


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    z = np.genfromtxt(os.path.join(C.D, 'pd_trend', 'pd_trend_1s.csv'), delimiter=',', names=True)
    th, uw = z['gps'] + HOST, z['pd_mean'] / K * 1e3
    ok = np.isfinite(uw); th, uw = th[ok], uw[ok]
    co = {r['name']: float(r['host_off']) for r in csv.DictReader(open(os.path.join(HERE, 'coasts_table.csv')))
          if r['run'] == 'night_nd4_il2'}
    P = list(csv.DictReader(open(os.path.join(HERE, 'night_pairs.csv'))))
    win = [(co[p['pair'].split('/')[0]], co[p['pair'].split('/')[1]]) for p in P]
    dg = np.array([float(p['dg']) for p in P]); on = np.array([p['laser'] == 'on' for p in P])
    t0 = win[0][0]
    # PD on a uniform 10-s grid from 5 h before the night (afternoon included) to the end
    ts = 1478928000 + HOST + 900             # ND4 in ~19:31, room lights back on ~19:4x; start after both
    g = np.arange(ts, win[-1][1] + 600, 10.0)
    pg = np.interp(g, th, uw)
    i0 = 0
    night_pd = pg

    def feel(series, shift=0.0):
        return np.array([series[((g >= a - shift) & (g <= a + 600 - shift)) | ((g >= b - shift) & (g <= b + 600 - shift))].mean()
                         if a - shift >= ts else np.nan for a, b in win])

    def rr(x):
        k_ = np.isfinite(x)
        return np.corrcoef(x[k_], dg[k_])[0, 1] if k_.sum() >= 12 else np.nan

    def lowpass(x, tau):
        a = np.exp(-10.0 / tau); y = np.empty_like(x); y[0] = x[:30].mean()
        for i in range(1, len(x)):
            y[i] = a * y[i - 1] + (1 - a) * x[i]
        return y

    def scan(series):
        rd = np.array([rr(feel(series, L)) for L in LAGS])
        rt = np.array([rr(feel(lowpass(series, tau))) for tau in TAUS])
        return rd, rt

    rd, rt = scan(pg)
    best = max(np.nanmax(np.abs(rd)), np.nanmax(np.abs(rt)))
    print(f'delay: best r {rd[np.nanargmax(np.abs(rd))]:+.2f} at {LAGS[np.nanargmax(np.abs(rd))] / 60:.0f} min; '
          f'r at 0 delay {rd[0]:+.2f}')
    print(f'thermal: best r {rt[np.nanargmax(np.abs(rt))]:+.2f} at tau {TAUS[np.nanargmax(np.abs(rt))] / 60:.1f} min')
    # null: circularly shift the night part of the PD series by random amounts (>= 1 h), keep the pre-night part
    rng = np.random.default_rng(1)
    nb = []
    for _ in range(300):
        s = rng.integers(360, len(night_pd) - 360)
        sh = pg.copy(); sh[i0:] = np.roll(night_pd, s)
        a_, b_ = scan(sh)
        nb.append(max(np.nanmax(np.abs(a_)), np.nanmax(np.abs(b_))))
    pval = float(np.mean(np.array(nb) >= best))
    print(f'largest |r| over all delays and taus {best:.2f}; shuffled PD gives >= that in {100 * pval:.0f} % of 300 trials; '
          f'null 50/95 %: {np.percentile(nb, 50):.2f} / {np.percentile(nb, 95):.2f}')

    fig, ax = plt.subplots(3, 1, figsize=(11, 11), gridspec_kw=dict(height_ratios=[3, 2, 2]))
    a = ax[0]
    h = np.array([(w[0] - t0) / 3600 + 0.2 for w in win])
    a2 = a.twinx()
    m = (g >= ts)
    k = ((g[m] - t0) // 60).astype(int); kk = np.unique(k)
    a2.plot(kk / 60, [pg[m][k == j].mean() for j in kk], '-', lw=0.8, color='#e6a23c', label='PD at the pickoff (1-min means)')
    a2.set_ylim(0.2, 1.8); a2.set_ylabel('measured power at the pickoff (µW)\n(includes PD dark offset)', color='#b07a1a'); a2.tick_params(axis='y', colors='#b07a1a')
    a.plot(h, dg, '-', color='k', lw=1.2, label='Δγ per pair (line joins pairs in time order)', zorder=2)
    for s, col, lab in ((~on, '0.35', 'laser off'), (on, '#c0392b', 'laser on')):
        a.errorbar(h[s], dg[s], [float(p['dge']) for p, ss in zip(P, s) if ss], fmt='o', ms=7, color=col, capsize=2, label=lab, zorder=3)
    a.set_zorder(a2.get_zorder() + 1); a.patch.set_visible(False)
    a.set_ylabel('Δγ = γ(−) − γ(+) (µHz)'); a.grid(alpha=0.3)
    l1, n1 = a.get_legend_handles_labels(); l2, n2 = a2.get_legend_handles_labels()
    a.legend(l1 + l2, n1 + n2, frameon=False, fontsize=9, loc='lower right')
    a.set_xlabel('hours after the first coast (19:52, 16 Nov)')
    a.set_title('ND4 night: Δγ per pair and the laser pickoff PD', fontsize=11)
    ax[1].plot(LAGS / 3600, rd, '-o', ms=3, color='k'); ax[1].axhline(0, color='0.5', lw=0.8)
    ax[1].set_xlabel('delay L (h): Δγ compared with the PD measured L earlier (pairs whose window predates ND4 dropped)'); ax[1].set_ylabel('r(PD, Δγ)')
    ax[1].set_ylim(-1, 1); ax[1].grid(alpha=0.3)
    ax[1].set_title(f'Pure delay (12-24 pairs, fewer at long delays). Largest |r| over all delays and τ: {best:.2f}; shuffled PD reaches it in '
                    f'{100 * pval:.0f} % of trials', fontsize=10)
    ax[2].semilogx(TAUS / 60, rt, '-o', ms=3, color='k'); ax[2].axhline(0, color='0.5', lw=0.8)
    ax[2].set_xlabel('thermal time constant τ (min): Δγ compared with the PD low-passed with τ'); ax[2].set_ylabel('r(PD, Δγ)')
    ax[2].set_ylim(-1, 1); ax[2].grid(alpha=0.3)
    ax[2].set_title('First-order thermal lag (PD after ND4 went in only; the afternoon mW light is not included)', fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'pd_lag.png'), dpi=130)


if __name__ == '__main__':
    main()
