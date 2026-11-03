#!/usr/bin/env python3
"""Gate W2 (analysis only): do the real amplifier outputs follow the command? Scope traces vs OUT_DQ.

    python3 scope_check.py RUN_DIR [--scope FILE.npz]   # RUN_DIR: command.npz, out_dq.npz, scope_*.npz
    python3 scope_check.py selftest

The scope has no GPS, so its trace is aligned to the front-end record by cross-correlation with OUT_DQ
(the commanded counts, measured at 1024 Hz in W1 to be exact). Per electrode (CH2 = V2, CH3 = V3,
CH4 = V4, Molly 2026-11-03):

  1. AC-coupled amplifier model: the electrode sees  v(t) = G * hp(x(t) - x0),  x = OUT_DQ counts,
     hp = one-pole high-pass with time constant tau (the output coupling; STATUS: tau ~ 5-7 s, estimated).
     Fit G (V/count), tau, a delay and a DC offset by least squares over the whole record. The pedestal
     ramp is the step that measures tau; the AC parts measure G and the delay.
  2. Report G, tau, delay, residual rms (V and % of the AC amplitude), and, for bburst, the delay of each
     electrode's joint burst relative to V2 (pass: within 1 ms).

Pass mark (agreed 2026-11-03: the scope matches the command x gain through the amplifier's response, three
electrodes within 1 ms; numbers proposed by Claude): the model explains the trace to <= 5 % of the AC
amplitude (rms), and the inter-electrode delays are within 1 ms. The gain and tau are measurements, not
pass criteria. Printed, not decided.
"""
import glob
import os
import sys

import numpy as np
from scipy.optimize import least_squares
from scipy.signal import lfilter

ELECTRODES = (2, 3, 4)
SCOPE_CH = {2: 'CH2', 3: 'CH3', 4: 'CH4'}


def highpass(x, fs, tau):
    """One-pole high-pass y' = x' - y/tau, discretised (bilinear)."""
    a = 2 * tau * fs
    b = np.array([a, -a]) / (a + 1)
    den = np.array([1.0, (1 - a) / (a + 1)])
    return lfilter(b, den, x - x[0])


def resample_to(t_src, y_src, t_dst):
    return np.interp(t_dst, t_src, y_src, left=y_src[0], right=y_src[-1])


def coarse_offset(t_dq, ac_dq, t_sc, y_sc, fs_work=200.0):
    """Scope time offset (scope t + off = FE time) from cross-correlating derivatives at fs_work."""
    tg = np.arange(t_dq[0], t_dq[-1], 1 / fs_work)
    a = np.gradient(resample_to(t_dq, ac_dq, tg))
    span = t_sc[-1] - t_sc[0]
    tsg = np.arange(t_sc[0], t_sc[-1], 1 / fs_work)
    b = np.gradient(resample_to(t_sc, y_sc, tsg))
    n = len(a) + len(b)
    nfft = 1 << int(np.ceil(np.log2(n)))
    c = np.fft.irfft(np.fft.rfft(a, nfft) * np.conj(np.fft.rfft(b, nfft)), nfft)
    k = int(np.argmax(np.abs(c)))
    if k > nfft // 2:
        k -= nfft
    return tg[0] - tsg[0] + k / fs_work, span


def fit_channel(t_dq, x_dq, fs_dq, t_sc, y_sc, off0, amp):
    """Fit G, tau, delay, dc: scope(t_sc + off0 + d) = G*hp(x)(t) + dc."""
    def model(p, ts):
        G, tau, d, dc = p
        hp = highpass(x_dq, fs_dq, max(tau, 0.05))
        return G * resample_to(t_dq, hp, ts + off0 + d) + dc

    inside = (t_sc + off0 > t_dq[0] + 0.5) & (t_sc + off0 < t_dq[-1] - 0.5)
    ts, ys = t_sc[inside], y_sc[inside]
    if ts.size > 200000:                       # thin for speed; keep timing resolution < 0.1 ms
        k = ts.size // 200000 + 1
        ts, ys = ts[::k], ys[::k]
    # stage 1: G, tau, dc with no delay; stage 2: delay on a fine grid (G, dc linear at each trial);
    # stage 3: all four together from there
    r1 = least_squares(lambda p: model([p[0], p[1], 0.0, p[2]], ts) - ys, [0.0134, 6.0, 0.0],
                       x_scale=[0.01, 3.0, 1.0], bounds=([-1, 0.05, -100], [1, 600, 100]))
    G, tau, dc = r1.x
    hp = highpass(x_dq, fs_dq, tau)
    ac = np.abs(np.gradient(resample_to(t_dq, hp, ts + off0))) > 1e-3 * np.abs(np.gradient(hp)).max()
    best = None
    for d in np.arange(-0.005, 0.005, 1e-5):
        xm = resample_to(t_dq, hp, ts[ac] + off0 + d)
        A = np.column_stack([xm, np.ones_like(xm)])
        coef, *_ = np.linalg.lstsq(A, ys[ac], rcond=None)
        e = np.sum((A @ coef - ys[ac]) ** 2)
        if best is None or e < best[0]:
            best = (e, d)
    r = least_squares(lambda p: model(p, ts) - ys, [G, tau, best[1], dc], x_scale=[0.01, 3.0, 1e-4, 1.0],
                      diff_step=[1e-6, 1e-6, 1e-3, 1e-6],
                      bounds=([-1, 0.05, best[1] - 2e-4, -100], [1, 600, best[1] + 2e-4, 100]))
    res = model(r.x, ts) - ys
    G, tau, d, dc = r.x
    return dict(G=G, tau=tau, delay=-d, dc=dc,   # delay: + = the electrode lags OUT_DQ
                rms=res.std(), rms_pct=100 * res.std() / abs(G * amp), ts=ts, ys=ys,
                model=model(r.x, ts))


