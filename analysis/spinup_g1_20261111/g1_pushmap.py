#!/usr/bin/env python3
"""Spin-up gate G1: push map over a larger swing (167-267 deg) and how the push scales with voltage. 2026-11-11.

    python3 g1_pushmap.py        # ~5-10 min; reads the Dropbox run, writes pushmap_g1.json, g1_summary.txt, plots/

Data (read only): Dropbox Microspheres/TFINER/data/spinup/2026-11-11/g1/
  brake_1794403551.csv          step 1: kick A 2400 counts 2 s, 10 s settle, then the pump (brake_offsets.py --pump-to 35)
  vsteps_1794403575/            step 2: 50 single-electrode 0.25 s pulses, 25 at 800 and 25 at 1600 counts (offset route);
                                out_dq.npz covers step 1 too
  tracker/blob_live_gps1478438744.csv  live tracker angles (blob_core.Tracker, centre 117.5,165.1, template gps1477428272)
  tracker/output_basler_gps1478438744.csv  per-frame camera timestamps (time base, as B2's host_time_cam)

Methods follow analysis/brake_b2_20261110 (README there): the B2 helpers are imported (SecondDiff, lsq, pulse_fit,
windows, gshape, rk4). Differences from B2, each said where it happens:
  - angles: the live tracker's angles are used directly. A re-track of frames 0-3999 (blob_core, same centre/template)
    agreed to 0.005 deg max (live csv rounds to 0.01 deg). Time = camera clock mapped to host by the median offset.
  - host -> FE mapping refitted (vsteps_score's lower-envelope fit put 3 early pulses 21-27 ms before their write):
    drift b chosen to minimise the spread of write -> landing delays (step-2 writes + the kick), zero = earliest.
  - AC tails: the electrode voltage is modelled from the OUT_DQ landings, high-passed with tau 5.57 s. A pulse that
    starts on a residual tail delta has drive (V + delta)^2 exp(-2t/tau): a is corrected by kappa = ((V+delta)/V)^2
    (V^2 assumed for the correction; the uncorrected ratio is quoted too).
  - field model a_k = S(level) * F(theta - s_q), F = c + m8 + m16 (45-deg periodic), S(800) = 1, fitted jointly by
    variable projection (F linear, S and shifts nonlinear), per-pulse sigma^2 = sigma_null^2 + (S sigma_shape)^2 with
    sigma_shape set so chi2/ndof = 1; ranges by bootstrap over pulses.
"""
import json, math, os, sys
import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline
from scipy.optimize import least_squares, brentq
from scipy.signal import savgol_filter
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
AN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(AN, 'brake_b1_20261110'))
sys.path.insert(0, os.path.join(AN, 'brake_b2_20261110'))
import b1_trap as B1          # noqa: E402
import b2_pushmap as B2       # noqa: E402  (also puts lab_utils/voltage_steps_score on the path)
VSS = B2.VSS

DATA = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-11/g1')
RUN = os.path.join(DATA, 'vsteps_1794403575')
BRAKE = os.path.join(DATA, 'brake_1794403551.csv')
LIVE = os.path.join(DATA, 'tracker', 'blob_live_gps1478438744.csv')
CAMCSV = os.path.join(DATA, 'tracker', 'output_basler_gps1478438744.csv')
B2DIR = os.path.join(AN, 'brake_b2_20261110')
PLOTS = os.path.join(HERE, 'plots')
T0 = 1794403500.0
PHASE = {2: 'A', 4: 'B', 3: 'C'}
QI = {'A': 0, 'B': 1, 'C': 2}
CHQ = {2: 0, 4: 1, 3: 2}
COL = {'A': '#1f77b4', 'B': '#d62728', 'C': '#2ca02c'}
PULSE, TAU_AC = B2.PULSE, B2.TAU_AC
NODES = np.arange(160.0, 274.01, 2.0)
PEN = 1.0
WIN = 1.5
CENTRE = 217.0
NBOOT = 400
SEED = 20261111
GMEAN = float(np.mean(B2.gshape(np.linspace(0, PULSE, 1001, endpoint=False), 0)))
KICK_ON, KICK_OFF = 1794403553.029015, 1794403555.042191     # brake log comment lines (host write times)

out = []
def say(s=''):
    print(s); out.append(s)


# ------------------------------------------------------------------------------------------------ data
def load_angles():
    L = pd.read_csv(LIVE, comment='#'); C = pd.read_csv(CAMCSV)
    assert len(L) == len(C) and np.all(L.host_time.values == C.host_time.values)
    cam = C.cam_timestamp_ns.values * 1e-9
    off = np.median(C.host_time.values - cam); tc = cam + off
    lag = C.host_time.values - tc
    th = np.degrees(np.unwrap(np.radians(L.angle_deg.values)))
    dt = np.median(np.diff(tc)); tu = np.arange(tc[0], tc[-1], dt)
    return tu, np.interp(tu, tc, th), dt, dict(t=tc, th=th, src=L.source.values, ncc=L.ncc.values, lag=lag)


def timing():
    """Landings from OUT_DQ (vsteps_score), host->FE mapping refitted by minimum delay spread."""
    R = VSS.load(RUN); res = VSS.score(R)
    VSS.assign(R, res['L'], res['M'], tol=0.06)          # loose pass with the score mapping, to pair writes and landings
    W = R['W']; L = res['L']
    assert all(w['land'] is not None for w in W)
    k_on = [e for e in L if e[2] == 2 and abs(e[3] - 2400) < 5][0]
    k_off = [e for e in L if e[2] == 2 and e[1] > k_on[1] and abs(e[3]) < 5][0]
    H = np.array([w['h'] for w in W] + [KICK_ON, KICK_OFF]); LF = np.array([w['land'] for w in W] + [k_on[1], k_off[1]])
    h0 = min(w['h'] for w in W)
    bs = np.arange(0.9995, 1.0025, 1e-6)
    spread = np.array([np.ptp(LF - b * (H - h0)) for b in bs]); b = float(bs[np.argmin(spread)])
    A = float(np.min(LF - b * (H - h0)))
    M2 = dict(h0=h0, a=A - (h0 - VSS.GPS_UNIX), b=b)
    VSS.assign(R, L, M2, tol=0.01)
    host_of_fe = lambda fe: h0 + (np.asarray(fe) - A) / b
    on = [w for w in W if w['v'] != 0]; off = [w for w in W if w['v'] == 0]
    P = []
    for x, y in zip(on, off):
        assert x['chan'] == y['chan'] and y['h'] > x['h'] and x['land'] is not None and y['land'] is not None
        P.append(dict(chan=x['chan'], phase=PHASE[x['chan']], level=x['v'], write_on=x['h'], write_off=y['h'],
                      land_on=float(host_of_fe(x['land'])), land_off=float(host_of_fe(y['land'])),
                      rel_delay_ms=1e3 * (x['land'] - x['m']), dur_s=float(y['land'] - x['land'])))
    land = [(float(host_of_fe(e[1])), e[2], e[3]) for e in L]
    info = dict(b=b, b_score=res['M']['b'], spread_ms=1e3 * float(spread.min()), score_unlanded_tol10ms=None,
                kick_delay_ms=[1e3 * float(k_on[1] - (A + b * (KICK_ON - h0))), 1e3 * float(k_off[1] - (A + b * (KICK_OFF - h0)))],
                n_landings=len(L))
    return P, land, info, host_of_fe, M2


class Drive:
    """Electrode voltage (counts) per channel from the OUT_DQ landings, AC-coupled: high-pass with tau 5.57 s."""
    def __init__(self, land):
        self.steps = {c: [] for c in (2, 3, 4)}
        prev = {c: 0.0 for c in (2, 3, 4)}
        for t, c, v in sorted(land):
            self.steps[c].append((t, v - prev[c])); prev[c] = v
        self.steps = {c: np.array(s) for c, s in self.steps.items()}

    def ve(self, c, t):
        t = np.atleast_1d(np.asarray(t, float)); s = self.steps[c]
        x = t[:, None] - s[None, :, 0]
        return np.sum(np.where(x >= 0, s[None, :, 1] * np.exp(-np.clip(x, 0, None) / TAU_AC), 0.0), 1)

    def cmd(self, c, t):
        t = np.atleast_1d(np.asarray(t, float)); s = self.steps[c]
        return np.sum(np.where(t[:, None] >= s[None, :, 0], s[None, :, 1], 0.0), 1)


# ------------------------------------------------------------------------------------------------ shape model
def basis(th, w, sh, ms):
    x = np.radians(th - sh[:, None]); cols = []
    for m in ms:
        cols += [(w * np.cos(m * x)).sum(1), (w * np.sin(m * x)).sum(1)]
    cols.append(np.ones(th.shape[0]))
    return np.column_stack(cols)


def Fpoint(coef, ms, xdeg):
    x = np.radians(np.asarray(xdeg, float)); f = coef[-1] + 0 * x
    for j, m in enumerate(ms):
        f = f + coef[2 * j] * np.cos(m * x) + coef[2 * j + 1] * np.sin(m * x)
    return f


def wrap45(s):
    return (s + 22.5) % 45 - 22.5


