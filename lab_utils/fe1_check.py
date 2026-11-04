#!/usr/bin/env python3
"""Gate FE1 scorer (analysis only): does the y1rds commutation block point the field where it should, smoothly,
from a KNOWN rotor angle? (fake_rotor.py -> feedback_drive.py frontend -> COMM block -> OUT_DQ, outputs off)

    python3 fe1_check.py TRUTH.csv FEEDBACK_LOG.csv OUT_DQ.npz [--sign -1 --m 8 --amp 5000 --kappa 0.00123]
    python3 fe1_check.py selftest

Inputs: fake_rotor.py truth (host_time, theta_true); the feedback_drive.py frontend log (its
"# loop_start host_time H fe_gps F" line pairs worker2's clock with the front end's, and its `lead` column);
OUT_DQ of V2, V3, V4 as an npz (gps0, fs, V2, V3, V4; awg_waveform_drive.fetch_dq writes this format).

Measured field angle: with the forward matrix, V2 = A cos(psi), V4 = A cos(psi - 120), V3 = A cos(psi - 240)
(stator_osc_drive.py MATRIX_FWD), so psi = atan2((V4 - V3)/sqrt(3), V2 - mean), A = |.|.
Expected: psi_true = sign * m * theta_true + dir * lead, dir = sign of the true velocity.
Clock: t_fe = fe0 + (t_host - h0) * (1 + kappa) + d. kappa = the front-end clock's rate excess (+1.23e-3,
measured on the scope 2026-11-03); d is fitted (it absorbs the ~1 s uncertainty of the clock pairing, so it
is NOT a latency measurement).

Reported, with the pass marks proposed in FEEDBACK_HANDOFF.md (FE1) and here:
  field size        median A vs --amp, within 1 %
  tracking error    |psi_meas - psi_true| at the best d, excluding 0.2 s around each direction flip and
                    times when the true rotor speed is below --vmin (direction undefined at rest):
                    95th percentile < 30 deg
  smoothness        "static" samples (field not moving although the true field moves > 0.5 deg/sample):
                    < 1 %  (the EPICS route held still 15 of every 16 ticks' worth of samples)
                    "jumps" (per-sample change differs from the true change by > 2 deg): < 3 %
                    (one correction per 16 Hz update = 1.6 % of 1024 Hz samples, by design)
Printed, not decided.
"""
import csv
import sys

import numpy as np


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def read_truth(fn):
    rows = list(csv.DictReader(l for l in open(fn) if not l.startswith('#')))
    return np.array([float(r['host_time']) for r in rows]), np.array([float(r['theta_true']) for r in rows])


def read_log(fn):
    h0 = fe0 = None
    rows = []
    for line in open(fn):
        if line.startswith('# loop_start'):
            parts = line.split()
            h0, fe0 = float(parts[3]), float(parts[5])
        elif not line.startswith('#') and not line.startswith('host_time'):
            rows.append(line.strip().split(','))
    t = np.array([float(r[0]) for r in rows])
    lead = np.array([float(r[9]) for r in rows])
    return h0, fe0, t, lead


def field(dq):
    v = {n: np.asarray(dq[f'V{n}'], float) for n in (2, 3, 4)}
    cm = (v[2] + v[3] + v[4]) / 3.0                       # a balanced three-phase set sums to 0: common mode = pedestal
    v = {n: x - cm for n, x in v.items()}
    c, s = v[2], (v[4] - v[3]) / np.sqrt(3)
    return np.degrees(np.arctan2(s, c)), np.hypot(c, s)


