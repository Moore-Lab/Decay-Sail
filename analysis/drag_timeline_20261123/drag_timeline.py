#!/usr/bin/env python3
"""Drag timeline 2026-09 -> 2026-11: gamma = -dln f/dt in fixed rotor-speed bands, and gamma = a + b/f, per coast / per night.
Analysis only, Mac, reads Dropbox. Rotor f in Hz.
  Sept 13 and Oct 11 coasts: LES_YAW h5, 2f line (rotor f = line/2, ASSUMED divisor 2), 40 s windows, 10 s step (as les_coasts.track).
  Nov: 50 fps tracker per-turn rates (tracker_coasts.turns), window = field off + 5 s .. coast end - 2 s (as coasts.py).
Per band: log f quadratic in t (linear if < 40 pts) evaluated where f crosses the band centre; 10-block jackknife error.
Per night: median over coasts (error sd/sqrt(n)); fit gamma = a + b/f by weighted least squares.
    python3 drag_timeline.py   # -> drag_timeline.json (plot: python3 plot_timeline.py)
"""
import csv, glob, json, os, sys, datetime
import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'overnight_20261114'))
import tracker_coasts as TC   # noqa: E402
import les_scan as LS         # noqa: E402

SP = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup')
BANDS = [(0.33, 0.40), (0.40, 0.47), (0.47, 0.50), (0.50, 0.59), (0.59, 0.73)]   # 0.73 not 0.75: laser-hold plateau at 0.75-0.79 Hz
NMIN = 20


def gamma_band(t, f, lo, hi):
    s = (f >= lo) & (f < hi)
    if s.sum() < NMIN:
        return None
    t, f = t[s], f[s]; fc = 0.5 * (lo + hi)

    def est(tt, ff):
        deg = 2 if len(tt) >= 40 else 1
        p = np.polyfit(tt - tt.mean(), np.log(ff), deg); tm = tt[np.argmin(np.abs(ff - fc))] - tt.mean()
        return -(np.polyval(np.polyder(p), tm))
    g = est(t, f); n = len(t); e = np.linspace(0, n, 11).astype(int)
    v = np.array([est(np.r_[t[:e[j]], t[e[j + 1]:]], np.r_[f[:e[j]], f[e[j + 1]:]]) for j in range(10)])
    jk = np.sqrt(9 / 10 * np.sum((v - v.mean()) ** 2))
    return dict(band=f'{lo:.2f}-{hi:.2f}', f_mean=float(f.mean()), gamma_uHz=1e6 * g, jk_uHz=1e6 * jk, T_s=float(t[-1] - t[0]), n=int(n))


def fit_ab(rows):
    """gamma = a + b/f from rows (f, gamma uHz, err uHz); returns dict or None."""
    r = [x for x in rows if x[2] > 0]
    if len(r) < 2:
        return None
    f, g, e = map(np.array, zip(*r)); A = np.c_[np.ones_like(f), 1 / f] / e[:, None]
    p = np.linalg.lstsq(A, g / e, rcond=None)[0]
    scale = 1.0
    if len(r) > 2:
        chi2 = float(np.sum((A @ p - g / e) ** 2)); scale = max(1.0, np.sqrt(chi2 / (len(r) - 2)))
    cov = np.linalg.inv(A.T @ A) * scale ** 2
    a, b = p; gam = a + b / 0.5
    j = np.array([1, 2.0]); sg = float(np.sqrt(j @ cov @ j))
    return dict(a_uHz=float(a), da=float(np.sqrt(cov[0, 0])), b_uHzHz=float(b), db=float(np.sqrt(cov[1, 1])),
                gamma05_uHz=float(gam), gamma05_err=sg, tau05_min=float(1e6 / gam / 60), tau05_err_min=float(1e6 / gam ** 2 * sg / 60),
                nbands=len(r))


# ---------------------------------------------------------------- LES coasts (Sept/Oct)
def track8(y, seed, t0=0.0, win=40.0, step=10.0, nfft=2 ** 14):
    """y at 8 Hz; returns (t, rotor f = line/2, snr). Seeded at LES line `seed`, then follows +-0.03 Hz."""
    n, s = int(win * 8), int(step * 8); w = signal.windows.hann(n); fr = np.fft.rfftfreq(nfft, 1 / 8)
    prev = seed; out = []
    for i in range(0, len(y) - n + 1, s):
        P = np.abs(np.fft.rfft((y[i:i + n] - y[i:i + n].mean()) * w, nfft)) ** 2
        m = (fr > prev - 0.03) & (fr < prev + 0.03); j = np.flatnonzero(m)[np.argmax(P[m])]
        a, b, c = np.log(P[j - 1:j + 2]); d = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) else 0.0
        fp = fr[j] + d * (fr[1] - fr[0]); prev = fp
        out.append((t0 + (i + n / 2) / 8, fp / 2, P[j] / np.median(P[(fr > 0.3) & (fr < 2.2)])))
    return np.array(out)


