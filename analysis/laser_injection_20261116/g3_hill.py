#!/usr/bin/env python3
"""Gate G3 (2026-11-22): does the hill's height change from coast to coast, and does that track gamma and temperature?
Analysis only, Mac. Observations; interpretation not approved.

Hill height from energy: with no drag, (1/2) I w(theta)^2 + U(theta) = const, so U(theta)/I = -(1/2) w^2 + const. Per turn:
w^2 in 36 bins of 10 deg of tracker angle (w = 10 deg / time to cross it, raw 50 fps angles), mean removed, fitted as
s x template(theta) + linear-in-time (absorbs the drag loss within the turn). template = the night's mean profile per
direction (mean removed). s = 1 means the night-average hill; s is speed-independent if the hill is fixed and conservative.
Per coast: mean s over turns in the gamma band (0.40-0.47 Hz), its standard error, and the hill depth in J
(I = 1.1e-11). Joined with gamma_res and air T from temp_noise_<run>.json where present.
    RUN=nd2_run LASER_DIR=.../2026-11-18/laser python3 g3_hill.py     # -> g3_hill_<run>.json
"""
import glob
import json
import os

import numpy as np

import coasts as C
import night_plots as NP

HERE = os.path.dirname(os.path.abspath(__file__))
NB = 36
# estimator check (2026-11-22): G3_PBAND='lo,hi' measures the angle only on turns in that speed band (speed-matched);
# G3_DETREND=1 removes the within-turn drag (linear-in-time) part before taking the angle. Output gets suffix G3_TAG.
PBAND = tuple(float(x) for x in os.environ.get('G3_PBAND', '0.40,0.47').split(','))
DETREND = os.environ.get('G3_DETREND', '0') == '1'
TAG = os.environ.get('G3_TAG', '')
I = 1.1e-11


