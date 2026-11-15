#!/usr/bin/env python3
"""Overnight coast series 2026-11-14/15: rotor spin rate and damping per coast from the LES. Mac only, reads Dropbox.

    python3 les_coasts.py          # -> les_coasts.json, les_coasts.csv, plots/les_tau_vs_time.png, plots/les_coasts_f.png

Data: Dropbox spinup/2026-11-14/overnight/{les,series}. LES = Y1:RDS-LES_PIT_OUT_DQ and _YAW_OUT_DQ, 1024 Hz, front-end
clock. Coast windows from coast_On.txt (fe_gps_field_off, fe_gps_coast_end: 1 s resolution, read live on worker2).

Method (per coast, per channel):
 1. Window [field off + 5 s, coast end - 2 s]. Remove the mean, decimate to 8 Hz.
 2. Sliding 40 s Hann windows every 10 s, zero-padded FFT; the LES line at 2x the rotation rate (CLAUDE.md: rotating,
    LES line = 2 f_rot) is found near 2x the previous window's rate (first window: strongest peak 0.6-1.1 Hz),
    refined by parabolic interpolation on log power. f_rot = peak / 2 at the window centre.
 3. Fit f(t) = f0 exp(-t / tau) (log-linear least squares) over (a) the whole coast and (b) the COMMON band
    0.40-0.47 Hz, covered by every coast that started at >= 0.47 Hz.
 4. Channel used: the one with the higher median line SNR (line power / median power 0.3-1.6 Hz) for that coast.
 Errors: 1-sigma delete-one-block jackknife over 10 contiguous blocks of windows (windows overlap, so the formal
 fit error would be too small).
 A coast counts as ROTATING if the rate starts above 0.35 Hz and falls through the coast; otherwise it is a swing
 (a swing's LES comb has lines near 0.6-0.7 Hz too, so the line frequency alone does not tell them apart; O04 and O20,
 by worker2's report from the brake logs) and is skipped.
 Whole-coast tau depends on the speed range covered, so whole-coast summaries use only coasts starting >= 0.48 Hz.
 Summary: per direction, mean and SCATTER (sd) of tau over coasts; the scatter between coasts is the measured
 repeatability. Linear trend of tau against time of night per direction. Pair differences (- minus +) for each
 back-to-back + then - pair where both coasts have a band tau.
Rotation direction is not in the LES; it is the commanded --dir from series.csv (+1 = increasing tracker angle).
"""
import csv
import glob
import json
import os
from datetime import datetime, timezone, timedelta

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-14/overnight')
FS, DEC = 1024.0, 8.0
WIN, STEP, NFFT = 40.0, 10.0, 2 ** 14
BAND = (0.40, 0.47)


def load_les():
    chunks = sorted(glob.glob(os.path.join(D, 'les', 'les_*.npz')), key=lambda p: int(os.path.basename(p).split('_')[1]))
    g0 = None; pit = []; yaw = []
    for p in chunks:
        z = np.load(p)
        if g0 is None:
            g0 = float(z['gps0'])
        exp = int(round((float(z['gps0']) - g0) * FS))
        have = sum(len(a) for a in pit)
        if exp != have:
            raise RuntimeError(f'{p}: gap/overlap of {exp - have} samples')
        pit.append(z['pit'].astype(float)); yaw.append(z['yaw'].astype(float))
    return g0, np.concatenate(pit), np.concatenate(yaw)


def coasts():
    rows = list(csv.DictReader(open(os.path.join(D, 'series', 'series.csv'))))
    out = []
    for r in rows:
        if not r['coast_end_host']:
            continue
        m = {}
        for line in open(os.path.join(D, 'series', f'coast_{r["name"]}.txt')):
            p = line.split(None, 1)
            if len(p) == 2:
                m[p[0]] = p[1].strip()
        out.append(dict(name=r['name'], dir=int(r['dir']), on_target=int(r['on_target']), stop=r['stop_reason'],
                        host_off=float(r['field_off_host']), host_end=float(r['coast_end_host']),
                        fe_off=float(m['fe_gps_field_off']), fe_end=float(m['fe_gps_coast_end'])))
    return out