def load(run_dir, scope_file=None):
    cmd = dict(np.load(os.path.join(run_dir, 'command.npz'), allow_pickle=False))
    dq = dict(np.load(os.path.join(run_dir, 'out_dq.npz'), allow_pickle=False))
    if scope_file is None:
        files = sorted(glob.glob(os.path.join(run_dir, 'scope_*.npz')))
        if not files:
            sys.exit(f'no scope_*.npz in {run_dir}')
        scope_file = files[-1]
    sc = dict(np.load(scope_file, allow_pickle=False))
    return cmd, dq, sc


def score(cmd, dq, sc, quiet=False):
    fs = float(dq['fs'])
    amp = float(cmd['amp'])
    t_dq = float(dq['gps0']) + np.arange(np.asarray(dq['V2']).size) / fs
    # coarse alignment on V2: the scope clock is arbitrary
    x2 = np.asarray(dq['V2'], float)
    off0, _ = coarse_offset(t_dq, x2 - x2.mean(), np.asarray(sc['CH2_t'], float), np.asarray(sc['CH2'], float))
    res = {}
    for n in ELECTRODES:
        ch = SCOPE_CH[n]
        if ch not in sc:
            continue
        res[n] = fit_channel(t_dq, np.asarray(dq[f'V{n}'], float), fs, np.asarray(sc[f'{ch}_t'], float),
                             np.asarray(sc[ch], float), off0, amp)
    ok = all(r['rms_pct'] <= 5.0 for r in res.values())
    rel = {n: 1e3 * (res[n]['delay'] - res[2]['delay']) for n in res}
    ok &= all(abs(v) <= 1.0 for v in rel.values())
    if not quiet:
        print(f'{cmd["name"]}: amp {amp:g} counts, scope aligned to the FE record by cross-correlation '
              f'(scope t + {off0:.3f} s)')
        print('  elec   gain V/count   tau s    delay ms   rel V2 ms   residual rms V (% of AC)')
        for n, r in res.items():
            print(f'  V{n}    {r["G"]:.5f}   {r["tau"]:7.2f}   {1e3 * r["delay"]:+8.2f}   {rel[n]:+8.2f}    '
                  f'{r["rms"]:.3f} ({r["rms_pct"]:.1f}%)')
        print(f'  W2 (proposed mark): {"PASS" if ok else "not met"}')
    return ok, res


def selftest():
    rng = np.random.default_rng(5)
    fs = 1024.0
    t = np.arange(int(30 * fs)) / fs
    ped = np.clip((t - 2) / 3, 0, 1) * 1000 - np.clip((t - 25) / 3, 0, 1) * 1000
    dq = dict(gps0=1477800000.0, fs=fs)
    truth = {2: (0.0134, 6.0, 0.0000), 3: (0.0130, 5.5, 0.0004), 4: (0.0136, 6.5, -0.0003)}
    sc = {}
    for k, n in enumerate(ELECTRODES):
        burst = np.zeros_like(t)
        for t0 in (16 + k, 19):
            u = t - t0
            burst += np.where((u >= 0) & (u < 0.1), 500 * np.sin(2 * np.pi * 10 * u), 0)
        x = ped + burst
        dq[f'V{n}'] = x
        G, tau, d = truth[n]
        fsc = 9920.5
        tsc = np.arange(int(26 * fsc)) / fsc - 6.2           # scope time base, arbitrary origin
        t_fe = tsc + 1477800002.7                             # true alignment
        v = G * resample_to(dq['gps0'] + t, highpass(x, fs, tau), t_fe - d) + 0.02
        sc[SCOPE_CH[n]] = v + rng.normal(0, 0.01, v.size)
        sc[SCOPE_CH[n] + '_t'] = tsc
    cmd = dict(name='bburst', amp=500.0)
    ok, res = score(cmd, dq, sc)
    good = ok and all(abs(res[n]['G'] / truth[n][0] - 1) < 0.02 and abs(res[n]['tau'] / truth[n][1] - 1) < 0.05
                      and abs(res[n]['delay'] - truth[n][2]) < 1e-4 for n in ELECTRODES)
    print('SELFTEST', 'PASSED' if good else 'FAILED')
    return 0 if good else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        sys.exit(selftest())
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sf = sys.argv[sys.argv.index('--scope') + 1] if '--scope' in sys.argv else None
    ok, _ = score(*load(sys.argv[1], sf))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
