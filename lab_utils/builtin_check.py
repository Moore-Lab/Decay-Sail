#!/usr/bin/env python3
"""Score the AWG built-in waveform runs (bsine, bchirp, bburst) from OUT_DQ (W1) or scope traces (W2 later).

    python3 builtin_check.py RUN_DIR       # command.npz + out_dq.npz from awg_waveform_drive.py
    python3 builtin_check.py selftest

Model-free where the AWG's conventions are undocumented (sin or cos, sign of `phase`, the exact log-sweep
law): it measures amplitudes, relative phases and lags between the electrodes, and the burst shape.

Electrodes: A, B, C = V2, V4, V3. Commanded electrical lags 0, 120, 240 deg. "forward" = V4 lags V2 by
120 deg and V3 by 240 (the 2026-08-24 field direction); "reversed" = the opposite sign. Either is reported.

Pass mark (agreed 2026-11-03: matches, and the three electrodes within 1 ms; numbers proposed by Claude):
  bsine   amplitudes within 1 % of --amp; relative phases within 0.72 deg of +-120/240 (= 1 ms at 2 Hz)
  bchirp  amplitudes within 1 % at every band from 0.3 to 10 Hz (sweep runs 0.1 -> 12 Hz so 10 Hz is inside it); inter-electrode lag within 1 ms at >= 1 Hz
  bburst  every burst present at its commanded second; the joint burst's lags within 1 ms of V2's
"""
import os
import sys

import numpy as np
from scipy.signal import hilbert

ELECTRODES = (2, 3, 4)
NOMINAL = {2: 0.0, 4: 120.0, 3: 240.0}


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def series(cmd, dq):
    fs = float(dq['fs'])
    x = {n: np.asarray(dq[f'V{n}'], float) for n in ELECTRODES}
    t = float(dq['gps0']) + np.arange(x[2].size) / fs - float(cmd['start_gps'])   # t = 0 at the commanded start
    return t, x, fs


def direction(rel):
    """rel = {n: phase of V_n relative to V2, deg (positive = V_n leads)} -> ('forward'|'reversed', errors)."""
    fwd = {n: wrap(rel[n] + NOMINAL[n]) for n in (3, 4)}
    rev = {n: wrap(rel[n] - NOMINAL[n]) for n in (3, 4)}
    if sum(abs(v) for v in fwd.values()) <= sum(abs(v) for v in rev.values()):
        return 'forward', fwd
    return 'reversed', rev


def check_bsine(cmd, dq, quiet=False, f=2.0):
    t, x, fs = series(cmd, dq)
    amp = float(cmd['amp'])
    m = (t > 1.0) & (t < float(cmd['duration']) - 0.5)
    tt = t[m]
    M = np.column_stack([np.cos(2 * np.pi * f * tt), np.sin(2 * np.pi * f * tt), np.ones_like(tt)])
    res = {}
    for n in ELECTRODES:
        (a, b, c), *_ = np.linalg.lstsq(M, x[n][m], rcond=None)
        r = x[n][m] - M @ [a, b, c]
        res[n] = dict(amp=np.hypot(a, b), ph=np.degrees(np.arctan2(-b, a)), ped=c, resid=100 * r.std() / amp)
    rel = {n: wrap(res[n]['ph'] - res[2]['ph']) for n in (3, 4)}
    d, err = direction(rel)
    ok = all(abs(res[n]['amp'] / amp - 1) <= 0.01 for n in ELECTRODES) and all(abs(e) <= 0.72 for e in err.values())
    if not quiet:
        print(f'bsine {f:g} Hz, amp {amp:g}: direction {d}')
        for n in ELECTRODES:
            e = err.get(n, 0.0)
            print(f'  V{n}: amp {res[n]["amp"]:8.1f} ({100 * (res[n]["amp"] / amp - 1):+.2f}%)  pedestal {res[n]["ped"]:7.1f}  '
                  f'phase vs V2 {rel.get(n, 0.0):+8.2f} deg  error {e:+.2f} deg = lag {-1e3 * e / 360 / f:+.2f} ms  '
                  f'residual {res[n]["resid"]:.2f}%')
        print(f'  W1 (proposed mark): {"PASS" if ok else "not met"}')
    return ok, dict(res=res, rel=rel, direction=d, err=err)


