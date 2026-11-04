"""F3 2026-11-04: the measured field (OUT_DQ) against the tracker, for live 2 and brake-only 1.

    python3 outdq_replay.py

1. Clock, LES: host = fe + off_les, from regressing LES_YAW and LES_PIT on harmonics 1..3 of the tracker
   angle while scanning the offset (LES and OUT_DQ are both front-end DQ channels).
2. OUT_DQ against the commands: the measured field angle matched against the logged writes, scanning the
   lag. OUT_DQ turns out to sit seconds later than LES (see README).
3. Coupling, per constant-field hold (~125 ms): dw - int(trap) dt = int(coupling) dt along the tracked angle,
   coupling = E (c1 cos D + s1 sin D) + E^2 (c2 cos 2D + s2 sin 2D), D = psi_field + 8 theta (+ optional c0 E).
   Fitted on live 2, tested on brake 1, scanning a small extra shift of the field.
4. Open-loop replay of brake 1 with the measured field, from the last free turning point (-0.97 s):
   the rotor model (f3_check.py: joint-fit trap) driven by the measured, AC-coupled field.
Phasor: z = (2/3) sum_n V_n exp(-i phi_n) / 4000, phi = 0 / -120 / -240 for V2 / V4 / V3
(feedback_drive.PHI); the pedestal is common mode and cancels.
"""
import csv
import glob
import math
import sys

import h5py
import numpy as np
from scipy.signal import medfilt, savgol_filter

import os  # noqa: E402
_here = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_here, '..', '..', 'lab_utils'), os.path.join(_here, '..', '..', '..', 'decay_sail_wt_fb', 'lab_utils')):
    if os.path.exists(os.path.join(_p, 'f3_check.py')):   # main after the merge, else the feedback-drive worktree
        sys.path.insert(0, _p); break
import f3_check as f3  # noqa: E402

B = '/Users/mollywatts/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/feedback/f3/'
REST = 229.8
AMP = 4000.0
PHI = {'V2': 0.0, 'V4': -120.0, 'V3': -240.0}
TAU = 5.6


def load(run):
    d = B + run + '/'
    bl = list(csv.DictReader(l for l in open(glob.glob(d + 'blob_live_*.csv')[0]) if not l.startswith('#')))
    tb = np.array([float(r['host_time']) for r in bl])
    ab = np.degrees(np.unwrap(np.radians([float(r['angle_deg']) for r in bl])))
    fn = glob.glob(d + 'feedback_*.csv')[0]
    h0 = fe0 = None
    for line in open(fn):
        if line.startswith('# loop_start'):
            p = line.split(); h0, fe0 = float(p[3]), float(p[5])
    lg = list(csv.DictReader(l for l in open(fn) if not l.startswith('#')))
    lt = np.array([float(r['host_time']) for r in lg]); ps = np.array([float(r['psi_deg']) for r in lg])
    wms = np.array([float(r['write_ms']) for r in lg])
    o = np.load(glob.glob(d + 'out_dq_*.npz')[0])
    fs = float(o['fs']); n = o['V2'].size
    tf = float(o['gps0']) + np.arange(n) / fs
    z = sum(o[k] * np.exp(-1j * np.radians(PHI[k])) for k in PHI) * 2 / 3 / AMP
    les = {}
    for ch in ('YAW', 'PIT'):
        h = h5py.File(sorted(glob.glob(d + f'Y1_RDS-LES_{ch}_IN1_DQ_*.h5'))[0])
        les[ch] = (float(h['segments/gps_start'][0]) + np.arange(h['data'].size) / 1024.0, h['data'][:])
    return dict(tb=tb, ab=ab, h0=h0, fe0=fe0, lt=lt, ps=ps, wms=wms, tf=tf, z=z, les=les)


