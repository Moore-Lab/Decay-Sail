import json, sys
f = sys.argv[1] if len(sys.argv) > 1 else 'scan_grid.json'
rows = json.load(open(f))
def key(r):
    return (r['setting']['stop_tol'], r['setting']['stop_n'])
print('rank within each stop rule (stop_tol, n): best 3 by p90 then median; rev = reversal from 0.44 Hz, fail = no stop in 300 s')
for k in sorted({key(r) for r in rows}):
    g = sorted([r for r in rows if key(r) == k], key=lambda r: (r['rev']['p90'], r['rev']['med']))
    for r in g[:3]:
        s = r['setting']; v = r['rev']
        print(f"stop {k}: wpm {s['wpm']:.0f} tol {s['tol']} lvl {s['level']:.0f} | med {v['med']:.0f} p90 {v['p90']:.0f} fail {v['fail']} wcap {v['wcap']} "
              f"first {v['first_med']:.0f} peak_f {v['peak_f_med']:.2f}/{v['peak_f_max']:.2f} rate@stop med {v['rate_stop_med']} p90max {v['rate_stop_p90']}" if v.get('rate_stop_med') else
              f"stop {k}: wpm {s['wpm']:.0f} tol {s['tol']} lvl {s['level']:.0f} | med {v['med']:.0f} p90 {v['p90']:.0f} fail {v['fail']} (old fields)")