def check_bchirp(cmd, dq, quiet=False, bands=(0.3, 0.5, 1, 2, 5, 10)):
    t, x, fs = series(cmd, dq)
    amp = float(cmd['amp'])
    dur = float(cmd['duration'])
    m = (t > 0.0) & (t < dur)
    an = {n: hilbert(x[n][m] - np.median(x[n][m])) for n in ELECTRODES}
    tt = t[m]
    ph2 = np.unwrap(np.angle(an[2]))
    finst = np.gradient(ph2, tt) / (2 * np.pi)
    k = int(0.25 * fs)
    finst_s = np.convolve(finst, np.ones(k) / k, mode='same')
    rows, ok = [], True
    for fb in bands:
        # window centred where V2's measured frequency crosses fb, >= 4 cycles and >= 0.5 s long;
        # each electrode is fitted to cos/sin of V2's own measured phase (common reference)
        inside = (tt > 1.0) & (tt < dur - 1.0)
        if not np.any(inside & (finst_s >= fb)):
            rows.append((fb, None)); ok = False; continue
        tc = tt[inside & (finst_s >= fb)][0]
        half = max(2.0 / fb, 0.25)
        sel = (tt > tc - half) & (tt < tc + half) & inside
        if sel.sum() < 20:
            rows.append((fb, None)); ok = False; continue
        M = np.column_stack([np.cos(ph2[sel]), np.sin(ph2[sel]), np.ones(sel.sum())])
        row = {}
        for n in ELECTRODES:
            (ca, sa, c0), *_ = np.linalg.lstsq(M, x[n][m][sel], rcond=None)
            row[n] = dict(amp=np.hypot(ca, sa), ph=np.degrees(np.arctan2(-sa, ca)))
        rel = {n: wrap(row[n]['ph'] - row[2]['ph']) for n in (3, 4)}
        d, err = direction(rel)
        row['dir'], row['err_ms'] = d, {n: -1e3 * err[n] / 360 / fb for n in (3, 4)}   # + = later than V2
        good = all(abs(row[n]['amp'] / amp - 1) <= 0.01 for n in ELECTRODES)
        if fb >= 1:
            good &= all(abs(v) <= 1.0 for v in row['err_ms'].values())
        row['good'] = good
        ok &= good
        rows.append((fb, row))
    if not quiet:
        print(f'bchirp, amp {amp:g}: measured sweep {finst_s[(tt > 1)][0]:.3f} -> {finst_s[(tt < dur - 1)][-1]:.2f} Hz')
        print('   band Hz   amp V2/V3/V4 (% of amp)        V3 lag ms   V4 lag ms   direction   (lag vs V2, + = later)')
        for fb, row in rows:
            if row is None:
                print(f'  {fb:6.2f}   (no data at this frequency)'); continue
            a = '/'.join(f'{100 * row[n]["amp"] / amp:.1f}' for n in ELECTRODES)
            print(f'  {fb:6.2f}   {a:28s} {row["err_ms"][3]:+9.3f}   {row["err_ms"][4]:+9.3f}   {row["dir"]}'
                  + ('' if row['good'] else '   <- misses mark'))
        print(f'  W1 (proposed mark): {"PASS" if ok else "not met"}')
    return ok, rows


def check_bburst(cmd, dq, quiet=False, f=10.0):
    t, x, fs = series(cmd, dq)
    amp = float(cmd['amp'])
    plan = {2: (1, 4), 3: (2, 4), 4: (3, 4)}
    shapes = {'sin': lambda u: np.sin(2 * np.pi * f * u), 'cos': lambda u: np.cos(2 * np.pi * f * u)}

    def fit(n, t0):
        sel = (t > t0 - 0.05) & (t < t0 + 0.15)
        tt, y = t[sel], x[n][sel]
        ped = np.median(x[n][(t > t0 - 0.4) & (t < t0 - 0.1)])
        best = None
        for name, fn in shapes.items():
            for lag in np.arange(-0.01, 0.01, 2e-5):
                u = tt - t0 - lag
                g = np.where((u >= 0) & (u < 1 / f), fn(u), 0.0)
                den = g @ g
                if den == 0:
                    continue
                a = (y - ped) @ g / den
                r = y - ped - a * g
                e = r @ r
                if best is None or e < best[0]:
                    best = (e, name, lag, a, np.sqrt(e / y.size))
        return dict(shape=best[1], lag=best[2], amp=best[3], resid=100 * best[4] / amp)

    res = {n: {t0: fit(n, t0) for t0 in plan[n]} for n in ELECTRODES}
    absent = {n: [t0 for t0 in range(1, 5) if t0 not in plan[n]] for n in ELECTRODES}
    leak = {n: max(np.ptp(x[n][(t > t0 - 0.05) & (t < t0 + 0.15)]) for t0 in absent[n]) for n in ELECTRODES}
    joint = {n: res[n][4]['lag'] for n in ELECTRODES}
    ok = all(abs(res[n][t0]['amp'] / amp - 1) <= 0.01 for n in ELECTRODES for t0 in plan[n])
    ok &= all(abs(joint[n] - joint[2]) <= 1e-3 for n in ELECTRODES)
    if not quiet:
        print(f'bburst {f:g} Hz one-cycle bursts, amp {amp:g}')
        for n in ELECTRODES:
            for t0 in plan[n]:
                r = res[n][t0]
                print(f'  V{n} burst at {t0} s: shape {r["shape"]}, amp {r["amp"]:8.1f} ({100 * (r["amp"] / amp - 1):+.2f}%), '
                      f'lag {1e3 * r["lag"]:+.2f} ms, residual {r["resid"]:.2f}%')
            print(f'  V{n} peak-to-peak where no burst was commanded: {leak[n]:.1f} counts')
        print('  joint burst (4 s), lag relative to V2: ' +
              ', '.join(f'V{n} {1e3 * (joint[n] - joint[2]):+.3f} ms' for n in (3, 4)))
        print(f'  W1 (proposed mark): {"PASS" if ok else "not met"}')
    return ok, res


