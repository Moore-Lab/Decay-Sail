#!/usr/bin/env python3
"""Gate B1 (braking plan): the rotor's field-off trap, angular acceleration vs angle over ~145-295 deg. 2026-11-10.

    python3 b1_trap.py            # ~1-2 min; writes trap_b1.json, b1_summary.txt, plots/ (gitignored)

Data (read only):
  detent free swing: ../detent_20261110/rotor_angle_detent.csv, host_time_cam >= 1794356925 (phase C ramp end + ~20 s,
      AC-coupled residue < 3 %, derived) to the end of the video. 50 fps, uniform camera clock.
  S1 free swing:     ../voltage_steps_20261110_s1/rotor/rotor_angle_s1.csv, host_time >= 1794345430 (field off).
  S1 trap:           ../f3_step2_20261110/refit/refit_coeffs.json -> trap_acc_canonical (198-234 deg).
  11-04 trap x TRAP_S: f3_check / f3_step2 via ../f3_step2_20261110/refit/s1data.py (zero aligned at 208.6, s1data convention).

Method (same as the refit): integral fit. The free window is cut into overlapping segments (length SEG_LEN, start step
SEG_STEP). For each, dw = w(t1) - w(t0) (w from a local quadratic, +-0.07 s) = sum_k a_k int hat_k(theta(t)) dt - gamma int w dt,
with a piecewise-linear acceleration on 2 deg nodes and a 2nd-difference penalty. A savgol + 2 deg bin table is also made
for comparison (it smears features the rotor crosses in < the window, see the synthetic test).
Damping is measured from the energy at the turning points, E_k = U(theta_turn), not from the acceleration fit.
"""
import json, math, os, sys
import numpy as np
from scipy.signal import savgol_filter
from scipy.interpolate import CubicSpline

HERE = os.path.dirname(os.path.abspath(__file__))
AN = os.path.dirname(HERE)
PLOTS = os.path.join(HERE, 'plots')
DET = os.path.join(AN, 'detent_20261110', 'rotor_angle_detent.csv')
S1 = os.path.join(AN, 'voltage_steps_20261110_s1', 'rotor', 'rotor_angle_s1.csv')
REFIT = os.path.join(AN, 'f3_step2_20261110', 'refit')
T_FREE = 1794356925.0          # detent free window start (host)
T_S1 = 1794345430.0            # S1 free swing start (host)
NODES = np.arange(142.0, 298.01, 2.0)
PEN = 0.3
SEG_LEN, SEG_STEP = 0.16, 0.02
H_OMEGA = 0.07
VALID = (150.0, 290.0)

out = []
def say(s=''):
    print(s); out.append(s)


# ------------------------------------------------------------------------------------------------ data
def load(path, t_min, col):
    a = np.genfromtxt(path, delimiter=',', names=True, dtype=None, encoding=None)
    t = np.asarray(a[col], float)
    th = np.degrees(np.unwrap(np.radians(np.asarray(a['angle_deg'], float))))
    src = np.asarray(a['source'])
    m = t >= t_min
    t, th, src = t[m], th[m], src[m]
    dt = np.median(np.diff(t))
    tu = np.arange(t[0], t[-1], dt)          # uniform grid (S1 host_time has jitter)
    return tu, np.interp(tu, t, th), dt, (t, th, src)


def omega_at(t, th, tc, h=H_OMEGA):
    """rad/s from a local quadratic over +-h (as refit_coupling.omega_at)."""
    m = np.abs(t - tc) < h
    if m.sum() < 5:
        return np.nan
    return math.radians(np.polyfit(t[m] - tc, th[m], 2)[1])


def hat(theta_deg, nodes=NODES):
    x = np.clip(theta_deg, nodes[0], nodes[-1])
    i = np.clip(np.searchsorted(nodes, x) - 1, 0, len(nodes) - 2)
    f = (x - nodes[i]) / (nodes[i + 1] - nodes[i])
    B = np.zeros((x.size, nodes.size))
    B[np.arange(x.size), i] = 1 - f; B[np.arange(x.size), i + 1] = f
    return B


# ------------------------------------------------------------------------------------------------ integral fit
def segments(t, th, seg_len=SEG_LEN, seg_step=SEG_STEP, nodes=NODES, step=0.002):
    ths = savgol_filter(th, 7, 2)
    dt = t[1] - t[0]
    wsg = savgol_filter(th, 7, 2, deriv=1, delta=dt)
    rows = []
    for u in np.arange(t[0] + 0.1, t[-1] - seg_len - 0.1, seg_step):
        v = u + seg_len
        w0, w1 = omega_at(t, th, u), omega_at(t, th, v)
        if not (np.isfinite(w0) and np.isfinite(w1)):
            continue
        tt = np.arange(u, v, step) + step / 2
        aa = np.interp(tt, t, ths); ww = np.interp(tt, t, wsg)
        H = hat(aa, nodes) * step
        rows.append(dict(t0=u, dw=w1 - w0, hat=H.sum(0), hat_pos=H[ww > 0].sum(0), hat_neg=H[ww <= 0].sum(0),
                         dth=math.radians(aa[-1] - aa[0]) if False else math.radians(np.interp(v, t, ths) - np.interp(u, t, ths))))
    return rows


def penalty(n, ncols, offs=(0,)):
    P = []
    for o in offs:
        for i in range(n - 2):
            r = np.zeros(ncols); r[o + i:o + i + 3] = [1, -2, 1]; P.append(r)
    return np.array(P)


def fit(rows, mode='plain', damping=False, nodes=NODES, pen=PEN):
    """mode 'plain': one table; 'split': separate tables for w>0 / w<0. damping adds -gamma*int w dt."""
    Y = np.array([r['dw'] for r in rows]); n = nodes.size
    if mode == 'plain':
        X = np.array([r['hat'] for r in rows]); offs = (0,)
    else:
        X = np.hstack([np.array([r['hat_pos'] for r in rows]), np.array([r['hat_neg'] for r in rows])]); offs = (0, n)
    if damping:
        X = np.hstack([X, -np.array([[r['dth']] for r in rows])])
    # nodes with no coverage are pinned by the penalty only
    A = np.vstack([X, pen * penalty(n, X.shape[1], offs)]); y = np.concatenate([Y, np.zeros(len(offs) * (n - 2))])
    p, *_ = np.linalg.lstsq(A, y, rcond=None)
    res = Y - X @ p
    # rows overlap (SEG_LEN / SEG_STEP ~ 8x): inflate the naive covariance by that factor
    infl = SEG_LEN / SEG_STEP
    cov = np.var(res) * len(Y) / max(len(Y) - X.shape[1], 1) * np.linalg.pinv(A.T @ A) * infl
    return p, np.sqrt(np.diag(cov)), res, X, Y