def track(x, t0):
    """x at 1024 Hz -> (t_mid from t0, f_rot, snr) per window."""
    y = x - x.mean()
    for q in (8, 8, 2):
        y = signal.decimate(y, q, ftype='fir', zero_phase=True)
    n, s = int(WIN * DEC), int(STEP * DEC)
    w = signal.windows.hann(n)
    fr = np.fft.rfftfreq(NFFT, 1 / DEC)
    out, prev = [], None
    for i in range(0, len(y) - n + 1, s):
        P = np.abs(np.fft.rfft(y[i:i + n] * w, NFFT)) ** 2
        if prev is None:
            m = (fr > 0.6) & (fr < 1.1)
        else:
            m = (fr > 2 * prev - 0.03) & (fr < 2 * prev + 0.03)
        j = np.flatnonzero(m)[np.argmax(P[m])]
        a, b, c = np.log(P[j - 1:j + 2])
        d = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
        fpk = fr[j] + d * (fr[1] - fr[0])
        noise = np.median(P[(fr > 0.3) & (fr < 1.6)])
        prev = fpk / 2
        out.append((t0 + (i + n / 2) / DEC, prev, P[j] / noise))
    return np.array(out)


def fit_tau(t, f):
    p = np.polyfit(t, np.log(f), 1)
    return -1.0 / p[0] / 60.0


def jack(arr, nb=10):
    if len(arr) < nb + 2:
        return float('nan')
    e = np.linspace(0, len(arr), nb + 1).astype(int)
    v = np.array([fit_tau(*np.concatenate([arr[:e[j]], arr[e[j + 1]:]]).T[:2]) for j in range(nb)])
    return float(np.sqrt((nb - 1) / nb * np.sum((v - v.mean()) ** 2)))


