#!/usr/bin/env python3
"""python3 gates.py -> phaseA_summary.md : selected settings across all gates (reads cells_*.json, excludes the 2-setting 'quick' file)."""
import glob, json, os
from summarize import agg

HERE = os.path.dirname(os.path.abspath(__file__))
rows = {}
for f in sorted(glob.glob(os.path.join(HERE, 'cells_*.json'))):
    b = os.path.basename(f)
    if 'quick' in b:
        continue
    p = b.split('_')
    key = (p[1], p[2], 't2' if 't2' in b else 'live-ctrl')
    rows.setdefault(key, []).extend(json.load(open(f)))
want = [(120, 800, .05, .03), (140, 1600, .1, .03), (160, 1600, .1, .03), (140, 1200, .1, .03), (160, 800, .1, .03),
        (140, 800, .1, .03), (120, 1600, .1, .03), (120, 1600, .1, .06), (140, 1200, .05, .03), (140, 800, .05, .03),
        (140, 1600, .05, .03), (160, 1200, .1, .03), (160, 1600, .05, .03), (300, 1600, .1, .03), (1000, 1600, .1, .03)]
L = ['Selected settings (wpm deg/s, level counts, tol, c_assumed s) per gate; 12 cells each; sim (D), level >1600 not used.',
     '', '| gate | controller | wpm | level | tol | c | ok | median t_reach (s) | median t3 (s) | reach3 in window | mean last 300 s (Hz) |',
     '|---|---|---|---|---|---|---|---|---|---|---|']
for key, rr in sorted(rows.items()):
    out = {o['k']: o for o in agg(rr)}
    g = ('A1/A2 ' if key[0] == 'a1' else 'A3 start ') + key[1] + ' Hz' if key[0] == 'a1' else 'A3 start ' + key[1] + ' Hz'
    for w in want:
        o = out.get((w[0], w[1], w[2], w[3]))
        if o:
            L.append(f"| {g} | {key[2]} | {w[0]} | {w[1]} | {w[2]} | {w[3]} | {o['ok']}/{o['n']} | {o['t_reach']:.0f} | "
                     f"{'inf' if o['t3'] > 1e9 else round(o['t3'])} | {o['reach3']}/{o['n']} | {o['late']:.3f} |")
open(os.path.join(HERE, 'phaseA_summary.md'), 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