def coverage(rows, nodes=NODES):
    return np.array([r['hat'] for r in rows]).sum(0)


# ------------------------------------------------------------------------------------------------ main method: position 2nd differences
LAGS = (3, 5, 8)       # frames
NODE_ERR = 0.3         # rad/s^2, MAIN node uncertainty from the synthetic recovery test (the jackknife misses penalty bias)
PEN2 = 1.0


def rows2(t, th, lags=LAGS, nodes=NODES, step=0.002):
    """theta(t+tau) - 2 theta(t) + theta(t-tau) = int acc(theta(s)) (tau - |s - t|) ds, exactly, for any acc.
    No velocity estimate is needed (the velocity-integral method's local quadratic smears features the rotor crosses in
    < ~0.15 s). Rows are divided by tau^2 (units rad/s^2). The path theta(s) between frames is a cubic spline of the frames.
    Returns Y, X, row centre times, sign of omega at the centre."""
    cs = CubicSpline(t, th)
    dts = t[1] - t[0]
    Y, X, T, S = [], [], [], []
    for m in lags:
        tau = m * dts
        off = np.arange(-tau, tau, step) + step / 2; K = (tau - np.abs(off)) * step
        for i in range(m, len(t) - m):
            Y.append(math.radians(th[i + m] - 2 * th[i] + th[i - m]) / tau ** 2)
            X.append((hat(cs(t[i] + off), nodes) * K[:, None]).sum(0) / tau ** 2)
            T.append(t[i]); S.append(np.sign(th[i + 1] - th[i - 1]))
    return np.array(Y), np.array(X), np.array(T), np.array(S)


def fit2(Y, X, pen=PEN2, nodes=NODES):
    n = X.shape[1]; nb = n // nodes.size
    P = penalty(nodes.size, n, tuple(k * nodes.size for k in range(nb)))
    p, *_ = np.linalg.lstsq(np.vstack([X, pen * P]), np.concatenate([Y, np.zeros(P.shape[0])]), rcond=None)
    return p, Y - X @ p


def jackknife(Y, X, T, nblk=10, pen=PEN2, nodes=NODES):
    """Node errors from delete-one-block jackknife over nblk contiguous time blocks (rows overlap, so naive errors are wrong)."""
    e = np.linspace(T.min(), T.max() + 1e-9, nblk + 1); ps = []
    for k in range(nblk):
        m = ~((T >= e[k]) & (T < e[k + 1]))
        ps.append(fit2(Y[m], X[m], pen, nodes)[0])
    ps = np.array(ps)
    return np.sqrt((nblk - 1) / nblk * np.sum((ps - ps.mean(0)) ** 2, 0))


# ------------------------------------------------------------------------------------------------ savgol + bins
def savgol_table(t, th, win, bw=2.0, lo=140.0, hi=300.0):
    dt = t[1] - t[0]
    acc = np.radians(savgol_filter(th, win, 3, deriv=2, delta=dt))
    edges = np.arange(lo, hi + 0.01, bw); c = (edges[1:] + edges[:-1]) / 2
    ib = np.digitize(th, edges) - 1
    tab = np.array([np.median(acc[ib == k]) if (ib == k).sum() >= 5 else np.nan for k in range(c.size)])
    return c, tab


# ------------------------------------------------------------------------------------------------ simulation, swing stats
def sim(trapf, th0, w0, T, gamma=0.0, dt=1e-3, frame=0.02):
    """f3_check.simulate_measured's integrator (semi-implicit Euler, 1 ms): om += (trap - gamma om) dt; ph += om dt."""
    ph, om = math.radians(th0), w0
    n = int(T / dt); nf = int(round(frame / dt)); ot, oy = [], []
    for i in range(n):
        if i % nf == 0:
            ot.append(i * dt); oy.append(math.degrees(ph))
        om += (trapf(math.degrees(ph)) - gamma * om) * dt
        ph += om * dt
    return np.array(ot), np.array(oy)


def turning_points(t, y, h=0.12):
    """Extrema of a swing: (time, angle, +1 max / -1 min) from a local quadratic at each sign change of the velocity."""
    dt = t[1] - t[0]
    ys = savgol_filter(y, 11, 3) if y.size > 11 else y
    w = np.gradient(ys, dt)
    idx = np.where(np.sign(w[1:]) != np.sign(w[:-1]))[0]
    tp = []
    for i in idx:
        m = np.abs(t - t[i]) < h
        if m.sum() < 7:
            continue
        a, b, c = np.polyfit(t[m] - t[i], y[m], 2)
        if a == 0:
            continue
        tc = -b / (2 * a)
        if abs(tc) > h:
            continue
        kind = -1 if a > 0 else 1
        if tp and tp[-1][2] == kind:      # noise double-crossing: keep the more extreme
            if kind * (c - b * b / (4 * a)) > kind * tp[-1][1]:
                tp[-1] = (t[i] + tc, c - b * b / (4 * a), kind)
            continue
        tp.append((t[i] + tc, c - b * b / (4 * a), kind))
    return np.array(tp)


def swing_summary(tp):
    mx = tp[tp[:, 2] == 1]; mn = tp[tp[:, 2] == -1]
    per = np.concatenate([np.diff(mx[:, 0]), np.diff(mn[:, 0])])
    return dict(period=float(np.mean(per)), period_sd=float(np.std(per)), n_per=int(per.size),
                max_mean=float(mx[:, 1].mean()), min_mean=float(mn[:, 1].mean()),
                max_first=float(mx[0, 1]), max_last=float(mx[-1, 1]), min_first=float(mn[0, 1]), min_last=float(mn[-1, 1]))


def potential(nodes, acc, ref=None):
    """U(theta) = -int acc dtheta (rad^2/s^2), piecewise-linear acc integrated exactly."""
    dthr = np.radians(np.diff(nodes))
    U = np.concatenate([[0.0], -np.cumsum(0.5 * (acc[1:] + acc[:-1]) * dthr)])
    return U - (U.min() if ref is None else np.interp(ref, nodes, U))


