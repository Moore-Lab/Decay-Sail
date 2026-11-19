#!/usr/bin/env python3
"""ND4 night 2026-11-16/17 (night_nd4_il2): gamma per coast from the LES vs from the tracker, laser on and off. (2026-11-19)
A second, camera-free readout of the rotation rate (the 405 nm beam was on that night), to check that the 660 nm laser
does not bias the tracker's gamma. Mac only; reads Dropbox spinup/2026-11-16/laser/{les,night_nd4_il2} and
coasts_table.csv (tracker gamma, from coasts.py).

    python3 les_vs_tracker.py      # prints; les_vs_tracker.csv; plots/les_vs_tracker_nd4.png (gitignored)
    RUNS=off1,on LESDIR=les_nd1 LABEL='ND1 pairs 16 Nov' python3 les_vs_tracker.py    # blocked vs ND1 single pairs

LES: PIT and YAW _OUT_DQ, 1024 Hz, front-end clock; coast windows from each coast file (fe_gps_field_off + 5 s to
fe_gps_coast_end - 2 s). Rate per 40 s window every 10 s from the line at 2x the rotation rate (CLAUDE.md), as
analysis/overnight_20261114/les_coasts.py (functions imported); channel with the higher median line SNR.
gamma at 0.435 Hz from the same quadratic fit in log f over 0.40-0.47 Hz as the tracker (pair_plots.gamma_mid);
LES error from a 10-block jackknife (the windows overlap, so the formal error is too small).
Compared: per coast LES - tracker gamma; per pair Delta gamma = gamma(-) - gamma(+); laser on - off from each readout.
Observations only.
"""
import csv
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'overnight_20261114'))
import les_coasts as L   # noqa: E402
import pair_plots as PP  # noqa: E402

D = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-16/laser')
RUN = os.environ.get('RUN', 'night_nd4_il2')            # RUNS=off1,on LESDIR=les_nd1 for the ND1 pairs (11-16)
RUNS = os.environ.get('RUNS', RUN).split(',')
LESDIR = os.environ.get('LESDIR', 'les')
TAG = '' if RUNS == ['night_nd4_il2'] else '_' + '_'.join(RUNS)
LABEL = os.environ.get('LABEL', 'ND4 night 16–17 Nov')
EXPECTED = float(os.environ['EXPECTED']) if os.environ.get('EXPECTED') else (0.05 if RUNS == ['night_nd4_il2'] else None)


def load_les():
    """Contiguous LES chunks from D/LESDIR (same file format and gap check as les_coasts.load_les)."""
    chunks = sorted(glob.glob(os.path.join(D, LESDIR, 'les_*.npz')), key=lambda p: int(os.path.basename(p).split('_')[1]))
    if not chunks:
        sys.exit(f'no LES files in {os.path.join(D, LESDIR)}')
    g0 = None; pit = []; yaw = []
    for p in chunks:
        z = np.load(p)
        if g0 is None:
            g0 = float(z['gps0'])
        if int(round((float(z['gps0']) - g0) * L.FS)) != sum(len(x) for x in pit):
            raise RuntimeError(f'{p}: gap or overlap')
        pit.append(z['pit'].astype(float)); yaw.append(z['yaw'].astype(float))
    return g0, np.concatenate(pit), np.concatenate(yaw)


def meta(p):
    m = {}
    for line in open(p):
        q = line.split()
        if len(q) >= 2 and q[0] in ('fe_gps_field_off', 'fe_gps_coast_end'):
            m[q[0]] = float(q[1])
        elif len(q) >= 2 and q[0] == 'laser':
            m['laser'] = q[1]
    return m