def les_coast(rel, t_start_h, t_end_h, seed, name, note):
    g0, y = LS.dec8(rel)
    i0, i1 = int(t_start_h * 3600 * 8), int(t_end_h * 3600 * 8)
    v = track8(y[i0:i1], seed, t0=t_start_h * 3600)
    bad = np.flatnonzero(v[:, 2] <= 30); end = bad[0] if len(bad) else len(v)
    v = v[:end]
    k = np.flatnonzero(v[:, 1] < v[:60, 1].max() * 0.997)[0]      # drop the laser-hold plateau before the coast
    v = v[k:]
    d = datetime.datetime(1980, 1, 6) + datetime.timedelta(seconds=g0 + v[0, 0] - 18)
    res = dict(name=name, source='LES_YAW 2f line (divisor 2 assumed)', date=d.strftime('%Y-%m-%d %H:%M'), note=note,
               f_start=float(v[0, 1]), f_end=float(v[-1, 1]), bands=[])
    for lo, hi in BANDS:
        r = gamma_band(v[:, 0], v[:, 1], lo, hi)
        if r:
            res['bands'].append(r)
    res['fit'] = fit_ab([(b['f_mean'], b['gamma_uHz'], b['jk_uHz']) for b in res['bands']])
    return res


# ---------------------------------------------------------------- tracker coasts (Nov)
def load_csvs(paths):
    K, A, N = [], [], []
    for p in paths:
        cache = os.path.join(HERE, 'plots', 'trk_' + p.split('/spinup/')[1].replace('/', '_') + '.npz')
        if os.path.exists(cache):
            z = np.load(cache); h, a, n, k = z['h'], z['a'], z['n'], z['k']
        else:
            k, h, a, n = [], [], [], []
            with open(p) as fh:
                for r in csv.DictReader(l for l in fh if not l.startswith('#')):
                    try:
                        k.append(int(r['frame'])); h.append(float(r['host_time'])); a.append(float(r['angle_deg'])); n.append(float(r['ncc']))
                    except (ValueError, TypeError, KeyError):
                        continue
            k, h, a, n = map(np.array, (k, h, a, n)); np.savez(cache, k=k, h=h, a=a, n=n)
        off = float(np.median(h - k / TC.FPS)); K.append(k / TC.FPS + off); A.append(a); N.append(n)
    t = np.concatenate(K); a = np.concatenate(A); n = np.concatenate(N); o = np.argsort(t)
    return t[o], a[o], n[o]


def meta(p):
    m = {}
    for line in open(p):
        q = line.split()
        if len(q) >= 2 and q[0] in ('field_off_host', 'coast_end_host'):
            m[q[0]] = float(q[1])
        if len(q) >= 2 and q[0] == 'laser':
            m['laser'] = q[1]
    return m


def night(label, date, csvs, coast_glob):
    t, a, n = load_csvs(csvs)
    out = []; skipped = 0
    for p in sorted(glob.glob(coast_glob)):
        m = meta(p)
        if 'field_off_host' not in m or 'coast_end_host' not in m:
            continue
        t0, t1 = m['field_off_host'] + 5, m['coast_end_host'] - 2
        w = (t >= t0) & (t <= t1)
        if w.sum() < 500:
            skipped += 1; continue
        th = np.degrees(np.unwrap(np.radians(a[w]))); d = 1 if th[-1] > th[0] else -1
        tr = TC.turns(t[w] - t0, th, d, n[w] >= 0.5)
        if len(tr) < 30 or tr[0, 1] < 0.46:       # skip swings / short / coasts starting low
            skipped += 1; continue
        f = tr[:, 1]
        if np.any(np.diff(np.log(f)) > 0.2):
            skipped += 1; continue
        bands = [b for b in (gamma_band(tr[:, 0], f, lo, hi) for lo, hi in BANDS) if b]
        out.append(dict(file=os.path.basename(p), dir=d, laser=m.get('laser'), f0=float(f[0]), bands=bands))
    return dict(name=label, source='tracker per-turn', date=date, n_coasts=len(out), n_skipped=skipped, coasts=out)


