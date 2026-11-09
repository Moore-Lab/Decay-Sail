"""Oscillator chirp 2026-11-06: R1 (chirp 0.40 -> 0.15 Hz, amp 6400, from rest) and the free swing after it.

    python3 analyze_r1.py [DATA_DIR]      # default: Dropbox data/osc_chirp/2026-11-06

1. Tracker: angle from rest (rest 229.6, worker2 rest check), 180-deg flips found and repaired (|jump| > 90 deg
   against both neighbours' median; the real swing never exceeds 137 deg from rest).
2. Clock: OUT_DQ (front-end time) -> host time from the DRVON write in each command's log (G0 and R1); the gain ramp
   starts at the next front-end tick after it (EPICS lands on 16 Hz ticks: +-0.06 s).
3. Energy at each turning point E = U(phi_turn) - U(0) (joint trap fit, f3_check.TRAP_CU, measured 11-04), so the
   change per half-swing is the work the drive did (plus damping, small: see 5).
4. Coupling test at amp 6400: per half-swing, measured dE against the work the F3 coupling (COUPLING_HOLD, measured
   at amp 4000) predicts with the measured field: W1 = int w E (c1 cos D + s1 sin D) dt (linear term) and
   W2 = int w E^2 (c2 cos 2D + s2 sin 2D) dt (2x term), E = |field| x 6400/4000, D = psi_field + 8 theta.
   Fit dE = a W1 + b W2: a = b = 1 means the coupling scales as assumed (V and V^2); a = 1/1.6, b = 1/2.56 means
   6400 pushes like 4000.
5. Free swing (drive off): period against amplitude, measured and from the trap model; damping time from the
   energy decay, tau = -<w^2> / (dE/dt) (linear drag; derived).
"""
import csv
import glob
import math
import os
import sys

import numpy as np
from scipy.signal import savgol_filter

_here = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_here, '..', '..', 'lab_utils'), os.path.join(_here, '..', '..', '..', 'decay_sail_wt_fb', 'lab_utils')):
    if os.path.exists(os.path.join(_p, 'f3_check.py')):
        sys.path.insert(0, _p); break
import f3_check as f3  # noqa: E402

D_DEF = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/osc_chirp/2026-11-06')
REST = 229.6
PHI = {'V2': 0.0, 'V4': -120.0, 'V3': -240.0}
TAU_AC = 5.6
DRVON_HOST = {'G0': 1793996500.834, 'R1': 1793996760.573}   # g0.log / r1.log
FREE = (1793997105.209, 1793997705.247)                      # freeswing_times.txt
R1_OFF_HOST = 1793996870.123                                  # r1.log "gains commanded to 0"
EXTRA = 0.10   # s added to the DRVON alignment: next 16 Hz tick (0-0.06) + F3's measured field lag 0.075; scanned below


def load_tracker(d):
    rows = list(csv.DictReader(l for l in open(glob.glob(os.path.join(d, 'blob_live_gps*.csv'))[0]) if not l.startswith('#')))
    t = np.array([float(r['host_time']) for r in rows]); a = np.array([float(r['angle_deg']) for r in rows])
    ncc = np.array([float(r['ncc']) for r in rows])
    phi = ((a - REST + 180) % 360) - 180
    # 180-degree tracker flips: a frame far from both neighbours' median
    med = np.array([np.median(phi[max(0, i - 3):i + 4]) for i in range(phi.size)])
    bad = np.abs(((phi - med + 180) % 360) - 180) > 90
    good = ~bad
    phi_fix = phi.copy(); phi_fix[bad] = np.interp(t[bad], t[good], phi[good])
    return t, phi_fix, ncc, bad


def load_field(d):
    import h5py
    V = {}
    for ch in PHI:
        fn = glob.glob(os.path.join(d, 'session', f'*OUTS_{ch}_OUT_DQ*.h5'))[0]
        with h5py.File(fn, 'r') as h:
            V[ch] = np.asarray(h['data'][:], float); g0 = float(h['segments/gps_start'][0])
    n = min(v.size for v in V.values())
    z = sum(V[k][:n] * np.exp(-1j * np.radians(PHI[k])) for k in PHI) * 2 / 3 / 6400.0
    return g0 + np.arange(n) / 1024.0, z


