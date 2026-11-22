#!/usr/bin/env python3
"""Code-variant scan (sim only): variants.fast (handover on rotation stop) with/without a separate pump push-speed gate, vs live controller,
at several parameter settings. Same cells/metrics as scan.py. python3 vscan.py '<json list of base settings>'"""
import json, os, sys
from concurrent.futures import ProcessPoolExecutor
import scan as K

HERE = os.path.dirname(os.path.abspath(__file__))
if __name__ == '__main__':
    bases = json.loads(sys.argv[1])
    S_ = []
    for b in bases:
        S_.append(dict(K.BASE, **b))                                                          # live controller
        S_.append(dict(K.BASE, **b, variant='fast', vparams={}))                              # handover only
        for wp in (200.0, 260.0, 320.0):
            S_.append(dict(K.BASE, **b, variant='fast', vparams=dict(wpm_pump=wp)))           # + pump gate at large swing speed
    with ProcessPoolExecutor() as ex:
        res = K.evaluate(S_, ex)
    json.dump(res, open(os.path.join(HERE, 'scan_variant.json'), 'w'), indent=1)