def score(t_true, th_true, h0, fe0, t_log, lead_log, dq, sign=-1, m=8, amp=5000.0, kappa=1.23e-3, vmin=5.0,
          quiet=False):
    fs = float(dq['fs'])
    psi_m, A = field(dq)
    t_fe = float(dq['gps0']) + np.arange(psi_m.size) / fs
    on = A > 0.5 * amp                                     # samples where the commutation output is up
    if on.sum() < fs:
        if not quiet:
            print('! less than 1 s of output above half amplitude: nothing to score')
        return False, {}
    # true velocity and direction on the truth grid
    w_true = np.gradient(th_true, t_true)
    d_true = np.where(w_true > vmin, 1.0, np.where(w_true < -vmin, -1.0, np.nan))
    for k in range(1, d_true.size):                        # hysteresis: hold the last direction
        if np.isnan(d_true[k]):
            d_true[k] = d_true[k - 1]
    d_true[np.isnan(d_true)] = 1.0
    flips = t_true[1:][np.diff(d_true) != 0]

    def host_of(tfe, d):
        return h0 + (tfe - fe0 - d) / (1 + kappa)

    def err_at(d, sel):
        th = host_of(t_fe[sel], d)
        inside = (th > t_true[0]) & (th < t_true[-1])
        thv = np.interp(th[inside], t_true, th_true)
        dv = np.interp(th[inside], t_true, d_true)
        dv = np.where(dv >= 0, 1.0, -1.0)
        ld = np.interp(th[inside], t_log, lead_log) if t_log.size else 0.0
        psi_true = sign * m * thv + dv * ld
        e = wrap(psi_m[sel][inside] - psi_true)
        keep = np.abs(np.interp(th[inside], t_true, w_true)) > vmin   # at rest the direction is undefined
        for tf in flips:
            keep &= np.abs(th[inside] - tf) > 0.2
        return e[keep], th[inside][keep], psi_true

    idx = np.where(on)[0]
    sub = idx[::8]
    best = None
    for d in np.arange(-3.0, 3.0, 0.002):
        e, _, _ = err_at(d, sub)
        if e.size < 50:
            continue
        q = np.mean(np.cos(np.radians(e)))
        if best is None or q > best[0]:
            best = (q, d)
    if best is None:
        if not quiet:
            print('! no overlap between the truth and the output')
        return False, {}
    # refine d, and fit the clock-rate excess kappa too (a wrong kappa tilts the error across the run: 0.1e-3 over
    # 100 s is 10 ms, ~35 deg at 1.2 rev/s); kappa grid +-0.8e-3 around the given value
    k0, kbest = kappa, kappa
    for kk in np.arange(k0 - 0.8e-3, k0 + 0.8e-3 + 1e-9, 0.05e-3):
        kappa = kk
        for d in np.arange(best[1] - 0.02, best[1] + 0.02, 0.0005):
            e, _, _ = err_at(d, sub)
            q = np.mean(np.cos(np.radians(e)))
            if q > best[0]:
                best = (q, d); kbest = kk
    kappa = kbest
    for d in np.arange(best[1] - 0.001, best[1] + 0.001, 0.00005):
        e, _, _ = err_at(d, sub)
        q = np.mean(np.cos(np.radians(e)))
        if q > best[0]:
            best = (q, d)
    d = best[1]
    e, th_h, _ = err_at(d, idx)
    p50, p95 = np.percentile(np.abs(e), [50, 95])

    # smoothness on consecutive "on" samples
    th_all = host_of(t_fe[idx], d)
    inside = (th_all > t_true[0]) & (th_all < t_true[-1])
    psi_t = sign * m * np.interp(th_all[inside], t_true, th_true)
    dpm = wrap(np.diff(psi_m[idx][inside]))
    dpt = np.diff(psi_t)
    contig = np.diff(idx[inside]) == 1
    moving = np.abs(dpt) > 0.5
    static = np.mean((np.abs(dpm) < 0.05)[contig & moving]) if np.any(contig & moving) else 0.0
    jumps = np.mean((np.abs(dpm - dpt) > 2.0)[contig])
    a_med = np.median(A[on])
    ok = abs(a_med / amp - 1) <= 0.01 and p95 < 30 and static < 0.01 and jumps < 0.03
    e_first = e[th_h < th_h[0] + 5.0] if e.size else e
    res = dict(d=d, kappa=kappa, p50=p50, p95=p95, static=static, jumps=jumps, A=a_med, n=e.size,
               p95_first5=np.percentile(np.abs(e_first), 95) if e_first.size else np.nan)
    if not quiet:
        print(f'FE1: {e.size} samples scored ({on.sum() / fs:.1f} s of output), {len(flips)} direction flips excluded (+-0.2 s)')
        print(f'  field size       median {a_med:.1f} counts vs amp {amp:g} ({100 * (a_med / amp - 1):+.2f}%)')
        print(f'  tracking error   median {p50:.1f} deg, 95th percentile {p95:.1f} deg  (best clock shift d = {d:+.4f} s, '
              f'clock-rate excess {1e3 * kappa:+.2f} ms/s); first 5 s scored: 95th percentile {res["p95_first5"]:.1f} deg')
        print(f'  smoothness       static {100 * static:.2f}% of moving samples; jumps > 2 deg {100 * jumps:.2f}% of samples')
        print(f'  FE1 (proposed marks): {"PASS" if ok else "not met"}')
    return ok, res


