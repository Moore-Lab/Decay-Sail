#!/usr/bin/env python3
"""Gate B2 (braking plan): push map, field acceleration of each electrode phase vs rotor angle. 2026-11-10.

    python3 b2_pushmap.py              # ~2-4 min; reads rotor_angle_b2.csv, writes pushmap_b2.json, b2_summary.txt, plots/
    python3 b2_pushmap.py --track      # first re-track the video (needs the decoded frames, see below)

Data (read only, Dropbox):  .../brake/2026-11-10/b2/
  vsteps_1794363701/  writes.csv, out_dq.npz, blocks.csv, plan.csv  (45 pulses, 15 each on V2 = A, V4 = B, V3 = C; 800 counts
                      offset for 0.25 s, offset route, 8 Hz intake grid)
  video/output_basler_gps1478398905.avi + .csv  (FFV1, 50 fps, 16503 frames, 0 dropped)
Tracking: ../detent_20261110/track_detent.py unchanged (centre 117.5, 165.1; template gps1477428272; 360 deg search) on
  frames decoded with  ffmpeg -nostdin -v error -i output_basler_gps1478398905.avi -f rawvideo -pix_fmt gray FRAMES.u8
  -> rotor_angle_b2.csv (time column used: host_time_cam).
Pulse timing: lab_utils/voltage_steps_score.load/score (decay_sail_wt_vs). Every write landed in OUT_DQ; each landing is put on
  the host clock as write_host + (landing_FE - mapped_write_FE). The mapping is re-zeroed so the earliest landing has zero delay,
  so landing_host = true landing - L, with L an unknown constant (latency). The fitted field start relative to landing_host
  (the "delay" d below) therefore measures L + DAC/amp/field delay. ASSUMED: camera host clock = vsteps host clock (same PC).

Method (all fits are linear least squares except the per-pulse trajectory fits):
  1. JOINT fit over the run (t < T_RUN_END): position 2nd differences th(t+tau) - 2 th(t) + th(t-tau) = int a(s) (tau-|s-t|) ds
     (B1 MAIN method, lags LAGS) with a(s) = trap(theta(s)) + sum_k a_k g_k(s); trap piecewise linear on 2 deg nodes,
     2nd-difference penalty; g_k = the pulse's drive shape (V^2: exp(-2 t'/TAU_AC) over the 0.25 s, starting at landing_host + d;
     tail (0.044)^2 ~ 0.2 %, ignored). a_k = mean field acceleration over the pulse. Common d scanned for min chi^2.
  2. TRAP check: the joint-fit trap, B1 MAIN, B1 smooth, S1 canonical replayed against the post-run free swing (field off).
  3. PER-PULSE trajectory fits (theta0, omega0, a_k, d_k) over [t_on - WIN, t_off + WIN] with the joint-fit trap (rk4, 2 ms),
     windows trimmed 0.2 s clear of neighbouring pulses. dw_k = a_k * 0.25 s * <g>. Angle and velocity at mid-pulse from the fit.
  4. NULL TEST: the same per-pulse estimator at fake pulse times in the post-run free swing (field off, outside the joint fit),
     trap from the run only -> per-pulse error = rms of the fake a_k.
  5. PUSH MAP: a_k = P_p cos(m theta - phi_p) + c_p, regressed on the pulse-averaged <cos m theta>, <sin m theta> (the rotor sweeps
     up to ~15 deg during a pulse). m = 4, 8, 16 compared by chi^2 with the null-test error. Also a global variant: the
     harmonic map fitted directly inside the 2nd-difference fit (no per-pulse step).
  6. AC tail systematic (if the push were linear in V): -4.4 % tail exp(-t/TAU_AC) times the push map, refit.
  7. Swing amplitude (turning points) through the run.
"""
import json, math, os, sys, subprocess
import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))
AN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(AN, 'brake_b1_20261110'))
import b1_trap as B1  # noqa: E402  (load, hat, turning_points, swing_summary, sim, penalty)
LU = '/Users/mollywatts/Desktop/VSCode/decay_sail_wt_vs/lab_utils'
sys.path.insert(0, LU)
import voltage_steps_score as VSS  # noqa: E402

DATA = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/brake/2026-11-10/b2')
RUN = os.path.join(DATA, 'vsteps_1794363701')
VID = os.path.join(DATA, 'video', 'output_basler_gps1478398905')
SCRATCH = '/private/tmp/claude-501/-Users-mollywatts/fd37af79-d00b-4dd9-9b6f-ae64bcbeb22b/scratchpad'
ANG = os.path.join(HERE, 'rotor_angle_b2.csv')
PLOTS = os.path.join(HERE, 'plots')
T0 = 1794363700.0
PHASE = {2: 'A', 4: 'B', 3: 'C'}
COL = {'A': '#1f77b4', 'B': '#d62728', 'C': '#2ca02c'}
PULSE = 0.25
TAU_AC = 5.57
TAIL = 1 - math.exp(-PULSE / TAU_AC)          # 0.0439: reversed step at switch-off (derived, AC coupling)
NODES = np.arange(184.0, 242.01, 2.0)
LAGS = (3, 5, 8, 12, 20)
PEN = 1.0
T_RUN_END = 1794363916.0 + 6.0                # last write + 6 s
T_FREE = 1794363916.0 + 20.0                  # post-run free swing (tail < 3 %)
WIN = 1.5
SEED = 2026

out = []
def say(s=''):
    print(s); out.append(s)


# ------------------------------------------------------------------------------------------------ data
def track():
    fr = os.path.join(SCRATCH, 'b2_frames.u8')
    if not os.path.exists(fr):
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', VID + '.avi', '-f', 'rawvideo', '-pix_fmt', 'gray', fr], check=True)
    subprocess.run([sys.executable, os.path.join(AN, 'detent_20261110', 'track_detent.py'), fr, VID + '.csv', ANG], check=True)


def pulses():
    R = VSS.load(RUN); res = VSS.score(R)
    W = R['W']
    on = [w for w in W if w['v'] != 0]; off = [w for w in W if w['v'] == 0]
    P = []
    for a, b in zip(on, off):
        assert a['chan'] == b['chan'] and b['h'] > a['h']
        P.append(dict(chan=a['chan'], phase=PHASE[a['chan']], write_on=a['h'], write_off=b['h'],
                      land_on=a['h'] + (a['land'] - a['m']), land_off=b['h'] + (b['land'] - b['m']),
                      rel_delay_ms=1e3 * (a['land'] - a['m'])))
    return P, res['M']


def gshape(t, t0, dur=PULSE, power=2):
    """Drive shape at the electrode (AC coupled): (V/V0)^power over the pulse, 0 outside (tail ignored)."""
    x = t - t0
    return np.where((x >= 0) & (x < dur), np.exp(-power * np.clip(x, 0, None) / TAU_AC), 0.0)


def tailshape(t, t1):
    """Linear-in-V tail after switch-off (normalised to V0): -TAIL exp(-(t - t1)/TAU_AC)."""
    x = t - t1
    return np.where(x >= 0, -TAIL * np.exp(-np.clip(x, 0, None) / TAU_AC), 0.0)


