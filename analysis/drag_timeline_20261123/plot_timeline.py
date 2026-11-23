#!/usr/bin/env python3
"""Plot drag_timeline.json -> plots/drag_timeline.png; also writes the pooled-November fit into drag_timeline_pooled.json."""
import datetime, json, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from drag_timeline import fit_ab

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, 'drag_timeline.json')))
D = lambda s: datetime.datetime.strptime(s[:10], '%Y-%m-%d')
CH = [('2026-09-08', 'model change (DRVMTRX)'), ('2026-09-09', 'chamber on optical table'), ('2026-10-15', 'rebuild: new tilt stage, board GND (10-15..22)'),
      ('2026-10-26', 'chamber on tilt stage'), ('2026-10-27', 'shims under PEEK'), ('2026-11-11', 'HV amp DC-coupled')]

# pooled November: night/coast band medians pooled, one fit
nov = [r for r in R if r['date'] >= '2026-11-12']
pool = {}
for r in nov:
    for b in r['bands']:
        pool.setdefault(b['band'], []).append((b['f_mean'], b['gamma_uHz']))
rows = []
for k, v in sorted(pool.items()):
    f, g = np.array(v).T
    rows.append((float(np.mean(f)), float(np.mean(g)), float(max(np.std(g, ddof=1) / np.sqrt(len(g)), 1.0))))
pooled = dict(bands=[dict(f=a, gamma=b, err=c) for a, b, c in rows], fit=fit_ab(rows))
json.dump(pooled, open(os.path.join(HERE, 'drag_timeline_pooled.json'), 'w'), indent=1)
print('pooled Nov', pooled['fit'])

fig, ax = plt.subplots(3, 1, figsize=(10, 10), sharex=True)
cols = {'0.40-0.47': '#1f6fb4', '0.47-0.50': '#7f7f7f', '0.50-0.59': '#d95f02', '0.33-0.40': '#2ca02c', '0.59-0.73': '#9467bd'}
for key, lab in [('0.33-0.40', '0.33-0.40 Hz'), ('0.40-0.47', '0.40-0.47 Hz (~0.435)'), ('0.50-0.59', '0.50-0.59 Hz (~0.545)'), ('0.59-0.73', '0.59-0.73 Hz')]:
    x, y, e = [], [], []
    for r in R:
        for b in r['bands']:
            if b['band'] == key:
                x.append(D(r['date'])); y.append(b['gamma_uHz']); e.append(b['jk_uHz'])
    ax[0].errorbar(x, y, e, fmt='o', ms=5, color=cols[key], label=lab, capsize=2)
ax[0].set_ylabel('gamma  (uHz)'); ax[0].legend(fontsize=8, ncol=2); ax[0].set_title('Decay rate per speed band (error: jackknife / coast-to-coast s.e.)')
for j, (k, lab) in enumerate([('a_uHz', 'a = speed-independent damping (uHz)'), ('b_uHzHz', 'b = friction-like term (uHz Hz)')]):
    for r in R:
        f = r.get('fit')
        if f:
            good = f['nbands'] >= 4
            ax[j + 1].errorbar(D(r['date']), f[k], f['da' if j == 0 else 'db'], fmt='o' if good else 's', mfc='C0' if good else 'none', color='C0', capsize=2)
    ax[j + 1].set_ylabel(lab); ax[j + 1].axhline(0, color='k', lw=0.5)
ax[1].set_title('gamma = a + b/f   (filled: >= 4 bands; open: 3 bands or fewer, poorly constrained)')
for a in ax:
    for d, lab in CH:
        a.axvline(D(d), color='k', ls=':', lw=0.8)
for d, lab in CH:
    ax[0].text(D(d), ax[0].get_ylim()[1], ' ' + lab, rotation=90, va='top', fontsize=6.5)
ax[2].set_xlabel('date (2026)'); fig.autofmt_xdate(); fig.tight_layout()
fig.savefig(os.path.join(HERE, 'plots', 'drag_timeline.png'), dpi=140)