CHECKS = {'bsine': check_bsine, 'bchirp': check_bchirp, 'bburst': check_bburst}


def selftest():
    rng = np.random.default_rng(3)
    fs, amp, ped, start = 1024.0, 500.0, 1000.0, 1477800000.0
    allok = True

    def mk(name, dur, gen):
        t = np.arange(int((dur + 6) * fs)) / fs - 3.0
        dq = dict(gps0=start - 3.0, fs=fs)
        for n in ELECTRODES:
            dq[f'V{n}'] = ped + gen(n, t) + rng.normal(0, 0.5, t.size)
        return dict(name=name, amp=amp, start_gps=start, duration=dur), dq

    lagms = {2: 0.0, 3: 0.3, 4: -0.2}
    # bsine, forward, small lags
    def gs(n, t, f=2.0):
        u = t - lagms[n] / 1e3
        return np.where((u > 0) & (u < 10), amp * np.sin(2 * np.pi * f * u - np.radians(NOMINAL[n])), 0)
    print('-- bsine forward, lags 0.3/-0.2 ms: expect PASS, forward')
    ok, r = check_bsine(*mk('bsine', 10.0, gs)); good = ok and r['direction'] == 'forward'; allok &= good
    print('-- bsine with V3 2 ms late: expect not met')
    lagms[3] = 2.0
    ok, _ = check_bsine(*mk('bsine', 10.0, gs)); allok &= not ok
    lagms[3] = 0.3

    # bchirp: log sweep 0.1 -> 10 Hz over 60 s, reversed direction
    def gc(n, t, f1=0.1, f2=12.0, T=60.0):
        u = t - lagms[n] / 1e3
        k = np.log(f2 / f1) / T
        ph = 2 * np.pi * f1 * (np.exp(k * u) - 1) / k
        return np.where((u > 0) & (u < T), amp * np.sin(ph + np.radians(NOMINAL[n])), 0)
    print('-- bchirp reversed, lags 0.3/-0.2 ms: expect PASS, reversed')
    ok, rows = check_bchirp(*mk('bchirp', 60.0, gc))
    good = ok and all(r is not None and r['dir'] == 'reversed' for _, r in rows); allok &= good
    print('-- bchirp with V4 3 ms late: expect not met')
    lagms[4] = 3.0
    ok, _ = check_bchirp(*mk('bchirp', 60.0, gc)); allok &= not ok
    lagms[4] = -0.2

    plan = {2: (1, 4), 3: (2, 4), 4: (3, 4)}
    def gb(n, t, f=10.0, shape=np.cos):
        out = np.zeros_like(t)
        for t0 in plan[n]:
            u = t - t0 - lagms[n] / 1e3
            out += np.where((u >= 0) & (u < 1 / f), amp * shape(2 * np.pi * f * u), 0)
        return out
    print('-- bburst cos-shaped, lags 0.3/-0.2 ms: expect PASS, shape cos, lags recovered')
    ok, r = check_bburst(*mk('bburst', 6.0, gb))
    good = ok and r[3][4]['shape'] == 'cos' and abs(1e3 * (r[3][4]['lag'] - r[2][4]['lag']) - 0.3) < 0.05
    allok &= good
    print('SELFTEST', 'PASSED' if allok else 'FAILED')
    return 0 if allok else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        sys.exit(selftest())
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = sys.argv[1]
    cmd = dict(np.load(os.path.join(d, 'command.npz'), allow_pickle=False))
    dq = dict(np.load(os.path.join(d, 'out_dq.npz'), allow_pickle=False))
    name = str(cmd['name'])
    ok, _ = CHECKS[name](cmd, dq)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