# ------------------------------------------------------------------------------------------------ 2nd-difference design
class SecondDiff:
    """Rows th(t_i+tau) - 2 th(t_i) + th(t_i-tau) (rad) / tau^2 and their kernel integrals of any function of time."""
    def __init__(self, t, th, lags=LAGS, mask=None, step=0.01):
        self.cs = CubicSpline(t, th)
        dts = t[1] - t[0]
        Y, C, K, TAU = [], [], [], []
        for m in lags:
            tau = m * dts
            for i in range(m, len(t) - m):
                if mask is not None and not mask[i - m:i + m + 1].all():
                    continue
                Y.append(math.radians(th[i + m] - 2 * th[i] + th[i - m]) / tau ** 2); C.append(t[i]); TAU.append(tau)
        self.Y, self.tc, self.tau = np.array(Y), np.array(C), np.array(TAU)
        self.step = step
        self.u = np.arange(-1.0, 1.0, step) + step / 2        # kernel abscissa in units of tau

    def _quad(self, fn):
        """X[:, j] = int fn(s)[j] (tau - |s - t|) ds / tau^2 for each row (fn returns (n, ncol))."""
        cols = None
        for uk in self.u:
            s = self.tc + uk * self.tau
            w = (1 - abs(uk)) * self.step                       # (tau - |s-t|) ds / tau^2 with ds = tau*step
            f = fn(s)
            cols = f * w if cols is None else cols + f * w
        return cols

    def trap_cols(self, nodes=NODES):
        return self._quad(lambda s: B1.hat(self.cs(s), nodes))

    def local(self, t_lo, t_hi, fn):
        """Columns of a function fn(s, theta_deg(s)) -> (n, ncol) that vanishes outside [t_lo, t_hi]: only rows that see it."""
        k = np.nonzero((self.tc + self.tau > t_lo) & (self.tc - self.tau < t_hi))[0]
        cols = None
        for uk in self.u:
            s = self.tc[k] + uk * self.tau[k]
            f = fn(s, self.cs(s)) * ((1 - abs(uk)) * self.step)
            cols = f if cols is None else cols + f
        return k, cols

    def pulse_cols(self, starts, power=2):
        X = np.zeros((self.Y.size, len(starts)))
        for j, t0 in enumerate(starts):
            k, c = self.local(t0, t0 + PULSE, lambda s, x, t0=t0: gshape(s, t0, power=power)[:, None])
            X[k, j] = c[:, 0]
        return X

    def harm_cols(self, starts_by_phase, m):
        X = np.zeros((self.Y.size, 3 * len(starts_by_phase)))
        for q, starts in enumerate(starts_by_phase):
            for t0 in starts:
                def fn(s, x, t0=t0):
                    g = gshape(s, t0); r = np.radians(x)
                    return np.column_stack([g * np.cos(m * r), g * np.sin(m * r), g])
                k, c = self.local(t0, t0 + PULSE, fn)
                X[k, 3 * q:3 * q + 3] += c
        return X


def lsq(X, Y, ntrap, pen=PEN, nodes=NODES):
    P = B1.penalty(nodes.size, X.shape[1], (0,)) if ntrap else np.zeros((0, X.shape[1]))
    A = np.vstack([X, pen * P]); y = np.concatenate([Y, np.zeros(P.shape[0])])
    p, *_ = np.linalg.lstsq(A, y, rcond=None)
    r = Y - X @ p
    return p, r


# ------------------------------------------------------------------------------------------------ trajectory
def rk4(trapf, th0, w0, t0, tt, field, dt=0.004):
    """Integrate th'' = trap(th) + field(t) from (th0 [rad], w0) at t0, both directions; return th(tt) rad, w(tt)."""
    def run(t_end):
        n = max(int(math.ceil(abs(t_end - t0) / dt)), 1); h = (t_end - t0) / n
        T = t0 + h * np.arange(n + 1); X = np.empty(n + 1); V = np.empty(n + 1)
        x, v = th0, w0; X[0], V[0] = x, v
        f = lambda tt_, xx: trapf(xx) + field(tt_)
        for i in range(n):
            t_ = T[i]
            k1x, k1v = v, f(t_, x)
            k2x, k2v = v + 0.5 * h * k1v, f(t_ + 0.5 * h, x + 0.5 * h * k1x)
            k3x, k3v = v + 0.5 * h * k2v, f(t_ + 0.5 * h, x + 0.5 * h * k2x)
            k4x, k4v = v + h * k3v, f(t_ + h, x + h * k3x)
            x += h / 6 * (k1x + 2 * k2x + 2 * k3x + k4x); v += h / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)
            X[i + 1], V[i + 1] = x, v
        return T, X, V
    Tf, Xf, Vf = run(tt.max()); Tb, Xb, Vb = run(tt.min())
    T = np.concatenate([Tb[::-1], Tf[1:]]); X = np.concatenate([Xb[::-1], Xf[1:]]); V = np.concatenate([Vb[::-1], Vf[1:]])
    return np.interp(tt, T, X), np.interp(tt, T, V)


def make_trapf(nodes, acc):
    nr = np.radians(nodes)
    return lambda x: float(np.interp(x, nr, acc))


def pulse_fit(t, th, trapf, t_on, lo, hi, fix_d=None, d0=0.0, extra=None):
    """Fit (th_mid, w_mid, a, d) to th over [lo, hi]; field a*g(t - t_on - d) (+ extra(t), known). th in deg."""
    m = (t >= lo) & (t <= hi)
    tt, yy = t[m], np.radians(th[m])
    tm = t_on + PULSE / 2
    if extra is not None:
        eg = np.arange(lo - 0.05, hi + 0.05, 0.002); ev = extra(eg)
        ex = lambda s: float(np.interp(s, eg, ev))
    else:
        ex = lambda s: 0.0

    def model(p):
        d = fix_d if fix_d is not None else p[3]
        ts = t_on + d; a_ = p[2]
        def fld(s):
            x = s - ts
            return (a_ * math.exp(-2 * x / TAU_AC) if 0 <= x < PULSE else 0.0) + ex(s)
        x, _ = rk4(trapf, p[0], p[1], tm, tt, fld)
        return x

    i = np.argmin(np.abs(tt - tm))
    w0 = (yy[min(i + 3, len(yy) - 1)] - yy[max(i - 3, 0)]) / (tt[min(i + 3, len(yy) - 1)] - tt[max(i - 3, 0)])
    p0 = [yy[i], w0, 0.0] + ([] if fix_d is not None else [d0])
    bounds = ([-np.inf, -np.inf, -5, ] + ([] if fix_d is not None else [-0.25]),
              [np.inf, np.inf, 5] + ([] if fix_d is not None else [0.4]))
    r = least_squares(lambda p: model(p) - yy, p0, bounds=bounds, x_scale=[0.01, 0.01, 0.1] + ([] if fix_d is not None else [0.05]),
                      diff_step=1e-4)
    J = r.jac; s2 = np.sum(r.fun ** 2) / max(len(yy) - len(p0), 1)
    try:
        cov = np.linalg.inv(J.T @ J) * s2
        err = np.sqrt(np.diag(cov))
    except np.linalg.LinAlgError:
        err = np.full(len(p0), np.nan)
    p = r.x
    return dict(th_mid=math.degrees(p[0]), w_mid=p[1], a=p[2], d=(fix_d if fix_d is not None else p[3]),
                a_err_fit=err[2], d_err_fit=(np.nan if fix_d is not None else err[3]),
                rms_deg=math.degrees(np.sqrt(np.mean(r.fun ** 2))), n=len(yy), tt=tt, resid=r.fun, model=model, p=p)


