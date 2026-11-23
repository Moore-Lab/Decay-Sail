#!/usr/bin/env python3
"""One figure for the PI: pair delta-gamma follows the air-temperature difference of its two coasts, on two runs.
Analysis only, Mac. Observations (M); interpretation not approved.

Top row: pair delta-gamma (mean removed; laser-state means removed on ND2) vs time, with the air-temperature difference
of the same pair scaled by that run's fitted coefficient (so both are in uHz on one axis).
Bottom row: delta-gamma vs delta-T with the fit; scatter before -> after removing the T term; circular-shift null.
ND2 11-18/19: temp_vs_noise.pairs('nd2_run') (O39 and the 17.6 C probe dip excluded, as reviewed).
11-22 5-min run: gamma at 0.465 Hz (band 0.44-0.49) from g3_frozen_test_fast_5min.json; T = mean ext_T0_C from field-off
to coast end (same window as temp_vs_noise). Laser off all night, no exclusions.
    python3 temp_story_figure.py   # -> plots/temp_story.png, temp_story.json
"""
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import pearsonr  # noqa: E402

import temp_vs_noise as V  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup')
INK, MUTED, C_G, C_T = '#1f2328', '#6b7280', '#2a5caa', '#d9822b'


def run_1122():
    T = pd.read_csv(V.TSP, skiprows=1)
    g = json.load(open(os.path.join(HERE, 'g3_frozen_test_fast_5min.json')))['main_fmid_0.465']['gamma_by_coast']
    Tc, h = {}, {}
    for nm in g:
        m = {l.split(' ', 1)[0]: l.split(' ', 1)[1].strip()
             for l in open(f'{SP}/2026-11-22/fast_5min/coast_{nm}.txt') if ' ' in l}
        a, b = float(m['field_off_host']), float(m['coast_end_host'])
        s = (T.unix >= a) & (T.unix <= b)
        Tc[nm] = float(T.ext_T0_C[s].mean()); h[nm] = a
    P = [(f'O{i:02d}', f'O{i + 1:02d}') for i in range(1, 200, 2) if f'O{i + 1:02d}' in g]
    dg = np.array([g[q] - g[p] for p, q in P]); dg -= dg.mean()
    dT = np.array([Tc[q] - Tc[p] for p, q in P])
    hr = np.array([h[p] for p, _ in P]); hr = (hr - hr[0]) / 3600
    return dg, dT, hr


def stats(dg, dT):
    r, p = pearsonr(dT, dg)
    b, cov = np.polyfit(dT, dg, 1, cov=True)
    null = np.array([pearsonr(np.roll(dT, k), dg)[0] for k in range(1, len(dT))])
    return dict(n=len(dg), r=round(float(r), 3), p=float(p), slope_uHz_per_K=round(float(b[0]), 2),
                slope_err=round(float(np.sqrt(cov[0, 0])), 2), sd_before=round(float(dg.std(ddof=1)), 2),
                sd_after=round(float((dg - np.polyval(b, dT)).std(ddof=2)), 2),
                shifts_as_good=f'{int(np.sum(np.abs(null) >= abs(r)))}/{len(null)}'), b


def main():
    runs = [('ND2 laser night, 11-18/19 (24.5 min pairs)', *V.pairs('nd2_run')),
            ('5-min coast run, 11-22 (11.4 min pairs, laser off)', *run_1122())]
    fig, ax = plt.subplots(2, 2, figsize=(12, 7.6), gridspec_kw=dict(height_ratios=[1.15, 1]))
    out = {}
    for j, (title, dg, dT, hr) in enumerate(runs):
        s, b = stats(dg, dT); out[title] = s
        a = ax[0, j]
        a.plot(hr, b[0] * dT, '-', color=C_T, lw=2, label=f'air ΔT × {b[0]:.1f} µHz/K', zorder=2)
        a.plot(hr, dg, 'o', color=C_G, ms=5, mec='white', mew=1, label='pair Δγ (measured)', zorder=3)
        a.axhline(0, color=MUTED, lw=0.6, zorder=1)
        a.set_title(title, fontsize=10.5, color=INK, loc='left')
        a.set_xlabel('hours from start', color=MUTED); a.set_ylabel('µHz', color=MUTED)
        a.legend(fontsize=8.5, frameon=False, loc='upper right')
        a = ax[1, j]
        x = np.linspace(dT.min(), dT.max(), 2)
        a.plot(dT * 1e3, dg, 'o', color=C_G, ms=5, mec='white', mew=1, zorder=3)
        a.plot(x * 1e3, np.polyval(b, x), '-', color=C_T, lw=2, zorder=2)
        a.set_xlabel('air temperature difference of the pair, T(−) − T(+)  (mK)', color=MUTED)
        a.set_ylabel('pair Δγ (µHz)', color=MUTED)
        a.text(0.02, 0.04, f"r = {s['r']:+.2f}  ({s['n']} pairs; {s['shifts_as_good']} time-shifts as good)\n"
               f"scatter {s['sd_before']:.2f} → {s['sd_after']:.2f} µHz with the T term",
               transform=a.transAxes, fontsize=9, color=INK, va='bottom')
    for a in ax.flat:
        a.grid(alpha=0.25); a.spines[['top', 'right']].set_visible(False); a.tick_params(colors=MUTED)
    fig.suptitle('Pair-to-pair noise follows the room-air temperature on two separate runs  (measured; '
                 'probe in air outside the chamber; interpretation not approved)', fontsize=11, x=0.01, ha='left', color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig.savefig(os.path.join(HERE, 'plots', 'temp_story.png'), dpi=140)
    json.dump(out, open(os.path.join(HERE, 'temp_story.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
