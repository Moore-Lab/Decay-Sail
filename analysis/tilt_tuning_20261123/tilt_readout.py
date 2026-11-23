#!/usr/bin/env python3
"""Per-coast readout for tilt tuning (2026-11-23): gamma, hill depth and angle, tracker health. Reads files only.

Runs on worker2 right after a coast ends (numpy only; reads just the coast's part of the growing tracker CSV):
    python3 tilt_readout.py --run-dir ~/spinup/2026-11-23/tilt --note "A +0.5 B 0"      # newest finished coast
    python3 tilt_readout.py --run-dir <dir> --coast O07                                 # a given coast
Prints one line and appends it to <run-dir>/tilt_log.csv.

Per coast (window field-off + 5 s to coast end - 2 s, as the coast analyses):
  gamma   - d ln f/dt at F_MID (0.465 Hz) from a quadratic in ln f over the turns in BAND (0.44-0.49 Hz), uHz, with a
            10-block jackknife error (pair_plots.gamma_mid / jk). 11-22 baseline: coast-to-coast sd ~3 uHz.
  hill    - per full turn, w^2 in 36 x 10 deg bins of tracker angle, minus a straight line in time (drag within the turn);
            the turns in BAND are averaged: depth_J = I/2 x (max - min) of that mean profile (U/I = -w^2/2 + const);
            h1_J, h1_deg = size and phase of its once-per-turn part (phase as g3_hill.py). I = 1.1e-11 kg m^2.
  health  - ncc median/min, dropped-turn count, r_px mean (dot distance from the pinned centre; drifts if the view moves).
"""
import argparse
import glob
import os
import time

import numpy as np

FPS, I, NB = 50.0, 1.1e-11, 36
BAND, F_MID = (0.44, 0.49), 0.465


def meta(p):
    m = {}
    for ln in open(p):
        k, _, v = ln.strip().partition(' ')
        m[k] = v
    return m


def tracker_csv(run_dir):
    c = sorted(glob.glob(os.path.join(run_dir, 'tracker*', 'blob_live_gps*.csv')), key=os.path.getmtime)
    if not c:
        raise SystemExit(f'no tracker CSV under {run_dir}/tracker*/')
    return c[-1]


def _row_time(fh, off):
    fh.seek(off); fh.readline()
    while True:
        ln = fh.readline()
        if not ln:
            return None
        try:
            return float(ln.split(b',')[1])
        except (IndexError, ValueError):
            continue


def read_window(path, t0, t1):
    """Rows with t0 <= host_time <= t1, found by bisection on byte offset (the file is time-ordered)."""
    with open(path, 'rb') as fh:
        fh.seek(0, 2); lo, hi = 0, fh.tell()
        while hi - lo > 1 << 16:
            mid = (lo + hi) // 2; t = _row_time(fh, mid)
            if t is None or t >= t0:
                hi = mid
            else:
                lo = mid
        fh.seek(lo); fh.readline() if lo else None
        rows = []
        for ln in fh:
            if ln.startswith(b'#') or ln.startswith(b'frame'):
                continue
            p = ln.split(b',')
            try:
                h = float(p[1])
                if h < t0:
                    continue
                if h > t1:
                    break
                rows.append((int(p[0]), h, float(p[2]), float(p[3]), float(p[4])))
            except (IndexError, ValueError):
                continue
    return np.array(rows).reshape(-1, 5)


def turns(t, th, d, good):
    x = d * (th - th[0]); n = np.floor(x / 360.0); idx = np.where(np.diff(n) > 0)[0]
    tc = np.array([t[i] + (360.0 * n[i + 1] - x[i]) / (x[i + 1] - x[i]) * (t[i + 1] - t[i]) for i in idx])
    bad_t = t[~good]; out = []; dropped = 0
    for j in range(1, len(tc)):
        if bad_t.size and np.any((bad_t >= tc[j - 1]) & (bad_t <= tc[j])):
            dropped += 1; continue
        out.append((0.5 * (tc[j] + tc[j - 1]), 1.0 / (tc[j] - tc[j - 1])))
    return np.array(out).reshape(-1, 2), dropped


def gamma_mid(t, f):
    p, cov = np.polyfit(t, np.log(f), 2, cov=True)
    tm = t[np.argmin(np.abs(f - F_MID))]; J = np.array([2 * tm, 1.0, 0.0])
    return float(-(J @ p)), float(np.sqrt(J @ cov @ J))


def jk(fn, n, nb=10):
    e = np.linspace(0, n, nb + 1).astype(int)
    v = np.array([fn(np.r_[0:e[j], e[j + 1]:n]) for j in range(nb)])
    return float(np.sqrt((nb - 1) / nb * np.sum((v - v.mean()) ** 2)))


