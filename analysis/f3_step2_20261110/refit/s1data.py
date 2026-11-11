"""S1 (2026-11-10) data loader for the refit: tracked angle and the applied field on the camera's host clock."""
import contextlib, io, math, os, sys
import numpy as np
from scipy.signal import savgol_filter

for _p in ('~/Desktop/VSCode/decay_sail_wt_fb/lab_utils', '~/Desktop/VSCode/decay_sail_wt_vs/lab_utils',
           os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'lab_utils')):   # worktrees, else main after merge
    _p = os.path.expanduser(_p)
    if os.path.isdir(_p):
        sys.path.append(_p)
import f3_check as F  # noqa: E402
import f3_step2 as S2  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/voltage_steps/2026-11-10/vsteps_1794345310')
ROT = os.path.join(HERE, '..', '..', 'voltage_steps_20261110_s1', 'rotor', 'rotor_angle_s1.csv')
REST_ABS = 208.6                    # deg, rest before the run (measured)
TAU = 5.57                          # s, AC coupling (S1 scope, measured)
ANG = {2: 0.0, 4: -120.0, 3: -240.0}  # V2, V4, V3 = A, B, C (sim phase angles)
FULL = 4000.0                       # counts for E = 1 (the sim's amp_scale unit)
EQ = S2.equilibrium()               # trap zero in the 11-04 trap's phi
OFF = REST_ABS - EQ                 # absolute angle = OFF + phi_trap


def load():
    import voltage_steps_score as vss
    with contextlib.redirect_stdout(io.StringIO()):
        R = vss.load(D); res = vss.score(R)
    M = res['M']
    host = lambda fe: M['h0'] + (np.asarray(fe) - (M['h0'] - vss.GPS_UNIX) - M['a']) / M['b']   # inverse of fe_of
    L = res['L']
    land = np.array([host(e[1]) for e in L]); ch = np.array([e[2] for e in L]); lev = np.array([e[3] for e in L])
    a = np.genfromtxt(ROT, delimiter=',', names=True, dtype=None, encoding=None)
    t = np.asarray(a['host_time'], float); th = np.degrees(np.unwrap(np.radians(np.asarray(a['angle_deg'], float))))
    blocks = {}
    for r in R['bl']:
        blocks.setdefault(int(r['block']), {})[r['edge']] = float(r['host_a'])
    writes = sorted({(w['h'], w['block']) for w in R['W']})
    return dict(t=t, th=th, land=land, ch=ch, lev=lev, blocks=blocks, pat=R['pat'], rate=R['rate'], writes=writes, M=M)


def levels_at(S, tg, delta=0.0):
    """Per-channel OUT_DQ settled level (counts) at host times tg, field = landing + delta."""
    out = {}
    for c in ANG:
        m = S['ch'] == c
        tl = S['land'][m] + delta; lv = S['lev'][m]
        j = np.searchsorted(tl, tg, side='right') - 1
        out[c] = np.where(j >= 0, lv[np.clip(j, 0, None)], 0.0)
    return out


def hp(x, dt, tau=TAU):
    """One-pole high-pass, as simulate_measured: y = a (y + x - x_prev), a = tau / (tau + dt)."""
    from scipy.signal import lfilter
    a = tau / (tau + dt)
    return lfilter([a, -a], [1.0, -a], x - x[0])


def field(S, tg, delta=0.0, tau=TAU):
    """Balanced field phasor z (E = 1 at 4000 counts) at uniformly spaced host times tg (start well before the run)."""
    lv = levels_at(S, tg, delta); dt = tg[1] - tg[0]
    z = sum(hp(lv[c], dt, tau) * np.exp(-1j * np.radians(ANG[c])) for c in ANG) * 2 / 3 / FULL
    cm = sum(hp(lv[c], dt, tau) for c in ANG) / 3 / FULL       # common mode (assumed no torque; checked)
    return z, cm


def smooth(t, th, win=11, order=3):
    dtm = np.median(np.diff(t))
    tu = np.arange(t[0], t[-1], dtm)
    y = np.interp(tu, t, th)
    return tu, savgol_filter(y, win, order), savgol_filter(y, win, order, deriv=1, delta=dtm), savgol_filter(y, win, order, deriv=2, delta=dtm)


def trap(th_abs_deg, scale=S2.TRAP_S):
    """11-04 trap rescaled (rad/s^2), aligned so its zero sits at the measured rest."""
    return np.array([scale * F.trap_acc(p) for p in np.atleast_1d(th_abs_deg) - OFF])