def windows(P, i, win=WIN, clear=0.2):
    t_on = P[i]['land_on']; t_off = P[i]['land_off']
    lo = t_on - win; hi = t_off + win
    if i > 0:
        lo = max(lo, P[i - 1]['land_off'] + 0.3 + clear)
    if i < len(P) - 1:
        hi = min(hi, P[i + 1]['land_on'] - clear)
    return lo, hi


# ------------------------------------------------------------------------------------------------ push map
def harm_basis(cs, P, d, m):
    """Pulse-averaged <cos m th>, <sin m th> (weighted by the drive shape) for each pulse."""
    C, S = [], []
    for p in P:
        s = p['land_on'] + d + np.linspace(0, PULSE, 51)
        g = gshape(s, p['land_on'] + d - 1e-9); x = np.radians(cs(s))
        C.append(np.sum(g * np.cos(m * x)) / g.sum()); S.append(np.sum(g * np.sin(m * x)) / g.sum())
    return np.array(C), np.array(S)


def fit_map(a, err, C, S, ph, shared_P=False):
    """Per phase: a = A cos + B sin + c. shared_P: one amplitude P and const for all phases, three phases phi (nonlinear)."""
    phases = ['A', 'B', 'C']
    if not shared_P:
        res = {}; chi2 = 0; npar = 0
        for q in phases:
            k = ph == q
            X = np.column_stack([C[k], S[k], np.ones(k.sum())]) / err[k, None]
            y = a[k] / err[k]
            c, *_ = np.linalg.lstsq(X, y, rcond=None)
            cov = np.linalg.inv(X.T @ X)
            r = y - X @ c; chi2 += float(r @ r); npar += 3
            Pm = math.hypot(c[0], c[1]); phi = math.atan2(c[1], c[0])
            # error propagation
            JP = np.array([c[0] / Pm, c[1] / Pm, 0]); Jf = np.array([-c[1] / Pm ** 2, c[0] / Pm ** 2, 0])
            res[q] = dict(P=Pm, P_err=float(np.sqrt(JP @ cov @ JP)), phi_deg=math.degrees(phi) % 360,
                          phi_err_deg=math.degrees(float(np.sqrt(Jf @ cov @ Jf))), const=float(c[2]),
                          const_err=float(np.sqrt(cov[2, 2])), chi2=float(r @ r), n=int(k.sum()))
        return res, chi2, npar
    idx = np.array([phases.index(q) for q in ph])

    def f(p):
        Pm, c0 = p[0], p[1]; phi = p[2:5][idx]
        return (Pm * (C * np.cos(phi) + S * np.sin(phi)) + c0 - a) / err
    best = None
    for start in np.linspace(0, 2 * np.pi, 8, endpoint=False):
        r = least_squares(f, [0.2, 0.0, start, start + 2.1, start + 4.2])
        if best is None or r.cost < best.cost:
            best = r
    p = best.x
    if p[0] < 0:
        p = p.copy(); p[0] = -p[0]; p[2:5] += np.pi
    return dict(P=float(p[0]), const=float(p[1]), phi_deg={q: math.degrees(p[2 + j]) % 360 for j, q in enumerate(phases)}), \
        float(2 * best.cost), 5


