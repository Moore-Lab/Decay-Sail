#!/usr/bin/env python3
"""One figure for the PI: pair scatter vs rotor speed band, three nights (from band_scatter_<run>.json). M; not approved.
Robust (MAD) sd of pair delta-gamma per 0.04 Hz band, laser-state means removed. The recoil signal grows only as 1/f.
    python3 speed_scatter_figure.py   # -> plots/speed_scatter.png
"""
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = [('night_nd4_il2', 'ND4, 11-16/17', '#2a5caa'), ('nd3_night', 'ND3, 11-17/18', '#d9822b'),
        ('nd2_run', 'ND2, 11-18/19', '#5b8c5a')]
fig, a = plt.subplots(figsize=(7, 4.6))
for run, lab, c in RUNS:
    b = json.load(open(os.path.join(HERE, f'band_scatter_{run}.json')))['bands']
    f = [x['f_mid'] for x in b]; s = [x['mad_sd'] for x in b]
    a.plot(f, s, '-o', color=c, lw=2, ms=7, mec='white', mew=1.5, label=lab)
    a.annotate(lab.split(',')[0], (f[0], s[0]), xytext=(-8, 0), textcoords='offset points', ha='right', va='center',
               fontsize=9, color='#1f2328')
a.set_xlim(0.355, 0.48); a.set_ylim(0, 11)
a.set_xticks([0.39, 0.43, 0.47]); a.set_xticklabels(['0.37–0.41', '0.41–0.45', '0.45–0.49'])
a.set_xlabel('rotor speed band (Hz)', color='#6b7280'); a.set_ylabel('pair-to-pair scatter of Δγ (µHz, robust sd)', color='#6b7280')
a.text(0.47, 10.3, 'recoil signal is only 1.1× larger\nat 0.39 Hz than at 0.43 Hz', ha='right', va='top', fontsize=9, color='#6b7280')
a.legend(frameon=False, fontsize=9, loc='lower left')
a.grid(alpha=0.25); a.spines[['top', 'right']].set_visible(False); a.tick_params(colors='#6b7280')
a.set_title('Noise roughly doubles below 0.41 Hz, on all three nights (measured; not approved)', fontsize=10.5,
            loc='left', color='#1f2328')
fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'speed_scatter.png'), dpi=140)
