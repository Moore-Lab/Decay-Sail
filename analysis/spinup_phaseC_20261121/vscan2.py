"""Variant at the live stop rule (0.01) and 0.08, rev only. python3 vscan2.py -> scan_variant2.json"""
import json
from concurrent.futures import ProcessPoolExecutor
import scan as K
if __name__ == '__main__':
    S_ = [dict(K.BASE, wpm=w, stop_tol=st, variant='fast', vparams=vp) for w, vp in ((140.0, {}), (140.0, dict(wpm_pump=200.0)), (220.0, dict(wpm_pump=200.0)))
          for st in (0.01, 0.08)]
    with ProcessPoolExecutor() as ex:
        res = K.evaluate(S_, ex, modes=('rev',))
    json.dump(res, open('scan_variant2.json', 'w'), indent=1)
    for r in res:
        s, a = r['setting'], r['rev']
        print('wpm %.0f stop %.2f vp %s | rev med %.0f p90 %.0f fail %d wcap %d pk %.2f/%.2f rate@stop %.3f' % (s['wpm'], s['stop_tol'], s['vparams'], a['med'], a['p90'], a['fail'], a['wcap'], a['peak_f_med'], a['peak_f_max'], a['rate_stop_med']))
