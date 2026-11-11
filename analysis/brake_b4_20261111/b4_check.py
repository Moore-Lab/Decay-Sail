#!/usr/bin/env python3
"""Gate B4 check (2026-11-11): swing vs time in the stage-2b kick-and-brake run, from the brake log and the tracker CSV."""
import os, numpy as np
D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/brake/2026-11-11/b4')
rows = [l.rstrip('\n').split(',') for l in open(os.path.join(D, 'brake_1794398171.csv')) if not l.startswith('#')]
hdr, rows = rows[0], rows[1:]
c = {k: i for i, k in enumerate(hdr)}
t = np.array([float(r[c['frame_t']]) for r in rows]); th = np.array([float(r[c['angle']]) for r in rows])
ph = np.array([r[c['phase']] for r in rows]); ch = np.array([r[c['choice']] for r in rows])
tb = t[ph == 'brake'][0]
print(f'phases: ' + ', '.join(f'{p} {np.sum(ph == p)} frames' for p in ('kick', 'settle', 'observe', 'brake')))
print(f'observe swing (half p-p): {np.ptp(th[ph == "observe"]) / 2:.2f} deg; kick/settle range {th[(ph == "kick") | (ph == "settle")].min():.1f}-{th[(ph == "kick") | (ph == "settle")].max():.1f}')
for a, b in ((0, 4), (4, 8), (8, 12), (12, 16), (16, 30), (30, 60), (60, 120)):
    m = (t >= tb + a) & (t < tb + b)
    print(f'  brake +{a:>3}..{b:<3} s: half p-p {np.ptp(th[m]) / 2:6.2f} deg, centre {(th[m].max() + th[m].min()) / 2:.1f}')
w = ch[(ph == 'brake') & (ch != '')]
print('choices:', {k: int(np.sum(w == k)) for k in ('A', 'B', 'C', 'off')})
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
os.makedirs('plots', exist_ok=True)
fig, ax = plt.subplots(figsize=(12, 4))
for p, col in (('kick', 'C3'), ('settle', 'C1'), ('observe', 'C2'), ('brake', 'C0')):
    m = ph == p; ax.plot(t[m] - tb, th[m], '.', ms=1.5, color=col, label=p)
on = (ph == 'brake') & np.isin(ch, ['A', 'B', 'C'])
ax.plot(t[on] - tb, th[on], '|', color='k', ms=6, label='brake push written')
ax.axhline(236, color='grey', ls=':'); ax.axhline(190, color='grey', ls=':')
ax.set_xlabel('s from brake start'); ax.set_ylabel('rotor angle (deg)'); ax.legend(fontsize=8, ncol=5)
ax.set_title('B4 stage 2b: kick (A, 2400 counts) then brake (800 counts, offsets, live tracker), 2026-11-11')
fig.tight_layout(); fig.savefig('plots/b4_kick_brake.png', dpi=110)