def main():
    g0, pit, yaw = load_les()
    g1 = g0 + len(pit) / FS
    res, traces = [], {}
    for c in coasts():
        a, b = c['fe_off'] + 5, c['fe_end'] - 2
        if b > g1:
            continue
        i0, i1 = int((a - g0) * FS), int((b - g0) * FS)
        tr = {ch: track(x[i0:i1], 0.0) for ch, x in (('pit', pit), ('yaw', yaw))}
        snr = {ch: float(np.median(v[:, 2])) for ch, v in tr.items()}
        ch = max(snr, key=snr.get)
        v = tr[ch]
        local = datetime.fromtimestamp(c['host_off'], timezone.utc) - timedelta(hours=5)     # EST
        r = dict(c, channel=ch, snr_pit=snr['pit'], snr_yaw=snr['yaw'], local_off=local.strftime('%H:%M'),
                 f_start=float(v[0, 1]), f_end=float(v[-1, 1]), rotating=bool(v[0, 1] > 0.35 and v[-1, 1] < v[0, 1] - 0.02))
        if r['rotating']:
            r['tau_whole_min'] = fit_tau(v[:, 0], v[:, 1]); r['tau_whole_err'] = jack(v)
            s = (v[:, 1] >= BAND[0]) & (v[:, 1] <= BAND[1])
            if r['f_start'] >= BAND[1] and s.sum() >= 12:
                r['tau_band_min'] = fit_tau(v[s, 0], v[s, 1]); r['tau_band_err'] = jack(v[s]); r['n_band'] = int(s.sum())
            # the other channel, for a channel cross-check
            o = tr['yaw' if ch == 'pit' else 'pit']
            r['tau_whole_other_min'] = fit_tau(o[:, 0], o[:, 1])
        traces[c['name']] = v
        res.append(r)
        print(f"{r['name']} {r['dir']:+d} {r['local_off']} {ch} snr {snr['pit']:.0f}/{snr['yaw']:.0f} "
              f"f {r['f_start']:.3f}->{r['f_end']:.3f} "
              + (f"tau {r['tau_whole_min']:.2f}±{r['tau_whole_err']:.2f} (other ch {r['tau_whole_other_min']:.2f})"
                 + (f" band {r['tau_band_min']:.2f}±{r['tau_band_err']:.2f}" if 'tau_band_min' in r else ' band -')
                 if r['rotating'] else 'NOT ROTATING (swing)') + ('' if r['on_target'] else f"  [{r['stop'][:20]}]"))
    summ = {}
    for key in ('tau_band_min', 'tau_whole_min'):
        for d in (1, -1):
            rr = [r for r in res if r['dir'] == d and key in r and (key == 'tau_band_min' or r['f_start'] >= 0.48)]
            t = np.array([(r['host_off'] - res[0]['host_off']) / 3600 for r in rr]); y = np.array([r[key] for r in rr])
            pf, cov = np.polyfit(t, y, 1, cov=True)
            summ[f'{key} dir{d:+d}'] = dict(n=len(rr), mean=float(y.mean()), sd=float(y.std(ddof=1)),
                                           sem=float(y.std(ddof=1) / np.sqrt(len(y))), slope_min_per_h=float(pf[0]),
                                           slope_err=float(np.sqrt(cov[0, 0])))
        diffs = []
        for i in range(len(res) - 1):
            a_, b_ = res[i], res[i + 1]
            if (a_['dir'] == 1 and b_['dir'] == -1 and key in a_ and key in b_
                    and (key == 'tau_band_min' or min(a_['f_start'], b_['f_start']) >= 0.48)):
                diffs.append((a_['name'], b_['name'], 100 * (b_[key] / a_[key] - 1)))
        dv = np.array([x[2] for x in diffs])
        summ[f'{key} pairs'] = dict(n=len(diffs), mean_pct=float(dv.mean()), sd_pct=float(dv.std(ddof=1)),
                                    sem_pct=float(dv.std(ddof=1) / np.sqrt(len(dv))), pairs=diffs)
    for k, v_ in summ.items():
        print(k, {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v_.items() if kk != 'pairs'})
    json.dump(dict(les_gps=[g0, g1], band=BAND, summary=summ, coasts=res), open(os.path.join(HERE, 'les_coasts.json'), 'w'), indent=1)
    keys = ['name', 'dir', 'local_off', 'on_target', 'rotating', 'channel', 'f_start', 'f_end', 'tau_whole_min',
            'tau_whole_err', 'tau_band_min', 'tau_band_err', 'tau_whole_other_min', 'snr_pit', 'snr_yaw', 'fe_off', 'fe_end']
    with open(os.path.join(HERE, 'les_coasts.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, keys, extrasaction='ignore'); w.writeheader(); w.writerows(res)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig, ax = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True)
    for d, col, lab in ((1, '#1f6fb4', '+1'), (-1, '#c8501e', '-1')):
        for key, a_, mk in (('tau_whole_min', ax[0], 'o'), ('tau_band_min', ax[1], 's')):
            rr = [r for r in res if r['dir'] == d and key in r and (key == 'tau_band_min' or r['f_start'] >= 0.48)]
            x = [datetime.fromtimestamp(r['host_off'], timezone.utc) - timedelta(hours=5) for r in rr]
            y = [r[key] for r in rr]
            on = [bool(r['on_target']) for r in rr]
            a_.plot([xi for xi, o in zip(x, on) if o], [yi for yi, o in zip(y, on) if o], mk, color=col, ms=6,
                    label=f'{lab}: {len(rr)} coasts')
            a_.plot([xi for xi, o in zip(x, on) if not o], [yi for yi, o in zip(y, on) if not o], mk, mfc='white',
                    mec=col, ms=6)
            sm = summ[f'{key} dir{d:+d}']
            t = np.array([(r['host_off'] - res[0]['host_off']) / 3600 for r in rr])
            a_.plot(x, sm['mean'] + sm['slope_min_per_h'] * (t - t.mean()), '-', color=col, lw=1, alpha=0.7)
    ax[0].set_ylabel('tau, whole coast (min)'); ax[1].set_ylabel(f'tau, {BAND[0]}-{BAND[1]} Hz (min)')
    ax[0].set_title('LES: damping time per 10-min coast, overnight 2026-11-14/15. Open = spin-up timed out; lines = '
                    'linear trend.\nWhole-coast panel: coasts starting >= 0.48 Hz only. Scatter between coasts ~0.1 min',
                    fontsize=9)
    for a_ in ax:
        a_.legend(fontsize=8); a_.grid(alpha=0.3)
    import matplotlib.dates as mdates
    ax[1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M')); ax[1].set_xlabel('field off, local time (EST)')
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'les_tau_vs_time.png'), dpi=95)
    fig, a_ = plt.subplots(figsize=(11, 4.5))
    for r in res:
        v = traces[r['name']]
        a_.plot(v[:, 0] / 60, v[:, 1], '-', lw=0.8, color='#1f6fb4' if r['dir'] > 0 else '#c8501e', alpha=0.6)
    a_.set_xlabel('min after field off'); a_.set_ylabel('f_rot from LES (Hz)'); a_.grid(alpha=0.3)
    a_.set_title('LES rate per coast (blue +1, orange -1)', fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'plots', 'les_coasts_f.png'), dpi=95)


if __name__ == '__main__':
    main()
