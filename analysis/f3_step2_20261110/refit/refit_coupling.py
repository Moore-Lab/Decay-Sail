#!/usr/bin/env python3
"""Refit the rotor model's field -> torque coupling (and check the trap) on S1, 2026-11-10. Analysis only, Mac.

    python3 refit_coupling.py            # fits, Delta scan, open-loop replays, plots/, refit_coeffs.json, refit_summary.txt

Data (measured): S1 tracked angle (../../voltage_steps_20261110_s1/rotor/rotor_angle_s1.csv, host clock) and the
OUT_DQ settled levels (voltage_steps_score.landings), put on the host clock with the scorer's host->FE map
(inverse of fe_of) + Delta, AC-coupled per channel (tau 5.57 s), balanced phasor z = 2/3 sum V_k e^{-j ang_k} / 4000
(V2, V4, V3 at 0, -120, -240), D = angle(z) + 8 theta_abs. Common mode: assumed no torque (tested, see summary).

Fit (integral form, as analysis/f3_20261104/outdq_replay.py but on segments of every block):
    w(t1) - w(t0) = int_{t0}^{t1} [trap(theta) + coupling(z, theta)] dt
segments bounded by the field landings and cut to <= 0.25 s; w at the ends from a local quadratic (+-0.07 s).
Training: hold block, all3 1/s, 8/s random, the 5 s before the run and the post-run free swing (field off).
Held out: all3 2/s (block 3).

Trap: (a) the 11-04 fit x TRAP_S (f3_step2), its zero put at the 208.6 deg rest (as delay_fit.py), fixed;
      (b) refit: piecewise linear in theta_abs, nodes every 2 deg over 176-252 deg, light 2nd-difference penalty.
Coupling forms (E = |z|, 1 = 4000 counts):
    E1     E (c1 cos D + s1 sin D)                                                (the 1x term alone)
    HOLD   E (c1 cos D + s1 sin D) + E^2 (c2 cos 2D + s2 sin 2D)                  (f3_check form, c0 = 0)
    HOLD0  HOLD + c0 E
    V2     E^2 (c1 cos D + s1 sin D + c2 cos 2D + s2 sin 2D)                      (all ~V^2)
    V2DET  HOLD + E^2 (k0 + a8 cos 8th + b8 sin 8th + a16 cos 16th + b16 sin 16th) (a field-direction-independent
           |z|^2 detent: the V^2 term that does not depend on the field angle, derived for an 8-fold rotor)
Open-loop check: a local copy of simulate_measured's integrator (1 ms Euler, same update order), fed the measured
z(t); checked against f3_check.simulate_measured on the hold block (unit-phasor replay) first.
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s1data as sd  # noqa: E402
F, S2 = sd.F, sd.S2

T0 = 1794345310.15                      # run start (host), for labels only
NODES = np.arange(176.0, 252.01, 2.0)   # trap nodes, deg (refit trap)
PEN = 0.3                               # 2nd-difference penalty weight (rad/s^2 per node, in units of segment dw)
FORMS = ('E1', 'HOLD', 'HOLD0', 'V2', 'V2DET')
PLOTS = os.path.join(HERE, 'plots')


# ------------------------------------------------------------------------------------------------ data + segments
def windows(S):
    """Block windows on the host clock: [first write - 0.5 s, next block's first write - 0.5 s]."""
    first = {}
    for h, b in S['writes']:
        first.setdefault(b, h)
    st = [first[b] - 0.5 for b in sorted(first)]
    W = {'b0 holds': (st[0], st[1]), 'b1 all3 1/s': (st[1], st[2]), 'b2 8/s random': (st[2], st[3]),
         'b3 all3 2/s': (st[3], T0 + 96.0), 'post free': (T0 + 97.0, S['t'][-1] - 1.0), 'pre rest': (st[0] - 6.0, st[0] - 1.0)}
    return W


def omega_at(t, th, tc, h=0.07):
    m = np.abs(t - tc) < h
    if m.sum() < 5:
        return np.nan
    return math.radians(np.polyfit(t[m] - tc, th[m], 2)[1])


def hat(theta_deg):
    """Piecewise-linear basis on NODES, rows = samples."""
    x = np.clip(theta_deg, NODES[0], NODES[-1])
    i = np.clip(np.searchsorted(NODES, x) - 1, 0, len(NODES) - 2)
    f = (x - NODES[i]) / (NODES[i + 1] - NODES[i])
    B = np.zeros((x.size, NODES.size))
    B[np.arange(x.size), i] = 1 - f; B[np.arange(x.size), i + 1] = f
    return B


def cpl_basis(z, th_deg, form, cm=None):
    E = np.abs(z); D = np.angle(z) + 8 * np.radians(th_deg); r = np.radians(th_deg)
    on = E > 1e-4
    E = np.where(on, E, 0.0)
    hold = [E * np.cos(D), E * np.sin(D), E ** 2 * np.cos(2 * D), E ** 2 * np.sin(2 * D)]
    if form == 'E1':
        cols = hold[:2]
    elif form == 'HOLD':
        cols = hold
    elif form == 'HOLD0':
        cols = [E] + hold
    elif form == 'V2':
        cols = [E ** 2 * np.cos(D), E ** 2 * np.sin(D), E ** 2 * np.cos(2 * D), E ** 2 * np.sin(2 * D)]
    elif form == 'V2DET':
        cols = hold + [E ** 2, E ** 2 * np.cos(8 * r), E ** 2 * np.sin(8 * r), E ** 2 * np.cos(16 * r), E ** 2 * np.sin(16 * r)]
    elif form == 'GEN':                      # per-electrode: sum_{j<=k} V_j V_k g_jk(8th) + sum_k V_k h_k(8th), V_k AC-coupled
        V = [cm + np.real(z * np.exp(1j * np.radians(a))) for a in (0.0, -120.0, -240.0)]
        h = [np.ones_like(r), np.cos(8 * r), np.sin(8 * r)]
        cols = [V[j] * V[k] * g for j in range(3) for k in range(j, 3) for g in h] + [V[k] * g for k in range(3) for g in h]
    elif form == 'V2DET+CM':                 # common-mode check: cm^2 detent and cm x balanced cross terms
        cols = (hold + [E ** 2, E ** 2 * np.cos(8 * r), E ** 2 * np.sin(8 * r), E ** 2 * np.cos(16 * r), E ** 2 * np.sin(16 * r)]
                + [cm ** 2, cm ** 2 * np.cos(8 * r), cm ** 2 * np.sin(8 * r), cm * E * np.cos(D), cm * E * np.sin(D)])
    return np.column_stack(cols)


NAMES = {'E1': ['c1', 's1'], 'HOLD': ['c1', 's1', 'c2', 's2'], 'HOLD0': ['c0', 'c1', 's1', 'c2', 's2'], 'V2': ['q1c', 'q1s', 'c2', 's2'],
         'V2DET': ['c1', 's1', 'c2', 's2', 'k0', 'a8', 'b8', 'a16', 'b16']}


def segments(S, delta, wins, maxlen=0.25, minlen=0.06, step=0.002):
    """Rows per segment: (window name, t0, dw, int trap_fixed dt, int hat dt, {form: int basis dt}, mean E)."""
    t, th = S['t'], S['th']
    tg = np.arange(T0 - 40.0, t[-1], 1e-3)
    z, cm = sd.field(S, tg, delta)
    from scipy.signal import savgol_filter
    ths = savgol_filter(th, 7, 2)
    land = np.sort(S['land'] + delta)
    rows = []
    for name, (a, b) in wins.items():
        cuts = [a] + [x for x in land if a < x < b] + [b]
        bnd = []
        for u, v in zip(cuts[:-1], cuts[1:]):
            n = max(1, int(math.ceil((v - u) / maxlen)))
            bnd += list(np.linspace(u, v, n + 1)[:-1])
        bnd.append(b)
        for u, v in zip(bnd[:-1], bnd[1:]):
            if v - u < minlen:
                continue
            w0, w1 = omega_at(t, th, u), omega_at(t, th, v)
            if not (np.isfinite(w0) and np.isfinite(w1)):
                continue
            tt = np.arange(u, v, step) + step / 2
            aa = np.interp(tt, t, ths)
            zz = np.interp(tt, tg, z.real) + 1j * np.interp(tt, tg, z.imag); cc = np.interp(tt, tg, cm)
            rows.append(dict(win=name, t0=u, dw=w1 - w0, trapfix=float(np.sum(sd.trap(aa))) * step,
                             hat=hat(aa).sum(0) * step,
                             cpl={f: cpl_basis(zz, aa, f, cc).sum(0) * step for f in FORMS + ('V2DET+CM', 'GEN')},
                             E=float(np.abs(zz).mean())))
    return rows


# ------------------------------------------------------------------------------------------------ fits
def design(rows, form, trap):
    Y = np.array([r['dw'] for r in rows])
    Xc = np.array([r['cpl'][form] for r in rows])
    if trap == 'fixed':
        return Y - np.array([r['trapfix'] for r in rows]), Xc, None
    return Y, Xc, np.array([r['hat'] for r in rows])


def fit(rows, form, trap):
    """Least squares; refit trap gets a 2nd-difference penalty. Returns coupling c, trap nodes (or None), cov(c)."""
    Y, Xc, Xh = design(rows, form, trap)
    if Xh is None:
        X = Xc
        c, *_ = np.linalg.lstsq(X, Y, rcond=None)
        res = Y - X @ c
        cov = np.var(res) * len(Y) / (len(Y) - X.shape[1]) * np.linalg.pinv(X.T @ X)
        return c, None, cov
    X = np.hstack([Xh, Xc]); nh = Xh.shape[1]
    P = np.zeros((nh - 2, X.shape[1]))
    for i in range(nh - 2):
        P[i, i:i + 3] = [1, -2, 1]
    A = np.vstack([X, PEN * P]); y = np.concatenate([Y, np.zeros(nh - 2)])
    p, *_ = np.linalg.lstsq(A, y, rcond=None)
    res = Y - X @ p
    cov = np.var(res) * len(Y) / max(len(Y) - X.shape[1], 1) * np.linalg.pinv(A.T @ A)
    return p[nh:], p[:nh], cov[nh:, nh:]


def predict(rows, form, trap, c, nodes):
    Y, Xc, Xh = design(rows, form, trap)
    P = Xc @ c + (0 if Xh is None else Xh @ nodes)
    return Y, P


def r2(Y, P):
    return float(1 - np.var(Y - P) / np.var(Y))


def coupling_r2(rows, form, trap, c, nodes):
    """R^2 of the field-on segments' dw left after the trap, explained by the coupling."""
    on = [r for r in rows if r['E'] > 0.02]
    Y, Xc, Xh = design(on, form, trap)
    Yt = Y - (0 if Xh is None else Xh @ nodes)
    return float(1 - np.var(Yt - Xc @ c) / np.var(Yt)), len(on)


# ------------------------------------------------------------------------------------------------ simulation
def trap_fn(nodes):
    if nodes is None:
        return lambda thd: sd.S2.TRAP_S * F.trap_acc(thd - sd.OFF)
    return lambda thd: float(np.interp(thd, NODES, nodes))


def cpl_fn(form, c):
    def f(z, thd):
        E = abs(z)
        if E < 1e-6:
            return 0.0
        return float(cpl_basis(np.array([z]), np.array([thd]), form) @ c)
    return f


def sim(z_of_t, t0, t1, th0, w0, trap, cpl, dt=1e-3, frame=0.02):
    """simulate_measured's integrator: om += (trap + coupling) dt; ph += om dt; output every frame.
    z_of_t: field on a 1 ms grid from t0 (index i). th0 deg abs, w0 deg/s."""
    ph, om = math.radians(th0), math.radians(w0)
    n = int((t1 - t0) / dt); nf = int(round(frame / dt)); out_t, out = [], []
    for i in range(n):
        if i % nf == 0:
            out_t.append(t0 + i * dt); out.append(math.degrees(ph))
        thd = math.degrees(ph)
        z = z_of_t[i]
        tq = cpl(z, thd)
        om += (trap(thd) + tq) * dt
        ph += om * dt
    return np.array(out_t), np.array(out)


class FastCpl:
    """Vectorisable-per-step coupling for speed (same algebra as cpl_basis)."""
    def __init__(self, form, c):
        self.form, self.c = form, np.asarray(c, float)

    def __call__(self, z, thd):
        E = abs(z)
        if E < 1e-4:
            return 0.0
        D = math.atan2(z.imag, z.real) + 8 * math.radians(thd); r = math.radians(thd); c = self.c
        if self.form == 'E1':
            return E * (c[0] * math.cos(D) + c[1] * math.sin(D))
        if self.form == 'HOLD':
            return E * (c[0] * math.cos(D) + c[1] * math.sin(D)) + E * E * (c[2] * math.cos(2 * D) + c[3] * math.sin(2 * D))
        if self.form == 'HOLD0':
            return E * c[0] + E * (c[1] * math.cos(D) + c[2] * math.sin(D)) + E * E * (c[3] * math.cos(2 * D) + c[4] * math.sin(2 * D))
        if self.form == 'V2':
            return E * E * (c[0] * math.cos(D) + c[1] * math.sin(D) + c[2] * math.cos(2 * D) + c[3] * math.sin(2 * D))
        if self.form == 'V2DET':
            return (E * (c[0] * math.cos(D) + c[1] * math.sin(D)) + E * E * (c[2] * math.cos(2 * D) + c[3] * math.sin(2 * D))
                    + E * E * (c[4] + c[5] * math.cos(8 * r) + c[6] * math.sin(8 * r) + c[7] * math.cos(16 * r) + c[8] * math.sin(16 * r)))
        raise ValueError(self.form)


def check_integrator():
    """Our integrator vs f3_check.simulate_measured on the hold block replay (delay_fit.py setup), HOLD coupling,
    11-04 trap x TRAP_S: max |difference| (deg)."""
    S = sd.load()
    ws = sorted({(h, b) for h, b in S['writes'] if b == 0})
    import voltage_steps_score  # noqa: F401  (loaded by sd.load)
    edges = [(h, c, v) for (h, c, v) in [(w[0], None, None) for w in ws]]
    del edges
    # unit-phasor replay of the six hold writes: psi 0 / 120 / 240 for V2 / V4 / V3 at 1200 counts, amp 0.2
    import csv
    wr = [r for r in csv.DictReader(open(os.path.join(sd.D, 'writes.csv'))) if r['block'] == '0']
    tw = np.array([float(r['host_t0']) for r in wr]); t0 = tw[0] - 1.0
    psi = []
    for r in wr:
        v = {c: float(r[f'V{c}']) for c in (2, 4, 3)}
        on = [c for c in v if v[c] > 0]
        psi.append(-sd.ANG[on[0]] % 360 if on else -1.0)
    psi = np.array(psi); T = 25.0; amp = 2 / 3 * 1200 / 4000
    eq = sd.EQ
    t_ref, ph_ref, _, _ = F.simulate_measured(T=T, phi0=eq, w0=0.0, coupling=F.COUPLING_HOLD, amp_scale=amp, write_ms=0.0,
                                              upd_every=0.016, tick_phase=0.0, mtramp=0.0, noise=0.0, rest=sd.OFF,
                                              replay=(tw - t0, psi), trap_scale=S2.TRAP_S, cpl_scale=1.0, tau_ac=5.6)
    # same field, built the way simulate_measured does it (land on the 1 ms grid, AC couple the unit phasor at tau 5.6)
    dt = 1e-3; n = int(T / dt); ang = np.radians([0.0, -120.0, -240.0])
    hp_in = np.zeros(3); hp_out = np.zeros(3); a_hp = 5.6 / (5.6 + dt); xy = np.zeros(2); zs = np.zeros(n, complex); ri = 0
    pend = []
    for i in range(n):
        t = i * dt
        while ri < len(tw) and tw[ri] - t0 <= t:
            p = psi[ri]; ri += 1
            pend.append((math.ceil(t / 0.001) * 0.001, np.zeros(2) if p < 0 else np.array([math.cos(math.radians(p)), math.sin(math.radians(p))])))
        while pend and pend[0][0] <= t:
            xy = pend.pop(0)[1]
        v_in = xy[0] * np.cos(ang) - xy[1] * np.sin(ang)
        hp_out = a_hp * (hp_out + v_in - hp_in); hp_in = v_in
        zs[i] = amp * np.sum(hp_out * np.exp(-1j * ang)) * 2 / 3
    tt, yy = sim(zs, 0.0, T, sd.OFF + eq, 0.0, trap_fn(None), FastCpl('HOLD', [2.42, -1.05, -1.73, 0.25]))
    m = min(len(tt), len(t_ref))
    return float(np.max(np.abs(yy[:m] - (sd.OFF + ph_ref[:m]))))


def replay_block(S, win, delta, trap, cpl, tg, z):
    """Open loop from the tracked state at the window start. Returns frame times, sim angle, tracked angle."""
    from scipy.signal import savgol_filter
    a, b = win
    tu, y, w, _ = sd.smooth(S['t'], S['th'], 15, 3)
    th0 = float(np.interp(a, tu, y)); w0 = float(np.interp(a, tu, w))
    i0 = int(round((a - tg[0]) / 1e-3))
    ts, ys = sim(z[i0:], a, b, th0, w0, trap, cpl)
    return ts, ys, np.interp(ts, S['t'], S['th'])


def swing_stats(t, y):
    """Mean frequency (upward velocity zero crossings) and half peak-to-peak of each swing."""
    from scipy.signal import savgol_filter
    ys = savgol_filter(y, 11, 3) if y.size > 11 else y
    w = np.gradient(ys, t)
    up = np.where((w[:-1] < 0) & (w[1:] >= 0))[0]
    if len(up) < 2:
        return np.nan, np.array([])
    amps = np.array([np.ptp(ys[i:j]) / 2 for i, j in zip(up[:-1], up[1:])])
    per = np.diff(t[up])
    per = per[per > 0.5]                         # ignore noise wiggles
    return (1.0 / np.mean(per) if per.size else np.nan), amps


# ------------------------------------------------------------------------------------------------ main
def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(PLOTS, exist_ok=True)
    out = []
    say = lambda s='': (print(s), out.append(s))
    S = sd.load(); W = windows(S)
    say(f'trap: 11-04 x TRAP_S {S2.TRAP_S:.3f}, zero at {sd.REST_ABS} (phi_trap = theta - {sd.OFF:.2f})')

    # 0. integrator check
    err = check_integrator()
    say(f'integrator check vs f3_check.simulate_measured (hold block, HOLD coupling): max |diff| {err:.2e} deg')

    # 1. trap check: field-off slope near rest vs the hold-block swing frequency
    post = (S['t'] > W['post free'][0]) & (S['t'] < W['post free'][1])
    tu, y, w, acc = sd.smooth(S['t'][post], S['th'][post], 15, 3)
    near = np.abs(y - sd.REST_ABS) < 3.0
    k = -np.polyfit(np.radians(y[near] - sd.REST_ABS), np.radians(acc[near]), 1)[0]
    say(f'field-off stiffness at 208.6 +- 3 deg (post-run free swing, savgol acc): {k:.1f} rad/s^2 -> small-swing '
        f'{math.sqrt(k) / 2 / math.pi:.2f} Hz (derived); 11-04 trap x TRAP_S there: '
        f'{-(sd.trap(sd.REST_ABS + 0.5)[0] - sd.trap(sd.REST_ABS - 0.5)[0]) / math.radians(1):.1f} rad/s^2 '
        f'({math.sqrt(-(sd.trap(sd.REST_ABS + 0.5)[0] - sd.trap(sd.REST_ABS - 0.5)[0]) / math.radians(1)) / 2 / math.pi:.2f} Hz)')
    say(f'post-run free swing (measured): {swing_stats(S["t"][post], S["th"][post])[0]:.3f} Hz, '
        f'range {S["th"][post].min():.1f}..{S["th"][post].max():.1f} deg')

    # 2. Delta scan with the refit trap (V2DET and HOLD forms)
    train_w = {k: v for k, v in W.items() if k != 'b3 all3 2/s'}
    test_w = {'b3 all3 2/s': W['b3 all3 2/s']}
    deltas = np.round(np.arange(-0.08, 0.161, 0.02), 3)
    scan = {}
    for dl in deltas:
        tr = segments(S, dl, {k: v for k, v in train_w.items() if k.startswith('b')})
        te = segments(S, dl, test_w)
        for form in ('HOLD', 'V2DET'):
            scan.setdefault(form, []).append((dl, tr, te))
    # field-off rows do not depend on Delta: compute once
    off_rows = segments(S, 0.0, {k: v for k, v in train_w.items() if not k.startswith('b')})
    curve = {}
    for form in ('HOLD', 'V2DET'):
        rr = []
        for dl, tr, te in scan[form]:
            c, nd, _ = fit(tr + off_rows, form, 'refit')
            Y, P = predict([r for r in tr if r['E'] > 0.02], form, 'refit', c, nd)
            Yt, Pt = predict(te, form, 'refit', c, nd)
            rr.append((dl, float(np.mean((Y - P) ** 2)), r2(Yt, Pt)))
        curve[form] = np.array(rr)
    say('\nDelta scan (refit trap; field-on training segments, mean sq. dw residual; held-out R^2):')
    for form, rr in curve.items():
        say('  ' + form + ': ' + ', '.join(f'{1e3 * d:+.0f} ms {m:.2e}/{h:.3f}' for d, m, h in rr))
    # best Delta by a parabola through the minimum of the V2DET curve
    rr = curve['V2DET']; i = int(np.argmin(rr[:, 1])); j = slice(max(i - 2, 0), i + 3)
    pc = np.polyfit(rr[j, 0], rr[j, 1], 2)
    dbest = float(-pc[1] / 2 / pc[0]) if pc[0] > 0 else float(rr[i, 0])
    # the curve is shallow and has two minima, so quote where the residual is within 10 % of its minimum
    fine = np.linspace(rr[0, 0], rr[-1, 0], 2001); cf = np.interp(fine, rr[:, 0], rr[:, 1] / rr[:, 1].min())
    ok = fine[cf <= 1.10]
    say(f'  lowest training residual at Delta {1e3 * dbest:+.0f} ms (V2DET, parabola), second minimum near -30 ms; residual '
        f'within 10 % of the minimum over {1e3 * ok.min():+.0f}..{1e3 * ok.max():+.0f} ms; held-out R^2 varies only '
        f'{rr[:, 2].min():.3f}..{rr[:, 2].max():.3f}: Delta is NOT well determined by this fit (mapping block residual 14 ms)')

    DL = float(np.round(dbest, 3))
    tr = segments(S, DL, {k: v for k, v in train_w.items() if k.startswith('b')}) + off_rows
    te = segments(S, DL, test_w)
    say(f'\nfits at Delta {1e3 * DL:+.0f} ms: {len(tr)} training segments ({sum(r["E"] > 0.02 for r in tr)} field-on), '
        f'{len(te)} held-out (all3 2/s)')
    say('| trap | form | R^2 train (all dw) | coupling R^2 (field-on, after trap) | held-out R^2 (coupling R^2) | coefficients +- 1 sigma |')
    say('|---|---|---|---|---|---|')
    res = {}
    for trap in ('fixed', 'refit'):
        for form in FORMS:
            c, nd, cov = fit(tr, form, trap)
            Y, P = predict(tr, form, trap, c, nd); Yt, Pt = predict(te, form, trap, c, nd)
            cr2, non = coupling_r2(tr, form, trap, c, nd)
            se = np.sqrt(np.diag(cov))
            res[(trap, form)] = dict(c=c, nodes=nd, se=se, r2=r2(Y, P), r2c=cr2, r2t=r2(Yt, Pt))
            say(f'| {trap} | {form} | {r2(Y, P):.3f} | {cr2:.3f} | {r2(Yt, Pt):.3f} ({coupling_r2(te, form, trap, c, nd)[0]:.2f}) | '
                + ', '.join(f'{n} {v:+.2f}+-{s:.2f}' for n, v, s in zip(NAMES[form], c, se)) + ' |')
    # trap-only (no coupling) and common-mode check
    for trap in ('refit',):
        Y, Xc, Xh = design(tr, 'HOLD', trap)
        c0, nd0, _ = fit(tr, 'HOLD', trap)
        Ytt, Ptt = predict(te, 'HOLD', trap, 0 * c0, nd0)
        say(f'  (refit trap with the coupling zeroed, same nodes: held-out R^2 {r2(Ytt, Ptt):.3f}: the trap alone)')
    c, nd, _ = fit(tr, 'V2DET+CM', 'refit')
    Y, P = predict(tr, 'V2DET+CM', 'refit', c, nd); Yt, Pt = predict(te, 'V2DET+CM', 'refit', c, nd)
    say(f'  common-mode check, V2DET + cm^2 detent + cm x E cross terms: train R^2 {r2(Y, P):.3f}, held-out {r2(Yt, Pt):.3f}; '
        f'cm coefs {np.round(c[-5:], 2).tolist()}')

    # consistency: per-block coupling (trap fixed at the all-data refit), and leave-one-block-out
    blk = {k: [r for r in tr if r['win'] == k] for k in W if k.startswith('b') and k != 'b3 all3 2/s'}
    blk['b3 all3 2/s'] = te
    allr = tr + te
    c_all, nd_all, _ = fit(allr, 'HOLD', 'refit')
    say('\nper-block HOLD coupling on the residual after the all-data refit trap (field-on segments; +- 1 sigma):')
    for k, rows in blk.items():
        on = [r for r in rows if r['E'] > 0.02]
        Y = np.array([r['dw'] for r in on]) - np.array([r['hat'] for r in on]) @ nd_all
        X = np.array([r['cpl']['HOLD'] for r in on])
        cc, *_ = np.linalg.lstsq(X, Y, rcond=None); rs = Y - X @ cc
        se = np.sqrt(np.diag(np.var(rs) * len(Y) / (len(Y) - 4) * np.linalg.pinv(X.T @ X)))
        say(f'  {k}: {len(on)} segs, R^2 {1 - np.var(rs) / np.var(Y):.2f}, c1 {cc[0]:+.2f}+-{se[0]:.2f} s1 {cc[1]:+.2f}+-{se[1]:.2f} '
            f'c2 {cc[2]:+.1f}+-{se[2]:.1f} s2 {cc[3]:+.1f}+-{se[3]:.1f}; 1x amplitude {math.hypot(cc[0], cc[1]):.2f} at '
            f'{math.degrees(math.atan2(cc[1], cc[0])):+.0f} deg')
    say('leave-one-block-out (train on the other blocks + field-off; R^2 of the held-out block, total / coupling after trap):')
    for k in blk:
        trk = sum([blk[j] for j in blk if j != k], []) + [r for r in tr if not r['win'].startswith('b')]
        cells = []
        c0_, nd0_, _ = fit(trk, 'HOLD', 'refit'); Yt, Pt = predict(blk[k], 'HOLD', 'refit', 0 * c0_, nd0_)
        cells.append(f'trap only {r2(Yt, Pt):.3f}')
        for form in ('E1', 'HOLD', 'V2DET', 'GEN'):
            cc, ndd, _ = fit(trk, form, 'refit'); Yt, Pt = predict(blk[k], form, 'refit', cc, ndd)
            cells.append(f'{form} {r2(Yt, Pt):.3f}/{coupling_r2(blk[k], form, "refit", cc, ndd)[0]:+.2f}')
        say(f'  {k}: ' + ', '.join(cells))

    tr0 = segments(S, 0.0, {k: v for k, v in train_w.items() if k.startswith('b')}) + off_rows
    c_d0, nd_d0, se_d0 = fit(tr0, 'HOLD', 'refit')
    say(f'  Delta sensitivity: refit trap + HOLD at Delta 0: {np.round(c_d0, 2).tolist()} (at {1e3 * DL:+.0f} ms: '
        f'{np.round(res[("refit", "HOLD")]["c"], 2).tolist()})')
    tu_, y_, w_, acc_ = sd.smooth(S['t'], S['th'], 15, 3)
    mb = (tu_ > W['b1 all3 1/s'][0]) & (tu_ < W['b1 all3 1/s'][1]) & (y_ > 212) & (y_ < 222)
    exc = np.radians(acc_[mb]) - np.interp(y_[mb], NODES, res[('refit', 'HOLD')]['nodes'])
    say(f'  all3 1/s frames at 212-222 deg: acceleration minus refit trap {np.mean(exc):+.2f} rad/s^2 (std {np.std(exc):.2f}, '
        f'n {mb.sum()}); per unit E (0.173): {np.mean(exc) / 0.173:+.1f}')

    # size of the coupling vs the trap at E ~ 0.17 (all3 level)
    best = res[('refit', 'V2DET')]
    th_grid = np.linspace(185, 245, 241)
    Dg = np.radians(np.linspace(-180, 180, 73))
    cp = [FastCpl('V2DET', best['c'])(0.173 * complex(math.cos(d), math.sin(d)), thv) for thv in th_grid[::10] for d in Dg]
    say(f'  coupling rms at E 0.173 over field angle and 185-245 deg: {np.std(cp):.2f} rad/s^2; '
        f'refit trap rms over 198-234: {np.std(np.interp(np.linspace(198, 234, 100), NODES, best["nodes"])):.2f} rad/s^2')

    # 3. open-loop replays per block
    tg = np.arange(T0 - 40.0, S['t'][-1], 1e-3)
    z, _ = sd.field(S, tg, DL)
    blocks = ['b0 holds', 'b1 all3 1/s', 'b2 8/s random', 'b3 all3 2/s', 'post free']
    models = {'11-04 HOLD (as step 2)': (trap_fn(None), FastCpl('HOLD', [2.42, -1.05, -1.73, 0.25])),
              'fixed trap + HOLD refit': (trap_fn(None), FastCpl('HOLD', res[('fixed', 'HOLD')]['c'])),
              'refit trap + HOLD refit': (trap_fn(res[('refit', 'HOLD')]['nodes']), FastCpl('HOLD', res[('refit', 'HOLD')]['c'])),
              'refit trap + V2DET': (trap_fn(best['nodes']), FastCpl('V2DET', best['c'])),
              'refit trap + E1': (trap_fn(res[('refit', 'E1')]['nodes']), FastCpl('E1', res[('refit', 'E1')]['c'])),
              'refit trap, no field': (trap_fn(res[('refit', 'HOLD')]['nodes']), FastCpl('HOLD', [0, 0, 0, 0]))}
    say('\nopen-loop replay from the tracked state at each block start (rms deg over the block; first 5 s in brackets):')
    say('| model | ' + ' | '.join(blocks) + ' |'); say('|---' * (len(blocks) + 1) + '|')
    rep = {}
    for mn, (tf, cf) in models.items():
        cells = []
        for bn in blocks:
            ts, ys, yt = replay_block(S, W[bn], DL, tf, cf, tg, z)
            rep[(mn, bn)] = (ts, ys, yt)
            e = ys - yt; f5 = ts < ts[0] + 5
            cells.append(f'{np.sqrt(np.mean(e ** 2)):.1f} ({np.sqrt(np.mean(e[f5] ** 2)):.1f})')
        say(f'| {mn} | ' + ' | '.join(cells) + ' |')
    say('\nswing frequency (Hz) and amplitude (half p-p, deg, first 3 / last 3 swings), tracked vs sim:')
    hold_win = (W['b0 holds'][0] + 1.0, W['b0 holds'][1])
    for bn in ('b0 holds', 'b1 all3 1/s', 'b2 8/s random', 'b3 all3 2/s', 'post free'):
        ts, ys, yt = rep[('refit trap + V2DET', bn)]
        m = ts > ts[0] + (1.0 if bn == 'b0 holds' else 0.0)
        ft, at = swing_stats(ts[m], yt[m])
        line = f'  {bn}: tracked {ft:.2f} Hz, amp {np.round(at[:3], 1).tolist()} .. {np.round(at[-3:], 1).tolist()}'
        for mn in ('11-04 HOLD (as step 2)', 'refit trap + E1', 'refit trap + HOLD refit', 'refit trap + V2DET', 'refit trap, no field'):
            ts, ys, yt = rep[(mn, bn)]
            fs_, as_ = swing_stats(ts[m], ys[m])
            line += f' | {mn}: {fs_:.2f} Hz, {np.round(as_[:3], 1).tolist()} .. {np.round(as_[-3:], 1).tolist()}'
        say(line)

    # 4. first hold edge onset vs Delta with the best model (sim rms over the first 1.5 s after the first landing)
    first_land = float(np.min(S['land']))
    say('\nfirst hold edge, open loop from rest, rms (deg) over [landing - 0.3 s, + 1.5 s] by Delta (refit trap + V2DET):')
    line = []
    for dl in np.round(np.arange(-0.06, 0.121, 0.02), 3):
        zz, _ = sd.field(S, tg, dl)
        a, b = first_land - 0.3, first_land + 1.5
        i0 = int(round((a - tg[0]) / 1e-3))
        ts, ys = sim(zz[i0:], a, b, sd.REST_ABS, 0.0, trap_fn(best['nodes']), FastCpl('V2DET', best['c']))
        line.append(f'{1e3 * dl:+.0f}: {np.sqrt(np.mean((ys - np.interp(ts, S["t"], S["th"])) ** 2)):.2f}')
    say('  ' + ', '.join(line))

    # JSON
    js = dict(
        date='2026-11-10', data='S1 vsteps_1794345310, rotor_angle_s1.csv', delta_s=DL, delta_range_s=[float(ok.min()), float(ok.max())],
        conventions=dict(E='|z|, z = 2/3 sum_k V_k exp(-j ang_k) / 4000 counts, AC-coupled per channel tau 5.57 s; '
                         'ang V2 0, V4 -120, V3 -240 deg', D='angle(z) + 8 * theta_abs (rad), theta_abs = tracked angle '
                         '(template zero of 11-06), rest 208.6 deg', trap='acc (rad/s^2) vs theta_abs (deg), linear '
                         'interpolation; valid ~198-234 (field-off data), 184-246 (field-on only), not outside',
                         simulate_measured='HOLD form plugs into f3_check.simulate_measured with coupling=[0,c1,s1,c2,s2], '
                         'amp_scale = E at the drive level (1200 counts on one electrode: 0.2), rest = theta_abs of the '
                         "sim's phi = 0 (sim absolute angle = rest + phi); V2DET and the refit trap do not fit its signature"),
        trap_nodes_deg=NODES.tolist(),
        trap_acc_canonical=dict(source='refit/HOLD fit (joint with the HOLD coupling); use this one',
                                acc_rad_s2=np.round(res[('refit', 'HOLD')]['nodes'], 4).tolist(),
                                valid_deg=[198, 234], field_on_only_deg=[184, 246]),
        hold_at_delta0=dict(c=np.round(c_d0, 4).tolist(), names=NAMES['HOLD']),
        warning='quadratic (E^2) coefficients measured only at E <= 0.2 (1200 counts); not usable at higher drive; '
                'the 2x term varies between blocks (see README)',
        fits={f'{t}/{f}': dict(names=NAMES[f], c=np.round(v['c'], 4).tolist(), se=np.round(v['se'], 4).tolist(),
                               r2_train=round(v['r2'], 4), r2_coupling=round(v['r2c'], 4), r2_heldout=round(v['r2t'], 4),
                               trap_acc_nodes=None if v['nodes'] is None else np.round(v['nodes'], 4).tolist())
              for (t, f), v in res.items()})
    json.dump(js, open(os.path.join(HERE, 'refit_coeffs.json'), 'w'), indent=1)
    open(os.path.join(HERE, 'refit_summary.txt'), 'w').write('\n'.join(out) + '\n')

    # plots
    fig, ax = plt.subplots(1, 2, figsize=(15, 5))
    tu, y, w, acc = sd.smooth(S['t'], S['th'], 15, 3)
    for bn, col in zip(blocks, ('C0', 'C1', 'C2', 'C3', 'k')):
        m = (tu > W[bn][0]) & (tu < W[bn][1])
        ax[0].plot(y[m], np.radians(acc[m]), '.', ms=1, color=col, label=bn)
    ax[0].plot(NODES, best['nodes'], 'r-', lw=2, label='refit trap (V2DET fit)')
    ax[0].plot(NODES, res[('refit', 'HOLD')]['nodes'], 'm--', lw=1, label='refit trap (HOLD fit)')
    ax[0].plot(NODES, sd.trap(NODES), 'b-', lw=1.5, label='11-04 trap x TRAP_S, zero at 208.6')
    ax[0].set_xlim(178, 250); ax[0].set_ylim(-4, 4); ax[0].grid(); ax[0].legend(fontsize=7)
    ax[0].set_xlabel('tracked angle (deg)'); ax[0].set_ylabel('angular acceleration (rad/s^2, savgol 0.3 s)')
    ax[0].set_title('trap: measured acceleration vs angle (field on and off) and fits')
    for form, rr in curve.items():
        ax[1].plot(1e3 * rr[:, 0], rr[:, 1] / rr[:, 1].min(), 'o-', label=f'{form}: training residual (rel.)')
        ax[1].plot(1e3 * rr[:, 0], rr[:, 2], 's:', label=f'{form}: held-out R^2')
    ax[1].axvline(1e3 * DL, color='grey', ls='--'); ax[1].set_xlabel('Delta (ms)'); ax[1].grid(); ax[1].legend(fontsize=7)
    ax[1].set_title('Delta scan (refit trap)')
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'trap_and_delta.png'), dpi=110); plt.close(fig)

    fig, ax = plt.subplots(len(blocks), 1, figsize=(15, 3.2 * len(blocks)))
    for k, bn in enumerate(blocks):
        ts, ys, yt = rep[('refit trap + V2DET', bn)]
        ax[k].plot(ts - T0, yt, 'k', lw=1.2, label='tracked')
        for mn, col in (('11-04 HOLD (as step 2)', 'C0'), ('refit trap + E1', 'C1'), ('refit trap + HOLD refit', 'C2'), ('refit trap + V2DET', 'C3'),
                        ('refit trap, no field', 'C7')):
            ts, ys, _ = rep[(mn, bn)]
            ax[k].plot(ts - T0, ys, color=col, lw=0.9, label=mn)
        ax[k].set_title(bn + (' (held out)' if bn.startswith('b3') else '')); ax[k].set_ylabel('deg'); ax[k].grid()
        if bn == 'post free':
            ax[k].set_xlim(ts[0] - T0, ts[0] - T0 + 30)
        ax[k].legend(fontsize=7, ncol=5)
    ax[-1].set_xlabel('s from run start (host)')
    fig.tight_layout(); fig.savefig(os.path.join(PLOTS, 'replay_blocks.png'), dpi=90); plt.close(fig)
    say(f'\nplots: {PLOTS}/trap_and_delta.png, {PLOTS}/replay_blocks.png; coefficients: {HERE}/refit_coeffs.json')
    open(os.path.join(HERE, 'refit_summary.txt'), 'w').write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
