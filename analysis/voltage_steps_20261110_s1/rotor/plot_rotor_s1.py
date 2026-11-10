"""Rotor angle vs commanded V2/V4/V3 (writes.csv) on one host-time axis, S1 2026-11-10.

    python3 plot_rotor_s1.py DATA_DIR
Reads rotor_angle_s1.csv (this folder); writes plots/rotor_s1.png and plots/rotor_s1_holds.png.
Angle: blob_track.py, centre (117.5, 165.1), template_gps1477428272.npz (live tracker's zero).
"""
import sys, os, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); D = sys.argv[1]
d = pd.read_csv(os.path.join(HERE, 'rotor_angle_s1.csv')); w = pd.read_csv(os.path.join(D, 'writes.csv'))
bl = pd.read_csv(os.path.join(D, 'blocks.csv'))
T0 = 1794345310.0
INK, MUTED, GRID = '#1f1f1e', '#6b6a63', '#e4e3dd'
COL = {'V2 (A)': '#2a78d6', 'V4 (B)': '#eb6834', 'V3 (C)': '#1baf7a'}
REST = np.median(d.angle_deg[d.host_time < T0])

def fig(xlim, name, title):
    m = (d.host_time - T0 >= xlim[0] - 1) & (d.host_time - T0 <= xlim[1] + 1)
    f, ax = plt.subplots(4, 1, sharex=True, figsize=(12, 8), gridspec_kw=dict(height_ratios=[3, 1, 1, 1], hspace=0.08))
    ax[0].plot(d.host_time[m] - T0, d.angle_deg[m], color=INK, lw=1.2)
    ax[0].axhline(REST, color=MUTED, lw=0.8, ls='--'); ax[0].text(xlim[0], REST, ' rest %.1f°' % REST, color=MUTED, va='bottom', fontsize=9)
    ax[0].set_ylabel('rotor angle (deg)\nimage coords, template zero'); ax[0].set_title(title, loc='left', fontsize=11, color=INK)
    # extend the step trace from before the first write to after the last
    tt = np.r_[xlim[0] - 1, w.host_t0 - T0, xlim[1] + 1]
    for a_, (lab, c) in zip(ax[1:], COL.items()):
        col = lab.split()[0]; v = np.r_[0, w[col], w[col].iloc[-1]]
        a_.step(tt, v, where='post', color=c, lw=1.5); a_.set_ylabel(lab + '\ncounts'); a_.set_ylim(-100, 1350); a_.set_yticks([0, 600, 1200])
    for a_ in ax:
        a_.grid(color=GRID, lw=0.6); a_.set_axisbelow(True)
        for s in ('top', 'right'): a_.spines[s].set_visible(False)
        for _, r in bl[bl.edge == 'start'].iterrows():
            a_.axvline(r.host_a - T0, color=MUTED, lw=0.6, ls=':')
    for k, (_, r) in enumerate(bl[bl.edge == 'start'].iterrows()):
        if xlim[0] <= r.host_a - T0 <= xlim[1]:
            y0, y1 = ax[0].get_ylim()
            ax[0].text(r.host_a - T0, y1 - (k % 2) * 0.06 * (y1 - y0), ' %s %g/s' % (r.pattern, r.rate), va='top', fontsize=9, color=MUTED)
    ax[-1].set_xlim(*xlim); ax[-1].set_xlabel('host time − %.0f s (worker2 clock; camera rows joined by frame order)' % T0)
    f.savefig(os.path.join(HERE, 'plots', name), dpi=130, bbox_inches='tight'); plt.close(f)

fig((d.host_time.iloc[0] - T0, d.host_time.iloc[-1] - T0), 'rotor_s1.png', 'S1 2026-11-10: rotor angle and commanded offsets (1200 counts ≈ 15 V)')
fig((0, 30), 'rotor_s1_holds.png', 'S1 holds block: each electrode 0→1200 counts for 4 s, then 0 for 4 s')