def zeros(nodes, acc):
    z = []
    for i in range(nodes.size - 1):
        a0, a1 = acc[i], acc[i + 1]
        if a0 == 0 or a0 * a1 < 0:
            x = nodes[i] - a0 * (nodes[i + 1] - nodes[i]) / (a1 - a0)
            k = -(a1 - a0) / math.radians(nodes[i + 1] - nodes[i])        # rad/s^2 per rad, local slope
            z.append((float(x), float(k), 'stable' if a1 < a0 else 'unstable'))
    return z


def stiffness_at(nodes, acc, x, half=3.0):
    m = (nodes >= x - half - 1e-9) & (nodes <= x + half + 1e-9)
    return float(-np.polyfit(np.radians(nodes[m] - x), acc[m], 1)[0])


# ------------------------------------------------------------------------------------------------ main
def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(PLOTS, exist_ok=True)
    n = NODES.size
    vm = (NODES >= VALID[0]) & (NODES <= VALID[1])

    t, th, dt, (traw, thraw, src) = load(DET, T_FREE, 'host_time_cam')
    say(f'detent free window: host {t[0]:.2f}..{t[-1]:.2f} ({t[-1] - t[0]:.1f} s, {t.size} frames at {1 / dt:.1f} fps), '
        f'angle {th.min():.1f}..{th.max():.1f} deg (measured)')
    bl = src == 'blanked'
    say(f'  blanked tracker frames in window: {bl.sum()} ({100 * bl.mean():.1f} %), angles {thraw[bl].min():.1f}..{thraw[bl].max():.1f} deg')
    noise = float(np.std(th - savgol_filter(th, 9, 3)))
    say(f'  angle noise (frame - savgol 9/3 residual): {noise:.3f} deg rms (measured)')

    # ---- main fit: position second differences
    Y, X, T, S = rows2(t, th)
    acc, res = fit2(Y, X)
    err = jackknife(Y, X, T)
    say(f'MAIN fit (position 2nd differences, lags {LAGS} frames, 2 deg nodes {NODES[0]:.0f}..{NODES[-1]:.0f}, pen {PEN2}): '
        f'{Y.size} rows, residual rms {np.std(res):.3f} rad/s^2, R2 {1 - np.var(res) / np.var(Y):.4f}; '
        f'jackknife node error (10 time blocks) median {np.median(err[vm]):.3f}, max {err[vm].max():.3f} rad/s^2 over {VALID[0]:.0f}-{VALID[1]:.0f}')
    # ---- the refit's velocity-integral method (smooths fast passages; kept as the 'smooth' table)
    rows = segments(t, th)
    acc_v, e_v, res_v, _, Yv = fit(rows)
    say(f'velocity-integral fit (refit method, {SEG_LEN} s segments): residual rms {np.std(res_v):.4f} rad/s; '
        f'rms difference to MAIN over {VALID[0]:.0f}-{VALID[1]:.0f}: {np.sqrt(np.mean((acc_v - acc)[vm] ** 2)):.2f} rad/s^2 (it smooths, see synthetic test)')
    sg = {w: savgol_table(t, th, w) for w in (7, 15)}

    # ---- direction
    Xs = np.hstack([X * (S > 0)[:, None], X * (S < 0)[:, None]])
    psp, _ = fit2(Y, Xs)
    pos, neg = psp[:n], psp[n:]
    dd = (pos - neg)[vm]
    say(f'direction (fit w>0 rows minus w<0 rows) over {VALID[0]:.0f}-{VALID[1]:.0f}: mean {dd.mean():+.3f}, rms {np.sqrt(np.mean(dd ** 2)):.3f}, '
        f'max |.| {np.abs(dd).max():.2f} rad/s^2 at {NODES[vm][np.argmax(np.abs(dd))]:.0f} deg; '
        f'cf. sqrt(2) x node error {np.sqrt(2) * np.median(err[vm]):.2f} (derived)')

    # ---- features
    U = potential(NODES, acc); Uf = lambda x: np.interp(x, NODES, U)
    U_v = potential(NODES, acc_v)
    say(f'zero crossings of acc (equilibria), MAIN table (derived); for each unstable zero, hump height above the higher '
        f'neighbouring minimum (U uncertainty ~{NODE_ERR} rad/s^2 x 4 deg = {NODE_ERR * math.radians(4):.2f} rad^2/s^2):')
    zs = [z for z in zeros(NODES, acc) if VALID[0] <= z[0] <= VALID[1]]
    eq = []
    for j, (x, k, kind) in enumerate(zs):
        kk = stiffness_at(NODES, acc, x)
        e_ = dict(deg=round(x, 1), kind=kind, stiffness_rad_s2=round(kk, 1), U=round(float(Uf(x)), 3))
        extra = ''
        if kind == 'unstable' and 0 < j < len(zs) - 1:
            hgt = float(Uf(x) - max(Uf(zs[j - 1][0]), Uf(zs[j + 1][0])))
            e_['hump_height'] = round(hgt, 3); extra = f'  hump {hgt:.3f}' + (' (at noise level)' if hgt < 2 * NODE_ERR * math.radians(4) else '')
        eq.append(e_)
        say(f'  {x:6.1f} deg  {kind:8s} stiffness {kk:6.1f} rad/s^2' + (f' ({math.sqrt(kk) / 2 / math.pi:.2f} Hz)' if kk > 0 else '')
            + f'  U {Uf(x):.3f}' + extra)
    zv = [z for z in zeros(NODES, acc_v) if VALID[0] <= z[0] <= VALID[1]]
    say('  smooth (velocity-integral) table zeros: ' + ', '.join(f'{x:.1f} {kd} k={stiffness_at(NODES, acc_v, x):.1f}' for x, k, kd in zv))
    tp = turning_points(t, th); ss = swing_summary(tp)
    say(f'measured swing: period {ss["period"]:.4f} +- {ss["period_sd"]:.3f} s ({ss["n_per"]} intervals), '
        f'max {ss["max_first"]:.2f} -> {ss["max_last"]:.2f}, min {ss["min_first"]:.2f} -> {ss["min_last"]:.2f} deg (measured)')
    say(f'potential, MAIN (derived): global min {NODES[np.argmin(U)]:.0f} deg; U(150) {Uf(150):.2f}, U(290) {Uf(290):.2f}; '
        f'U at the first turning points 145.3 / 293.3: {Uf(145.32):.3f} / {Uf(293.30):.3f} rad^2/s^2 (= swing energy per inertia)')
    say(f'  acc at the edges: a(146) {np.interp(146, NODES, acc):+.2f}, a(150) {np.interp(150, NODES, acc):+.2f}, '
        f'a(290) {np.interp(290, NODES, acc):+.2f}, a(292) {np.interp(292, NODES, acc):+.2f} rad/s^2 (restoring at both ends)')
    hump = [(float(NODES[i]), round(float(U[i]), 3)) for i in range(1, n - 1) if vm[i] and U[i] > U[i - 1] and U[i] > U[i + 1]]
    say(f'  interior local maxima of U: {hump}')

    # ---- damping from turning-point energies
    say('damping from turning-point energy E_k = U(theta_turn) (derived):')
    dmp = {}
    for lab, Ut in (('MAIN U', U), ('smooth U', U_v)):
        E_turn = np.interp(tp[:, 1], NODES, Ut)
        for kind, nm in ((1, 'upper'), (-1, 'lower'), (0, 'both')):
            mm = (tp[:, 2] == kind) if kind else np.ones(len(tp), bool)
            sl, ic = np.polyfit(tp[mm, 0] - T_FREE, E_turn[mm], 1)
            r = E_turn[mm] - (sl * (tp[mm, 0] - T_FREE) + ic)
            se = np.std(r) / np.sqrt(np.sum((tp[mm, 0] - tp[mm, 0].mean()) ** 2))
            dmp[(lab, nm)] = (sl, se, ic)
            say(f'  {lab:8s} {nm:5s}: E(t=0) {ic:.3f} rad^2/s^2, dE/dt {sl:+.2e} +- {se:.1e} rad^2/s^3, scatter {np.std(r):.4f}')
        for a_, b_ in ((0, 52), (52, 105)):
            m = (tp[:, 0] - T_FREE >= a_) & (tp[:, 0] - T_FREE < b_)
            say(f'    {lab} dE/dt over {a_}-{b_} s: {np.polyfit(tp[m, 0], E_turn[m], 1)[0]:+.2e}')
    for kind, nm in ((1, 'max'), (-1, 'min')):
        mm = tp[:, 2] == kind
        say(f'  {nm} turning angle drift: {np.polyfit(tp[mm, 0] - T_FREE, tp[mm, 1], 1)[0] * 60:+.2f} deg/min (measured)')
    w2 = np.radians(np.gradient(savgol_filter(th, 9, 3), dt)) ** 2
    sl, se, E0 = dmp[('MAIN U', 'both')]
    gamma = float(-sl / np.mean(w2)); gamma_e = float(se / np.mean(w2))
    sl_v = dmp[('smooth U', 'both')][0]
    say(f'  -> viscous gamma = -dE/dt / <w^2> = {gamma:.2e} +- {gamma_e:.1e} 1/s (stat.; smooth U gives {-sl_v / np.mean(w2):.2e}); '
        f'<w^2> {np.mean(w2):.2f} rad^2/s^2; Q = omega_swing/gamma ~ {2 * math.pi / ss["period"] / gamma:.0f}; '
        f'energy loss {100 * -sl * ss["period"] / E0:.3f} % per cycle')
    say(f'  equivalent acc at peak speed {math.sqrt(w2.max()):.2f} rad/s: {gamma * math.sqrt(w2.max()):.1e} rad/s^2 '
        f'(cf. direction-split noise {np.sqrt(np.mean(dd ** 2)):.2f}: not visible in the acc fit)')

    # ---- validation replay
    def replay(trap_fn, tp, T, gam):
        ts, ys = sim(trap_fn, tp[0, 1], 0.0, T, gam)
        ts = ts + tp[0, 0]
        return ts, ys, turning_points(ts, ys)

    def compare(tp_m, tp_s, lab):
        tp_m = tp_m[(tp_m[:, 0] >= tp_s[0, 0] - 0.01) & (tp_m[:, 0] <= tp_s[-1, 0] + 0.5)]
        sm, sS = swing_summary(tp_m), swing_summary(tp_s)
        mm = tp_m[tp_m[:, 2] == 1]; ms = tp_s[tp_s[:, 2] == 1]
        # pair each measured max with the sim max nearest in time (valid while |drift| < half a period)
        j = np.array([np.argmin(np.abs(ms[:, 0] - x)) for x in mm[:, 0]])
        k = len(mm); drift = ms[j, 0] - mm[:, 0]; mm = mm[:, :]
        r = dict(period_meas=sm['period'], period_sim=sS['period'], period_err_pct=100 * (sS['period'] / sm['period'] - 1),
                 max_meas=sm['max_mean'], max_sim=sS['max_mean'], min_meas=sm['min_mean'], min_sim=sS['min_mean'],
                 max_last_meas=sm['max_last'], max_last_sim=sS['max_last'], min_last_meas=sm['min_last'], min_last_sim=sS['min_last'],
                 p2p_err_pct=100 * ((sS['max_mean'] - sS['min_mean']) / (sm['max_mean'] - sm['min_mean']) - 1),
                 drift_end_s=float(drift[-1]), drift_end_phase_deg=float(360 * drift[-1] / sm['period']), n_cycles=int(k))
        say(f'  {lab}: period {sm["period"]:.4f} meas / {sS["period"]:.4f} sim ({r["period_err_pct"]:+.2f} %); mean turning max '
            f'{sm["max_mean"]:.2f}/{sS["max_mean"]:.2f}, min {sm["min_mean"]:.2f}/{sS["min_mean"]:.2f} deg (p2p {r["p2p_err_pct"]:+.2f} %); '
            f'last max {sm["max_last"]:.2f}/{sS["max_last"]:.2f}, last min {sm["min_last"]:.2f}/{sS["min_last"]:.2f}; '
            f'drift after {k} cycles {drift[-1]:+.3f} s ({r["drift_end_phase_deg"]:+.0f} deg of swing phase; nearest-max pairing, wraps if |period err| x cycles > 1/2)')
        return r, drift, mm[:, 0]

    trapf = lambda x: float(np.interp(x, NODES, acc))
    trapv = lambda x: float(np.interp(x, NODES, acc_v))
    Tfull = t[-1] - tp[0, 0]
    say('validation: trap alone, open loop from the first measured turning point (w = 0), 1 ms semi-implicit Euler (f3_check form):')
    val = {}
    tsd, ysd, tpsd = replay(trapf, tp, Tfull, gamma)
    val['MAIN, gamma'], driftd, tdr = compare(tp, tpsd, f'MAIN trap + gamma {gamma:.2e}  [B1 test]')
    ts0, ys0, tps0 = replay(trapf, tp, Tfull, 0.0)
    val['MAIN, no damping'], drift0, tdr0 = compare(tp, tps0, 'MAIN trap, no damping')
    tsv, ysv, tpsv = replay(trapv, tp, Tfull, gamma)
    val['smooth, gamma'], driftv, tdrv = compare(tp, tpsv, 'smooth (velocity-integral) trap + gamma')
    say(f'  sim range {ysd.min():.1f}..{ysd.max():.1f} deg (data {th.min():.1f}..{th.max():.1f}; nodes {NODES[0]:.0f}..{NODES[-1]:.0f})')
    tm = t[0] + (t[-1] - t[0]) / 2
    for lab, mfit, te in (('fit 1st half -> replay 2nd half', T < tm - 0.2, (tm, t[-1])), ('fit 2nd half -> replay 1st half', T > tm + 0.2, (t[0], tm))):
        ph_, _ = fit2(Y[mfit], X[mfit])
        f_ = lambda x, ph_=ph_: float(np.interp(x, NODES, ph_))
        m = (t >= te[0]) & (t <= te[1])
        tpm = turning_points(t[m], th[m])
        _, _, tps_ = replay(f_, tpm, t[m][-1] - tpm[0, 0], gamma)
        val['hold-out ' + lab], _, _ = compare(tpm, tps_, 'hold-out ' + lab + ', + gamma')

    # ---- comparisons
    cj = json.load(open(os.path.join(REFIT, 'refit_coeffs.json')))
    cn = np.array(cj['trap_nodes_deg']); ca = np.array(cj['trap_acc_canonical']['acc_rad_s2'])
    sys.path.insert(0, REFIT)
    import s1data as sd
    t1, th1, dt1, _ = load(S1, T_S1, 'host_time')
    n1 = np.arange(194.0, 238.01, 2.0)
    Y1, X1, T1, _ = rows2(t1, th1, nodes=n1)
    p1, _ = fit2(Y1, X1, nodes=n1); e1 = jackknife(Y1, X1, T1, nodes=n1)
    g = np.arange(198.0, 234.01, 2.0)
    ours = np.interp(g, NODES, acc)
    say('comparison with S1 over 198-234 deg (rad/s^2; derived):')
    cmp = {}
    for lab, ref in (('S1 canonical (refit HOLD)', np.interp(g, cn, ca)), ('S1 free swing, MAIN method', np.interp(g, n1, p1)),
                     ('S1 canonical vs smooth B1', None)):
        if ref is None:
            d = np.interp(g, NODES, acc_v) - np.interp(g, cn, ca); ref = np.interp(g, cn, ca)
        else:
            d = ours - ref
        cmp[lab] = dict(mean=float(d.mean()), rms=float(np.sqrt(np.mean(d ** 2))), maxabs=float(np.abs(d).max()))
        say(f'  {lab}: B1 - ref mean {d.mean():+.2f}, rms {np.sqrt(np.mean(d ** 2)):.2f}, max |.| {np.abs(d).max():.2f} at {g[np.argmax(np.abs(d))]:.0f}; '
            f'ref rms {np.sqrt(np.mean(ref ** 2)):.2f}; B1 MAIN node error ~{NODE_ERR} (synthetic)')
    d1 = np.interp(g, n1, p1) - np.interp(g, cn, ca)
    say(f'  (check) S1 MAIN-method fit vs S1 canonical: rms {np.sqrt(np.mean(d1 ** 2)):.2f}, S1 node error ~{np.median(e1):.2f}')
    Ub = potential(NODES, acc, ref=208.6); Us1 = potential(cn, ca, ref=208.6)
    say(f'  potential relative to 208.6: U(198) B1 {np.interp(198, NODES, Ub):.3f} / S1 {np.interp(198, cn, Us1):.3f}; '
        f'U(216) {np.interp(216, NODES, Ub):.3f} / {np.interp(216, cn, Us1):.3f}; U(234) {np.interp(234, NODES, Ub):.3f} / {np.interp(234, cn, Us1):.3f} rad^2/s^2')
    say(f'  stiffness at 208.6 +-3 deg: B1 MAIN {stiffness_at(NODES, acc, 208.6):.1f}, B1 smooth {stiffness_at(NODES, acc_v, 208.6):.1f}, '
        f'S1 canonical {stiffness_at(cn, ca, 208.6):.1f} rad/s^2')
    tp1 = turning_points(t1, th1)
    say('S1 free swing (+-17.5 deg about 215.8) replayed open loop, 60 s, no damping (out of sample for B1):')
    s1v = {}
    for lab, f_ in (('B1 MAIN', trapf), ('B1 smooth', trapv), ('S1 canonical', lambda x: float(np.interp(x, cn, ca)))):
        ts_, ys_, tps_ = replay(f_, tp1, 60.0, 0.0)
        s1v[lab], _, _ = compare(tp1, tps_, lab)
        s1v[lab]['_t'], s1v[lab]['_y'] = ts_, ys_
    old = lambda x: sd.trap(np.atleast_1d(x))
    gw = np.arange(150.0, 290.01, 2.0); aw = np.interp(gw, NODES, acc); awv = np.interp(gw, NODES, acc_v)
    say(f'11-04 trap x TRAP_S {sd.S2.TRAP_S:.3f} (zero placed at 208.6, the s1data convention; 11-04 own rest was 229.8) vs B1 over 150-290: '
        f'rms diff to MAIN {np.sqrt(np.mean((aw - old(gw)) ** 2)):.2f}, to smooth {np.sqrt(np.mean((awv - old(gw)) ** 2)):.2f}; '
        f'rms MAIN {np.sqrt(np.mean(aw ** 2)):.2f}, smooth {np.sqrt(np.mean(awv ** 2)):.2f}, old {np.sqrt(np.mean(old(gw) ** 2)):.2f} rad/s^2')
    best = None
    for sh in np.arange(-60, 60.1, 0.5):
        o = old(gw - sh); s_ = float(o @ awv / (o @ o)); r_ = np.sqrt(np.mean((awv - s_ * o) ** 2))
        if best is None or r_ < best[2]:
            best = (sh, s_, r_)
    say(f'  best shift/scale of the old trap onto the smooth B1: shift {best[0]:+.1f} deg, x{best[1]:.2f} on top of TRAP_S, rms {best[2]:.2f}')
    Uo = potential(gw, old(gw))
    say(f'  old trap x TRAP_S: U(150) {np.interp(150, gw, Uo):.2f}, U(290) {np.interp(290, gw, Uo):.2f} (B1 MAIN {Uf(150):.2f}, {Uf(290):.2f})')
    phi = np.arange(-180, 180, 0.25); Uo2 = np.array([sd.S2.TRAP_S * sd.F.trap_U(p) for p in phi])
    say(f'  old trap x TRAP_S barrier {Uo2.max() - Uo2.min():.2f} rad^2/s^2 at abs {(sd.OFF + phi[np.argmax(Uo2)]) % 360:.1f} deg in this alignment '
        f'(reference only: assumed harmonic form, other alignment)')

    # ---- what tracking error would turn S1 canonical into B1 MAIN at full speed (acc_meas ~ acc + delta''(theta) w^2(theta))
    gd = np.arange(198.0, 234.01, 0.5)
    w2b = 2 * (E0 - np.interp(gd, NODES, U))               # w^2 of the big swing at theta (rad^2/s^2)
    dd2 = (np.interp(gd, NODES, acc) - np.interp(gd, cn, ca)) / w2b   # delta'' (rad per rad^2)
    hr = math.radians(gd[1] - gd[0])
    d1_ = np.concatenate([[0], np.cumsum(0.5 * (dd2[1:] + dd2[:-1]) * hr)])
    d0_ = np.concatenate([[0], np.cumsum(0.5 * (d1_[1:] + d1_[:-1]) * hr)])
    d0_ = d0_ - np.polyval(np.polyfit(gd, d0_, 1), gd)       # offset + linear term are not constrained
    say(f'implied tracking error if the B1-S1 difference over 198-234 were a speed-dependent artefact (derived): '
        f'delta(theta) peak-to-peak {np.degrees(np.ptp(d0_)):.3f} deg, rms {np.degrees(np.std(d0_)):.3f} deg '
        f'(1 px at r 23.5 px = {math.degrees(1 / 23.5):.1f} deg, i.e. ~{np.degrees(np.ptp(d0_)) / math.degrees(1 / 23.5):.3f} px p-p); '
        f'w^2 of the big swing there {w2b.min():.1f}-{w2b.max():.1f} vs <={2 * float(np.interp(198.3, cn, Us1)):.2f} rad^2/s^2 in S1')
    art = dict(ptp_deg=float(np.degrees(np.ptp(d0_))), rms_deg=float(np.degrees(np.std(d0_))))

    # ---- amplitude ladder: same-day swings at other amplitudes (steps_detent.csv; measured periods)
    import pandas as pd
    st = pd.read_csv(os.path.join(AN, 'detent_20261110', 'steps_detent.csv'))
    cases = [('detent pre-run (field off)', st.before_centre[0], st.before_amp[0], st.before_period[0])]
    cases += [('detent gap after %s (AC residue, field not off)' % r.step, r.gap_centre, r.gap_amp, r.gap_period) for r in st.itertuples()]
    cases += [('S1 free swing (field off)', 215.8, 17.5, s1v['S1 canonical']['period_meas'])]
    say('amplitude ladder: period of a free swing from (centre - amp) at w = 0, per trap, vs measured (steps_detent.csv; derived):')
    ladder = []
    for lab, c_, a_, P_ in cases:
        row = dict(case=lab, centre=float(c_), amp=float(a_), period_meas=float(P_))
        txt = []
        for nm, q, nn in (('B1 MAIN', acc, NODES), ('B1 smooth', acc_v, NODES), ('S1 canonical', ca, cn)):
            ts_, ys_ = sim(lambda x, q=q, nn=nn: float(np.interp(x, nn, q)), c_ - a_, 0.0, 25.0)
            tq = turning_points(ts_, ys_)
            try:
                sq = swing_summary(tq); row[nm] = round(sq['period'], 3)
                txt.append(f'{nm} {sq["period"]:.3f} ({sq["min_mean"]:.0f}..{sq["max_mean"]:.0f})')
            except (IndexError, ValueError):
                row[nm] = None; txt.append(f'{nm} n/a')
        ladder.append(row)
        say(f'  {lab}: centre {c_:.1f} amp {a_:.1f}, measured {P_:.3f} s | ' + '; '.join(txt))
    say('  (S1 canonical is held flat outside 184-252 deg nodes, so its periods above ~+-20 deg are not meaningful)')

    # ---- synthetic recovery test
    say('synthetic test: simulate the measured swing (+ gamma) through a known trap, add frame noise, refit (derived):')
    rng = np.random.default_rng(1)
    hyb = acc.copy(); mS = (NODES >= 198) & (NODES <= 234); hyb[mS] = np.interp(NODES[mS], cn, ca)
    syn = {}
    for lab, truth in (('truth = MAIN', acc), ('truth = MAIN with S1 canonical in 198-234', hyb)):
        f_ = lambda x, tr=truth: float(np.interp(x, NODES, tr))
        ts_, ys_ = sim(f_, tp[0, 1], 0.0, Tfull, gamma)
        ys_ = ys_ + rng.normal(0, noise, ys_.size); ts_ = ts_ + tp[0, 0]
        Ys_, Xs_, _, _ = rows2(ts_, ys_)
        pf, _ = fit2(Ys_, Xs_)
        pv, *_ = fit(segments(ts_, ys_))
        gg = (NODES >= 196) & (NODES <= 236)
        tz = [round(z[0], 1) for z in zeros(NODES, truth) if 196 <= z[0] <= 240]
        fz = [round(z[0], 1) for z in zeros(NODES, pf) if 196 <= z[0] <= 240]
        vz = [round(z[0], 1) for z in zeros(NODES, pv) if 196 <= z[0] <= 240]
        r1 = {}
        for nm, q in (('truth', truth), ('MAIN refit', pf), ('velocity-integral refit', pv)):
            _, _, tq = replay(lambda x, q=q: float(np.interp(x, NODES, q)), tp1, 60.0, 0.0)
            r1[nm] = swing_summary(tq)
        say(f'  {lab}: MAIN refit err rms {np.sqrt(np.mean((pf - truth)[gg] ** 2)):.2f} (196-236) / {np.sqrt(np.mean((pf - truth)[vm] ** 2)):.2f} (150-290); '
            f'velocity-integral refit {np.sqrt(np.mean((pv - truth)[gg] ** 2)):.2f} / {np.sqrt(np.mean((pv - truth)[vm] ** 2)):.2f} rad/s^2; '
            f'zeros 196-240 truth {tz}, MAIN {fz}, vel-int {vz}; S1-swing replay period truth {r1["truth"]["period"]:.3f}, '
            f'MAIN refit {r1["MAIN refit"]["period"]:.3f}, vel-int {r1["velocity-integral refit"]["period"]:.3f} s '
            f'(min turn {r1["truth"]["min_mean"]:.1f} / {r1["MAIN refit"]["min_mean"]:.1f} / {r1["velocity-integral refit"]["min_mean"]:.1f})')
        syn[lab] = dict(truth=truth, fit=pf, vfit=pv)

    # ---- JSON
    rnd = lambda a, k=4: [round(float(x), k) for x in a]
    clean = lambda d: {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items() if not k.startswith('_')}
    res = {
        'date': '2026-11-10', 'gate': 'B1 (braking plan)', 'script': 'analysis/brake_b1_20261110/b1_trap.py',
        'data': {'detent': 'analysis/detent_20261110/rotor_angle_detent.csv, host_time_cam %.2f..%.2f' % (t[0], t[-1]),
                 's1': 'analysis/voltage_steps_20261110_s1/rotor/rotor_angle_s1.csv, host_time >= %.0f' % T_S1},
        'conventions': {'theta': 'absolute tracked angle, deg (template zero of 11-06; S1 rest 208.6)',
                        'acc': 'field-off angular acceleration, rad/s^2; use np.interp(theta, trap_nodes_deg, acc) (piecewise linear, as fitted)',
                        'potential': 'U = -int acc dtheta (theta in rad), rad^2/s^2 per unit inertia, min = 0',
                        'damping': 'viscous: theta_ddot = acc(theta) - gamma * omega (omega in rad/s)'},
        'trap_nodes_deg': NODES.tolist(),
        'trap_acc_rad_s2': rnd(acc), 'trap_acc_node_err_rad_s2': NODE_ERR, 'trap_acc_jackknife_err_rad_s2 (underestimate)': rnd(err),
        'trap_acc_smooth_rad_s2': rnd(acc_v),
        'recommended_use': 'Both B1 tables reproduce the +-74 deg free swing (period, turning points). Neither is validated below '
                           '~+-30 deg: the same-day pre-run swing (+-1.76 deg about 208.6, field off) has 1.480 s; MAIN gives 0.97 s, '
                           'smooth 2.72 s, S1 canonical 1.49 s. Near rest (198-234, small swings) use the S1 canonical trap. '
                           'The fine structure in MAIN (wells of 40-50 rad/s^2, humps at 248-264) is fitted, not validated.',
        'tables_note': 'trap_acc = MAIN (position 2nd differences; resolves ~2-4 deg structure, synthetic test). trap_acc_smooth = the '
                       'refit velocity-integral method on the same data (smears fine structure at full swing speed). Both pass the B1 '
                       'replay. Over 198-234 neither matches the S1 canonical trap; see README.',
        'potential_rad2_s2': rnd(U), 'potential_smooth_rad2_s2': rnd(U_v),
        'valid_deg': list(VALID), 'data_range_deg': [round(float(th.min()), 1), round(float(th.max()), 1)],
        'outside_valid': 'not measured; np.interp holds the end node flat, which is not physical',
        'equilibria': eq,
        'equilibria_smooth': [dict(deg=round(x, 1), kind=kd, stiffness_rad_s2=round(stiffness_at(NODES, acc_v, x), 1)) for x, k, kd in zv],
        'swing_energy_rad2_s2': round(float(E0), 4),
        'damping': {'gamma_per_s': gamma, 'gamma_err_stat': gamma_e, 'model': 'viscous, from turning-point energy slope / <omega^2>',
                    'dE_dt_rad2_s3': float(sl), 'Q': 2 * math.pi / ss['period'] / gamma},
        'direction_split': {'acc_pos_rad_s2': rnd(pos), 'acc_neg_rad_s2': rnd(neg)},
        'savgol_bins_2deg': {'centres_deg': sg[7][0].tolist(), 'win7': [None if not np.isfinite(x) else round(float(x), 3) for x in sg[7][1]],
                             'win15': [None if not np.isfinite(x) else round(float(x), 3) for x in sg[15][1]]},
        'validation': {k: clean(v) for k, v in val.items()},
        'comparison_s1_198_234': cmp,
        's1_replay': {k: clean(v) for k, v in s1v.items()},
        'amplitude_ladder': ladder,
        'implied_tracking_error_198_234': art,
    }
    json.dump(res, open(os.path.join(HERE, 'trap_b1.json'), 'w'), indent=1)

    # ---- plots
    C = dict(ink='#1f1f1e', mute='#6b6a63', grid='#e4e3dd', b1='#2a78d6', s1='#eb6834', old='#8a8a80', sg='#1baf7a', neg='#c0398b')

    def style(ax):
        ax.grid(color=C['grid'], lw=0.6); ax.axhline(0, color=C['mute'], lw=0.6)
        for s_ in ('top', 'right'):
            ax.spines[s_].set_visible(False)

    def shade(a):
        a.axvspan(NODES[0], VALID[0], color=C['grid'], alpha=0.7, lw=0); a.axvspan(VALID[1], NODES[-1], color=C['grid'], alpha=0.7, lw=0)

    f, ax = plt.subplots(2, 1, figsize=(11, 8.5), sharex=True, gridspec_kw=dict(height_ratios=[3, 2]))
    a = ax[0]
    a.plot(sg[15][0], sg[15][1], '.', color=C['mute'], ms=4, label='savgol 15 fr + 2° bins')
    a.plot(sg[7][0], sg[7][1], '.', color=C['sg'], ms=4, label='savgol 7 fr + 2° bins')
    a.fill_between(NODES, acc - 2 * err, acc + 2 * err, color=C['b1'], alpha=0.2, lw=0)
    a.plot(NODES, acc, color=C['b1'], lw=2, label='B1 MAIN fit, 2° nodes (±2σ jackknife)')
    a.plot(NODES, acc_v, color=C['ink'], lw=1.2, label='B1 smooth (velocity-integral, refit method)')
    m = (cn >= 198) & (cn <= 234)
    a.plot(cn[m], ca[m], color=C['s1'], lw=2, label='S1 canonical trap (198–234)')
    a.plot(gw, old(gw), '--', color=C['old'], lw=1.2, label='11-04 trap × %.3f (zero at 208.6)' % sd.S2.TRAP_S)
    shade(a); style(a); a.set_ylabel('field-off angular acc (rad/s²)'); a.legend(fontsize=8, frameon=False, loc='upper right', ncol=2)
    a.set_title('Rotor trap, field off: detent free swing 145–293° (measured), 2026-11-10', loc='left', fontsize=11)
    a = ax[1]
    a.plot(NODES, pos, color=C['b1'], lw=1.3, label='fit with ω > 0 rows')
    a.plot(NODES, neg, color=C['neg'], lw=1.3, label='fit with ω < 0 rows')
    a.plot(NODES, pos - neg, color=C['ink'], lw=1, label='difference')
    shade(a); style(a); a.set_xlabel('rotor angle (deg)'); a.set_ylabel('acc (rad/s²)'); a.legend(fontsize=8, frameon=False)
    a.set_title('direction check', loc='left', fontsize=10); a.set_xlim(NODES[0], NODES[-1])
    f.tight_layout(); f.savefig(os.path.join(PLOTS, 'b1_trap_acc.png'), dpi=130); plt.close(f)

    f, a = plt.subplots(figsize=(11, 4.5))
    a.plot(NODES, U, color=C['b1'], lw=2, label='B1 MAIN')
    a.plot(NODES, U_v, color=C['ink'], lw=1.2, label='B1 smooth')
    a.plot(cn[m], (Us1 + np.interp(208.6, NODES, U))[m], color=C['s1'], lw=1.5, label='S1 canonical, matched at 208.6')
    a.plot(gw, Uo + np.interp(208.6, NODES, U) - np.interp(208.6, gw, Uo), '--', color=C['old'], lw=1.2, label='11-04 × TRAP_S, matched at 208.6')
    a.axhline(E0, color=C['mute'], lw=1, ls=':', label='swing energy at t = 0')
    for e in eq:
        a.plot([e['deg']], [e['U']], 'o' if e['kind'] == 'stable' else 'x', color=C['ink'], ms=5)
    shade(a); style(a); a.set_xlim(NODES[0], NODES[-1]); a.set_ylim(-0.2, 3.2)
    a.set_xlabel('rotor angle (deg)'); a.set_ylabel('U per inertia (rad²/s²)'); a.legend(fontsize=8, frameon=False, loc='upper center')
    a.set_title('Potential, field off (derived; ○ stable, × unstable zero of the MAIN acc)', loc='left', fontsize=11)
    f.tight_layout(); f.savefig(os.path.join(PLOTS, 'b1_potential.png'), dpi=130); plt.close(f)

    f, ax = plt.subplots(3, 1, figsize=(12, 9.5))
    a = ax[0]
    a.plot(t - T_FREE, th, color=C['ink'], lw=1, label='measured')
    a.plot(tsd - T_FREE, ysd, color=C['b1'], lw=1, alpha=0.8, label='MAIN trap + γ, open loop from first turning point')
    style(a); a.set_ylabel('angle (deg)'); a.legend(fontsize=8, frameon=False, loc='upper right'); a.set_ylim(140, 310)
    a.set_title('B1 validation replay, detent free swing (field off)', loc='left', fontsize=11)
    a = ax[1]
    a.plot(t - T_FREE, th, color=C['ink'], lw=1.4, label='measured'); a.plot(tsd - T_FREE, ysd, color=C['b1'], lw=1.2, label='MAIN + γ')
    a.plot(ts0 - T_FREE, ys0, color=C['neg'], lw=1, alpha=0.8, label='MAIN, no damping')
    a.set_xlim(t[-1] - T_FREE - 13, t[-1] - T_FREE); a.set_ylim(140, 300)
    style(a); a.set_ylabel('angle (deg)'); a.set_title('last 13 s', loc='left', fontsize=10); a.legend(fontsize=8, frameon=False, loc='upper right')
    a = ax[2]
    a.plot(tdr - T_FREE, driftd * 1e3, 'o-', color=C['b1'], ms=3, lw=1, label='MAIN + γ')
    a.plot(tdr0 - T_FREE, drift0 * 1e3, 's-', color=C['neg'], ms=3, lw=1, label='MAIN, no damping')
    a.plot(tdrv - T_FREE, driftv * 1e3, '^-', color=C['ink'], ms=3, lw=1, label='smooth + γ')
    style(a); a.set_xlabel('host − %.0f (s)' % T_FREE); a.set_ylabel('time of k-th max, sim − meas (ms)'); a.legend(fontsize=8, frameon=False)
    f.tight_layout(); f.savefig(os.path.join(PLOTS, 'b1_validation.png'), dpi=130); plt.close(f)

    f, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    a = ax[0]
    a.plot(t1 - tp1[0, 0], th1, color=C['ink'], lw=1.2, label='S1 free swing (measured)')
    for lab, col in (('B1 MAIN', C['b1']), ('B1 smooth', C['mute']), ('S1 canonical', C['s1'])):
        a.plot(s1v[lab]['_t'] - tp1[0, 0], s1v[lab]['_y'], color=col, lw=1, label=lab + ' replay')
    a.set_xlim(0, 20); style(a); a.set_ylim(188, 240); a.set_xlabel('s from first turning point'); a.set_ylabel('angle (deg)')
    a.legend(fontsize=8, frameon=False, loc='lower left'); a.set_title('S1 free swing replayed (out of sample for B1)', loc='left', fontsize=10)
    a = ax[1]
    s_ = syn['truth = MAIN with S1 canonical in 198-234']
    g_ = (NODES >= 180) & (NODES <= 252)
    a.plot(NODES[g_], s_['truth'][g_], color=C['s1'], lw=2.5, alpha=0.6, label='truth (MAIN with S1 spliced in 198–234)')
    a.plot(NODES[g_], s_['fit'][g_], color=C['b1'], lw=1.3, label='MAIN-method refit')
    a.plot(NODES[g_], s_['vfit'][g_], '--', color=C['ink'], lw=1.2, label='velocity-integral refit')
    style(a); a.set_xlabel('rotor angle (deg)'); a.set_ylabel('acc (rad/s²)'); a.legend(fontsize=8, frameon=False)
    a.set_title('synthetic recovery test (simulated ±74° swing + frame noise)', loc='left', fontsize=10)
    f.tight_layout(); f.savefig(os.path.join(PLOTS, 'b1_s1_and_synthetic.png'), dpi=130); plt.close(f)
    say('plots: ' + ', '.join('plots/' + p for p in sorted(os.listdir(PLOTS))))
    open(os.path.join(HERE, 'b1_summary.txt'), 'w').write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
