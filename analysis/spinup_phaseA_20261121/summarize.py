#!/usr/bin/env python3
"""python3 summarize.py FILE.json [FILE2.json ...] -> table per setting, sorted best first, with gate verdicts."""
import json, sys
from collections import defaultdict
import numpy as np

def med(v):
    v = [np.inf if x is None else x for x in v]
    return float(np.median(v))

def agg(rows):
    g = defaultdict(list)
    for r in rows:
        g[(int(r['wpm']), int(r['level']), r['tol'], r['ca'])].append(r)
    out = []
    for k, rr in g.items():
        mode_rev = rr[0]['start_f'] > 0
        n = len(rr)
        ok = sum(r['ok'] for r in rr)
        tr = med([r['t_reach'] for r in rr]); t3m = med([r['t3'] for r in rr])
        reach3 = sum(r['t3'] is not None and not r['aborted'] and r['dir_first'] == r['dir'] for r in rr)
        ab = sum(r['aborted'] for r in rr)
        late = np.mean([r['late_mean'] for r in rr]); pk = max(r['wmax'] for r in rr)
        out.append(dict(k=k, n=n, ok=ok, t_reach=tr, t3=t3m, reach3=reach3, aborts=ab, late=late, peak=pk, rev=mode_rev,
                        f_t=rr[0]['f_t'], start_f=rr[0]['start_f']))
    return out

def show(out, top=None):
    rev = out[0]['rev']
    key = (lambda o: (-o['reach3'], o['t3'])) if rev else (lambda o: (-o['ok'], o['t_reach']))
    out = sorted(out, key=key)
    print('| wpm | level | tol | c_assumed | ok | med t_reach | ' + ('reach3 within 300 s | med t3 |' if rev else 'med t3 (1 %x3) | n reach3 |') + ' aborts | mean last 300 s (Hz) | peak (deg/s) |')
    print('|---|---|---|---|---|---|---|---|---|---|---|')
    for o in out[:top]:
        k = o['k']
        print(f"| {k[0]} | {k[1]} | {k[2]} | {k[3]} | {o['ok']}/{o['n']} | {o['t_reach']:.0f} | {o['reach3']}/{o['n']} | {o['t3']:.0f} | {o['aborts']} | {o['late']:.3f} | {o['peak']:.0f} |")

if __name__ == '__main__':
    rows = []
    for f in sys.argv[1:]:
        rows += json.load(open(f))
    out = agg(rows)
    print(f"f_t {out[0]['f_t']}, start_f {out[0]['start_f']}, settings {len(out)}")
    show(out, top=int(__import__('os').environ.get('TOP', 12)))
