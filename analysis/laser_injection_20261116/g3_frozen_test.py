#!/usr/bin/env python3
"""The frozen G3 test (HANDOFF, set 2026-11-22 before the data arrived) on the 11-22 5-min run. Analysis only, Mac.

Spec: G3_DETREND=1, angle band and gamma band both 0.44-0.49 Hz, pairs (O1,O2),(O3,O4)..., pair dg = gamma(-) - gamma(+)
with its mean removed, dangle = angle(-) - angle(+). Pass: r > 0.3, positive sign, and < 5 % of circular shifts of dangle
against dg reach |r|. Report the coefficient and the scatter with/without the term.

Not fixed by the spec, chosen here (stated in the output): gamma is pair_plots.gamma_mid evaluated at the band centre
F_MID = 0.465 Hz (its default 0.435 is outside this band); 0.44 (nearest the old point) is printed as a sensitivity row.
Angles come from g3_hill_fast_5min_frozen.json:
    LASER_DIR=.../spinup/2026-11-22/ RUN=fast_5min G3_DETREND=1 G3_PBAND=0.44,0.49 G3_TAG=_frozen python3 g3_hill.py
    LASER_DIR=.../spinup/2026-11-22/ RUN=fast_5min python3 g3_frozen_test.py   # -> g3_frozen_test_fast_5min.json
"""
import json
import os

import numpy as np
from scipy.stats import pearsonr

import coasts as C
import g1_within_coast as G
import night_plots as NP

HERE = os.path.dirname(os.path.abspath(__file__))
BAND = (0.44, 0.49)


def gammas(f_mid):
    C.BAND = BAND
    C.PP.F_MID = f_mid
    k, h, a, n = C.load_tracker(False)
    out = {}
    for r in json.load(open(os.path.join(HERE, f'g3_hill_{NP.RUN}_frozen.json')))['coasts']:
        x = G.coast(r['name'], k, h, a, n)
        out[r['name']] = dict(gamma=1e6 * x['g'], ge=1e6 * x['ge'], jk=1e6 * x['jk'], n=len(x['t']))
    return out


def test(g, ang):
    P = [(f'O{i:02d}', f'O{i + 1:02d}') for i in range(1, 200, 2)]
    P = [(p, q) for p, q in P if p in g and q in g and ang.get(p) is not None and ang.get(q) is not None]
    dg = np.array([g[q]['gamma'] - g[p]['gamma'] for p, q in P]); dg -= dg.mean()
    da = np.array([ang[q] - ang[p] for p, q in P])
    r, pv = pearsonr(da, dg)
    shifts = np.array([pearsonr(np.roll(da, s), dg)[0] for s in range(1, len(da))])
    frac = float(np.mean(np.abs(shifts) >= abs(r)))
    b, cov = np.polyfit(da, dg, 1, cov=True)
    return dict(n_pairs=len(P), r=round(float(r), 3), p=float(pv), shift_frac=round(frac, 3), n_shifts=len(shifts),
                passed=bool(r > 0.3 and frac < 0.05), coef_uHz_per_deg=round(float(b[0]), 1),
                coef_err=round(float(np.sqrt(cov[0, 0])), 1), sd_dg=round(float(dg.std(ddof=1)), 2),
                sd_dg_after=round(float((dg - np.polyval(b, da)).std(ddof=2)), 2), sd_dangle_deg=round(float(da.std()), 4))


def main():
    hill = json.load(open(os.path.join(HERE, f'g3_hill_{NP.RUN}_frozen.json')))['coasts']
    ang = {r['name']: r['phase_deg'] for r in hill}
    res = dict(run=NP.RUN, spec='HANDOFF frozen test 2026-11-22', band=BAND)
    for fm, key in ((0.465, 'main_fmid_0.465'), (0.44, 'sensitivity_fmid_0.44')):
        g = gammas(fm)
        res[key] = test(g, ang)
        res[key]['jk_median_uHz'] = round(float(np.median([v['jk'] for v in g.values()])), 2)
        res[key]['formal_median_uHz'] = round(float(np.median([v['ge'] for v in g.values()])), 3)
        res[key]['turns_in_band_median'] = int(np.median([v['n'] for v in g.values()]))
        res[key]['gamma_by_coast'] = {k: round(v['gamma'], 3) for k, v in g.items()}
        print(key, {k: v for k, v in res[key].items() if k != 'gamma_by_coast'})
    json.dump(res, open(os.path.join(HERE, f'g3_frozen_test_{NP.RUN}.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
