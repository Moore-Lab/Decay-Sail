#!/usr/bin/env python3
"""Speed around a turn, laser on vs off (for the burst / duty-cycle question, 2026-11-22). Measured; Mac only.

(a,b) ND2 run 11-18/19: + coasts, turns averaging 0.435 +- 0.005 Hz, time to cross each 10 deg of rotor angle from the raw
      50 fps tracker angles (as sawtooth_windows.measured_speed_vs_angle), laser-off vs laser-on coasts (ND2, 30.5 uW).
(not plotted) 2026-11-21 damping_1300: laser held at 1300 counts (~8 mW, 16:05-16:21, 0.605 Hz) vs the free coast right after
      laser-off (turns 0.55-0.60 Hz); speed normalised by each turn's mean.
At 8 mW the tracker angle jumps by ~+90 deg at ~55 deg and back at ~140 deg on every turn (laser glare; 964 jumps > 20 deg in
the plateau, 60 % of frames from the 'blanked' path), so laser-on bins 40-150 deg are blanked (grey) in (c,d); the turn time is
unaffected because the angle comes back. Shaded: the laser windows, ASSUMED position (two wings, 74 deg each, face-on at 85/260 deg as in sawtooth_windows.py).
Expected laser kick per pass (D, sawtooth_windows.py, ND1 calibration): 133 uHz per mW-equivalent of 3.08 mW, i.e. ~1.3 uHz
per pass at ND2 and ~350 uHz at 8 mW.
    LASER_DIR=.../2026-11-18/laser python3 ripple_figure.py   # -> plots/ripple_on_off.png, ripple_on_off.json
"""
import glob
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('LASER_DIR', os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-18/laser'))
import angle_profile as A   # noqa: E402
import damping_1300 as DM   # noqa: E402

WINS = [(38.0, 112.0), (213.0, 287.0)]
BIN = 10


def turns_binned(tt, x, f_lo, f_hi):
    """Per-turn speed in each 10-deg bin (Hz), for turns whose mean rate is in [f_lo, f_hi]. -> (n_turns, 36)."""
    marks = np.arange(np.ceil(x[0] / 360) * 360, x[-1], BIN)
    tc = np.interp(marks, x, tt)
    seg = np.diff(tc); nb = 360 // BIN
    out = []
    for i in range(0, len(seg) - nb + 1, nb):
        s = seg[i:i + nb]
        fm = 1 / s.sum()
        if f_lo <= fm <= f_hi:
            out.append(BIN / 360 / s)
    return np.array(out).reshape(-1, nb)


def nd2():
    C = A.C
    k, h, a, n = C.load_tracker(False)
    t_all = k / C.TC.FPS; off = float(np.median(h - t_all))
    acc = {'off': [], 'on': []}
    for p in sorted(glob.glob(os.path.join(C.D, A.RUN, 'coast_O*.txt'))):
        nm = os.path.basename(p)[6:-4]; m = A.meta(p)
        if nm == 'O39' or 'coast_end_host' not in m or m.get('laser') not in acc or int(nm[1:]) % 2 == 0:
            continue
        t0, t1 = m['field_off_host'] + 5 - off, m['coast_end_host'] - 2 - off
        w = (t_all >= t0) & (t_all <= t1)
        acc[m['laser']].append(turns_binned(t_all[w], np.degrees(np.unwrap(np.radians(a[w]))), 0.430, 0.440))
    return {s: np.vstack(v) for s, v in acc.items()}


def mw8():
    h, a, ncc = DM.load()
    out = {}
    for lab, (t0, t1), (lo, hi) in [('on', DM.PLATEAU, (0.60, 0.61)), ('off', (DM.LASER_OFF_HOST + 5, DM.LASER_OFF_HOST + 600), (0.55, 0.60))]:
        w = (h >= t0) & (h <= t1) & (ncc >= 0.5)
        out[lab] = turns_binned(h[w], np.degrees(np.unwrap(np.radians(a[w]))), lo, hi)
    T = out['on'] / out['on'].mean(axis=1, keepdims=True)          # normalise by the true turn mean, then blank the glare bins
    T[:, (np.arange(BIN / 2, 360, BIN) > 40) & (np.arange(BIN / 2, 360, BIN) < 150)] = np.nan
    out['on_norm'] = T
    return out


def stats(T, norm, pre=None):
    y = pre if pre is not None else (T / T.mean(axis=1, keepdims=True) if norm else T)
    return np.nanmean(y, 0), np.nanstd(y, 0, ddof=1) / np.sqrt(len(y))


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    CON, COFF, INK, MUTED, GRID, WIN = '#eb6834', '#2a78d6', '#1f1f1e', '#6b6a63', '#e4e3dd', '#f3d9c9'
    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'xtick.color': MUTED, 'ytick.color': MUTED,
                         'axes.spines.top': False, 'axes.spines.right': False})
    th = np.arange(BIN / 2, 360, BIN)
    D = nd2()
    m_on, e_on = stats(D['on'], False); m_off, e_off = stats(D['off'], False)
    dd = m_on - m_off; de = np.hypot(e_on, e_off)
    fig, ax = plt.subplots(2, 1, figsize=(7.5, 7), sharex=True, gridspec_kw=dict(height_ratios=[1.2, 1]))
    for a_ in ax:
        for lo, hi in WINS:
            a_.axvspan(lo, hi, color=WIN, lw=0, zorder=0)
        a_.grid(True, color=GRID, lw=0.6); a_.set_axisbelow(True)
    ax[0].plot(th, m_off, '-o', color=COFF, ms=3.5, lw=1.6, label=f'laser off ({len(D["off"])} turns)')
    ax[0].plot(th, m_on, '-o', color=CON, ms=3.5, lw=1.6, label=f'laser on, ND2 30.5 µW ({len(D["on"])} turns)')
    ax[0].set_ylabel('speed (Hz)'); ax[0].legend(frameon=False, fontsize=8, loc='upper left')
    ax[0].set_title('(a) speed around one turn: turns averaging 0.435 Hz, + direction, ND2 run 11-18/19', fontsize=9.5, loc='left', color=INK)
    ax[1].errorbar(th, 1e6 * dd, 1e6 * de, fmt='o', color=INK, ms=3.5, lw=1, capsize=0)
    ax[1].axhline(0, color=MUTED, lw=0.8)
    ax[1].set_ylabel('laser on − off (µHz)'); ax[1].set_xlabel('rotor angle (deg, tracker)')
    ax[1].set_title('(b) laser on − off per 10° bin; expected laser kick ~1.3 µHz per pass (too small to see here)',
                    fontsize=9.5, loc='left', color=INK)
    ax[1].set_xticks(range(0, 361, 45)); ax[1].set_xlim(0, 360)
    fig.text(0.01, 0.005, 'Shaded: laser on a wing (two 74° windows; position ASSUMED).\nSpeed = 10° / time to cross it, '
             'raw 50 fps tracker angles; O39 excluded.', fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    p = os.path.join(HERE, 'plots', 'ripple_on_off.png'); fig.savefig(p, dpi=150)
    res = dict(n_on=len(D['on']), n_off=len(D['off']), speed_off_min_max_Hz=[float(m_off.min()), float(m_off.max())],
               diff_rms_uHz=float(1e6 * np.sqrt(np.mean(dd ** 2))), diff_err_median_uHz=float(1e6 * np.median(de)),
               chi2_dof=float(np.mean((dd - dd.mean()) ** 2 / de ** 2)), expected_kick_uHz=1.3)
    json.dump(res, open(os.path.join(HERE, 'ripple_on_off.json'), 'w'), indent=1)
    print(p); print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