def vp(D, ms=(8, 16), grad=False, split=None, fixF=None, fix_shifts=None, x0=None, multistart=True):
    """a_k = S[grp_k] * F(theta - s_q) (pulse-averaged), S[0] = 1. F linear (lstsq), S, s_B, s_C (, kappa) nonlinear."""
    G = D['ngrp']; nsh = 0 if fix_shifts is not None else 2

    def unpack(p):
        S = np.concatenate([[1.0], p[:G - 1]])
        sB, sC = (fix_shifts if fix_shifts is not None else (p[G - 1], p[G]))
        kap = p[G - 1 + nsh] if grad else 0.0
        return S, sB, sC, kap

    def design(p):
        S, sB, sC, kap = unpack(p)
        X = basis(D['th'], D['w'], np.array([0.0, sB, sC])[D['q']], ms)
        if grad:
            X = X * (1 + kap * (D['thm'] - CENTRE) / 50.0)[:, None]
        if split is not None:
            X = np.hstack([X * (~split)[:, None], X * split[:, None]])
        return X * S[D['grp']][:, None]

    def solve(p):
        X = design(p)
        if fixF is not None:
            c = np.asarray(fixF); r = (D['a'] - X @ c) / D['sig']
        else:
            Xw = X / D['sig'][:, None]; c, *_ = np.linalg.lstsq(Xw, D['a'] / D['sig'], rcond=None); r = D['a'] / D['sig'] - Xw @ c
        return c, r, X
    fun = lambda p: solve(p)[1]
    S0 = list(D['S0'][1:])
    if x0 is not None:
        starts = [np.asarray(x0, float)]
    elif fix_shifts is not None or not multistart:
        starts = [np.array(S0 + ([] if fix_shifts is not None else [-16.0, 14.5]) + ([0.0] if grad else []))]
    else:
        g = np.arange(-22.5, 22.5, 7.5)
        starts = [np.array(S0 + [sb, sc] + ([0.0] if grad else [])) for sb in g for sc in g]
    best = None
    for p0 in starts:
        r = least_squares(fun, p0, x_scale=1.0)
        if best is None or r.cost < best.cost:
            best = r
    p = best.x
    c, r, X = solve(p)
    S, sB, sC, kap = unpack(p)
    ncoef = 0 if fixF is not None else X.shape[1]
    npar = (G - 1) + nsh + int(grad) + ncoef
    model = X @ c
    return dict(p=p, S=S, sB=wrap45(sB), sC=wrap45(sC), kap=kap, coef=c, chi2=float(r @ r), n=len(r), npar=npar,
                ndof=len(r) - npar, model=model, resid=D['a'] - model, ms=ms, F800=(X / S[D['grp']][:, None]) @ c)


def set_sigma(D, fitfun, sig_null, iters=4):
    """sigma_k^2 = sig_null_k^2 + (S_k sigma_shape)^2, sigma_shape such that chi2/ndof = 1."""
    ss = 0.05
    for _ in range(iters):
        D['sig'] = np.sqrt(sig_null ** 2 + (D['S0'][D['grp']] * ss) ** 2) if 'S_fit' not in D else \
            np.sqrt(sig_null ** 2 + (D['S_fit'][D['grp']] * ss) ** 2)
        f = fitfun(D)
        D['S_fit'] = f['S']; e = f['resid']; Sk = f['S'][D['grp']]
        g = lambda s: np.sum(e ** 2 / (sig_null ** 2 + (Sk * s) ** 2)) - f['ndof']
        ss = brentq(g, 1e-5, 2.0) if g(1e-5) > 0 else 1e-5
    D['sig'] = np.sqrt(sig_null ** 2 + (D['S_fit'][D['grp']] * ss) ** 2)
    return fitfun(D), ss


def subset(D, idx):
    E = dict(D)
    for k in ('th', 'w', 'q', 'a', 'sig', 'grp', 'thm', 'lev'):
        E[k] = D[k][idx]
    return E


def boot(D, fitkw, best, nb=NBOOT, seed=SEED):
    rng = np.random.default_rng(seed); outp = []
    for _ in range(nb):
        idx = rng.integers(0, len(D['a']), len(D['a']))
        if any(np.sum(D['grp'][idx] == g) < 3 for g in range(D['ngrp'])):
            continue
        f = vp(subset(D, idx), x0=best['p'], **fitkw)
        outp.append(f)
    return outp


def ftest(f0, f1):
    d = f0['chi2'] - f1['chi2']; dp = f1['npar'] - f0['npar']
    F = (d / dp) / (f1['chi2'] / f1['ndof'])
    return dict(dchi2=d, dpar=dp, F=F, p=float(stats.f.sf(F, dp, f1['ndof'])))


def rk4_x(acc, th0, w0, t0, t1, dt=0.002):
    """th'' = acc(t, th) (th in rad), forward from t0. Returns t, th (deg), w."""
    n = int(math.ceil((t1 - t0) / dt)); T = t0 + dt * np.arange(n + 1)
    X = np.empty(n + 1); V = np.empty(n + 1); x, v = th0, w0; X[0], V[0] = x, v
    for i in range(n):
        t = T[i]
        k1x, k1v = v, acc(t, x)
        k2x, k2v = v + 0.5 * dt * k1v, acc(t + 0.5 * dt, x + 0.5 * dt * k1x)
        k3x, k3v = v + 0.5 * dt * k2v, acc(t + 0.5 * dt, x + 0.5 * dt * k2x)
        k4x, k4v = v + dt * k3v, acc(t + dt, x + dt * k3x)
        x += dt / 6 * (k1x + 2 * k2x + 2 * k3x + k4x); v += dt / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)
        X[i + 1], V[i + 1] = x, v
    return T, np.degrees(X), V


def half_amps(t, y):
    tp = B1.turning_points(t, y)
    return np.array([((tp[k, 0] + tp[k + 1, 0]) / 2, abs(tp[k, 1] - tp[k + 1, 1]) / 2, (tp[k, 1] + tp[k + 1, 1]) / 2)
                     for k in range(len(tp) - 1) if tp[k, 2] != tp[k + 1, 2]])