def hill(t, th, d):
    """Mean detrended w^2 profile (36 bins of physical tracker angle) over turns in BAND."""
    y = d * th; marks = np.arange(np.ceil(y[0] / 360) * 360, y[-1], 10.0)
    tc = np.interp(marks, y, t); seg = np.diff(tc); prof = []
    for i in range(0, len(seg) - NB + 1, NB):
        s = seg[i:i + NB]
        if np.any(s <= 0) or np.any(s > 5) or not (BAND[0] <= 1 / s.sum() <= BAND[1]):
            continue
        ang = (d * marks[i:i + NB] + (5.0 if d > 0 else -5.0)) % 360
        idx = (ang // 10).astype(int); w2 = np.empty(NB); w2[idx] = (np.radians(10.0) / s) ** 2
        tb = np.empty(NB); tb[idx] = np.arange(NB)                       # time order of the bins in this turn
        X = np.column_stack([np.ones(NB), tb - tb.mean()])
        prof.append(w2 - X @ np.linalg.lstsq(X, w2, rcond=None)[0])
    if len(prof) < 5:
        return None
    P = np.array(prof); m = P.mean(0); th_c = np.radians(np.arange(5, 360, 10))
    z = np.sum(m * np.exp(-1j * th_c))
    ph = np.array([np.angle(np.sum(p * np.exp(-1j * th_c))) for p in P])
    ph_err = np.degrees(np.std(np.unwrap(ph), ddof=1) / np.sqrt(len(ph)))
    return dict(n_turns_hill=len(P), depth_J=I / 2 * (m.max() - m.min()), h1_J=I / 2 * 2 * 2 * abs(z) / NB,
                h1_deg=float(np.degrees(np.angle(z))), h1_deg_err=float(ph_err),
                depth_err_J=I / 2 * float(np.std([p.max() - p.min() for p in P], ddof=1) / np.sqrt(len(P))))


def readout(run_dir, name, csv_path=None):
    m = meta(os.path.join(run_dir, f'coast_{name}.txt'))
    if 'coast_end_host' not in m:
        raise SystemExit(f'{name}: coast not finished yet')
    d = int(m.get('dir', 1 if int(name[1:]) % 2 else -1))
    t0, t1 = float(m['field_off_host']) + 5, float(m['coast_end_host']) - 2
    R = read_window(csv_path or tracker_csv(run_dir), t0, t1)
    if len(R) < 1000:
        raise SystemExit(f'{name}: only {len(R)} tracker rows in the coast window')
    k, h, a, r, n = R.T
    t = k / FPS; t = t + np.median(h - t) - t0                          # frame-exact time, seconds from window start
    th = np.degrees(np.unwrap(np.radians(a)))
    tr, dropped = turns(t, th, d, n >= 0.5)
    s = (tr[:, 1] >= BAND[0]) & (tr[:, 1] <= BAND[1])
    out = dict(coast=name, dir=d, f_start=round(float(tr[0, 1]), 4), f_end=round(float(tr[-1, 1]), 4),
               n_turns_band=int(s.sum()), dropped_turns=dropped, ncc_med=round(float(np.median(n)), 3),
               ncc_min=round(float(n.min()), 3), r_px=round(float(np.median(r)), 2))
    if s.sum() >= 15:
        tt, ff = tr[s, 0], tr[s, 1]
        g, ge = gamma_mid(tt, ff)
        out.update(gamma_uHz=round(1e6 * g, 2), gamma_jk_uHz=round(1e6 * jk(lambda i: gamma_mid(tt[i], ff[i])[0], len(tt)), 2),
                   tau_min=round(1 / g / 60, 2))
    hl = hill(t, th, d)
    if hl:
        out.update(depth_J=f"{hl['depth_J']:.4g}", depth_err_J=f"{hl['depth_err_J']:.2g}", h1_J=f"{hl['h1_J']:.4g}",
                   h1_deg=round(hl['h1_deg'], 2), h1_deg_err=round(hl['h1_deg_err'], 3), n_turns_hill=hl['n_turns_hill'])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--run-dir', required=True)
    ap.add_argument('--coast', help='e.g. O07 (default: newest finished coast)')
    ap.add_argument('--note', default='', help='knob positions etc., logged with the line')
    ap.add_argument('--tracker-csv', help='tracker CSV if it is not under <run-dir>/tracker*/ (e.g. a tracker kept running from another run)')
    ap.add_argument('--no-log', action='store_true')
    a = ap.parse_args()
    rd = os.path.expanduser(a.run_dir)
    if a.coast:
        names = [a.coast]
    else:
        done = [os.path.basename(p)[6:-4] for p in glob.glob(os.path.join(rd, 'coast_O*.txt'))
                if 'coast_end_host' in meta(p)]
        if not done:
            raise SystemExit('no finished coast yet')
        names = [sorted(done, key=lambda s: int(s[1:]))[-1]]
    for nm in names:
        o = readout(rd, nm, os.path.expanduser(a.tracker_csv) if a.tracker_csv else None); o['note'] = a.note; o['read_at'] = time.strftime('%H:%M:%S')
        print('  '.join(f'{k}={v}' for k, v in o.items()))
        if not a.no_log:
            p = os.path.join(rd, 'tilt_log.csv'); new = not os.path.exists(p)
            with open(p, 'a') as fh:
                if new:
                    fh.write(','.join(o) + '\n')
                fh.write(','.join(str(v).replace(',', ';') for v in o.values()) + '\n')


if __name__ == '__main__':
    main()
