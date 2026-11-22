#!/usr/bin/env python3
"""Live Phase B reversal metrics from the per-step logs (measured). Mac only, read-only.
Per step (field-on = first 'brake' row): brake end (first time f_against <= 0.05 Hz, the governor's own reverse flag),
first full turn along d (new forward max of 360 deg from the minimum of d*th), t_reach (f_mean within 5 % of 0.5),
hunt = t_stop - t_reach, t_stop = last row."""
import json, os
import numpy as np
D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-21/phaseB')
STEPS = {'B1': (1795307740, +1), 'R1': (1795308102, -1), 'R2': (1795308537, +1), 'R3': (1795308921, -1), 'R4': (1795309324, +1),
         'R5': (1795309774, -1), 'R6': (1795310161, +1), 'R7': (1795311159, -1)}


def load(step):
    fn = os.path.join(D, f'brake_{STEPS[step][0]}.csv'); rows = []
    for ln in open(fn):
        if ln.startswith('#') or ln.startswith('host_t'):
            continue
        p = ln.rstrip('\n').split(',')
        if len(p) < 16 or p[5] != 'brake':
            continue
        note = dict(kv.split('=') for kv in p[15].split(';') if '=' in kv)
        rows.append((float(p[0]), float(p[3]), p[9], float(note.get('f_mean', 'nan')), float(note.get('f_against', 'nan'))))
    return rows


def series(step):
    d = STEPS[step][1]; r = load(step); t = np.array([x[0] for x in r]); t = t - t[0]
    ang = np.degrees(np.unwrap(np.radians([x[1] for x in r])))
    return d, t, ang, np.array([x[2] for x in r]), np.array([x[3] for x in r]), np.array([x[4] for x in r])


def metrics(step):
    d, t, ang, ch, fm, fa = series(step)
    w = np.convolve(np.gradient(ang, t), np.ones(5) / 5, mode='same')
    x = d * ang
    ib0 = int(np.argmax(fa > 0.05)); ibe = ib0 + int(np.argmax(fa[ib0:] <= 0.05)) if step != 'B1' else 0
    wd = np.convolve(d * np.gradient(ang, t), np.ones(25) / 25, mode='same')      # 0.5 s smoothing, along d
    neg = np.where(wd < -30)[0]; iz = int(neg[0] + np.argmax(wd[neg[0]:] > 0)) if neg.size else 0   # first turn-around after rotating against d
    base = np.minimum.accumulate(x); i1 = int(np.argmax(x - base >= 360))
    ir = int(np.argmax(np.abs(fm / 0.5 - 1) < 0.05))
    ws = np.convolve(np.abs(w), np.ones(50) / 50, mode='same')
    j = slice(ibe, min(len(t), ibe + 1500))
    amp = np.array([(ang[max(0, i - 100):i + 1].max() - ang[max(0, i - 100):i + 1].min()) / 2 for i in range(len(t))])
    return dict(step=step, dir=d, t_rot_stop=float(t[iz]), over_brake=float(t[ibe] - t[iz]), t_stop=float(t[-1]), t_brake_end=float(t[ibe]), t_first_turn=float(t[i1]), t_reach=float(t[ir]),
                hunt=float(t[-1] - t[ir]), gap_brake_to_turn=float(t[i1] - t[ibe]),
                min_ws_after_brake=float(ws[j].min()), t_min_ws=float(t[j][np.argmin(ws[j])]), peak_w=float(np.abs(w).max()),
                amp_before_turn=float(amp[max(i1 - 100, 0)]), peak_f=float(np.nanmax(fm)))


if __name__ == '__main__':
    out = [metrics(s) for s in STEPS if s != 'B1']
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'live_metrics.json'), 'w'), indent=1)
    for m in out:
        print({k: (round(v, 1) if isinstance(v, float) else v) for k, v in m.items()})