# ------------------------------------------------------------------------------------------------ main
def main():
    os.makedirs(PLOTS, exist_ok=True)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    rng = np.random.default_rng(SEED)
    J = dict(date='2026-11-11', gate='G1 (spin-up)', script='analysis/spinup_g1_20261111/g1_pushmap.py',
             data=dict(dir=DATA, run=RUN, brake=BRAKE, angles=LIVE, camera_csv=CAMCSV))

    t, th, dts, raw = load_angles()
    cs = CubicSpline(t, th)
    say('# Gate G1 push map + voltage scaling, 2026-11-11 (g1_pushmap.py)')
    say(f'angles: live tracker, {len(raw["t"])} frames, host {raw["t"][0]:.2f}..{raw["t"][-1]:.2f}, angle {raw["th"].min():.1f}..'
        f'{raw["th"].max():.1f} deg, ncc median {np.median(raw["ncc"]):.3f} min {raw["ncc"].min():.3f}, '
        f'{(raw["src"] == "blanked").sum()} blanked-source frames (kept, as B1/B2)')
    say(f'  time base: camera clock + median offset; host stamp - mapped: p1..p99 {np.percentile(raw["lag"], 1) * 1e3:.1f}..'
        f'{np.percentile(raw["lag"], 99) * 1e3:.1f} ms, max {raw["lag"].max() * 1e3:.0f} ms (one host stall, not used)')
    say('  re-track check (measured, separate run): frames 0-3999 re-tracked with blob_core -> max |live - retrack| 0.005 deg')

    P, land, tinfo, host_of_fe, M2 = timing()
    drv = Drive(land)
    lev = np.array([p['level'] for p in P]); ph = np.array([p['phase'] for p in P]); q = np.array([QI[x] for x in ph])
    rel = np.array([p['rel_delay_ms'] for p in P])
    say(f'pulses: {len(P)}; per phase x level: ' + ', '.join(f'{x}{int(v)} {np.sum((ph == x) & (lev == v))}' for v in (800, 1600) for x in 'ABC'))
    say(f'  timing: host->FE drift refitted b = {tinfo["b"]:.6f} (score {tinfo["b_score"]:.6f}); write->landing delays span '
        f'{tinfo["spread_ms"]:.1f} ms (one 125 ms tick = consistent); kick on/off delays {tinfo["kick_delay_ms"][0]:.0f}/'
        f'{tinfo["kick_delay_ms"][1]:.0f} ms; step-2 relative delays {rel.min():.0f}..{rel.max():.0f} ms')
    tk = np.array([p['dur_s'] for p in P])
    say(f'  pulse length at OUT_DQ (landing on -> landing off, FE clock): {tk.min():.4f}..{tk.max():.4f} s (measured)')
    # AC-tail factor per pulse
    delta = np.array([float(drv.ve(p['chan'], p['land_on'] - 1e-3)[0]) for p in P])
    kappa2 = ((lev + delta) / lev) ** 2; kappa1 = (lev + delta) / lev
    say(f'  residual AC tail on the pulsed electrode at pulse start: {delta.min():+.0f}..{delta.max():+.0f} counts; '
        f'kappa = ((V+delta)/V)^2 {kappa2.min():.3f}..{kappa2.max():.3f} (V^2 assumed)')

    # ---------------- step-1 reconciliation (pump writes vs landings)
    B = pd.read_csv(BRAKE, comment='#')
    wr = B[B.write_t0.notna()]
    prev = {2: 0.0, 4: 0.0, 3: 0.0}; nchg = 0; nland = 0; merged = []
    lt = {c: np.array([x[0] for x in land if x[1] == c]) for c in (2, 3, 4)}
    lv = {c: np.array([x[2] for x in land if x[1] == c]) for c in (2, 3, 4)}
    wt = wr.write_t0.values
    for i, (_, r) in enumerate(wr.iterrows()):
        nxt = wt[i + 1] if i + 1 < len(wt) else r.write_t0 + 0.4
        for c in (2, 4, 3):
            v = float(r[f'V{c}'])
            if v != prev[c]:
                nchg += 1
                ok = np.any((lt[c] > r.write_t0 - 0.01) & (lt[c] < nxt + 0.13) & (np.abs(lv[c] - v) < 1))
                nland += ok
                if not ok:
                    merged.append((round(r.write_t0 - T0, 3), c, v))
            prev[c] = v
    pump_land = [x for x in land if wt[0] - 0.05 < x[0] < wt[-1] + 1.0]
    say(f'step 1: {len(wr)} pump writes, {nchg} channel-level changes commanded, {nland} seen as OUT_DQ landings, '
        f'{len(merged)} not (superseded within one 8 Hz tick): {merged}; {len(pump_land)} landings in the pump window '
        f'(includes the stop write)')
    J['step1_writes'] = dict(n_writes=len(wr), n_changes=nchg, n_landed=int(nland), not_landed=merged, n_landings_window=len(pump_land))

    # ---------------- 1. joint 2nd-difference fit over the run
    t_run0 = P[0]['land_on'] - 2.5; t_run1 = P[-1]['write_off'] + 6.0; t_free = P[-1]['write_off'] + 20.0
    rm = (t >= t_run0) & (t < t_run1)
    SD = B2.SecondDiff(t[rm], th[rm])
    Xt = SD.trap_cols(nodes=NODES)
    lsq = lambda X, Y: B2.lsq(X, Y, True, PEN, NODES)
    scan = np.arange(-0.10, 0.201, 0.01); chi = []
    for d in scan:
        _, r = lsq(np.hstack([Xt, SD.pulse_cols([p['land_on'] + d for p in P])]), SD.Y); chi.append(float(r @ r))
    chi = np.array(chi); j = int(np.argmin(chi)); jj = slice(max(j - 3, 0), min(j + 4, len(scan)))
    cq = np.polyfit(scan[jj], chi[jj], 2); d_best = float(-cq[1] / (2 * cq[0])) if cq[0] > 0 else float(scan[j])
    pj, rj = lsq(np.hstack([Xt, SD.pulse_cols([p['land_on'] + d_best for p in P])]), SD.Y)
    trap_run = pj[:NODES.size]; a_joint = pj[NODES.size:] * GMEAN / kappa2
    say(''); say('## 1. Joint fit (trap + 50 pulse accelerations), run data')
    say(f'common delay d (field start - landing_host): {1e3 * d_best:.0f} ms; chi2 rise at +-50 ms '
        f'{np.interp(d_best - 0.05, scan, chi) / chi.min() - 1:+.2%} / {np.interp(d_best + 0.05, scan, chi) / chi.min() - 1:+.2%}')
    # between-pulse-only trap (no pulse columns; rows that see a pulse +-0.1 s are dropped)
    mask = np.ones(rm.sum(), bool); tr = t[rm]
    for p in P:
        mask &= ~((tr > p['land_on'] - 0.1) & (tr < p['land_off'] + 0.2))
    SDm = B2.SecondDiff(tr, th[rm], mask=mask); trap_mask, _ = lsq(SDm.trap_cols(nodes=NODES), SDm.Y)
    fm = t >= t_free
    SDf = B2.SecondDiff(t[fm], th[fm]); trap_free, _ = lsq(SDf.trap_cols(nodes=NODES), SDf.Y)
    cov_run = np.histogram(th[rm], bins=np.append(NODES - 1, NODES[-1] + 1))[0]
    cov_free = np.histogram(th[fm], bins=np.append(NODES - 1, NODES[-1] + 1))[0]

    # ---------------- 2. trap comparison
    say(''); say('## 2. Trap (field-off data)')
    b1 = json.load(open(os.path.join(AN, 'brake_b1_20261110', 'trap_b1.json')))
    b2j = json.load(open(os.path.join(B2DIR, 'pushmap_b2.json')))
    gamma = b1['damping']['gamma_per_s']
    other = {'B1 MAIN': (np.array(b1['trap_nodes_deg']), np.array(b1['trap_acc_rad_s2'])),
             'B1 smooth': (np.array(b1['trap_nodes_deg']), np.array(b1['trap_acc_smooth_rad_s2'])),
             'B2 joint (run)': (np.array(b2j['trap_run']['nodes_deg']), np.array(b2j['trap_run']['acc_rad_s2'])),
             'B2 free swing': (np.array(b2j['trap_run']['nodes_deg']), np.array(b2j['trap_run']['acc_free_post_run']))}
    mine = {'G1 joint (run)': trap_run, 'G1 between-pulse (run)': trap_mask, 'G1 free swing (post-run)': trap_free}
    xx = np.arange(192.0, 236.01, 0.5)
    tpf = B1.turning_points(t[fm], th[fm]); swf = B1.swing_summary(tpf)
    say(f'post-run free swing (t >= last write + 20 s): period {swf["period"]:.4f} s, mean max/min {swf["max_mean"]:.2f}/'
        f'{swf["min_mean"]:.2f} deg, {swf["n_per"]} periods')

    def stiff(nn, aa, lo=186.0, hi=240.0):
        """Straight-line fit over the range all traps share: zero, restoring slope k (rad/s^2 per rad), ripple rms about it."""
        x = np.arange(lo, hi + 0.01, 0.5); y = np.interp(x, nn, aa)
        c = np.polyfit(np.radians(x), y, 1)
        return float(math.degrees(-c[1] / c[0])), float(-c[0]), float(np.std(y - np.polyval(c, np.radians(x))))
    trap_tab = {}
    for name, aa in list(mine.items()) + [(k, None) for k in other]:
        nn, a_ = (NODES, aa) if aa is not None else other[name]
        z0, kst, rip = stiff(nn, a_)
        rowd = dict(linfit_186_240=dict(zero_deg=z0, slope_k_rad_s2_per_rad=kst, ripple_rms_rad_s2=rip),
                    rms_vs_G1joint_192_236=float(np.sqrt(np.mean((np.interp(xx, nn, a_) - np.interp(xx, NODES, trap_run)) ** 2))),
                    max_abs_192_236=float(np.max(np.abs(np.interp(xx, nn, a_)))))
        if aa is not None:
            f = lambda x, a_=a_: float(np.interp(x, NODES, a_))
            ts, ys = B1.sim(f, tpf[0, 1], 0.0, t[fm][-1] - tpf[0, 0], gamma=gamma); ts = ts + tpf[0, 0]
            ss = B1.swing_summary(B1.turning_points(ts, ys)); m10 = (t > tpf[0, 0]) & (t < tpf[0, 0] + 10)
            rowd.update(replay_period_err_pct=100 * (ss['period'] / swf['period'] - 1), replay_max=ss['max_mean'], replay_min=ss['min_mean'],
                        replay_rms_first10s=float(np.sqrt(np.mean((np.interp(t[m10], ts, ys) - th[m10]) ** 2))))
        trap_tab[name] = rowd
        say(f'  {name:26s}: line fit 186-240: zero {z0:6.1f} deg, k {kst:5.2f} rad/s^2/rad, ripple rms {rip:.2f}; rms vs G1 joint (192-236) '
            f'{rowd["rms_vs_G1joint_192_236"]:.3f} rad/s^2' + (f'; replay of post-run swing: period {rowd["replay_period_err_pct"]:+.2f} %, '
                                                              f'rms first 10 s {rowd["replay_rms_first10s"]:.2f} deg' if aa is not None else ''))
    say('  (B1/B2 traps are defined only on 184-242 / B1 data range; not replayed on the 180-253 G1 swing)')
    outer = (NODES < 180) | (NODES > 252)
    say(f'  outer nodes (<180, >252; visited only with pulses present): |joint - between-pulse| median '
        f'{np.median(np.abs(trap_run - trap_mask)[outer]):.2f}, max {np.max(np.abs(trap_run - trap_mask)[outer]):.2f} rad/s^2; '
        f'inner 182-250: median {np.median(np.abs(trap_run - trap_mask)[~outer]):.2f}')
    say('  trap table (deg: joint / between-pulse / free / frames run / frames free):')
    for k in range(0, NODES.size, 3):
        say(f'    {NODES[k]:5.0f}: {trap_run[k]:+6.2f} {trap_mask[k]:+6.2f} {trap_free[k]:+6.2f}  {cov_run[k]:5d} {cov_free[k]:5d}')
    trapf = B2.make_trapf(NODES, trap_run); trapf_mask = B2.make_trapf(NODES, trap_mask)

    # ---------------- 3. per-pulse trajectory fits
    say(''); say(f'## 3. Per-pulse trajectory fits (window {WIN} s each side, joint-fit trap)')
    rows = []
    for i, p in enumerate(P):
        lo, hi = B2.windows(P, i)
        B2.PULSE = p['dur_s']          # measured OUT_DQ length (one pulse straddled a tick: 0.375 s); b2 pulse_fit reads this global
        gm = float(np.mean(np.exp(-2 * np.linspace(0, p['dur_s'], 1001, endpoint=False) / TAU_AC)))
        fx = B2.pulse_fit(t, th, trapf, p['land_on'], lo, hi, fix_d=d_best)
        fr = B2.pulse_fit(t, th, trapf, p['land_on'], lo, hi, d0=d_best)
        fmk = B2.pulse_fit(t, th, trapf_mask, p['land_on'], lo, hi, fix_d=d_best)
        B2.PULSE = PULSE
        a_raw = fx['a'] * gm
        rows.append(dict(i=i, phase=p['phase'], chan=p['chan'], level=p['level'], write_on=p['write_on'], land_on=p['land_on'],
                         rel_delay_ms=p['rel_delay_ms'], tail_delta_counts=float(delta[i]), kappa=float(kappa2[i]),
                         theta_mid_deg=fx['th_mid'], omega_mid_rad_s=fx['w_mid'], a_raw_rad_s2=a_raw, a_rad_s2=a_raw / kappa2[i],
                         a_fit_err=fx['a_err_fit'] * gm, dw_rad_s=a_raw * p['dur_s'], a_joint_rad_s2=float(a_joint[i]),
                         d_free_ms=1e3 * fr['d'], rms_deg=fx['rms_deg'], a_between_trap_rad_s2=fmk['a'] * gm / kappa2[i], dur_s=p['dur_s'],
                         sweep_deg=float(np.ptp(cs(p['land_on'] + d_best + np.linspace(0, p['dur_s'], 26))))))
    a = np.array([r['a_rad_s2'] for r in rows]); a_raw = np.array([r['a_raw_rad_s2'] for r in rows])
    aj = np.array([r['a_joint_rad_s2'] for r in rows]); thm = np.array([r['theta_mid_deg'] for r in rows])
    wm = np.array([r['omega_mid_rad_s'] for r in rows])

    # ---------------- 4. null test
    fake = []; tt0 = t_free + WIN + 0.1
    while tt0 < t[-1] - WIN - PULSE - 0.1:
        fake.append(tt0); tt0 += rng.uniform(1.6, 2.4)
    nulls = np.array([B2.pulse_fit(t, th, trapf, f0, f0 - WIN, f0 + PULSE + WIN, fix_d=0.0)['a'] * GMEAN for f0 in fake])
    tff = B2.make_trapf(NODES, trap_free)
    nulls_in = np.array([B2.pulse_fit(t, th, tff, f0, f0 - WIN, f0 + PULSE + WIN, fix_d=0.0)['a'] * GMEAN for f0 in fake])
    sig = float(np.sqrt(np.mean(nulls ** 2)))
    spread = {v: float(np.sqrt(np.mean(((a - aj)[lev == v]) ** 2))) for v in (800, 1600)}
    say(f'null test: {len(nulls)} fake pulses in the post-run swing, run trap: mean {nulls.mean():+.4f}, rms {sig:.4f} rad/s^2 '
        f'(trap fitted on the same data: {np.sqrt(np.mean(nulls_in ** 2)):.4f}); B2 was 0.020')
    say(f'method spread (trajectory vs joint) rms: 800 {spread[800]:.3f}, 1600 {spread[1600]:.3f} rad/s^2; corr {np.corrcoef(a, aj)[0, 1]:.3f}')
    dfree = np.array([r['d_free_ms'] for r in rows]); big = np.abs(a) > 3 * sig
    say(f'per-pulse free delay (|a| > 3 sigma, n {big.sum()}): median {np.median(dfree[big]):+.0f} ms, IQR '
        f'{np.percentile(dfree[big], 25):+.0f}..{np.percentile(dfree[big], 75):+.0f}; corr with time {np.corrcoef(dfree[big], [r["land_on"] for r, b_ in zip(rows, big) if b_])[0, 1]:+.2f}')
    say('per-pulse table (phase, level, t, theta_mid, omega_mid, a [tail-corr], a_raw, joint, kappa, sweep deg, rms deg)')
    for r in rows:
        say(f'  {r["i"]:2d} {r["phase"]} {int(r["level"]):4d} t={r["land_on"] - T0:6.1f} th {r["theta_mid_deg"]:6.1f} w {r["omega_mid_rad_s"]:+.3f} '
            f'a {r["a_rad_s2"]:+.3f} raw {r["a_raw_rad_s2"]:+.3f} joint {r["a_joint_rad_s2"]:+.3f} k {r["kappa"]:.3f} '
            f'sw {r["sweep_deg"]:4.1f} rms {r["rms_deg"]:.3f}')

    # ---------------- 5. shape + scaling fits
    def pulse_samples(Pl, csx, d):
        TH, Wt = [], []
        for p in Pl:
            s = p['land_on'] + d + np.linspace(0, p.get('dur_s', PULSE), 51); g = np.exp(-2 * (s - s[0]) / TAU_AC)
            TH.append(csx(s)); Wt.append(g / g.sum())
        return np.array(TH), np.array(Wt)
    THs, Ws = pulse_samples(P, cs, d_best)
    sig_null = np.full(len(a), sig)
    grp = (lev == 1600).astype(int)
    G1 = dict(th=THs, w=Ws, q=q, a=a, thm=thm, lev=lev, grp=grp, ngrp=2, S0=np.array([1.0, 3.0]))
    # B2 pulses
    t2, th2, _, _ = B1.load(os.path.join(B2DIR, 'rotor_angle_b2.csv'), 0, 'host_time_cam'); cs2 = CubicSpline(t2, th2)
    P2 = b2j['pulses']; d2 = b2j['delay']['common_ms'] / 1e3
    TH2, W2 = pulse_samples(P2, cs2, d2)
    a2 = np.array([p['a_rad_s2'] for p in P2]); q2 = np.array([QI[p['phase']] for p in P2]); thm2 = np.array([p['theta_mid_deg'] for p in P2])
    sig2_null = b2j['per_pulse_sigma_rad_s2']
    b2F = b2j['shared_shape']; F_b2 = np.array([b2F['coef'][k] for k in ('c8', 's8', 'c16', 's16', 'const')])
    s_b2 = (b2F['s_B_deg'], b2F['s_C_deg'])

    say(''); say('## 5. Voltage scaling and shape: a = S(level) F(theta - s_q), S(800) = 1')
    # 5a. main G1 fit
    fitG1 = lambda D: vp(D)
    f_main, ss_main = set_sigma(G1, fitG1, sig_null)
    bt = boot(G1, {}, f_main)
    rat = np.array([b_['S'][1] for b_ in bt]); sBb = np.array([b_['sB'] for b_ in bt]); sCb = np.array([b_['sC'] for b_ in bt])
    pc = lambda x: [float(np.percentile(x, k)) for k in (2.5, 16, 50, 84, 97.5)]
    say(f'G1 joint fit (m = 8+16, shared F, shifts free): S(1600)/S(800) = {f_main["S"][1]:.3f}; bootstrap ({len(bt)}) 68 % '
        f'{pc(rat)[1]:.2f}..{pc(rat)[3]:.2f}, 95 % {pc(rat)[0]:.2f}..{pc(rat)[4]:.2f}')
    say(f'   s_B {f_main["sB"]:+.1f} (68 % {pc(sBb)[1]:+.1f}..{pc(sBb)[3]:+.1f}), s_C {f_main["sC"]:+.1f} (68 % {pc(sCb)[1]:+.1f}..{pc(sCb)[3]:+.1f}) deg; '
        f'sigma_shape {ss_main:.3f} rad/s^2 per unit S; rms residual 800 {np.sqrt(np.mean(f_main["resid"][lev == 800] ** 2)):.3f}, '
        f'1600 {np.sqrt(np.mean(f_main["resid"][lev == 1600] ** 2)):.3f}')
    n_exp = math.log2(f_main['S'][1])
    say(f'   -> exponent n = log2(ratio) = {n_exp:.2f} (68 % {math.log2(pc(rat)[1]):.2f}..{math.log2(pc(rat)[3]):.2f}); '
        f'linear-in-V would be 1, V^2 would be 2')
    # uncorrected (no AC-tail kappa)
    G1u = dict(G1); G1u['a'] = a_raw; G1u.pop('S_fit', None)
    f_unc, _ = set_sigma(G1u, fitG1, sig_null)
    G1l = dict(G1); G1l['a'] = a_raw / kappa1; G1l.pop('S_fit', None)
    f_lin, _ = set_sigma(G1l, fitG1, sig_null)
    say(f'   AC-tail correction: ratio {f_main["S"][1]:.3f} with V^2 kappa, {f_lin["S"][1]:.3f} with linear kappa, {f_unc["S"][1]:.3f} uncorrected')
    a_mk = np.array([r['a_between_trap_rad_s2'] for r in rows])
    outer_p = (thm < 182) | (thm > 250)
    say(f'   trap systematic: per-pulse a with the between-pulse trap differs by rms {np.sqrt(np.mean((a_mk - a)[outer_p] ** 2)):.3f} '
        f'(pulses at <182 / >250 deg, n {outer_p.sum()}), {np.sqrt(np.mean((a_mk - a)[~outer_p] ** 2)):.3f} (others)')
    G1m = dict(G1); G1m['a'] = a_mk; G1m.pop('S_fit', None); f_mk, _ = set_sigma(G1m, fitG1, sig_null)
    G1jj = dict(G1); G1jj['a'] = aj; G1jj.pop('S_fit', None); f_jj, _ = set_sigma(G1jj, fitG1, sig_null)
    say(f'   ratio with a from the between-pulse trap {f_mk["S"][1]:.3f}; with a from the joint 2nd-difference fit {f_jj["S"][1]:.3f}')
    # 5b. B2's F and shifts fixed
    G1f = dict(G1); G1f['ngrp'] = 2
    f_fixB2 = vp(G1f, fixF=F_b2, fix_shifts=s_b2)
    G1f2 = dict(G1); G1f2['grp'] = np.where(lev == 1600, 2, 1); G1f2['ngrp'] = 3; G1f2['S0'] = np.array([1.0, 1.0, 3.0])
    f_fixB2b = vp(G1f2, fixF=F_b2, fix_shifts=s_b2)
    btf = boot(G1f, dict(fixF=F_b2, fix_shifts=s_b2), f_fixB2)
    rf = np.array([b_['S'][1] for b_ in btf])
    say(f'cross-check, F and shifts fixed to B2: S(1600)/S(800=1) = {f_fixB2["S"][1]:.3f} (68 % {pc(rf)[1]:.2f}..{pc(rf)[3]:.2f}); '
        f'with S(800) free too: S(800) = {f_fixB2b["S"][1]:.3f}, S(1600) = {f_fixB2b["S"][2]:.3f}, ratio {f_fixB2b["S"][2] / f_fixB2b["S"][1]:.3f}')
    # 5c. per phase
    Gp = dict(G1); Gp['grp'] = q + 3 * (lev == 1600); Gp['ngrp'] = 6; Gp['S0'] = np.array([1, 1, 1, 3, 3, 3.0]); Gp.pop('S_fit', None)
    Gp['sig'] = G1['sig']
    f_pp = vp(Gp, x0=np.concatenate([[1, 1, 3, 3, 3], [f_main['sB'], f_main['sC']]]))
    btp = boot(Gp, {}, f_pp, nb=NBOOT // 2)
    perphase = {}
    for k, x in enumerate('ABC'):
        rr = np.array([b_['S'][3 + k] / b_['S'][k] for b_ in btp])
        perphase[x] = dict(ratio=float(f_pp['S'][3 + k] / f_pp['S'][k]), S800=float(f_pp['S'][k]), S1600=float(f_pp['S'][3 + k]),
                           r68=[pc(rr)[1], pc(rr)[3]], r95=[pc(rr)[0], pc(rr)[4]])
        say(f'   phase {x}: ratio {perphase[x]["ratio"]:.2f} (68 % {perphase[x]["r68"][0]:.2f}..{perphase[x]["r68"][1]:.2f}); '
            f'S800 {perphase[x]["S800"]:.2f}, S1600 {perphase[x]["S1600"]:.2f} (relative to A at 800)')
    # 5d. G1 vs B2's F
    pred_b2 = (basis(THs, Ws, np.array([0.0, *s_b2])[q], (8, 16)) @ F_b2) * f_main['S'][grp]
    inside = (thm >= 187) & (thm <= 238)
    say(f'G1 pulses vs B2 F (shifts B2, S from G1 fit): rms residual inside 187-238 {np.sqrt(np.mean((a - pred_b2)[inside] ** 2)):.3f} '
        f'(n {inside.sum()}), outside {np.sqrt(np.mean((a - pred_b2)[~inside] ** 2)):.3f} (n {(~inside).sum()}); G1 own fit '
        f'{np.sqrt(np.mean(f_main["resid"][inside] ** 2)):.3f} / {np.sqrt(np.mean(f_main["resid"][~inside] ** 2)):.3f} rad/s^2'
        f'  [residuals are 1600 pulses at full size]')
    # 5e. joint G1 + B2
    GJ = dict(th=np.vstack([THs, TH2]), w=np.vstack([Ws, W2]), q=np.concatenate([q, q2]), a=np.concatenate([a, a2]),
              thm=np.concatenate([thm, thm2]), lev=np.concatenate([lev, np.full(len(a2), 800.0)]),
              grp=np.concatenate([grp, np.full(len(a2), 2)]), ngrp=3, S0=np.array([1.0, 3.0, 1.0]))
    sn_J = np.concatenate([sig_null, np.full(len(a2), sig2_null)])
    f_J, ss_J = set_sigma(GJ, lambda D: vp(D), sn_J)
    GJt = dict(GJ); GJt['grp'] = np.concatenate([grp, np.zeros(len(a2), int)]); GJt['ngrp'] = 2; GJt['S0'] = np.array([1.0, 3.0])
    GJt.pop('S_fit', None); f_Jt, ss_Jt = set_sigma(GJt, lambda D: vp(D), sn_J)
    btJ = boot(GJt, {}, f_Jt)
    rJ = np.array([b_['S'][1] for b_ in btJ]); sBJ = np.array([b_['sB'] for b_ in btJ]); sCJ = np.array([b_['sC'] for b_ in btJ])
    say(f'joint G1 + B2 (B2 tied to S(800) = 1): ratio {f_Jt["S"][1]:.3f} (68 % {pc(rJ)[1]:.2f}..{pc(rJ)[3]:.2f}, 95 % {pc(rJ)[0]:.2f}..{pc(rJ)[4]:.2f}); '
        f's_B {f_Jt["sB"]:+.1f} ({pc(sBJ)[1]:+.1f}..{pc(sBJ)[3]:+.1f}), s_C {f_Jt["sC"]:+.1f} ({pc(sCJ)[1]:+.1f}..{pc(sCJ)[3]:+.1f}); sigma_shape {ss_Jt:.3f}')
    say(f'   B2 amplitude free: S_B2/S_G1(800) = {f_J["S"][2]:.3f}, ratio {f_J["S"][1]:.3f}; chi2 {f_J["chi2"]:.1f} vs tied {f_Jt["chi2"]:.1f} '
        f'(same sigma scale only approximately)')
    cJ = f_Jt['coef']
    P8 = math.hypot(cJ[0], cJ[1]); P16 = math.hypot(cJ[2], cJ[3]); Pb8 = math.hypot(F_b2[0], F_b2[1]); Pb16 = math.hypot(F_b2[2], F_b2[3])
    xg = np.linspace(0, 45, 451)
    say(f'   F(G1+B2): P8 {P8:.3f}, P16 {P16:.3f}, const {cJ[4]:+.3f}, span {Fpoint(cJ, (8, 16), xg).min():+.2f}..{Fpoint(cJ, (8, 16), xg).max():+.2f}; '
        f'B2 F: P8 {Pb8:.3f}, P16 {Pb16:.3f}, span {Fpoint(F_b2, (8, 16), xg).min():+.2f}..{Fpoint(F_b2, (8, 16), xg).max():+.2f} rad/s^2')
    say(f'   F(G1+B2) - F(B2) rms over one period {np.sqrt(np.mean((Fpoint(cJ, (8, 16), xg) - Fpoint(F_b2, (8, 16), xg)) ** 2)):.3f} rad/s^2')
    # 5f. periodicity and shape tests, on the joint data with the tied fit's sigma
    GJt['sig'] = GJt['sig']
    tests = {}
    base = vp(GJt, x0=f_Jt['p'])
    for name, kw in [('m 8+16+24 (45-periodic)', dict(ms=(8, 16, 24))),
                     ('m 4+8+12+16+20 (adds non-45-periodic)', dict(ms=(4, 8, 12, 16, 20))),
                     ('amplitude gradient across theta', dict(grad=True)),
                     ('separate F for theta_mid < 217 / >= 217', dict(split=GJt['thm'] >= CENTRE))]:
        x0 = np.concatenate([f_Jt['p'], [0.0]]) if kw.get('grad') else f_Jt['p']
        f1 = vp(GJt, x0=x0, **kw); ft = ftest(base, f1)
        tests[name] = dict(chi2=f1['chi2'], npar=f1['npar'], **ft, ratio=float(f1['S'][1]), sB=f1['sB'], sC=f1['sC'],
                           kappa=f1['kap'] if kw.get('grad') else None)
        say(f'   {name:42s}: chi2 {base["chi2"]:.1f} -> {f1["chi2"]:.1f} (+{ft["dpar"]} par), F {ft["F"]:.2f}, p {ft["p"]:.3f}; '
            f'ratio {f1["S"][1]:.2f}' + (f', kappa {f1["kap"]:+.3f} per 50 deg' if kw.get('grad') else ''))
    # split fits on G1 alone (shape over the two halves)
    for name, sel in [('G1 theta_mid < 217', thm < CENTRE), ('G1 theta_mid >= 217', thm >= CENTRE),
                      ('G1 outside B2 range', ~inside)]:
        Dh = subset(G1, np.nonzero(sel)[0]); fh = vp(Dh, x0=f_main['p'])
        resid_b2 = a[sel] - (basis(THs[sel], Ws[sel], np.array([0.0, *s_b2])[q[sel]], (8, 16)) @ F_b2) * f_main['S'][grp[sel]]
        say(f'   {name:24s} (n {sel.sum()}): own fit ratio {fh["S"][1]:.2f}, s_B {fh["sB"]:+.1f}, s_C {fh["sC"]:+.1f}, rms {np.sqrt(np.mean(fh["resid"] ** 2)):.3f}; '
            f'rms vs B2 F {np.sqrt(np.mean(resid_b2 ** 2)):.3f}')
        tests[name] = dict(n=int(sel.sum()), ratio=float(fh['S'][1]), sB=fh['sB'], sC=fh['sC'], rms=float(np.sqrt(np.mean(fh['resid'] ** 2))),
                           rms_vs_B2F=float(np.sqrt(np.mean(resid_b2 ** 2))))

    # amplitude-gradient robustness on G1 alone
    for name, D_ in [('G1, trajectory a', G1), ('G1, joint 2nd-diff a', G1jj)]:
        f0 = vp(D_, x0=f_main['p']); f1 = vp(D_, x0=np.concatenate([f_main['p'], [0.0]]), grad=True); ft = ftest(f0, f1)
        tests[f'gradient, {name}'] = dict(kappa=f1['kap'], **ft)
        say(f'   amplitude gradient, {name:22s}: kappa {f1["kap"]:+.3f} per 50 deg, F {ft["F"]:.2f}, p {ft["p"]:.3f}')
    D8 = subset(G1, np.nonzero(lev == 800)[0]); D8['ngrp'] = 1; D8['grp'] = np.zeros(int((lev == 800).sum()), int); D8['S0'] = np.array([1.0])
    f0 = vp(D8); f1 = vp(D8, x0=np.array([f0['sB'], f0['sC'], 0.0]), grad=True); ft = ftest(f0, f1)
    tests['gradient, G1 800 only'] = dict(kappa=f1['kap'], **ft)
    say(f'   amplitude gradient, G1 800 only          : kappa {f1["kap"]:+.3f} per 50 deg, F {ft["F"]:.2f}, p {ft["p"]:.3f}')
    swp = np.array([r['sweep_deg'] for r in rows]); Xb2 = basis(THs, Ws, np.array([0.0, *s_b2])[q], (8, 16)) @ F_b2
    for name, sel in [('slow pulses (sweep < 8 deg)', swp < 8), ('fast pulses (sweep >= 8 deg)', swp >= 8)]:
        fh = vp(subset(G1, np.nonzero(sel)[0]), x0=f_main['p'])
        sl = {v: float(np.sum(Xb2[sel & (lev == v)] * a[sel & (lev == v)]) / np.sum(Xb2[sel & (lev == v)] ** 2)) for v in (800, 1600)}
        bs_ = []
        for _ in range(500):
            ii = rng.choice(np.nonzero(sel)[0], sel.sum())
            bs_.append([np.sum(Xb2[ii][lev[ii] == v] * a[ii][lev[ii] == v]) / np.sum(Xb2[ii][lev[ii] == v] ** 2) for v in (800, 1600)])
        bs_ = np.array(bs_); sl_err = {800: float(np.std(bs_[:, 0])), 1600: float(np.std(bs_[:, 1]))}
        tests[name] = dict(n=int(sel.sum()), ratio=float(fh['S'][1]), slope_vs_B2F=sl, slope_err=sl_err)
        say(f'   {name:28s} (n {sel.sum()}): own-fit ratio {fh["S"][1]:.2f}; regression on B2 F: 800 x{sl[800]:.2f}+-{sl_err[800]:.2f}, '
            f'1600 x{sl[1600]:.2f}+-{sl_err[1600]:.2f} '
            f'(ratio {sl[1600] / sl[800]:.2f})')

    # ---------------- 6. step 1: did the pump raise the energy as the map predicts?
    say(''); say('## 6. Step 1 checks (kick and pump) against the map')
    Uf = lambda x: np.interp(x, NODES, B1.potential(NODES, trap_run))
    thsg = savgol_filter(th, 9, 3); w_meas = np.radians(savgol_filter(th, 9, 3, deriv=1, delta=dts))
    E_meas = 0.5 * w_meas ** 2 + Uf(thsg)
    pw0, pw1 = wr.write_t0.values[0], wr.write_t0.values[-1]
    stop_land = max(x[0] for x in pump_land)
    shapes = {'G1+B2 F': (cJ, f_Jt['sB'], f_Jt['sC']), 'B2 F (used by the pump)': (F_b2, *s_b2)}

    def afield(tq, xdeg, F, sB, sC, n):
        sh = {2: 0.0, 4: sB, 3: sC}
        return sum((np.abs(drv.ve(c, tq)) / 800.0) ** n * Fpoint(F, (8, 16), xdeg - sh[c]) for c in (2, 4, 3))
    ta, tb = pw0 - 0.5, stop_land + 0.8
    sel = (t >= ta) & (t <= tb)
    Ea = float(np.mean(E_meas[(t > ta - 2.0) & (t < ta)])); Eb = float(np.mean(E_meas[(t > tb) & (t < tb + 2.0)]))
    Ea_sd = float(np.std(E_meas[(t > ta - 2.0) & (t < ta)])); Eb_sd = float(np.std(E_meas[(t > tb) & (t < tb + 2.0)]))
    pump = dict(window_host=[ta, tb], E_before=Ea, E_after=Eb, E_sd_before=Ea_sd, E_sd_after=Eb_sd, dE_measured=Eb - Ea, models={})
    amp = half_amps(t, th)
    amp_b = amp[(amp[:, 0] < pw0) & (amp[:, 0] > pw0 - 6)][:, 1].mean(); amp_a = amp[(amp[:, 0] > stop_land + 0.5)][:3, 1].mean()
    say(f'pump: writes {pw0 - T0:.2f}..{pw1 - T0:.2f} s, last landing {stop_land - T0:.2f}; half-amplitude {amp_b:.1f} -> {amp_a:.1f} deg (measured); '
        f'E = w^2/2 + U(theta) (G1 joint trap) {Ea:.3f} (sd {Ea_sd:.3f}) -> {Eb:.3f} (sd {Eb_sd:.3f}) rad^2/s^2, dE {Eb - Ea:+.3f}')
    pump_curves = {}
    for nm, (F, sB, sC) in shapes.items():
        for n in (2.0, n_exp):
            af = afield(t[sel], thsg[sel], F, sB, sC, n)
            pw = np.cumsum(w_meas[sel] * af - gamma * w_meas[sel] ** 2) * dts
            # forward simulation from ta
            i0 = int(np.argmin(np.abs(t - ta)))
            acc = lambda tq, x, F=F, sB=sB, sC=sC, n=n: trapf(x) + float(afield(tq, math.degrees(x), F, sB, sC, n)[0])
            Ts, Ys, Vs = rk4_x(acc, math.radians(thsg[i0]), w_meas[i0], t[i0], tb + 6.0, dt=0.004)
            ams = half_amps(Ts, Ys); amp_sim = ams[ams[:, 0] > stop_land + 0.5][:3, 1].mean() if len(ams) else float('nan')
            key = f'{nm}, n={n:.2f}'
            pump['models'][key] = dict(dE_work_along_measured=float(pw[-1]), sim_half_amp_after=float(amp_sim))
            pump_curves[key] = (t[sel], Ea + pw, Ts, Ys)
            say(f'   {key:34s}: predicted dE (work along the measured path) {pw[-1]:+.3f}; simulated half-amplitude after {amp_sim:.1f} deg')
    # kick
    kl = [x for x in land if x[1] == 2 and abs(x[2] - 2400) < 5][0][0]
    i0 = int(np.argmin(np.abs(t - (kl - 0.5))))
    amp_k = amp[(amp[:, 0] > kl + 4) & (amp[:, 0] < pw0 - 0.5)][:, 1]
    kick = dict(measured_half_amp=float(amp_k.mean()), models={}, traj_scan={})
    mk = (t > kl - 0.5) & (t < kl + 2.0)
    Sgrid = np.arange(2.5, 9.51, 0.5)
    for nm, (F, sB, sC) in shapes.items():
        for mode in ('V2', 'linear, signed'):
            rr = []
            for S_ in Sgrid:
                def acc(tq, x, F=F, S_=S_, mode=mode):
                    v = float(drv.ve(2, tq)[0]) / 2400.0
                    return trapf(x) + (S_ * v * v if mode == 'V2' else S_ * v) * float(Fpoint(F, (8, 16), math.degrees(x)))
                Ts, Ys, _ = rk4_x(acc, math.radians(thsg[i0]), w_meas[i0], t[i0], kl + 2.0, dt=0.004)
                rr.append(float(np.sqrt(np.mean((np.interp(t[mk], Ts, Ys) - th[mk]) ** 2))))
            rr = np.array(rr); jb = int(np.argmin(rr))
            kick['traj_scan'][f'{nm}, {mode}'] = dict(S_grid=Sgrid, rms_deg=rr, S_best=float(Sgrid[jb]), n_implied=math.log(Sgrid[jb], 3))
            say(f'   trajectory during the kick (-0.5..+2.0 s), {nm}, {mode}: rms vs S(2400) ' +
                ' '.join(f'{x_:.1f}:{y_:.1f}' for x_, y_ in zip(Sgrid, rr)) + f' -> best S(2400) {Sgrid[jb]:.1f} (n = {math.log(Sgrid[jb], 3):.2f})')
    say(f'kick (A 2400 counts, 2 s, from rest at {thsg[i0]:.1f} deg): measured half-amplitude after {amp_k.mean():.2f} deg')
    for nm, (F, sB, sC) in shapes.items():
        for n in (1.0, 2.0, n_exp):
            acc = lambda tq, x, F=F, sB=sB, sC=sC, n=n: trapf(x) + float(afield(tq, math.degrees(x), F, sB, sC, n)[0])
            Ts, Ys, _ = rk4_x(acc, math.radians(thsg[i0]), w_meas[i0], t[i0], pw0 - 0.5, dt=0.004)
            ams = half_amps(Ts, Ys); v = ams[ams[:, 0] > kl + 4][:, 1].mean()
            kick['models'][f'{nm}, n={n:.2f}'] = float(v)
            say(f'   {nm}, n={n:.2f} (S(2400) = {3 ** n:.1f}): simulated half-amplitude after the kick {v:.2f} deg '
                '(threshold-like in S: not a clean scaling test)')

    # ---------------- 7. carry estimate (derived)
    say(''); say('## 7. Carry: push needed to beat the trap over 167-267 at slow speed (derived)')
    xc = np.arange(167.0, 267.01, 0.25)
    traps_c = {'G1 joint': trap_run, 'G1 between-pulse': trap_mask}
    def need(F, sB, sC, tr):
        Fq = np.array([Fpoint(F, (8, 16), xc - s) for s in (0.0, sB, sC)])
        Pf = Fq.max(0); Pb = (-Fq).max(0); T_ = np.interp(xc, NODES, tr)
        with np.errstate(divide='ignore', invalid='ignore'):
            Sf = np.where(T_ < 0, -T_ / np.where(Pf > 0, Pf, np.nan), 0.0)
            Sb = np.where(T_ > 0, T_ / np.where(Pb > 0, Pb, np.nan), 0.0)
        return Pf, Pb, Sf, Sb, T_
    Pf, Pb, Sf, Sb, Tc = need(cJ, f_Jt['sB'], f_Jt['sC'], trap_run)
    say(f'best single phase at each angle (800 counts, G1+B2 F): forward push min {Pf.min():.3f} at {xc[np.argmin(Pf)]:.1f} deg, '
        f'backward min {Pb.min():.3f} at {xc[np.argmin(Pb)]:.1f}; any angle with no forward phase: {bool(np.any(Pf <= 0))}')
    Sreq = {}
    for tn, tr in traps_c.items():
        _, _, Sf_, Sb_, T_ = need(cJ, f_Jt['sB'], f_Jt['sC'], tr)
        Sreq[tn] = dict(fwd=float(np.nanmax(Sf_)), fwd_at=float(xc[np.nanargmax(Sf_)]), bwd=float(np.nanmax(Sb_)), bwd_at=float(xc[np.nanargmax(Sb_)]),
                        max_trap=float(np.max(np.abs(T_))))
    # bootstrap of F/shifts for the requirement
    Sbf = []
    for b_ in btJ:
        _, _, Sf_, Sb_, _ = need(b_['coef'], b_['sB'], b_['sC'], trap_run); Sbf.append((np.nanmax(Sf_), np.nanmax(Sb_)))
    Sbf = np.array(Sbf)
    nlo, nhi = math.log2(pc(rJ)[1]), math.log2(pc(rJ)[3]); nJ = math.log2(f_Jt['S'][1])
    def counts(S, n):
        return 800.0 * S ** (1.0 / n)
    carry = dict(S_required=Sreq, S_required_boot68=dict(fwd=[pc(Sbf[:, 0])[1], pc(Sbf[:, 0])[3]], bwd=[pc(Sbf[:, 1])[1], pc(Sbf[:, 1])[3]]),
                 exponent=dict(best=nJ, lo68=nlo, hi68=nhi), counts={})
    for tn in traps_c:
        for dirn in ('fwd', 'bwd'):
            S_ = Sreq[tn][dirn]
            cc = {f'n={n:.2f}': counts(S_, n) for n in (nlo, nJ, nhi, 2.0, 1.0)}
            carry['counts'][f'{tn} {dirn}'] = cc
            say(f'  {tn:17s} {dirn}: S needed {S_:.2f} (worst at {Sreq[tn][dirn + "_at"]:.1f} deg, max |trap| {Sreq[tn]["max_trap"]:.2f}) -> counts '
                + ', '.join(f'{k} {v:.0f}' for k, v in cc.items()))
    say(f'  bootstrap of F/shifts (G1 joint trap): S needed fwd 68 % {carry["S_required_boot68"]["fwd"][0]:.2f}..{carry["S_required_boot68"]["fwd"][1]:.2f}, '
        f'bwd {carry["S_required_boot68"]["bwd"][0]:.2f}..{carry["S_required_boot68"]["bwd"][1]:.2f}')
    say('  limit: V_LIMIT 12800 counts (offset route). Counts -> volts not re-measured here.')
    cover = {}
    for n in (nlo, nJ, nhi, 2.0):
        Smax = 16.0 ** n
        okf = Smax * Pf >= -np.minimum(Tc, 0); okb = Smax * Pb >= np.maximum(Tc, 0)
        cover[f'n={n:.2f}'] = dict(S_at_12800=Smax, frac_fwd=float(okf.mean()), frac_bwd=float(okb.mean()),
                                   fwd_fail_deg=[float(xc[~okf].min()), float(xc[~okf].max())] if (~okf).any() else None)
        say(f'  at 12800 counts, n={n:.2f} (S = {Smax:.1f}): forward push beats the trap on {100 * okf.mean():.0f} % of 167-267, '
            f'backward on {100 * okb.mean():.0f} %' + (f'; forward fails within {xc[~okf].min():.1f}..{xc[~okf].max():.1f}' if (~okf).any() else ''))
    carry['coverage_at_12800'] = cover

    # ---------------- 8. swing amplitude through the run
    say(''); say('## 8. Swing amplitude (turning points)')
    segs = {'pre-kick': amp[:, 0] < KICK_ON, 'after kick, before pump': (amp[:, 0] > kl + 4) & (amp[:, 0] < pw0),
            'run, first 30 s': (amp[:, 0] > P[0]['land_on']) & (amp[:, 0] < P[0]['land_on'] + 30),
            'run, last 30 s': (amp[:, 0] > P[-1]['land_off'] - 30) & (amp[:, 0] < P[-1]['land_off']), 'post-run': amp[:, 0] > t_free}
    amp_summary = {}
    for k, mm in segs.items():
        amp_summary[k] = dict(amp_mean=float(amp[mm, 1].mean()), amp_min=float(amp[mm, 1].min()), amp_max=float(amp[mm, 1].max()),
                              centre=float(amp[mm, 2].mean()), n=int(mm.sum()))
        say(f'  {k:24s}: half-amplitude {amp[mm, 1].mean():.2f} (range {amp[mm, 1].min():.2f}..{amp[mm, 1].max():.2f}) deg, centre {amp[mm, 2].mean():.1f}')
    rr_ = (amp[:, 0] > P[0]['land_on']) & (amp[:, 0] < P[-1]['land_off'])
    say(f'  during step 2: {amp[rr_, 1].min():.1f}..{amp[rr_, 1].max():.1f} deg; tracked angle {th[(t > P[0]["land_on"]) & (t < P[-1]["land_off"])].min():.1f}..'
        f'{th[(t > P[0]["land_on"]) & (t < P[-1]["land_off"])].max():.1f}')
    dE = wm * a_raw * np.array([p['dur_s'] for p in P])
    say(f'  per-pulse w*dw: sum {dE.sum():+.3f} rad^2/s^2; 800: {dE[lev == 800].sum():+.3f}, 1600: {dE[lev == 1600].sum():+.3f}')

    # ================================================================================================ plots
    fig, ax = plt.subplots(2, 1, figsize=(13, 7), sharex=True, gridspec_kw=dict(height_ratios=[3, 1]))
    ax[0].plot(t - T0, th, lw=0.5, color='0.4')
    for p in P:
        ax[0].axvspan(p['land_on'] - T0, p['land_off'] - T0, color=COL[p['phase']], alpha=0.35 if p['level'] == 800 else 0.8, lw=0)
    ax[0].axvspan(kl - T0, kl + 2 - T0, color=COL['A'], alpha=0.2, lw=0); ax[0].axvspan(pw0 - T0, stop_land - T0, color='orange', alpha=0.25, lw=0)
    for x in 'ABC':
        ax[0].plot([], [], color=COL[x], lw=6, alpha=0.8, label=f'{x} pulse (pale 800, dark 1600)')
    ax[0].plot([], [], color='orange', lw=6, alpha=0.3, label='pump'); ax[0].axvline(t_free - T0, color='k', ls=':', lw=0.8)
    ax[0].legend(loc='upper right', ncol=4, fontsize=8); ax[0].set_ylabel('rotor angle (deg)')
    ax[0].set_title('G1: kick, pump (step 1) and 50 pulses (step 2); tracked angle (live tracker, camera clock)', fontsize=10)
    ax[1].plot(amp[:, 0] - T0, amp[:, 1], '.-', ms=3, lw=0.6, color='k'); ax[1].set_ylabel('half-amp (deg)'); ax[1].set_xlabel(f'host time - {T0:.0f} s')
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'g1_angle_vs_time.png'), dpi=130); plt.close(fig)

    # push map per phase, scaled to 800
    xx2 = np.linspace(165, 270, 800)
    fig, axs = plt.subplots(3, 1, figsize=(12, 11), sharex=True)
    S16 = f_Jt['S'][1]
    for k, x in enumerate('ABC'):
        axx = axs[k]; sft = [0.0, f_Jt['sB'], f_Jt['sC']][k]; sb2 = [0.0, *s_b2][k]
        axx.plot(xx2, Fpoint(cJ, (8, 16), xx2 - sft), color=COL[x], lw=1, label='F(theta - s), G1+B2 fit (point value)')
        axx.plot(xx2, Fpoint(F_b2, (8, 16), xx2 - sb2), color='k', lw=0.8, ls='--', alpha=0.6, label='B2 F and shift')
        axx.axvspan(187, 238, color='0.9', zorder=-1, label='B2 coverage')
        m2 = q2 == k
        axx.plot(thm2[m2], a2[m2], '.', color='0.5', ms=5, label='B2 pulses (800)')
        for v, mk, S_ in ((800, 'o', 1.0), (1600, 's', S16)):
            mm = (q == k) & (lev == v)
            axx.errorbar(thm[mm], a[mm] / S_, yerr=G1['sig'][mm] / S_, fmt=mk, color=COL[x], ms=5, mfc='none' if v == 1600 else COL[x], capsize=2,
                         label=f'G1 {v}' + (f' / {S_:.2f}' if v == 1600 else ''))
            jx = np.nonzero(mm)[0]
            axx.plot(thm[jx], basis(THs[jx], Ws[jx], np.array([0.0, f_Jt['sB'], f_Jt['sC']])[q[jx]], (8, 16)) @ cJ,
                     'kx', ms=5)
        axx.plot([], [], 'kx', label='model, averaged over the pulse sweep')
        axx.axhline(0, color='0.7', lw=0.6); axx.set_ylabel('field acc. at 800 counts (rad/s$^2$)')
        axx.set_title(f'phase {x}', fontsize=9); axx.legend(fontsize=7, ncol=4, loc='lower left')
    axs[-1].set_xlabel('rotor angle at mid-pulse (deg)'); axs[-1].set_xlim(165, 270)
    fig.suptitle(f'G1 push map: mean field acceleration per 0.25 s pulse (1600 pulses divided by fitted S = {S16:.2f}); '
                 f'rotor sweeps up to {max(r["sweep_deg"] for r in rows):.0f} deg per pulse, compare dots with crosses', fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'g1_pushmap.png'), dpi=130); plt.close(fig)

    # scaling
    fig, axs = plt.subplots(1, 3, figsize=(16, 4.8))
    F800 = basis(THs, Ws, np.array([0.0, f_main['sB'], f_main['sC']])[q], (8, 16)) @ f_main['coef']
    for v, mk in ((800, 'o'), (1600, 's')):
        for x in 'ABC':
            mm = (lev == v) & (ph == x)
            axs[0].errorbar(F800[mm], a[mm], yerr=G1['sig'][mm], fmt=mk, color=COL[x], ms=5, mfc='none' if v == 1600 else COL[x], capsize=2)
    lim = np.array([-1, 1]) * 0.85
    for s_, ls_, lb in ((1, '-', '1 (800)'), (2, ':', '2 (linear in V)'), (4, '--', '4 (V$^2$)'), (f_main['S'][1], '-', f'fit {f_main["S"][1]:.2f}')):
        axs[0].plot(lim, s_ * lim, ls_, color='k' if lb.startswith('fit') is False else 'm', lw=0.8, label=f'slope {lb}')
    axs[0].set_xlabel('F(theta - s_q) at 800, averaged over the pulse (rad/s$^2$)'); axs[0].set_ylabel('measured a (rad/s$^2$)')
    axs[0].legend(fontsize=7); axs[0].set_title('G1 pulses vs the fitted 800-count shape (open = 1600)', fontsize=9)
    axs[1].hist(rat, bins=30, alpha=0.6, label='G1 alone'); axs[1].hist(rJ, bins=30, alpha=0.6, label='G1 + B2')
    axs[1].hist(rf, bins=30, alpha=0.4, label='B2 F fixed')
    for v_ in (2, 4):
        axs[1].axvline(v_, color='k', ls=':')
    axs[1].set_xlabel('S(1600) / S(800)'); axs[1].legend(fontsize=8); axs[1].set_title('bootstrap over pulses', fontsize=9)
    for k, x in enumerate('ABC'):
        d_ = perphase[x]
        axs[2].errorbar(k, d_['ratio'], yerr=[[d_['ratio'] - d_['r68'][0]], [d_['r68'][1] - d_['ratio']]], fmt='o', color=COL[x], capsize=3)
    axs[2].errorbar(3, f_main['S'][1], yerr=[[f_main['S'][1] - pc(rat)[1]], [pc(rat)[3] - f_main['S'][1]]], fmt='ks', capsize=3)
    axs[2].errorbar(4, f_Jt['S'][1], yerr=[[f_Jt['S'][1] - pc(rJ)[1]], [pc(rJ)[3] - f_Jt['S'][1]]], fmt='kD', capsize=3)
    axs[2].set_xticks(range(5)); axs[2].set_xticklabels(['A', 'B', 'C', 'G1 all', 'G1+B2'])
    for v_ in (2, 4):
        axs[2].axhline(v_, color='k', ls=':', lw=0.8)
    axs[2].set_ylabel('S(1600) / S(800)'); axs[2].set_title('ratio per phase (68 % bootstrap)', fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'g1_scaling.png'), dpi=130); plt.close(fig)

    # trap
    fig, axs = plt.subplots(1, 2, figsize=(15, 5), gridspec_kw=dict(width_ratios=[3, 2]))
    for name, aa in mine.items():
        axs[0].plot(NODES, aa, lw=1.5, label=name)
    for name, (nn, aa) in other.items():
        axs[0].plot(nn, aa, lw=0.8, ls='--', label=name)
    axs[0].axvspan(167, 180, color='0.9', zorder=-1); axs[0].axvspan(253, 267, color='0.9', zorder=-1, label='visited only with pulses')
    axs[0].set_xlim(160, 274); axs[0].set_ylim(-12, 12); axs[0].axhline(0, color='0.7', lw=0.6)
    axs[0].set_xlabel('theta (deg)'); axs[0].set_ylabel('trap acceleration (rad/s$^2$)'); axs[0].legend(fontsize=7)
    ax2 = axs[0].twinx(); ax2.step(NODES, cov_run / 50, where='mid', color='0.6', lw=0.6); ax2.step(NODES, cov_free / 50, where='mid', color='0.8', lw=0.6)
    ax2.set_ylabel('time per 2 deg bin (s): run dark, free light', fontsize=8)
    m10 = (t > tpf[0, 0]) & (t < tpf[0, 0] + 12)
    axs[1].plot(t[m10] - tpf[0, 0], th[m10], 'k.', ms=2, label='measured (post-run)')
    for name, aa in mine.items():
        f = lambda x, aa=aa: float(np.interp(x, NODES, aa))
        ts, ys = B1.sim(f, tpf[0, 1], 0.0, 12.0, gamma=gamma)
        axs[1].plot(ts, ys, lw=0.8, label=f'{name}: period {trap_tab[name]["replay_period_err_pct"]:+.2f} %')
    axs[1].legend(fontsize=7); axs[1].set_xlabel('t from first post-run turning point (s)'); axs[1].set_ylabel('deg')
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'g1_trap.png'), dpi=130); plt.close(fig)

    # pump / kick
    fig, axs = plt.subplots(2, 1, figsize=(12, 8))
    mm = (t > ta - 2) & (t < tb + 2)
    axs[0].plot(t[mm] - T0, E_meas[mm], 'k', lw=0.8, label='measured w$^2$/2 + U(theta)')
    for key, (tt_, ee, _, _) in pump_curves.items():
        axs[0].plot(tt_ - T0, ee, lw=1, label=f'predicted (work along measured path): {key}')
    axs[0].axvspan(pw0 - T0, stop_land - T0, color='orange', alpha=0.15)
    axs[0].set_ylabel('energy (rad$^2$/s$^2$)'); axs[0].legend(fontsize=7); axs[0].set_title('pump (step 1): energy', fontsize=9)
    mm = (t > ta - 1) & (t < tb + 6)
    axs[1].plot(t[mm] - T0, th[mm], 'k', lw=1, label='measured')
    for key, (_, _, Ts, Ys) in pump_curves.items():
        axs[1].plot(Ts - T0, Ys, lw=0.8, label=f'sim: {key}')
    axs[1].set_xlabel(f'host time - {T0:.0f} s'); axs[1].set_ylabel('deg'); axs[1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'g1_pump_check.png'), dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(xc, -Tc, 'k', lw=1.2, label='-trap (G1 joint): push needed forward')
    ax.plot(xc, np.interp(xc, NODES, -trap_mask), 'k--', lw=0.8, label='-trap (between-pulse)')
    for s_, ls_ in ((1, ':'), (S16, '-'), (Sreq['G1 joint']['fwd'], '-')):
        ax.plot(xc, s_ * Pf, ls_, lw=0.9, label=f'best single phase forward x S = {s_:.2f}')
    ax.axhline(0, color='0.7', lw=0.6); ax.set_xlabel('theta (deg)'); ax.set_ylabel('rad/s$^2$'); ax.legend(fontsize=7)
    ax.set_title('carry (derived): forward push available from the best phase vs the trap', fontsize=9)
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'g1_carry.png'), dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(nulls, bins=15, alpha=0.6, label=f'null, rms {sig:.3f}'); ax.hist(a, bins=25, alpha=0.6, label='real pulses (tail-corr)')
    ax.set_xlabel('mean field acc (rad/s$^2$)'); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'g1_null_test.png'), dpi=130); plt.close(fig)

    # ================================================================================================ json
    def fitsum(f):
        return dict(S=f['S'], s_B_deg=f['sB'], s_C_deg=f['sC'], coef=f['coef'], chi2=f['chi2'], ndof=f['ndof'], ms=f['ms'])
    J.update(
        conventions=dict(theta='absolute tracked angle, deg (template zero of 11-06)', a='mean field acceleration over the 0.25 s pulse, rad/s^2, '
                         'B2 definition, divided by kappa (AC-tail start offset, V^2 assumed); a_raw without that',
                         F='a_q(theta) = S(level) * F(theta - s_q), F = c8 cos8x + s8 sin8x + c16 cos16x + s16 sin16x + const, coef in that order',
                         landing_host='host write time + relative landing delay, refitted drift; absolute latency unknown'),
        timing=tinfo | dict(common_delay_ms=1e3 * d_best, per_pulse_delay_median_ms=float(np.median(dfree[big]))),
        null=dict(n=len(nulls), mean=float(nulls.mean()), rms=sig, rms_trap_on_same_data=float(np.sqrt(np.mean(nulls_in ** 2)))),
        method_spread=spread,
        scaling=dict(G1=fitsum(f_main) | dict(sigma_shape=ss_main, ratio=float(f_main['S'][1]), ratio_boot=pc(rat), boot_pct=[2.5, 16, 50, 84, 97.5],
                                                 sB_boot=pc(sBb), sC_boot=pc(sCb), exponent=n_exp),
                     G1_uncorrected_ratio=float(f_unc['S'][1]), G1_linear_kappa_ratio=float(f_lin['S'][1]),
                     B2_shape_fixed=dict(ratio=float(f_fixB2['S'][1]), ratio_boot=pc(rf), S800_free=float(f_fixB2b['S'][1]), S1600=float(f_fixB2b['S'][2])),
                     per_phase=perphase, G1_plus_B2=fitsum(f_Jt) | dict(sigma_shape=ss_Jt, ratio_boot=pc(rJ), sB_boot=pc(sBJ), sC_boot=pc(sCJ)),
                     G1_plus_B2_B2amp_free=fitsum(f_J)),
        shape=dict(B2=dict(coef=F_b2, s_B=s_b2[0], s_C=s_b2[1], P8=Pb8, P16=Pb16), G1_plus_B2=dict(coef=cJ, s_B=f_Jt['sB'], s_C=f_Jt['sC'], P8=P8, P16=P16),
                   tests=tests),
        trap=dict(nodes_deg=NODES, joint_run=trap_run.round(4), between_pulse=trap_mask.round(4), free_post_run=trap_free.round(4),
                  frames_run=cov_run, frames_free=cov_free, comparison=trap_tab, post_run_swing=swf, gamma_assumed_B1=gamma),
        pump=pump, kick=kick, carry=carry, swing=amp_summary,
        pulses=[{k: v for k, v in r.items()} | dict(sigma=float(G1['sig'][r['i']]), resid_G1fit=float(f_main['resid'][r['i']])) for r in rows])

    def conv(o):
        if isinstance(o, dict): return {str(k): conv(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)): return [conv(v) for v in o]
        if isinstance(o, np.ndarray): return conv(o.tolist())
        if isinstance(o, (np.floating,)): return float(o)
        if isinstance(o, (np.integer,)): return int(o)
        if isinstance(o, (np.bool_,)): return bool(o)
        if isinstance(o, float) and not math.isfinite(o): return None
        return o
    json.dump(conv(J), open(os.path.join(HERE, 'pushmap_g1.json'), 'w'), indent=1)
    open(os.path.join(HERE, 'g1_summary.txt'), 'w').write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