def simulate(kind='profile', staircase=False, seed=0, T=80.0, amp=5000.0, lead=45.0, sign=-1, m=8,
             clock_off=0.37, kappa=1.23e-3, upd_hz=25.0, lat=0.06, noise=0.7, timestamp=False, transport=0.003):
    """Synthetic FE1 run: truth -> tracker noise -> feedback_drive.Controller at 50 fps, sent at upd_hz ->
    EPICS values land on the front end's next 1/16 s tick (+ transport) -> commutation law at 2048 Hz -> OUT_DQ
    at 1024 Hz. Prediction horizon tau:
      timestamp=False  commutate.c as written: time since the value landed + LATENCY (fixed);
      timestamp=True   true age of the frame (what a frame timestamp would give);
      staircase=True   the field held between updates (the EPICS matrix route)."""
    rng = np.random.default_rng(seed)
    import os, types
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fake_rotor
    from feedback_drive import Controller
    a = types.SimpleNamespace(rev_s=0.8, amp_deg=80.0, freq=0.35, theta0=227.0, csv='')
    th_f = fake_rotor.profile_angle(kind, a)
    h0 = 1793750000.0
    t_true = h0 + np.arange(0, T, 0.02)
    th_true = np.array([th_f(t - h0) for t in t_true])
    th_meas = th_true + rng.normal(0, noise, th_true.size)
    ctrl = Controller(lead=lead, sign=sign, m=m, latency=lat)
    upd_t, upd = [], []
    step = int(round(50 / upd_hz))
    for k in range(t_true.size):
        ctrl.update(t_true[k], th_meas[k] % 360.0)
        if k >= 9 and k % step == 0:
            upd_t.append(t_true[k]); upd.append((ctrl.th, ctrl.w, ctrl.a))
    upd_t = np.array(upd_t); upd = np.array(upd)
    fe0 = 1477800000.0
    fe_of = lambda th: fe0 + (th - h0) * (1 + kappa) + clock_off
    fs2 = 2048.0
    t2 = np.arange(fe_of(h0) + 1.0, fe_of(h0 + T) - 0.5, 1 / fs2)
    land = np.ceil((fe_of(upd_t) + transport) * 16) / 16
    j = np.searchsorted(land, t2, side='right') - 1
    ok = j >= 0
    t2, j = t2[ok], j[ok]
    th0, w0, a0 = upd[j, 0], upd[j, 1], upd[j, 2]
    if staircase:
        tau = np.full(t2.size, lat)
    elif timestamp:
        tau = t2 - fe_of(upd_t)[j]
    else:
        tau = (t2 - land[j]) + lat
    w_p = w0 + a0 * tau
    dirv = np.empty(t2.size); dcur = 1.0                   # VMIN hysteresis, as in commutate.c
    for k in range(t2.size):
        if w_p[k] > 6.0:
            dcur = 1.0
        elif w_p[k] < -6.0:
            dcur = -1.0
        dirv[k] = dcur
    psi = sign * m * (th0 + w0 * tau + 0.5 * a0 * tau ** 2) + dirv * lead
    V = {2: amp * np.cos(np.radians(psi)), 4: amp * np.cos(np.radians(psi - 120)), 3: amp * np.cos(np.radians(psi - 240))}
    dq = dict(gps0=t2[0], fs=1024.0)
    for n in (2, 3, 4):
        dq[f'V{n}'] = 6400 + V[n][::2] + rng.normal(0, 0.3, V[n][::2].size)
    return t_true, th_true, h0, fe0, upd_t, np.full(upd_t.size, lead), dq


def selftest():
    """The scorer must pass a well-timed block, and fail both the EPICS staircase and a block whose
    prediction horizon ignores when the frame was taken (commutate.c as of 2026-11-02)."""
    allok = True
    cases = [('profile', dict(timestamp=True), True), ('spin', dict(timestamp=True), True),
             ('profile', dict(staircase=True), False), ('spin', dict(), False)]
    for kind, kw, want in cases:
        label = 'timestamped prediction' if kw.get('timestamp') else ('EPICS staircase' if kw.get('staircase') else
                                                                     'prediction from arrival time (as written)')
        print(f'-- {kind}, {label}: expect {"PASS" if want else "not met"}')
        ok, r = score(*simulate(kind, **kw))
        allok &= (ok == want)
        if kind == 'profile' and want:
            good = abs(r['d'] - 0.37) < 0.01
            print(f'   clock shift recovered ({r["d"]:+.4f} vs +0.37 s): {good}')
            allok &= good
    print('-- front-end clock rate 1.6e-3 in the simulation, scorer started at 1.23e-3: expect PASS (kappa fitted)')
    ok, r = score(*simulate('profile', timestamp=True, kappa=1.6e-3))
    good = ok and abs(r['kappa'] - 1.6e-3) < 0.15e-3
    print(f'   kappa recovered ({1e3 * r["kappa"]:.2f} vs 1.60 ms/s): {good}')
    allok &= good
    print('-- wrong field size (amp 5000 scored as 5200): expect not met')
    ok, _ = score(*simulate('spin', timestamp=True), amp=5200.0)
    allok &= not ok
    print('SELFTEST', 'PASSED' if allok else 'FAILED')
    return 0 if allok else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        sys.exit(selftest())
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    opts = dict(sign=-1.0, m=8.0, amp=5000.0, kappa=1.23e-3, vmin=5.0)
    argv = sys.argv[4:]
    for k in list(opts):
        if f'--{k}' in argv:
            opts[k] = float(argv[argv.index(f'--{k}') + 1])
    t_true, th_true = read_truth(sys.argv[1])
    h0, fe0, t_log, lead_log = read_log(sys.argv[2])
    if h0 is None:
        sys.exit('! no "# loop_start" line in the feedback log')
    dq = dict(np.load(sys.argv[3], allow_pickle=False))
    ok, _ = score(t_true, th_true, h0, fe0, t_log, lead_log, dq, **opts)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