def main():
    g0, pit, yaw = load_les()
    g1 = g0 + len(pit) / L.FS
    trk = {(r['run'], r['name']): r for r in csv.DictReader(open(os.path.join(HERE, 'coasts_table.csv'))) if r['run'] in RUNS}
    rows = []
    for run, p in [(rn, p) for rn in RUNS for p in sorted(glob.glob(os.path.join(D, rn, 'coast_O*.txt')))]:
        nm = os.path.basename(p)[6:-4]
        m = meta(p)
        if 'fe_gps_coast_end' not in m or 'fe_gps_field_off' not in m:
            continue
        a, b = m['fe_gps_field_off'] + 5, m['fe_gps_coast_end'] - 2
        if a < g0 or b > g1:
            print(f'{nm}: outside the LES span'); continue
        i0, i1 = int((a - g0) * L.FS), int((b - g0) * L.FS)
        tr = {ch: L.track(x[i0:i1], 0.0) for ch, x in (('pit', pit), ('yaw', yaw))}
        snr = {ch: float(np.median(v[:, 2])) for ch, v in tr.items()}
        ch = max(snr, key=snr.get)
        v = tr[ch]
        s = (v[:, 1] >= PP.BAND[0]) & (v[:, 1] <= PP.BAND[1])
        t, f = v[s, 0], v[s, 1]
        las = m.get('laser') or ('on' if run == 'on' else 'off')    # the 11-16 single pairs have no laser line
        r = dict(run=run, name=nm, dir=1 if int(nm[1:]) % 2 else -1, laser=las, channel=ch, snr=snr[ch], n_win=int(s.sum()))
        tg = trk.get((run, nm), {}).get('gamma_mHz') or ''
        r['g_trk'] = 1e3 * float(tg) if tg else np.nan
        r['g_trk_err'] = 1e3 * float(trk[(run, nm)]['gamma_err_mHz']) if tg else np.nan
        if s.sum() >= 15 and v[0, 1] >= PP.BAND[1]:
            r['g_les'] = 1e6 * PP.gamma_mid(t, f)[0]
            r['g_les_err'] = 1e6 * PP.jk(lambda idx: PP.gamma_mid(t[idx], f[idx])[0], len(t))
        else:
            r['g_les'] = r['g_les_err'] = np.nan
        rows.append(r)
        print(f"{nm} {r['dir']:+d} {r['laser']:>3} {ch} snr {snr[ch]:.0f}  gamma LES {r['g_les']:.1f} +- {r['g_les_err']:.1f}  "
              f"tracker {r['g_trk']:.2f} +- {r['g_trk_err']:.2f} uHz")
    with open(os.path.join(HERE, f'les_vs_tracker{TAG}.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    ok = [r for r in rows if np.isfinite(r['g_les']) and np.isfinite(r['g_trk'])]
    d = np.array([r['g_les'] - r['g_trk'] for r in ok])
    print(f"\nper coast LES - tracker: mean {d.mean():+.2f}, sd {d.std(ddof=1):.2f} uHz, n {len(d)}")
    for s_ in ('off', 'on'):
        x = np.array([r['g_les'] - r['g_trk'] for r in ok if r['laser'] == s_])
        print(f"  laser {s_}: mean {x.mean():+.2f} +- {x.std(ddof=1) / np.sqrt(len(x)):.2f} (n {len(x)})")
    by = {(r['run'], r['name']): r for r in rows}
    pairs = []
    for run in RUNS:
        for i in range(1, 100, 2):
            pn, mn = (run, f'O{i:02d}'), (run, f'O{i + 1:02d}')
            if pn in by and mn in by:
                P, M = by[pn], by[mn]
                pairs.append(dict(run=run, pair=(i + 1) // 2, laser=P['laser'], dg_les=M['g_les'] - P['g_les'],
                                  dg_les_err=float(np.hypot(P['g_les_err'], M['g_les_err'])), dg_trk=M['g_trk'] - P['g_trk'],
                                  dg_trk_err=float(np.hypot(P['g_trk_err'], M['g_trk_err']))))
                print(f"pair {run} {i}/{i + 1} laser {P['laser']}: dgamma LES {pairs[-1]['dg_les']:+.2f} +- {pairs[-1]['dg_les_err']:.2f}, "
                      f"tracker {pairs[-1]['dg_trk']:+.2f} +- {pairs[-1]['dg_trk_err']:.2f}")
    res = {}
    for key in ('dg_les', 'dg_trk'):
        on = np.array([q[key] for q in pairs if q['laser'] == 'on' and np.isfinite(q[key])])
        off = np.array([q[key] for q in pairs if q['laser'] == 'off' and np.isfinite(q[key])])
        if len(on) > 1 and len(off) > 1:
            err = np.hypot(on.std(ddof=1) / np.sqrt(len(on)), off.std(ddof=1) / np.sqrt(len(off)))
        else:                                     # single pairs: formal errors
            e = np.array([q[key + '_err'] for q in pairs if np.isfinite(q[key])]); err = float(np.sqrt(np.sum(e ** 2)))
        res[key] = (on.mean() - off.mean(), err, len(on), len(off))
        print(f"{key}: laser on - off {res[key][0]:+.2f} +- {res[key][1]:.2f} uHz (pairs on {len(on)}, off {len(off)})")
    plot(rows, pairs, res)


def plot(rows, pairs, res):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'sans-serif', 'axes.spines.top': False, 'axes.spines.right': False})
    con, coff = '#c0392b', '0.45'
    fig, ax = plt.subplots(1, 3, figsize=(16, 5.2))
    for s_, c in (('off', coff), ('on', con)):
        x = [r['g_trk'] for r in rows if r['laser'] == s_]; y = [r['g_les'] for r in rows if r['laser'] == s_]
        ye = [r['g_les_err'] for r in rows if r['laser'] == s_]
        ax[0].errorbar(x, y, ye, fmt='o', color=c, ms=4, capsize=2, label=f'laser {s_}')
    lo = np.nanmin([r['g_trk'] for r in rows]) - 3; hi = np.nanmax([r['g_trk'] for r in rows]) + 3
    ax[0].plot([lo, hi], [lo, hi], color='0.6', lw=0.8); ax[0].set_xlim(lo, hi); ax[0].set_ylim(lo, hi)
    ax[0].set_xlabel('γ from the tracker (µHz)'); ax[0].set_ylabel('γ from the LES (µHz)'); ax[0].legend(frameon=False)
    ax[0].set_title('γ per coast at 0.435 Hz: two readouts', fontsize=11); ax[0].grid(alpha=0.3)
    idx = np.arange(len(rows))
    for s_, c in (('off', coff), ('on', con)):
        m = [i for i, r in enumerate(rows) if r['laser'] == s_]
        ax[1].errorbar(idx[m], [rows[i]['g_les'] - rows[i]['g_trk'] for i in m], [rows[i]['g_les_err'] for i in m],
                       fmt='o', color=c, ms=4, capsize=2, label=f'laser {s_}')
    ax[1].axhline(0, color='0.5', lw=0.8); ax[1].set_xlabel('coast (in order)'); ax[1].set_ylabel('LES − tracker (µHz)')
    ax[1].set_title('Difference per coast', fontsize=11); ax[1].grid(alpha=0.3); ax[1].legend(frameon=False)
    for k, (key, lab) in enumerate((('dg_trk', 'tracker'), ('dg_les', 'LES'))):
        v, e, non, noff = res[key]
        ax[2].errorbar(k, v, e, fmt='o', ms=8, capsize=4, color='#1f3b73')
        ax[2].annotate(f'{v:+.2f} ± {e:.2f}', (k, v), xytext=(10, 0), textcoords='offset points', va='center')
    if EXPECTED is not None:
        ax[2].axhline(EXPECTED, color=con, ls='--', lw=1, label=f'expected ({EXPECTED:+g})')
    ax[2].axhline(0, color='0.5', lw=0.8)
    ax[2].set_xticks([0, 1]); ax[2].set_xticklabels(['tracker', 'LES']); ax[2].set_xlim(-0.6, 1.8)
    ax[2].set_ylabel('laser on − off of Δγ (µHz)'); ax[2].legend(frameon=False, fontsize=9)
    ax[2].set_title('Laser effect, each readout', fontsize=11); ax[2].grid(alpha=0.3)
    fig.suptitle(f'{LABEL}: the LES (405 nm beam, no camera) vs the tracker (camera)', fontsize=12)
    fig.tight_layout()
    os.makedirs(os.path.join(HERE, 'plots'), exist_ok=True)
    fig.savefig(os.path.join(HERE, 'plots', f'les_vs_tracker{TAG or "_nd4"}.png'), dpi=120)


if __name__ == '__main__':
    main()