def turns_w2(tt, x, d):
    """Per full turn (along the motion): w^2 (rad^2/s^2) in 36 tracker-angle bins, turn mean rate (Hz), turn mid-time."""
    y = d * x
    marks = np.arange(np.ceil(y[0] / 360) * 360, y[-1], 10.0)
    tc = np.interp(marks, y, tt)
    seg = np.diff(tc)
    rows = []
    for i in range(0, len(seg) - NB + 1, NB):
        s = seg[i:i + NB]
        if np.any(s <= 0) or np.any(s > 5):
            continue
        ang = (d * marks[i:i + NB] + (5.0 if d > 0 else -5.0)) % 360          # bin centre, physical tracker angle
        idx = (ang // 10).astype(int)
        w2 = np.empty(NB); w2[idx] = (np.radians(10.0) / s) ** 2
        rows.append((w2, 1 / s.sum(), tc[i] + s.sum() / 2, np.argsort(idx)))
    return rows


def main():
    k, h, a, n = C.load_tracker(False)
    t_all = k / C.TC.FPS; off = float(np.median(h - t_all))
    names = sorted(os.path.basename(p)[6:-4] for p in glob.glob(os.path.join(C.D, NP.RUN, 'coast_O*.txt'))
                   if 'coast_end_host' in C.read_meta(p))
    per = {}
    for nm in names:
        m = C.read_meta(os.path.join(C.D, NP.RUN, f'coast_{nm}.txt'))
        d = 1 if int(nm[1:]) % 2 else -1
        t0, t1 = m['field_off_host'] + 5 - off, m['coast_end_host'] - 2 - off
        w = (t_all >= t0) & (t_all <= t1) & (n >= 0.5)
        if w.sum() < 1000:
            continue
        per[nm] = (d, m, turns_w2(t_all[w], np.degrees(np.unwrap(np.radians(a[w]))), d))
    tmpl = {}
    for d in (1, -1):
        W = np.array([r[0] - r[0].mean() for nm, (dd, m, rows) in per.items() if dd == d for r in rows if 0.40 <= r[1] <= 0.47])
        tmpl[d] = W.mean(0)
    out = dict(run=NP.RUN, template_depth_J={str(d): float(I * 0.5 * (tmpl[d].max() - tmpl[d].min())) for d in tmpl},
               template_corr_plus_minus=float(np.corrcoef(tmpl[1], tmpl[-1])[0, 1]), coasts=[])
    tj = os.path.join(HERE, f'temp_noise_{NP.RUN}.json')
    extra = {c['name']: c for c in json.load(open(tj))['coasts']} if os.path.exists(tj) else {}
    for nm, (d, m, rows) in per.items():
        S, F, Tm, PH = [], [], [], []
        th_c = np.radians(np.arange(5, 360, 10))
        for w2, fr, tm, order in rows:
            y = w2 - w2.mean()
            tb = np.empty(NB); tb[order] = np.arange(NB)            # time order of the bins within the turn
            X = np.column_stack([tmpl[d], tb - tb.mean()])
            cf = np.linalg.lstsq(X, y, rcond=None)[0]
            S.append(cf[0]); F.append(fr); Tm.append(tm)
            yp = y - cf[1] * (tb - tb.mean()) if DETREND else y
            PH.append(np.angle(np.sum(yp * np.exp(-1j * th_c))))     # phase of the 1-per-turn part of the hill (rad)
        S, F, Tm, PH = map(np.array, (S, F, Tm, PH))
        PH = np.degrees(np.unwrap(PH))
        b = (F >= 0.40) & (F <= 0.47)
        if b.sum() < 10:
            continue
        hi = (F > 0.455) & b; lo = (F < 0.425) & b
        pb = (F >= PBAND[0]) & (F <= PBAND[1])
        row = dict(name=nm, dir=d, laser=m.get('laser', ''), host=m['field_off_host'], n_turns=int(b.sum()),
                   s=float(S[b].mean()), s_err=float(S[b].std(ddof=1) / np.sqrt(b.sum())),
                   s_hi_minus_lo=float(S[hi].mean() - S[lo].mean()) if hi.sum() > 3 and lo.sum() > 3 else None,
                   s_slope_per_10min=float(600 * np.polyfit(Tm[b] - Tm[b][0], S[b], 1)[0]),
                   phase_deg=float(PH[pb].mean()) if pb.sum() >= 3 else None,
                   phase_err=float(PH[pb].std(ddof=1) / np.sqrt(pb.sum())) if pb.sum() >= 3 else None,
                   phase_n=int(pb.sum()), phase_f_mean=float(F[pb].mean()) if pb.sum() else None,
                   phase_slope_deg_per_10min=float(600 * np.polyfit(Tm[b] - Tm[b][0], PH[b], 1)[0]))
        if nm in extra:
            row.update(gamma_res=extra[nm]['gamma_res'], T=extra[nm]['T'], gamma=extra[nm]['gamma'], jk=extra[nm]['jk'])
        out['coasts'].append(row)
    json.dump(out, open(os.path.join(HERE, f'g3_hill_{NP.RUN}{TAG}.json'), 'w'), indent=1)
    c = out['coasts']; A_ = lambda key: np.array([r[key] for r in c if r.get(key) is not None], float)
    print(NP.RUN, 'template depth J', out['template_depth_J'], 'corr +/- templates %.3f' % out['template_corr_plus_minus'])
    print(' coasts', len(c), 's mean %.4f sd %.4f median s_err %.4f' % (A_('s').mean(), A_('s').std(ddof=1), np.median(A_('s_err'))))
    print(' within-coast s high-speed minus low-speed: mean %.4f sd %.4f' % (np.nanmean(A_('s_hi_minus_lo')), np.nanstd(A_('s_hi_minus_lo'))))
    print(' within-coast s drift per 10 min: median %.4f, sd %.4f' % (np.median(A_('s_slope_per_10min')), A_('s_slope_per_10min').std()))
    for d in (1, -1):
        s_ = np.array([r['s'] for r in c if r['dir'] == d]); print(f'  dir {d:+d}: n {len(s_)} s sd {s_.std(ddof=1):.4f}')


if __name__ == '__main__':
    main()