def onsets(tfe, z):
    a = np.abs(z); on = a > 0.003
    idx = np.flatnonzero(on[1:] & ~on[:-1]) + 1
    keep = []
    for i in idx:                                  # a real burst: |z| > 0.5 within 5 s
        if np.any(a[i:i + 5 * 1024] > 0.5) and (not keep or tfe[i] - tfe[keep[-1]] > 60):
            keep.append(i)
    return [tfe[i] for i in keep]


def hp(z, dt, tau=TAU_AC):
    a = tau / (tau + dt); y = np.zeros_like(z); prev = z[0]
    for i in range(1, z.size):
        y[i] = a * (y[i - 1] + z[i] - prev); prev = z[i]
    return y


def turning_points(t, phi, w):
    i = np.flatnonzero(np.sign(w[1:]) != np.sign(w[:-1])) + 1
    out = []
    for k in i:                                    # keep real extremes (> 3 deg from rest, alternating sign)
        if abs(phi[k]) > 3 and (not out or np.sign(phi[k]) != np.sign(phi[out[-1]])):
            out.append(k)
    return np.array(out, int)


def model_period(E):
    """Free-swing period (s) at energy E (rad^2/s^2) in the joint-fit trap, by integrating dt = dphi / w."""
    ph = np.radians(np.linspace(-179.9, 179.9, 7200))
    U = np.array([f3.trap_U(math.degrees(p)) - f3.trap_U(0.0) for p in ph])
    m = U < E
    if m.all():
        return np.nan
    # the connected region around 0
    i0 = np.argmin(np.abs(ph)); lo = i0; hi = i0
    while lo > 0 and m[lo - 1]:
        lo -= 1
    while hi < ph.size - 1 and m[hi + 1]:
        hi += 1
    v = np.sqrt(2 * np.clip(E - U[lo:hi + 1], 1e-9, None))
    dph = ph[1] - ph[0]
    return 2 * float(np.sum(dph / v))


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else D_DEF
    t, phi, ncc, bad = load_tracker(d)
    print(f'tracker: {t.size} frames; 180-deg flips repaired: {bad.sum()} frames '
          f'(ncc at flips median {np.median(ncc[bad]) if bad.any() else np.nan:.3f}, elsewhere {np.median(ncc[~bad]):.3f})')
    dt = np.median(np.diff(t))
    ps = savgol_filter(phi, 11, 3); w = np.radians(savgol_filter(phi, 11, 3, deriv=1, delta=dt))
    tfe, z = load_field(d)
    on = onsets(tfe, z)
    offs = [DRVON_HOST[k] - fe for k, fe in zip(('G0', 'R1'), on)]
    print(f'clock: host - fe from the DRVON writes: G0 {offs[0]:.3f}, R1 {offs[1]:.3f} s (difference {offs[1] - offs[0]:+.3f} s '
          f'over {DRVON_HOST["R1"] - DRVON_HOST["G0"]:.0f} s)')
    off = offs[1] + EXTRA
    th = tfe + off
    k = 16; m = (th.size // k) * k
    thd = th[:m].reshape(-1, k).mean(1); zd = hp(z[:m].reshape(-1, k).mean(1), k / 1024.0)
    zf = np.interp(t, thd, zd.real) + 1j * np.interp(t, thd, zd.imag)
    r1 = DRVON_HOST['R1']
    # turning points and energies over R1 + the free swing
    sel = (t > r1 - 20) & (t < FREE[1])
    tp = turning_points(t[sel], ps[sel], w[sel]); idx = np.flatnonzero(sel)[tp]
    Et = np.array([f3.trap_U(ps[i]) - f3.trap_U(0.0) for i in idx])
    E_bar = max(f3.trap_U(p) for p in range(-180, 180)) - f3.trap_U(0.0)
    print(f'turning points: {idx.size}; max energy {Et.max():.2f} rad^2/s^2 = {Et.max() / E_bar:.2f} of the barrier {E_bar:.2f}; '
          f'max |angle| {np.max(np.abs(ps[sel])):.0f} deg')
    # coupling test per half-swing while the field is on
    c = f3.COUPLING_HOLD; s = 6400 / 4000
    rows = []
    for i0, i1 in zip(idx[:-1], idx[1:]):
        seg = slice(i0, i1 + 1)
        E = np.abs(zf[seg]) * s
        if np.median(np.abs(zf[seg])) < 0.5:
            continue
        D = np.angle(zf[seg]) + np.radians(8 * (REST + ps[seg]))
        W1 = np.sum(w[seg] * E * (c[1] * np.cos(D) + c[2] * np.sin(D))) * dt
        W2 = np.sum(w[seg] * E * E * (c[3] * np.cos(2 * D) + c[4] * np.sin(2 * D))) * dt
        dE = (f3.trap_U(ps[i1]) - f3.trap_U(ps[i0]))
        rows.append((t[i0] - r1, dE, W1, W2))
    R = np.array(rows)
    X = R[:, 2:4]; Y = R[:, 1]
    ab, *_ = np.linalg.lstsq(X, Y, rcond=None); r2 = 1 - np.var(Y - X @ ab) / np.var(Y)
    for lab, a_, b_ in (('as scaled to 6400 (a = b = 1)', 1, 1), ('as at 4000 (a = 1/1.6, b = 1/2.56)', 1 / 1.6, 1 / 2.56)):
        res = Y - X @ np.array([a_, b_])
        print(f'  dE per half-swing vs coupling {lab}: rms residual {res.std():.2f}, R^2 {1 - np.var(res) / np.var(Y):.2f}')
    se = np.sqrt(np.diag(np.var(Y - X @ ab) * len(Y) / (len(Y) - 2) * np.linalg.inv(X.T @ X)))
    print(f'  free fit (clock +{EXTRA:.2f} s): a {ab[0]:.2f} +- {se[0]:.2f}, b {ab[1]:.2f} +- {se[1]:.2f}, R^2 {r2:.2f}; '
          f'{len(R)} half-swings with the field on; dE std {Y.std():.2f}, mean {Y.mean():+.2f} rad^2/s^2')
    # free swing: period vs amplitude, damping
    fsel = (t[idx] >= FREE[0]) & (t[idx] <= FREE[1])
    fi = idx[fsel]
    halfT = np.diff(t[fi]); Ef = np.array([f3.trap_U(ps[i]) - f3.trap_U(0.0) for i in fi])
    Emid = 0.5 * (Ef[1:] + Ef[:-1])
    gap = np.array([np.max(np.diff(t[a:b + 1])) > 0.2 for a, b in zip(fi[:-1], fi[1:])])   # tracker gaps (2 episodes)
    print(f'free swing: {gap.sum()} half-swings span a tracker gap (> 0.2 s between frames) and are dropped')
    halfT, Emid = halfT[~gap], Emid[~gap]
    ampl = np.array([0.5 * (abs(ps[a]) + abs(ps[b])) for a, b in zip(fi[:-1], fi[1:])])[~gap]
    Tm = np.array([model_period(e) for e in Emid])
    print(f'free swing: {fi.size} turning points; period measured {2 * halfT[:20].mean():.3f} s at E {Emid[:20].mean():.2f} '
          f'-> {2 * halfT[-20:].mean():.3f} s at E {Emid[-20:].mean():.2f}; model {Tm[:20].mean():.3f} -> {Tm[-20:].mean():.3f} s')
    tt = t[fi]; pE = np.polyfit(tt - tt[0], Ef, 1)
    wsel = (t >= FREE[0]) & (t <= FREE[1])
    w2 = np.mean(w[wsel] ** 2)
    tau = -w2 / pE[0]
    print(f'damping: dE/dt {pE[0]:.2e} rad^2/s^3 over the 10 min, <w^2> {w2:.3f} rad^2/s^2 -> tau = I/gamma ~ {tau:.0f} s '
          f'({tau / 60:.0f} min) (derived; linear drag assumed)')
    plot(t, ps, ncc, bad, r1, idx, Et, E_bar, R, ab, zf, ampl, halfT, Tm, fi)


def plot(t, ps, ncc, bad, r1, idx, Et, E_bar, R, ab, zf, ampl, halfT, Tm, fi):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    INK, MUTED, GRID = '#2b2b2b', '#6b6b6b', '#e4e4e0'
    B, O, A = '#2a78d6', '#eb6834', '#1baf7a'
    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED,
                         'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})
    fig = plt.figure(figsize=(10, 12), constrained_layout=True)
    gs = fig.add_gridspec(4, 2, height_ratios=[1.2, 0.9, 0.9, 1.1])
    ax1 = fig.add_subplot(gs[0, :]); ax2 = fig.add_subplot(gs[1, :], sharex=ax1); ax3 = fig.add_subplot(gs[2, :], sharex=ax1)
    ax4 = fig.add_subplot(gs[3, 0]); ax5 = fig.add_subplot(gs[3, 1])
    for a in (ax1, ax2, ax3, ax4, ax5):
        a.grid(True, color=GRID, lw=0.6); a.set_axisbelow(True)
    m = (t > r1 - 20) & (t < r1 + 175); x = t - r1
    ax1.plot(x[m], ps[m], lw=0.6, color=B)
    ax1.axvspan(0, R1_OFF_HOST - r1, color=GRID, alpha=0.5, lw=0)
    ax1.text(2, 150, 'field on', color=MUTED, fontsize=8)
    ax1.set_ylabel('angle from rest, deg'); ax1.set_ylim(-180, 180); ax1.set_yticks([-180, -90, 0, 90, 180])
    ax1.set_title('R1: rotor angle (tracker; two ~2.5 s recording gaps at 137 s and 380 s are bridged)', loc='left', color=INK)
    # frequencies: field, and swing from half-periods
    k = idx[(t[idx] > r1 - 20) & (t[idx] < r1 + 175)]
    fsw = 0.5 / np.diff(t[k]); xs = 0.5 * (t[k][1:] + t[k][:-1]) - r1
    ph = np.unwrap(np.angle(zf)); fz = savgol_filter(np.gradient(ph, t) / (2 * np.pi), 51, 1)
    live = (np.abs(zf) > 0.5) & m
    ax2.plot(x[live], fz[live], lw=1.2, color=O, label='field (drive), measured')
    ax2.plot(xs, fsw, 'o', ms=3.5, color=B, label='swing, from half-periods')
    ax2.set_ylabel('frequency, Hz'); ax2.set_ylim(0.1, 0.45); ax2.legend(loc='upper right', frameon=False)
    ax2.set_title('drive frequency and swing frequency', loc='left', color=INK)
    kk = (t[idx] > r1 - 20) & (t[idx] < r1 + 175)
    ax3.plot(t[idx][kk] - r1, Et[kk] / E_bar, 'o-', ms=3, lw=0.8, color=INK)
    ax3.axhline(1.0, color=O, lw=1, ls='--'); ax3.text(150, 1.02, 'barrier (over the top)', color=O, fontsize=8, ha='right')
    ax3.set_ylabel('energy / barrier'); ax3.set_ylim(0, 1.1); ax3.set_xlabel('time from the drive start (DRVON), s')
    ax3.set_title('energy at each turning point (trap model, measured 11-04)', loc='left', color=INK)
    W = R[:, 2] + R[:, 3]
    ax4.plot(W, R[:, 1], 'o', ms=4, color=B, label='per half-swing')
    lim = max(np.max(np.abs(W)), np.max(np.abs(R[:, 1]))) * 1.1
    ax4.plot([-lim, lim], [-lim, lim], color=O, lw=1, label='coupling scaled to 6400')
    Wl = R[:, 2] / 1.6 + R[:, 3] / 2.56
    ax4.plot(np.sort(W), np.interp(np.sort(W), W[np.argsort(W)], Wl[np.argsort(W)]), color=MUTED, lw=0, marker='')
    ax4.set_xlabel('predicted work, coupling scaled to 6400, rad²/s²'); ax4.set_ylabel('measured ΔE, rad²/s²')
    ax4.set_title(f'drive work per half-swing (fit: a {ab[0]:.2f}, b {ab[1]:.2f})', loc='left', color=INK)
    ax4.legend(loc='upper left', frameon=False)
    from scipy.signal import medfilt
    o = np.argsort(ampl)
    ax5.plot(ampl, 2 * halfT, 'o', ms=2.5, color=B, label='free swing, measured (10 min)')
    ax5.plot(ampl[o], medfilt(Tm[o], 15), color=O, lw=1.5, label='trap model (11-04)')
    ax5.set_xlabel('swing amplitude (mean of the two turning points), deg'); ax5.set_ylabel('period, s')
    ax5.set_ylim(3.0, 4.0)
    ax5.set_title('free swing: period vs amplitude', loc='left', color=INK); ax5.legend(loc='upper left', frameon=False)
    fig.suptitle('Oscillator chirp R1, 2026-11-06: what the swing did', x=0.01, ha='left', fontsize=12, color=INK)
    os.makedirs(os.path.join(_here, 'plots'), exist_ok=True)
    out = os.path.join(_here, 'plots', 'osc_chirp_r1_swing.png'); fig.savefig(out, dpi=200); print('wrote', out)


if __name__ == '__main__':
    main()