def aggregate(nd):
    bands = []
    for lo, hi in BANDS:
        key = f'{lo:.2f}-{hi:.2f}'
        v = [(b['f_mean'], b['gamma_uHz']) for c in nd['coasts'] for b in c['bands'] if b['band'] == key]
        if len(v) >= 3:
            f, g = np.array(v).T
            bands.append(dict(band=key, f_mean=float(np.median(f)), gamma_uHz=float(np.median(g)), mean_uHz=float(g.mean()),
                              jk_uHz=float(g.std(ddof=1) / np.sqrt(len(g))), sd_coast_uHz=float(g.std(ddof=1)), n=len(g)))
    nd['bands'] = bands
    nd['fit'] = fit_ab([(b['f_mean'], b['gamma_uHz'], b['jk_uHz']) for b in bands])
    del nd['coasts']
    return nd


NIGHTS = [
    ('2026-11-12 C1-C6', '2026-11-12', sorted(glob.glob(f'{SP}/2026-11-12/coast/tracker_*/blob_live_gps*.csv')), f'{SP}/2026-11-12/coast/coast_C*.txt'),
    ('2026-11-14/15 overnight', '2026-11-14', [f'{SP}/2026-11-14/overnight/tracker/blob_live_gps1478746563.csv'], f'{SP}/2026-11-14/overnight/series/coast_O*.txt'),
    ('2026-11-16/17 ND4', '2026-11-16', sorted(glob.glob(f'{SP}/2026-11-16/laser/tracker*/blob_live_gps*.csv')), f'{SP}/2026-11-16/laser/night_nd4_il2/coast_O*.txt'),
    ('2026-11-17/18 ND3', '2026-11-17', glob.glob(f'{SP}/2026-11-17/laser/nd3_night/tracker/blob_live_gps*.csv'), f'{SP}/2026-11-17/laser/nd3_night/coast_O*.txt'),
    ('2026-11-18/19 ND2', '2026-11-18', glob.glob(f'{SP}/2026-11-18/laser/nd2_run/tracker/blob_live_gps*.csv'), f'{SP}/2026-11-18/laser/nd2_run/coast_O*.txt'),
    ('2026-11-22 fast 5 min', '2026-11-22', glob.glob(f'{SP}/2026-11-22/fast_5min/tracker/blob_live_gps*.csv'), f'{SP}/2026-11-22/fast_5min/coast_O*.txt'),
]


def damping_1300():
    t, a, n = load_csvs([f'{SP}/2026-11-21/laser/damping_1300/tracker/blob_live_gps1479326928.csv'])
    LASER_OFF = 1795296085.180; BRAKE = 1795297547.785
    w = (t >= LASER_OFF + 60) & (t <= BRAKE - 2)
    tr = TC.turns(t[w] - t[w][0], np.degrees(np.unwrap(np.radians(a[w]))), 1, n[w] >= 0.5)
    res = dict(name='2026-11-21 damping_1300 coast', source='tracker per-turn', date='2026-11-21', bands=[])
    for lo, hi in BANDS:
        r = gamma_band(tr[:, 0], tr[:, 1], lo, hi)
        if r:
            res['bands'].append(r)
    res['fit'] = fit_ab([(b['f_mean'], b['gamma_uHz'], b['jk_uHz']) for b in res['bands']])
    return res


def main():
    out = []
    F = 'LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_'
    out.append(les_coast(F + '1473029300_1473037100.h5', 0.45, 1.45, 0.75, '2026-09-09 coast (laser/drive state not checked)', 'rotor 0.37 -> 0.20 Hz'))
    out.append(les_coast(F + '1473375897_1473435502.h5', 0.00, 2.1, 1.58, '2026-09-13 CCW laser-off coast', 'slide "Spindown: laser off"'))
    out.append(les_coast(F + '1475768725_1475784000.h5', 0.00, 2.0, 1.51, '2026-10-11 CW laser-off coast', 'slide "Spindown: laser off"'))
    for lab, date, csvs, gl in NIGHTS:
        nd = night(lab, date, csvs, gl)
        print(lab, nd['n_coasts'], 'coasts', nd['n_skipped'], 'skipped')
        out.append(aggregate(nd))
    out.append(damping_1300())
    for r in out:
        print(r['name'], r.get('n_coasts', 1), [(b['band'], round(b['gamma_uHz']), round(b['jk_uHz'], 1)) for b in r['bands']],
              {k: round(v, 3) for k, v in (r['fit'] or {}).items()})
    json.dump(out, open(os.path.join(HERE, 'drag_timeline.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