# ------------------------------------------------------------------------------------------------ main
def main():
    if '--track' in sys.argv:
        track()
    os.makedirs(PLOTS, exist_ok=True)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt

    t, th, dts, (traw, thraw, src) = B1.load(ANG, 0, 'host_time_cam')
    say('# Gate B2 push map, 2026-11-10 (b2_pushmap.py)')
    say(f'video: {len(traw)} frames, host {traw[0]:.2f}..{traw[-1]:.2f}, angle {thraw.min():.1f}..{thraw.max():.1f} deg, '
        f'{(src == "blanked").sum()} blanked-source frames (kept, as B1)')
    P, M = pulses()
    say(f'pulses: {len(P)} ({sum(p["phase"] == "A" for p in P)} A / {sum(p["phase"] == "B" for p in P)} B / '
        f'{sum(p["phase"] == "C" for p in P)} C); all 90 writes landed; landing durations '
        f'{min(p["land_off"] - p["land_on"] for p in P):.4f}..{max(p["land_off"] - p["land_on"] for p in P):.4f} s (measured, OUT_DQ)')
    rel = np.array([p['rel_delay_ms'] for p in P])
    say(f'write -> landing relative delay: {rel.min():.0f}..{rel.max():.0f} ms (zero = earliest; host->FE drift fitted {1e3 * (M["b"] - 1):+.3f} ms/s)')
    ph = np.array([p['phase'] for p in P])
    cs = CubicSpline(t, th)

    # ---------------- 1. joint 2nd-difference fit over the run, common delay scan
    run_mask = t < T_RUN_END
    SD = SecondDiff(t[run_mask], th[run_mask])
    Xt = SD.trap_cols()
    def pulse_cols(d, power=2):
        return SD.pulse_cols([p['land_on'] + d for p in P], power)
    scan = np.arange(-0.10, 0.301, 0.01); chi = []
    for d in scan:
        X = np.hstack([Xt, pulse_cols(d)]); _, r = lsq(X, SD.Y, True); chi.append(float(r @ r))
    chi = np.array(chi); j = int(np.argmin(chi))
    # parabola refine
    jj = slice(max(j - 3, 0), min(j + 4, len(scan)))
    cq = np.polyfit(scan[jj], chi[jj], 2); d_best = float(-cq[1] / (2 * cq[0])) if cq[0] > 0 else float(scan[j])
    X = np.hstack([Xt, pulse_cols(d_best)]); p_joint, r_joint = lsq(X, SD.Y, True)
    trap_run = p_joint[:NODES.size]; a_joint = p_joint[NODES.size:]
    # delay curvature -> rough error: rows overlap and are correlated, so use a block bootstrap on the pulses instead
    say(''); say('## 1. Joint fit (trap + 45 pulse accelerations), run data')
    say(f'common delay d (field start - landing_host): best {1e3 * d_best:.0f} ms (scan {1e3*scan[0]:.0f}..{1e3*scan[-1]:.0f} ms, '
        f'chi2 rise at +-50 ms: {np.interp(d_best - 0.05, scan, chi) / chi.min() - 1:+.3%} / {np.interp(d_best + 0.05, scan, chi) / chi.min() - 1:+.3%})')
    # same scan with landing replaced by the write time (is the 8 Hz grid visible?)
    def wcols(d):
        return SD.pulse_cols([p['write_on'] + d for p in P])
    chi_w = []
    for d in scan + 0.05:
        Xw = np.hstack([Xt, wcols(d)]); _, r = lsq(Xw, SD.Y, True); chi_w.append(float(r @ r))
    chi_w = np.array(chi_w)
    say(f'same fit timed from the WRITE instead of the landing: best chi2 / landing best chi2 = {chi_w.min() / chi.min():.4f} '
        f'(at {1e3 * (scan + 0.05)[np.argmin(chi_w)]:.0f} ms after the write)')

    # ---------------- 2. trap check against the post-run free swing
    say(''); say('## 2. Trap check: replay of the post-run free swing (field off, t >= last write + 20 s)')
    fm = t >= T_FREE
    tf, thf = t[fm], th[fm]
    tpf = B1.turning_points(tf, thf); sw = B1.swing_summary(tpf)
    say(f'measured: period {sw["period"]:.4f} s, mean max/min {sw["max_mean"]:.2f}/{sw["min_mean"]:.2f} deg, {sw["n_per"]} periods')
    b1 = json.load(open(os.path.join(AN, 'brake_b1_20261110', 'trap_b1.json')))
    s1 = json.load(open(os.path.join(AN, 'f3_step2_20261110', 'refit', 'refit_coeffs.json')))['trap_acc_canonical']
    s1all = json.load(open(os.path.join(AN, 'f3_step2_20261110', 'refit', 'refit_coeffs.json')))
    s1n = np.array(s1all['trap_nodes_deg'], float)
    # free-swing-only trap (MAIN method, same nodes) for comparison
    SDf = SecondDiff(tf, thf); p_free, _ = lsq(SDf.trap_cols(), SDf.Y, True)
    traps = {'B2 joint (run)': (NODES, trap_run), 'B2 free swing (post-run)': (NODES, p_free),
             'B1 MAIN': (np.array(b1['trap_nodes_deg']), np.array(b1['trap_acc_rad_s2'])),
             'B1 smooth': (np.array(b1['trap_nodes_deg']), np.array(b1['trap_acc_smooth_rad_s2'])),
             'S1 canonical': (s1n, np.array(s1['acc_rad_s2']))}
    i0 = int(np.argmin(np.abs(tf - tpf[0, 0])))
    rep = {}
    for name, (nn, aa) in traps.items():
        f = lambda x, nn=nn, aa=aa: float(np.interp(x, nn, aa))
        ts, ys = B1.sim(f, tpf[0, 1], 0.0, tf[-1] - tpf[0, 0], gamma=b1['damping']['gamma_per_s'])
        ts = ts + tpf[0, 0]
        tps = B1.turning_points(ts, ys)
        try:
            ss = B1.swing_summary(tps)
            rep[name] = dict(period=ss['period'], max=ss['max_mean'], min=ss['min_mean'],
                             rms_deg_first10s=float(np.sqrt(np.mean((np.interp(tf[(tf < tpf[0, 0] + 10) & (tf > tpf[0, 0])], ts, ys)
                                                                     - thf[(tf < tpf[0, 0] + 10) & (tf > tpf[0, 0])]) ** 2))))
            say(f'  {name:26s}: period {ss["period"]:.4f} s ({100 * (ss["period"] / sw["period"] - 1):+.2f} %), '
                f'max/min {ss["max_mean"]:.2f}/{ss["min_mean"]:.2f}, rms over first 10 s {rep[name]["rms_deg_first10s"]:.2f} deg')
        except Exception as e:  # noqa
            rep[name] = dict(error=str(e)); say(f'  {name}: replay failed ({e})')
    say(f'  (S1 canonical valid only 198-234 deg; the swing reaches {thf.min():.1f}..{thf.max():.1f})')
    say(f'  joint-fit trap vs free-swing trap over 192-236 deg: rms difference '
        f'{np.sqrt(np.mean((trap_run - p_free)[(NODES >= 192) & (NODES <= 236)] ** 2)):.3f} rad/s^2')

    trapf = make_trapf(NODES, trap_run)

    # ---------------- 3. per-pulse trajectory fits
    say(''); say(f'## 3. Per-pulse trajectory fits (window {WIN} s each side, joint-fit trap)')
    rows = []
    for i, p in enumerate(P):
        lo, hi = windows(P, i)
        fr = pulse_fit(t, th, trapf, p['land_on'], lo, hi, d0=d_best)           # free delay
        fx = pulse_fit(t, th, trapf, p['land_on'], lo, hi, fix_d=d_best)          # common delay
        gmean = float(np.mean(gshape(np.linspace(0, PULSE, 1001, endpoint=False), 0)))
        rows.append(dict(i=i, phase=p['phase'], chan=p['chan'], write_on=p['write_on'], land_on=p['land_on'],
                         rel_delay_ms=p['rel_delay_ms'], win=(lo - p['land_on'], hi - p['land_off']),
                         theta_mid_deg=fx['th_mid'], omega_mid_rad_s=fx['w_mid'],
                         a_rad_s2=fx['a'] * gmean, a_fit_err=fx['a_err_fit'] * gmean, dw_rad_s=fx['a'] * gmean * PULSE,
                         a_joint_rad_s2=float(a_joint[i]) * gmean, d_free_ms=1e3 * fr['d'],
                         a_freed_rad_s2=fr['a'] * gmean, rms_deg=fx['rms_deg'], _fx=fx))
    R = rows

    # ---------------- 4. null test
    rng = np.random.default_rng(SEED)
    fake_t = []
    tt0 = T_FREE + WIN + 0.1
    while tt0 < t[-1] - WIN - PULSE - 0.1:
        fake_t.append(tt0); tt0 += rng.uniform(1.6, 2.4)
    nulls = []; nulls_short = []
    for tf0 in fake_t:
        fx = pulse_fit(t, th, trapf, tf0, tf0 - WIN, tf0 + PULSE + WIN, fix_d=0.0)
        nulls.append(fx['a'] * gmean)
    nulls = np.array(nulls)
    # same with the free-swing trap fitted ON that data (optimistic floor)
    trapf_free = make_trapf(NODES, p_free)
    nulls_in = np.array([pulse_fit(t, th, trapf_free, tf0, tf0 - WIN, tf0 + PULSE + WIN, fix_d=0.0)['a'] * gmean for tf0 in fake_t])
    sig = float(np.sqrt(np.mean(nulls ** 2)))
    say(''); say('## 4. Null test (fake pulses in the post-run free swing, run-only trap)')
    say(f'{len(nulls)} fake pulses (overlapping windows, spacing 1.6-2.4 s): mean {nulls.mean():+.4f}, rms {sig:.4f} rad/s^2 '
        f'(trap fitted on the same free data: rms {np.sqrt(np.mean(nulls_in ** 2)):.4f}); median fit-covariance error of real pulses '
        f'{np.median([r["a_fit_err"] for r in R]):.4f} rad/s^2')
    say(f'-> per-pulse uncertainty on the mean field acceleration: {sig:.3f} rad/s^2 (dw: {sig * PULSE:.4f} rad/s) (derived)')

    a = np.array([r['a_rad_s2'] for r in R]); aj = np.array([r['a_joint_rad_s2'] for r in R])
    err = np.full(len(a), sig)
    say(''); say('per-pulse table (phase, theta_mid deg, omega_mid rad/s, a rad/s^2 [trajectory], a [joint 2nd-diff], d_free ms)')
    for r in R:
        say(f'  {r["i"]:2d} {r["phase"]} t={r["land_on"] - T0:7.2f}  th {r["theta_mid_deg"]:6.1f}  w {r["omega_mid_rad_s"]:+.3f}  '
            f'a {r["a_rad_s2"]:+.3f}  joint {r["a_joint_rad_s2"]:+.3f}  d {r["d_free_ms"]:+5.0f}  rms {r["rms_deg"]:.3f}')
    say(f'trajectory vs joint a: rms difference {np.sqrt(np.mean((a - aj) ** 2)):.4f} rad/s^2, corr {np.corrcoef(a, aj)[0, 1]:.3f}')

    # delay per pulse
    dfree = np.array([r['d_free_ms'] for r in R])
    big = np.abs(a) > 3 * sig
    say(''); say('## Delay (field start after landing_host)')
    say(f'common (joint fit): {1e3 * d_best:.0f} ms. Per-pulse free fits, pulses with |a| > 3 sigma ({big.sum()}): '
        f'median {np.median(dfree[big]):.0f} ms, IQR {np.percentile(dfree[big], 25):.0f}..{np.percentile(dfree[big], 75):.0f} ms; '
        f'bootstrap error of the median {np.std([np.median(rng.choice(dfree[big], big.sum())) for _ in range(2000)]):.1f} ms '
        f'(per-pulse fit-covariance errors are unreliable here and not used)')
    wr = dfree[big] + rel[big]
    say(f'  same measured from the WRITE: spread (std) {np.std(wr):.0f} ms vs from the landing {np.std(dfree[big]):.0f} ms; '
        f'corr(d_free, relative landing delay) = {np.corrcoef(dfree[big], rel[big])[0, 1]:+.2f} (expect ~0 if landing timing is right)')

    # ---------------- 5. push map
    say(''); say('## 5. Push map a(theta) = P cos(m theta - phi) + c per phase (pulse-averaged basis, sigma = null rms)')
    fits = {}
    for m in (4, 8, 16):
        C, S = harm_basis(cs, P, d_best, m)
        res, chi2, npar = fit_map(a, err, C, S, ph)
        sh, chi2s, nps = fit_map(a, err, C, S, ph, shared_P=True)
        c0 = sum(float(np.sum(((a[ph == q] - np.mean(a[ph == q])) / sig) ** 2)) for q in 'ABC')
        fits[m] = dict(per_phase=res, chi2=chi2, ndof=len(a) - npar, shared=sh, chi2_shared=chi2s, ndof_shared=len(a) - nps,
                       chi2_const_only=c0, ndof_const_only=len(a) - 3)
        say(f'm={m:2d}: chi2/ndof per-phase {chi2:.1f}/{len(a) - npar}; shared P {chi2s:.1f}/{len(a) - nps}; const-only {c0:.1f}/{len(a) - 3}')
        for q in 'ABC':
            x = res[q]
            say(f'   {q}: P {x["P"]:.3f}+-{x["P_err"]:.3f}  phi {x["phi_deg"]:6.1f}+-{x["phi_err_deg"]:.1f} deg  const {x["const"]:+.3f}+-{x["const_err"]:.3f}  chi2 {x["chi2"]:.1f}/{x["n"] - 3}')
        dp = {k: (sh['phi_deg'][k[1]] - sh['phi_deg'][k[0]]) % 360 for k in ('AB', 'BC', 'CA')}
        say(f'   shared-P fit: P {sh["P"]:.3f}, const {sh["const"]:+.3f}, phi A/B/C {sh["phi_deg"]["A"]:.1f}/{sh["phi_deg"]["B"]:.1f}/'
            f'{sh["phi_deg"]["C"]:.1f}; phi_B-phi_A {dp["AB"]:.1f}, phi_C-phi_B {dp["BC"]:.1f}, phi_A-phi_C {dp["CA"]:.1f} deg (electrical)')
        fits[m]['phase_diffs_deg'] = dp
    # angle coverage
    th_mid = np.array([r['theta_mid_deg'] for r in R])
    for q in 'ABC':
        say(f'   coverage {q}: theta_mid {np.sort(th_mid[ph == q]).round(0).astype(int).tolist()}')

    # ---------------- 5b. two harmonics (m = 8 and 16 together: any 45-deg-periodic shape to 2nd order)
    sig2 = float(np.sqrt(np.mean((a - aj) ** 2)))     # method spread (trajectory vs joint), a second error scale
    say(''); say(f'## 5b. Harmonic combinations, per phase (chi2/ndof at sigma = null {sig:.3f} and = method spread {sig2:.3f} rad/s^2)')
    def multi_basis(ms, d=d_best, shift=None):
        rows_ = []
        for k, p in enumerate(P):
            s = p['land_on'] + d + np.linspace(0, PULSE, 51); g = gshape(s, p['land_on'] + d - 1e-9)
            x = np.radians(cs(s) - (0.0 if shift is None else shift[k]))
            r_ = []
            for m in ms:
                r_ += [np.sum(g * np.cos(m * x)) / g.sum(), np.sum(g * np.sin(m * x)) / g.sum()]
            rows_.append(r_ + [1.0])
        return np.array(rows_)
    combos = {}
    for ms in [(8,), (16,), (24,), (4, 8), (8, 16), (16, 24), (8, 16, 24)]:
        Xm = multi_basis(ms); rr = np.zeros(len(a)); coef = {}
        for q in 'ABC':
            k = ph == q
            c, *_ = np.linalg.lstsq(Xm[k], a[k], rcond=None); rr[k] = a[k] - Xm[k] @ c
            coef[q] = {f'm{m}': dict(P=float(math.hypot(c[2 * j], c[2 * j + 1])), phi_deg=math.degrees(math.atan2(c[2 * j + 1], c[2 * j])) % 360)
                       for j, m in enumerate(ms)} | dict(const=float(c[-1]))
        nd = len(a) - 3 * Xm.shape[1]
        combos[str(ms)] = dict(rms_resid=float(np.sqrt(np.mean(rr ** 2))), ndof=nd, coef=coef,
                               chi2_null=float(rr @ rr / sig ** 2), chi2_spread=float(rr @ rr / sig2 ** 2))
        say(f'  m {str(ms):12s}: rms residual {np.sqrt(np.mean(rr ** 2)):.3f} rad/s^2, chi2/ndof {rr @ rr / sig ** 2:.0f}/{nd} '
            f'(null sigma), {rr @ rr / sig2 ** 2:.0f}/{nd} (spread sigma)')
    for q in 'ABC':
        x = combos['(8, 16)']['coef'][q]
        say(f'   (8,16) {q}: P8 {x["m8"]["P"]:.3f} phi8 {x["m8"]["phi_deg"]:.0f}  P16 {x["m16"]["P"]:.3f} phi16 {x["m16"]["phi_deg"]:.0f}  const {x["const"]:+.3f}')
    for m in (8, 16):
        f_ = {q: combos['(8, 16)']['coef'][q][f'm{m}']['phi_deg'] for q in 'ABC'}
        say(f'   (8,16) m={m} phase differences: B-A {(f_["B"] - f_["A"]) % 360:.0f}, C-B {(f_["C"] - f_["B"]) % 360:.0f}, '
            f'A-C {(f_["A"] - f_["C"]) % 360:.0f} deg electrical')
    # shared shape, shifted per phase: a_q(theta) = F(theta - s_q), F = m8 + m16 + const, s_A = 0
    say('  shared-shape test: a_q(theta) = F(theta - s_q), F = c + m=8 + m=16 terms, s_A = 0, grid over s_B, s_C (mech deg, period 45):')
    grid = np.arange(-22.5, 22.51, 0.5); best = None; chimap = np.zeros((grid.size, grid.size))
    base = multi_basis((8, 16))
    th_pul = [cs(p['land_on'] + d_best + np.linspace(0, PULSE, 51)) for p in P]
    def shifted_basis(sB, sC):
        rows_ = []
        for k, p in enumerate(P):
            sft = {'A': 0.0, 'B': sB, 'C': sC}[p['phase']]
            x = np.radians(th_pul[k] - sft)
            rows_.append([np.mean(np.cos(8 * x)), np.mean(np.sin(8 * x)), np.mean(np.cos(16 * x)), np.mean(np.sin(16 * x)), 1.0])
        return np.array(rows_)
    for i_, sB in enumerate(grid):
        for j_, sC in enumerate(grid):
            Xs = shifted_basis(sB, sC); c, *_ = np.linalg.lstsq(Xs, a, rcond=None); rr = a - Xs @ c
            chimap[i_, j_] = rr @ rr
            if best is None or rr @ rr < best[0]:
                best = (float(rr @ rr), float(sB), float(sC), c)
    nd_s = len(a) - 7
    def chi_at(sB, sC):
        Xs = shifted_basis(sB, sC); c, *_ = np.linalg.lstsq(Xs, a, rcond=None); rr = a - Xs @ c; return float(rr @ rr)
    ref = {f'sB={sb:+.0f}, sC={sc:+.0f}': chi_at(sb, sc) for sb, sc in [(15, -15), (-15, 15), (15, 30 - 45), (0, 0)]}
    say(f'   best s_B {best[1]:+.1f}, s_C {best[2]:+.1f} mech deg; rms residual {np.sqrt(best[0] / len(a)):.3f} rad/s^2, '
        f'chi2/ndof {best[0] / sig2 ** 2:.0f}/{nd_s} (spread sigma) vs independent per-phase (8,16) {combos["(8, 16)"]["chi2_spread"]:.0f}/{combos["(8, 16)"]["ndof"]}')
    for k_, v_ in ref.items():
        say(f'   fixed {k_}: rms residual {np.sqrt(v_ / len(a)):.3f} (chi2 spread-sigma {v_ / sig2 ** 2:.0f})')
    # 1-sigma region (delta chi2 = 2.3 * chi2min/ndof scaling)
    scale = best[0] / nd_s
    okm = chimap <= best[0] + 2.3 * scale
    say(f'   ~68 % region (chi2 rescaled to ndof): s_B {grid[okm.any(1)].min():+.1f}..{grid[okm.any(1)].max():+.1f}, '
        f's_C {grid[okm.any(0)].min():+.1f}..{grid[okm.any(0)].max():+.1f} mech deg')
    shared_shape = dict(s_B_deg=best[1], s_C_deg=best[2], rms_resid=float(np.sqrt(best[0] / len(a))), ndof=nd_s,
                        coef=dict(c8=best[3][0], s8=best[3][1], c16=best[3][2], s16=best[3][3], const=best[3][4]),
                        region68_sB=[float(grid[okm.any(1)].min()), float(grid[okm.any(1)].max())],
                        region68_sC=[float(grid[okm.any(0)].min()), float(grid[okm.any(0)].max())], fixed=ref)

    # global harmonic variant inside the 2nd-difference fit (no per-pulse step)
    say(''); say('global variant: harmonic map fitted inside the 2nd-difference fit (run data), per m:')
    glob = {}
    for m in (4, 8, 16):
        Xh = SD.harm_cols([[p['land_on'] + d_best for p in P if p['phase'] == q] for q in 'ABC'], m)
        Xg = np.hstack([Xt, Xh]); pg, rg = lsq(Xg, SD.Y, True)
        cg = pg[NODES.size:].reshape(3, 3)
        glob[m] = dict(chi2_rows=float(rg @ rg), **{q: dict(P=float(math.hypot(*cg[k, :2])), phi_deg=math.degrees(math.atan2(cg[k, 1], cg[k, 0])) % 360,
                                                         const=float(cg[k, 2])) for k, q in enumerate('ABC')})
        say(f'  m={m:2d}: row chi2 {rg @ rg:.2f} (vs per-pulse free {r_joint @ r_joint:.2f}); ' +
            '; '.join(f'{q} P {glob[m][q]["P"]:.3f} phi {glob[m][q]["phi_deg"]:.0f} c {glob[m][q]["const"]:+.3f}' for q in 'ABC'))

    # ---------------- 6. AC tail systematic (linear-in-V hypothesis)
    say(''); say('## 6. AC tail (if the push were linear in V: -4.4 % reversed tail, tau 5.57 s, times the push map)')
    mbest = '(8, 16)'
    pm = combos[mbest]['coef']
    def amap(q, xdeg):
        return pm[q]['const'] + sum(pm[q][f'm{m}']['P'] * np.cos(m * np.radians(xdeg) - math.radians(pm[q][f'm{m}']['phi_deg'])) for m in (8, 16))
    a_tail = []
    for i, p in enumerate(P):
        lo, hi = windows(P, i)
        def extra(s, i=i):
            # tails of this and all earlier pulses, push map evaluated on the tracked angle (vectorised over s)
            x = cs(s)
            return sum(tailshape(s, pk['land_off'] + d_best) * amap(pk['phase'], x) for pk in P[:i + 1])
        fx = pulse_fit(t, th, trapf, p['land_on'], lo, hi, fix_d=d_best, extra=extra)
        a_tail.append(fx['a'] * gmean)
    a_tail = np.array(a_tail)
    say(f'(map m={mbest}, per phase) per-pulse a shifts by {np.mean(a_tail - a):+.4f} mean, {np.sqrt(np.mean((a_tail - a) ** 2)):.4f} rms rad/s^2; '
        f'max |shift| {np.max(np.abs(a_tail - a)):.4f}')
    Xm = multi_basis((8, 16)); res_t = {}
    for q in 'ABC':
        k = ph == q; c, *_ = np.linalg.lstsq(Xm[k], a_tail[k], rcond=None)
        res_t[q] = dict(P8=float(math.hypot(c[0], c[1])), phi8=math.degrees(math.atan2(c[1], c[0])) % 360,
                        P16=float(math.hypot(c[2], c[3])), phi16=math.degrees(math.atan2(c[3], c[2])) % 360, const=float(c[4]))
        say(f'   {q}: P8 {res_t[q]["P8"]:.3f} (was {pm[q]["m8"]["P"]:.3f}), phi8 {res_t[q]["phi8"]:.0f} (was {pm[q]["m8"]["phi_deg"]:.0f}), '
            f'P16 {res_t[q]["P16"]:.3f} (was {pm[q]["m16"]["P"]:.3f}), phi16 {res_t[q]["phi16"]:.0f} (was {pm[q]["m16"]["phi_deg"]:.0f}), '
            f'const {res_t[q]["const"]:+.3f} (was {pm[q]["const"]:+.3f})')

    # ---------------- 7. swing amplitude through the run
    say(''); say('## 7. Swing amplitude (turning points)')
    tp = B1.turning_points(t, th)
    amp = []
    for k in range(len(tp) - 1):
        if tp[k, 2] != tp[k + 1, 2]:
            amp.append(((tp[k, 0] + tp[k + 1, 0]) / 2, abs(tp[k, 1] - tp[k + 1, 1]) / 2, (tp[k, 1] + tp[k + 1, 1]) / 2))
    amp = np.array(amp)
    first_on = P[0]['land_on']; last_off = P[-1]['land_off']
    segs = {'pre-run': amp[:, 0] < first_on, 'run, first 30 s': (amp[:, 0] > first_on) & (amp[:, 0] < first_on + 30),
            'run, last 30 s': (amp[:, 0] > last_off - 30) & (amp[:, 0] < last_off),
            'post-run (> +20 s)': amp[:, 0] > T_FREE}
    amp_summary = {}
    for k, mm in segs.items():
        amp_summary[k] = dict(amp_mean=float(amp[mm, 1].mean()), amp_min=float(amp[mm, 1].min()), amp_max=float(amp[mm, 1].max()),
                              centre=float(amp[mm, 2].mean()), n=int(mm.sum()))
        say(f'  {k:20s}: half-amplitude {amp[mm, 1].mean():.2f} deg (range {amp[mm, 1].min():.2f}..{amp[mm, 1].max():.2f}), centre {amp[mm, 2].mean():.2f}, n {mm.sum()}')
    rr = (amp[:, 0] > first_on) & (amp[:, 0] < last_off)
    say(f'  during the run: half-amplitude range {amp[rr, 1].min():.2f}..{amp[rr, 1].max():.2f} deg')
    # energy kick vs prediction: omega*dw sign
    wmid = np.array([r['omega_mid_rad_s'] for r in R])
    dE = wmid * a * PULSE
    say(f'  per-pulse energy change w*dw (rad^2/s^2): sum {dE.sum():+.4f}, rms {np.sqrt(np.mean(dE ** 2)):.4f}; '
        f'fraction of pulses adding energy {np.mean(dE > 0):.2f}')

    # ---------------- plots
    fig, ax = plt.subplots(2, 1, figsize=(13, 7), sharex=True, gridspec_kw=dict(height_ratios=[3, 1]))
    ax[0].plot(t - T0, th, lw=0.5, color='0.4')
    for p, r in zip(P, R):
        ax[0].axvspan(p['land_on'] - T0, p['land_off'] - T0, color=COL[p['phase']], alpha=0.5, lw=0)
    for q in 'ABC':
        ax[0].plot([], [], color=COL[q], lw=6, alpha=0.5, label=f'phase {q} pulse')
    ax[0].axvline(T_FREE - T0, color='k', ls=':', lw=0.8); ax[0].legend(loc='upper right', ncol=3, fontsize=8)
    ax[0].set_ylabel('rotor angle (deg)'); ax[0].set_title('B2 pulse run: tracked angle, pulses marked by phase (landing time on host clock)')
    ax[1].plot(amp[:, 0] - T0, amp[:, 1], '.-', ms=3, lw=0.6, color='k'); ax[1].set_ylabel('half-amplitude (deg)')
    ax[1].set_xlabel(f'host time - {T0:.0f} s')
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'b2_angle_vs_time.png'), dpi=130); plt.close(fig)

    fig, axs = plt.subplots(3, 3, figsize=(14, 10), sharey=True)
    xx = np.linspace(184, 242, 600)
    for row, ms in enumerate([(8,), (16,), (8, 16)]):
        Xm = multi_basis(ms)
        for col, q in enumerate('ABC'):
            axx = axs[row, col]; k = ph == q
            co = combos[str(ms)]['coef'][q]
            curve = co['const'] + sum(co[f'm{m}']['P'] * np.cos(m * np.radians(xx) - math.radians(co[f'm{m}']['phi_deg'])) for m in ms)
            pred = co['const'] + sum(co[f'm{m}']['P'] * (Xm[k, 2 * j] * math.cos(math.radians(co[f'm{m}']['phi_deg'])) +
                                                          Xm[k, 2 * j + 1] * math.sin(math.radians(co[f'm{m}']['phi_deg'])))
                                     for j, m in enumerate(ms))
            axx.plot(xx, curve, color=COL[q], lw=0.8, alpha=0.6, label='a(theta) (point value)')
            axx.errorbar(th_mid[k], a[k], yerr=sig2, fmt='o', color=COL[q], ms=4, capsize=2, label='measured (bar: method spread)')
            axx.plot(th_mid[k], pred, 'kx', ms=5, label='model, pulse-averaged')
            rr = a[k] - pred
            axx.axhline(0, color='0.7', lw=0.6); axx.legend(fontsize=6, loc='lower left')
            axx.set_title(f'phase {q}, m = {"+".join(map(str, ms))}: rms resid {np.sqrt(np.mean(rr ** 2)):.3f} rad/s$^2$', fontsize=9)
            axx.set_xlim(184, 242)
            if col == 0:
                axx.set_ylabel('field acc. (rad/s$^2$)')
            if row == 2:
                axx.set_xlabel('rotor angle at mid-pulse (deg)')
    fig.suptitle('B2 push map: mean field acceleration over each 0.25 s pulse vs angle. Rotor sweeps up to ~13 deg per pulse, so '
                 'compare dots with crosses (model averaged over the sweep), not with the curve', fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'b2_pushmap.png'), dpi=130); plt.close(fig)

    # shared-shape fit, all phases on one axis
    fig, ax = plt.subplots(figsize=(8, 4.5))
    cf = shared_shape['coef']
    for q in 'ABC':
        sft = {'A': 0.0, 'B': shared_shape['s_B_deg'], 'C': shared_shape['s_C_deg']}[q]; x = np.radians(xx - sft)
        ax.plot(xx, cf['const'] + cf['c8'] * np.cos(8 * x) + cf['s8'] * np.sin(8 * x) + cf['c16'] * np.cos(16 * x) + cf['s16'] * np.sin(16 * x),
                color=COL[q], lw=1, label=f'{q}: F(theta - {sft:+.1f})')
        ax.plot(th_mid[ph == q], a[ph == q], 'o', color=COL[q], ms=4)
    ax.axhline(0, color='0.7', lw=0.6); ax.legend(fontsize=8); ax.set_xlabel('rotor angle (deg)'); ax.set_ylabel('field acc. (rad/s$^2$)')
    ax.set_title(f'shared shape (m=8+16) shifted per phase; rms resid {shared_shape["rms_resid"]:.3f} rad/s$^2$', fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'b2_shared_shape.png'), dpi=130); plt.close(fig)

    # example pulse fits: largest |a| and a near-zero
    order = np.argsort(-np.abs(a))
    ex = [int(order[0]), int(order[len(order) // 2])]
    fig, axs = plt.subplots(2, 2, figsize=(13, 7), gridspec_kw=dict(height_ratios=[2, 1]))
    for c, i in enumerate(ex):
        fx = R[i]['_fx']; p = P[i]; tt = fx['tt']
        y = np.degrees(fx['model'](fx['p']) + fx['resid'])
        pz = fx['p'].copy(); pz[2] = 0.0
        # trap-only continuation from the pre-pulse side: refit the no-field model on the pre window only
        pre = tt < p['land_on']
        axs[0, c].plot(tt - p['land_on'], y, '.', ms=2, color='0.4', label='tracked')
        axs[0, c].plot(tt - p['land_on'], np.degrees(fx['model'](fx['p'])), color=COL[p['phase']], label=f'fit, a = {R[i]["a_rad_s2"]:+.3f} rad/s$^2$')
        axs[0, c].axvspan(d_best, d_best + PULSE, color=COL[p['phase']], alpha=0.2)
        axs[1, c].plot(tt - p['land_on'], np.degrees(fx['resid']), '.', ms=2, color='k', label='residual (fit)')
        # residual if a forced to 0 (same theta0, omega0 at mid): shows the kick
        axs[1, c].plot(tt - p['land_on'], np.degrees(fx['model'](pz) - (fx['model'](fx['p']) + fx['resid'])) * -1, lw=0.8,
                       color=COL[p['phase']], label='data - (same start, a = 0)')
        axs[0, c].set_title(f'pulse {i} (phase {p["phase"]}), theta {R[i]["theta_mid_deg"]:.1f} deg, omega {R[i]["omega_mid_rad_s"]:+.2f} rad/s', fontsize=9)
        axs[0, c].legend(fontsize=7); axs[1, c].legend(fontsize=7)
        axs[1, c].set_xlabel('t - landing_host (s)'); axs[0, c].set_ylabel('deg'); axs[1, c].set_ylabel('deg')
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'b2_example_pulses.png'), dpi=130); plt.close(fig)

    fig, axs = plt.subplots(1, 3, figsize=(15, 4))
    axs[0].plot(1e3 * scan, chi / chi.min(), '.-', label='from landing'); axs[0].plot(1e3 * (scan + 0.05) - 0, chi_w / chi.min(), '.-', label='from write (x-axis: delay after write)')
    axs[0].set_xlabel('delay (ms)'); axs[0].set_ylabel('chi2 / min'); axs[0].legend(fontsize=8); axs[0].set_title('common delay scan (joint fit)', fontsize=9)
    axs[1].plot(rel[big], dfree[big], 'o', ms=3)
    axs[1].set_xlabel('write->landing relative delay (ms)'); axs[1].set_ylabel('fitted start - landing_host (ms)'); axs[1].set_title('per-pulse delay', fontsize=9)
    for name, (nn, aa) in traps.items():
        axs[2].plot(nn, aa, lw=1, label=name)
    axs[2].set_xlim(180, 245); axs[2].set_ylim(-6, 6); axs[2].legend(fontsize=7); axs[2].set_xlabel('theta (deg)'); axs[2].set_ylabel('trap acc (rad/s$^2$)')
    axs[2].axhline(0, color='0.7', lw=0.6)
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'b2_delay_and_trap.png'), dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(nulls, bins=15, alpha=0.6, label=f'null (fake pulses), rms {sig:.3f}')
    ax.hist(a, bins=15, alpha=0.6, label='real pulses')
    ax.set_xlabel('fitted mean field acc (rad/s$^2$)'); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'b2_null_test.png'), dpi=130); plt.close(fig)

    # ---------------- outputs
    J = dict(date='2026-11-10', gate='B2 (braking plan)', script='analysis/brake_b2_20261110/b2_pushmap.py',
             data=dict(run=RUN, video=VID + '.avi', angle_csv='analysis/brake_b2_20261110/rotor_angle_b2.csv'),
             conventions=dict(theta='absolute tracked angle, deg (template zero of 11-06), mid-pulse from the fitted trajectory',
                              a='mean field angular acceleration over the 0.25 s pulse, rad/s^2 (dw = a * 0.25 s); positive = increasing theta',
                              map='a(theta) = P cos(m theta - phi) + const, phi in electrical deg',
                              landing_host='write host time + OUT_DQ relative landing delay (zero = earliest); absolute latency unknown',
                              d='fitted field start - landing_host'),
             delay=dict(common_ms=1e3 * d_best, per_pulse_median_ms=float(np.median(dfree[big])), n_used=int(big.sum())),
             per_pulse_sigma_rad_s2=sig, null=dict(n=len(nulls), mean=float(nulls.mean()), rms=sig, rms_trap_on_same_data=float(np.sqrt(np.mean(nulls_in ** 2)))),
             fits={str(m): dict(per_phase=fits[m]['per_phase'], chi2=fits[m]['chi2'], ndof=fits[m]['ndof'], shared=fits[m]['shared'],
                                chi2_shared=fits[m]['chi2_shared'], ndof_shared=fits[m]['ndof_shared'], chi2_const_only=fits[m]['chi2_const_only'],
                                ndof_const_only=fits[m]['ndof_const_only'], phase_diffs_deg=fits[m]['phase_diffs_deg']) for m in fits},
             global_fit=glob, combos=combos, shared_shape=shared_shape, sigma_method_spread=sig2, tail_test=dict(m=mbest, per_phase=res_t, shift_rms=float(np.sqrt(np.mean((a_tail - a) ** 2)))),
             trap_run=dict(nodes_deg=NODES.tolist(), acc_rad_s2=trap_run.round(4).tolist(), acc_free_post_run=p_free.round(4).tolist()),
             trap_replay_post_run=dict(measured=sw, **rep), swing=amp_summary,
             pulses=[{k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in r.items() if not k.startswith('_') and k != 'win'}
                     | dict(win_pre_s=float(-r['win'][0]), win_post_s=float(r['win'][1]), a_tail_corrected=float(a_tail[r['i']]))
                     for r in R])
    def conv(o):
        if isinstance(o, dict): return {str(k): conv(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)): return [conv(v) for v in o]
        if isinstance(o, (np.floating,)): return float(o)
        if isinstance(o, (np.integer,)): return int(o)
        return o
    json.dump(conv(J), open(os.path.join(HERE, 'pushmap_b2.json'), 'w'), indent=1)
    open(os.path.join(HERE, 'b2_summary.txt'), 'w').write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