def les_offset(R, span=(-5, 60), scan=np.arange(-1.5, 1.5001, 0.005)):
    """host = fe + off: best off from LES vs tracker-angle harmonics. Returns off, R^2 curve."""
    nom = R['h0'] - R['fe0']
    tfe, y1 = R['les']['YAW']; _, y2 = R['les']['PIT']
    k = 20                                        # 1024 -> ~51 Hz block means
    m = (tfe.size // k) * k
    tfe = tfe[:m].reshape(-1, k).mean(1); Y = np.column_stack([y1[:m].reshape(-1, k).mean(1), y2[:m].reshape(-1, k).mean(1)])
    sel = (tfe + nom > R['h0'] + span[0]) & (tfe + nom < R['h0'] + span[1])
    tfe, Y = tfe[sel], Y[sel] - Y[sel].mean(0)
    r2 = []
    for d in scan:
        th = np.radians(np.interp(tfe + nom + d, R['tb'], R['ab']))
        X = np.column_stack([np.ones_like(th)] + [g(j * th) for j in (1, 2, 3) for g in (np.cos, np.sin)])
        c, *_ = np.linalg.lstsq(X, Y, rcond=None)
        r2.append(1 - np.sum((Y - X @ c) ** 2) / np.sum(Y ** 2))
    r2 = np.array(r2)
    return nom + scan[np.argmax(r2)], scan, r2


def hp(z, t, tau=TAU):
    """First-order high-pass (the amplifier's AC coupling), on a uniformly sampled complex series."""
    dt = t[1] - t[0]; a = tau / (tau + dt)
    y = np.zeros_like(z); prev = z[0]
    for i in range(1, z.size):
        y[i] = a * (y[i - 1] + z[i] - prev); prev = z[i]
    return y


def replay(R, off, coupling, t_start=-11.0, T=20.0, amp_scale=1.0):
    """Rotor model driven by the measured field from the tracker state at h0 + t_start."""
    th_h = R['tf'] + off
    m = (th_h > R['h0'] + t_start - 30) & (th_h < R['h0'] + t_start + T + 1)
    tz, zz = th_h[m], hp(R['z'][m], th_h[m])
    asm = savgol_filter(medfilt(R['ab'], 5), 21, 3)
    w = savgol_filter(asm, 21, 3, deriv=1, delta=np.median(np.diff(R['tb'])))
    t0 = R['h0'] + t_start
    ph = math.radians(np.interp(t0, R['tb'], asm) - REST); om = math.radians(np.interp(t0, R['tb'], w))
    c0, c1, s1, c2, s2 = coupling
    dt = 1e-3; out_t = []; out_p = []
    for i in range(int(T / dt)):
        t = t0 + i * dt
        zf = np.interp(t, tz, zz.real) + 1j * np.interp(t, tz, zz.imag)
        E = abs(zf); tq = 0.0
        if E > 1e-3:
            D = np.angle(zf) + 8 * (math.radians(REST) + ph)
            tq = amp_scale * E * (c0 + c1 * math.cos(D) + s1 * math.sin(D)) + (amp_scale * E) ** 2 * (c2 * math.cos(2 * D) + s2 * math.sin(2 * D))
        om += (f3.trap_acc(math.degrees(ph)) + tq) * dt
        ph += om * dt
        if i % 20 == 0:
            out_t.append(t - R['h0']); out_p.append(math.degrees(ph))
    return np.array(out_t), np.array(out_p)


def cmd_lag(R, off_les, scan=np.arange(1.0, 5.0, 0.005)):
    """OUT_DQ lag s behind the LES time base: the fraction of field-on samples whose angle equals (5 deg) the last
    or second-to-last logged write within the 0.25 s before, maximised over s."""
    base = R['h0'] - R['fe0'] + off_les - R['h0'] + R['h0']
    k = 16; m = (R['tf'].size // k) * k
    tf = R['tf'][:m].reshape(-1, k).mean(1); z = R['z'][:m].reshape(-1, k).mean(1)
    on = np.abs(z) > 0.5; ang = np.degrees(np.angle(z))
    lon = R['ps'] >= 0; lt = R['lt'][lon]; lp = R['ps'][lon]
    score = []
    for s in scan:
        th = tf[on] + off_les - s
        j = np.searchsorted(lt, th) - 1; jj = np.clip(j, 0, None)
        d1 = np.abs((ang[on] - lp[jj] + 180) % 360 - 180); d2 = np.abs((ang[on] - lp[np.clip(jj - 1, 0, None)] + 180) % 360 - 180)
        score.append(((j >= 0) & (th - lt[jj] < 0.25) & (np.minimum(d1, d2) < 5)).mean())
    score = np.array(score); i = score.argmax()
    return scan[i], score[i], score[np.abs(scan - scan[i]) > 0.1].max()


def landed_fraction(R, off):
    """Of the field-on writes, the fraction whose psi appears (5 deg) in the measured field within 0.3 s."""
    th = R['tf'] + off; ang = np.degrees(np.angle(R['z'])); on = np.abs(R['z']) > 0.5
    n = hit = 0
    for t0, p in zip(R['lt'], R['ps']):
        if p < 0:
            continue
        j0, j1 = np.searchsorted(th, t0), np.searchsorted(th, t0 + 0.3)
        n += 1; hit += np.any(on[j0:j1] & (np.abs((ang[j0:j1] - p + 180) % 360 - 180) < 5))
    return hit / max(n, 1), n


def _w(t, a, tc, h=0.07):
    m = np.abs(t - tc) < h
    if m.sum() < 5:
        return np.nan
    return np.radians(np.polyfit(t[m] - tc, a[m], 2)[1])


def holds(R, off):
    """Rows (t0 - h0, dw - int trap dt, regressors) for each constant-field hold (>60 ms, |z| > 0.5)."""
    th = R['tf'] + off; z = R['z']; on = np.abs(z) > 0.5; ang = np.degrees(np.angle(z))
    t, a = R['tb'], R['ab']; rows = []; i = 0; n = z.size
    while i < n:
        if not on[i]:
            i += 1; continue
        j = i
        while j + 1 < n and on[j + 1] and abs((ang[j + 1] - ang[i] + 180) % 360 - 180) < 3:
            j += 1
        t0, t1 = th[i], th[j]
        if t1 - t0 > 0.06 and t0 > t[0] + 0.2 and t1 < t[-1] - 0.2:
            w0, w1 = _w(t, a, t0), _w(t, a, t1)
            tt = np.arange(t0, t1, 0.002); aa = np.interp(tt, t, a)
            trap = np.sum([f3.trap_acc(p) for p in ((aa - REST + 180) % 360) - 180]) * 0.002
            E = np.abs(z[i:j + 1]).mean(); D = np.angle(z[i:j + 1].mean()) + np.radians(8 * aa)
            reg = [E * D.size, E * np.cos(D).sum(), E * np.sin(D).sum(), E * E * np.cos(2 * D).sum(), E * E * np.sin(2 * D).sum()]
            if np.isfinite(w0) and np.isfinite(w1):
                rows.append((t0 - R['h0'], w1 - w0 - trap, np.array(reg) * 0.002))
        i = j + 1
    return rows


def lstsq_rows(rows, cols):
    Y = np.array([r[1] for r in rows]); X = np.array([r[2] for r in rows])[:, cols]
    c, *_ = np.linalg.lstsq(X, Y, rcond=None)
    return c, 1 - np.var(Y - X @ c) / np.var(Y)


def r2_rows(rows, cols, c):
    Y = np.array([r[1] for r in rows]); X = np.array([r[2] for r in rows])[:, cols]
    return 1 - np.var(Y - X @ c) / np.var(Y)


def main():
    runs = {r: load(r) for r in ('live2', 'brake1')}
    base = {}
    for name, R in runs.items():
        off, scan, r2 = les_offset(R)
        nom = R['h0'] - R['fe0']
        lag, sc, sc2 = cmd_lag(R, off)
        base[name] = off - lag
        lf, nw = landed_fraction(R, base[name] + 0.075)
        print(f'{name}: LES clock: host = fe + nominal {off - nom:+.3f} s (R^2 {r2.max():.3f}, at nominal {r2[np.argmin(np.abs(scan))]:.3f}; '
              f'+-{np.ptp(scan[r2 > r2.max() - 0.01]) / 2:.3f} s)')
        print(f'   OUT_DQ lags the LES time base by {lag:.3f} s (command match {sc:.2f}; best elsewhere {sc2:.2f}); '
              f'{lf:.0%} of {nw} field-on writes appear in the measured field')
    print('per-hold coupling fit, live 2 -> brake 1 (extra shift of the field after command matching):')
    best = None
    for sh in np.arange(-0.05, 0.1501, 0.025):
        tr = holds(runs['live2'], base['live2'] + sh); te = holds(runs['brake1'], base['brake1'] + sh)
        c, r2 = lstsq_rows(tr, [1, 2, 3, 4]); r2t = r2_rows(te, [1, 2, 3, 4], c)
        c5, r25 = lstsq_rows(tr, [0, 1, 2, 3, 4])
        print(f'   shift {sh:+.3f}: live 2 {len(tr)} holds R^2 {r2:.2f}, c {np.round(c, 2).tolist()}; brake 1 {len(te)} holds R^2 {r2t:.2f}; '
              f'with c0: R^2 {r25:.2f}, c0 {c5[0]:+.2f}')
        if best is None or r2 > best[1]:
            best = (sh, r2, c)
    sh, _, c = best
    coup = [0.0] + list(c)
    tr = holds(runs['live2'], base['live2'] + sh)
    Y = np.array([r[1] for r in tr]); X = np.array([r[2] for r in tr])
    c5, *_ = np.linalg.lstsq(X, Y, rcond=None)
    se = np.sqrt(np.diag(np.var(Y - X @ c5) * len(Y) / (len(Y) - 5) * np.linalg.inv(X.T @ X)))
    print(f'best shift {sh:+.3f}; f3_check.COUPLING_HOLD = {np.round(coup, 2).tolist()}; '
          f'with c0: {np.round(c5, 2).tolist()} +- {np.round(se, 2).tolist()}')
    D = np.radians(np.arange(-180, 180, 0.5)); d = np.degrees(D)
    fD = coup[1] * np.cos(D) + coup[2] * np.sin(D) + coup[3] * np.cos(2 * D) + coup[4] * np.sin(2 * D)
    print(f'push angles (E = 1): best + {d[fD.argmax()]:+.0f} ({fD.max():+.2f}), best - {d[fD.argmin()]:+.0f} ({fD.min():+.2f}); '
          f'in use -88: {np.interp(-88, d, fD):+.2f}, +167: {np.interp(167, d, fD):+.2f} rad/s^2')
    Rb = runs['brake1']
    m = (Rb['tb'] > Rb['h0'] - 11) & (Rb['tb'] < Rb['h0'] + 12)
    ab_rel = Rb['ab'] - REST - 360 * np.round((np.median(Rb['ab'][m][:50]) - REST) / 360)
    mm = (Rb['tb'] > Rb['h0'] - 0.5) & (Rb['tb'] < Rb['h0'] + 9)
    print('brake 1 live: turning', f3.swing_extremes(Rb['tb'][mm] - Rb['h0'], ab_rel[mm])[:2],
          'over the top at', np.round(f3.turns(Rb['tb'][mm] - Rb['h0'], ab_rel[mm])[0][:1], 2))
    for lab, cp in (('no field', [0] * 5), ('COUPLING_010 (commanded fit)', f3.COUPLING_010), ('per-hold fit', coup),
                    ('per-hold fit with c0', list(c5))):
        for s2 in ((0.0,) if lab == 'no field' else (-0.025, 0.0, 0.025)):
            for sc in ((1.0,) if lab == 'no field' else (0.8, 1.0, 1.25)):
                t, p = replay(Rb, base['brake1'] + sh + s2, cp, t_start=-0.97, T=10.0, amp_scale=sc)
                tc, dc = f3.turns(t, p); live = np.interp(t, Rb['tb'] - Rb['h0'], ab_rel); w = (t > 0) & (t < 5.5)
                print(f'   replay {lab}, shift {sh + s2:+.3f}, x{sc}: turning {[e for e in f3.swing_extremes(t, p) if e[0] > -0.5][:3]}; '
                      f'over {"none" if not tc.size else f"{dc[0]:+.0f} at {tc[0]:.2f} s"}; rms 0..5.5 s {np.std(live[w] - p[w]):.0f} deg')


if __name__ == '__main__':
    main()
