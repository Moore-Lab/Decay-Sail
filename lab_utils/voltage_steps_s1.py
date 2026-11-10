#!/usr/bin/env python3
"""Score S1 (outputs on, scope): what the electrodes actually get from voltage_steps.py --preset s1 --scope.

    python3 voltage_steps_s1.py RUNDIR [--outdir analysis/voltage_steps_<date>/plots]
    python3 voltage_steps_s1.py selftest

Mac, analysis only. RUNDIR as for voltage_steps_score.py plus scope_*_s1.npz (scope_rtb.read; CH2 = V2, CH3 = V3,
CH4 = V4). Plan: lab_utils/VOLTAGE_STEPS_HANDOFF.md, S1. The OUT_DQ side (landings, clock fit, 8/s) is scored by
voltage_steps_score.py first, unchanged.

WHAT IT MEASURES (printed; the pass mark is the handoff's, printed not decided):
  1. Whole-record fit per electrode (scope_check.fit_channel, as in W2): scope = G * hp(x, tau) + dc, x = the applied
     staircase rebuilt from OUT_DQ's settled per-tick levels (not raw OUT_DQ, whose edges ring). G = V/count (slow
     part), tau = AC-coupling time constant (the holds measure it). The scope has no GPS: it is aligned by
     cross-correlation, so delays are relative only (between electrodes), never absolute.
  2. Per edge (every OUT_DQ landing inside the scope record): step height at the electrode / step in counts = V/count
     at the first instant (median 8..25 ms after vs 25..3 ms before the edge); 10-90 % rise time; overshoot
     (% of the step, first 20 ms); whether the edge was seen (> half the expected height).
  3. 8/s block: fraction of OUT_DQ landings seen at the electrodes.
  4. Electrode skew: for steps that change several electrodes, the 50 %-crossing time of each minus the earliest.
Expected (handoff): V/count ~0.0118-0.0122 (refit, offset path), ~0.0124-0.0128 (AWG burst gain); tau 5.69 / 5.56 /
5.43 s (V2 / V3 / V4, W2 11-03). Pass (handoff): steps = counts x refit V/count within 10 % and the droop matches tau
(taken as within 10 % of W2's), or a clear measurement of how they differ.
"""
import glob
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scope_check as S  # noqa: E402
import voltage_steps as vs  # noqa: E402
import voltage_steps_score as vss  # noqa: E402

CHANS = vs.CHANS
SCOPE_CH = {2: 'CH2', 3: 'CH3', 4: 'CH4'}
REFIT = (0.0118, 0.0122)          # offset-path V/count, derived (handoff "What is already known")
AWG = (0.0124, 0.0128)            # _EXC path, measured 11-03
TAU_W2 = {2: 5.69, 3: 5.56, 4: 5.43}


def load_scope(rd):
    f = sorted(glob.glob(os.path.join(rd, 'scope_*.npz')))
    if not f:
        sys.exit(f'! no scope_*.npz in {rd}')
    sc = dict(np.load(f[-1], allow_pickle=False))
    js = f[-1][:-4] + '.json'
    meta = json.load(open(js)) if os.path.exists(js) else {}
    return sc, meta, f[-1]


def staircase(R, res):
    """Applied counts per OUT_DQ sample, from the settled landings (level held from each landing's tick start)."""
    dq = R['dq']; n = dq['V2'].size
    x = {}
    for c in CHANS:
        y = np.zeros(n)
        for i, t, ch, v in res['L']:
            if ch == c:
                y[i:] = v
        x[c] = y
    return x


def fit(R, res, sc):
    dq = R['dq']; fs = dq['fs']
    t_dq = dq['gps0'] + np.arange(dq['V2'].size) / fs
    x = staircase(R, res)
    amp = max(np.ptp(x[c]) for c in CHANS)
    # one alignment for all electrodes (one scope clock): coarse offset on the sum of derivatives
    t_sc = np.asarray(sc['CH2_t'], float)
    # clock rate: the FE runs ~+1.2 ms/s against NTP (S0, field8) and the scope crystal keeps ~true time, so over a
    # 120 s screen a pure shift is off by up to ~70 ms at the ends. Correct the scope time axis with the FE drift
    # measured from the writes before the coarse cross-correlation, and seed fit_channel's kappa with it.
    kappa0 = float(res['M']['b'] - 1)
    S.TREF[0] = float(t_sc.mean())
    t_corr = (t_sc - S.TREF[0]) * (1 + kappa0) + S.TREF[0]
    off = []
    for c in CHANS:
        if SCOPE_CH[c] in sc:
            off.append(S.coarse_offset(t_dq, x[c] - x[c].mean(), t_corr, np.asarray(sc[SCOPE_CH[c]], float))[0])
    off0 = float(np.median(off))
    out = {}
    for c in CHANS:
        ch = SCOPE_CH[c]
        if ch not in sc:
            continue
        r = S.fit_channel(t_dq, x[c], fs, t_sc, np.asarray(sc[ch], float), off0, amp, kappa=kappa0)
        for k in ('ts', 'ys', 'model'):
            r.pop(k)
        out[c] = r
    return dict(off0=off0, ch=out, x=x, t_dq=t_dq)


def to_scope(F, c, t_fe):
    """FE time -> scope time for electrode c, inverting scope_check's model mapping."""
    r = F['ch'][c]
    return (np.asarray(t_fe) - F['off0'] - (-r['delay']) - S.TREF[0]) / (1 + r['kappa']) + S.TREF[0]


def locate(y, ts, tp, win, sign):
    """Time of the steepest slope of the given sign within +-win of tp (scope time), or nan."""
    w = (ts >= tp - win) & (ts <= tp + win)
    if w.sum() < 10:
        return np.nan
    dy = np.convolve(np.gradient(y[w]), np.ones(5) / 5, mode='same') * sign
    return float(ts[w][np.argmax(dy)])


def edge_map(R, res, F, sc):
    """Scope time = A + B * (FE time - t_mid), from the edges themselves: start from the whole-record fit, then
    locate the large edges on the trace and refit the line, narrowing the search window (60, 20, 5 ms). One map
    for all electrodes (one scope clock), so inter-electrode skew stays measurable."""
    big = []
    prev = {c: 0.0 for c in CHANS}
    for i, t, c, v in res['L']:
        if c in F['ch'] and abs(v - prev[c]) >= 400:
            big.append((t, c, np.sign(v - prev[c])))
        prev[c] = v
    t_mid = float(np.median([b[0] for b in big]))
    c0 = list(F['ch'])[0]
    A = float(to_scope(F, c0, t_mid)); B = float(to_scope(F, c0, t_mid + 1.0)) - A
    for win in (0.06, 0.02, 0.005):
        pts = []
        for t, c, sg in big:
            y = np.asarray(sc[SCOPE_CH[c]], float); ts = np.asarray(sc[f'{SCOPE_CH[c]}_t'], float)
            tp = A + B * (t - t_mid)
            if ts[0] + 0.1 < tp < ts[-1] - 0.1:
                te = locate(y, ts, tp, win, sg)
                if np.isfinite(te):
                    pts.append((t - t_mid, te))
        pts = np.array(pts)
        keep = np.ones(len(pts), bool)
        for _ in range(3):
            B, A = np.polyfit(pts[keep, 0], pts[keep, 1], 1)
            e = pts[:, 1] - (A + B * pts[:, 0])
            keep = np.abs(e - np.median(e[keep])) < max(4 * 1.4826 * np.median(np.abs(e[keep] - np.median(e[keep]))), 2e-4)
    return dict(A=A, B=B, t_mid=t_mid, n=int(keep.sum()), rms_ms=1e3 * float(np.std(e[keep])))


def edges(R, res, F, sc):
    """Per OUT_DQ landing inside the scope record: height, V/count, rise, overshoot, seen, 50 % time (FE)."""
    E = []
    prev = {c: 0.0 for c in CHANS}
    blk = block_of_time(R, res)
    for i, t, c, v in res['L']:
        dv = v - prev[c]; prev[c] = v
        if c not in F['ch']:
            continue
        y = np.asarray(sc[SCOPE_CH[c]], float); ts = np.asarray(sc[f'{SCOPE_CH[c]}_t'], float)
        Mp = F['map']
        tp = Mp['A'] + Mp['B'] * (t - Mp['t_mid'])  # predicted from the edge map; the edge itself is located on the trace
        if tp - 0.05 < ts[0] or tp + 0.05 > ts[-1]:
            continue
        te = locate(y, ts, tp, 0.015, np.sign(dv)) if dv else np.nan
        if not np.isfinite(te):
            continue
        def med(a, b):
            m = (ts >= te + a) & (ts < te + b)
            return float(np.median(y[m])) if m.any() else np.nan
        pre, post = med(-0.025, -0.003), med(0.008, 0.025)
        h = post - pre
        G = F['ch'][c]['G']
        w = (ts >= te - 0.005) & (ts <= te + 0.020)
        yy, tt = (y[w] - pre) * np.sign(dv), ts[w]
        H = abs(h)
        rise = ovs = t50 = np.nan
        if H > 0:
            try:
                t10 = tt[np.nonzero(yy >= 0.1 * H)[0][0]]; t90 = tt[np.nonzero(yy >= 0.9 * H)[0][0]]
                t50 = tt[np.nonzero(yy >= 0.5 * H)[0][0]]
                rise = t90 - t10
            except IndexError:
                pass
            ovs = (yy[tt >= te].max() - H) / H
        E.append(dict(chan=c, t=t, dv=dv, h=h, gain=h / dv if dv else np.nan, rise=rise, ovs=ovs,
                      seen=abs(h) > 0.5 * abs(G * dv), t50=t50, te=te, dte=te - tp, block=blk(t), tick=i))
    return E


def block_of_time(R, res):
    """FE time -> block, from the mapped write times (a landing belongs to the block of the latest write before it)."""
    ws = sorted(R['W'], key=lambda w: w['m'])
    mt = np.array([w['m'] for w in ws]); bb = np.array([w['block'] for w in ws])
    return lambda t: int(bb[max(np.searchsorted(mt, t, side='right') - 1, 0)])


def summarise(R, res, F, E):
    S1 = dict(fit=F['ch'], off0=F['off0'], per_chan={}, blocks={}, skew=[])
    for c in F['ch']:
        e = [x for x in E if x['chan'] == c and abs(x['dv']) >= 400]
        g = np.array([x['gain'] for x in e]); ri = np.array([x['rise'] for x in e]); ov = np.array([x['ovs'] for x in e])
        S1['per_chan'][c] = dict(n=len(e), gain_med=np.nanmedian(g) if len(g) else np.nan,
                                 gain_p16=np.nanpercentile(g, 16) if len(g) else np.nan,
                                 gain_p84=np.nanpercentile(g, 84) if len(g) else np.nan,
                                 rise_med=np.nanmedian(ri) if len(ri) else np.nan, ovs_med=np.nanmedian(ov) if len(ov) else np.nan,
                                 ovs_max=np.nanmax(ov) if len(ov) else np.nan)
    for b in sorted({x['block'] for x in E}):
        e = [x for x in E if x['block'] == b]
        S1['blocks'][b] = dict(pattern=R['pat'][b], rate=R['rate'][b], n=len(e), seen=np.mean([x['seen'] for x in e]))
    d = np.array([1e3 * x['dte'] for x in E])
    S1['dte'] = (np.median(d), np.percentile(d, 5), np.percentile(d, 95)) if d.size else (np.nan,) * 3
    by_tick = {}
    for x in E:
        if abs(x['dv']) >= 400:                    # small steps: the 50 % crossing is noise-limited
            by_tick.setdefault(x['tick'], []).append(x)
    for xs in by_tick.values():
        if len(xs) > 1 and all(np.isfinite(x['t50']) for x in xs):
            # scope times -> common FE axis (one scope clock; per-channel delay is what we measure, so use channel 2's map)
            t0 = min(x['t50'] for x in xs)
            S1['skew'] += [1e3 * (x['t50'] - t0) for x in xs]
    return S1


def report(S1):
    L = ['# S1: what the electrodes get (scope)', '',
         'Whole-record fit per electrode: scope = G * highpass(applied counts, tau) + dc. Scope aligned to OUT_DQ by '
         'its edges (no common clock), so delays are relative only.', '',
         '| electrode | G (V/count, slow) | tau (s) | tau W2 (s) | edge V/count (first instant), median [p16-p84] | edges | '
         'rise 10-90 % median (ms) | overshoot median / max | residual rms (V) |', '|' + '---|' * 9]
    for c, r in S1['fit'].items():
        p = S1['per_chan'][c]
        L.append(f'| V{c} | {r["G"]:.5f} | {r["tau"]:.2f} | {TAU_W2[c]:.2f} | {p["gain_med"]:.5f} [{p["gain_p16"]:.5f}-{p["gain_p84"]:.5f}] | '
                 f'{p["n"]} | {1e3 * p["rise_med"]:.2f} | {100 * p["ovs_med"]:.1f} % / {100 * p["ovs_max"]:.1f} % | {r["rms"]:.3f} |')
    L += ['', '| block | pattern | steps/s | OUT_DQ landings in the scope record | seen at the electrode |', '|---|---|---|---|---|']
    for b, r in S1['blocks'].items():
        L.append(f'| {b} | {r["pattern"]} | {r["rate"]:g} | {r["n"]} | {100 * r["seen"]:.1f} % |')
    sk = np.array(S1['skew'])
    if 'range' in S1:
        L += ['', '- Scope range: ' + '; '.join(f'V{c} {a:+.1f} .. {b:+.1f} V' + (f' (CLIPPED? {100 * f:.2f} % of samples at an extreme)' if f > 1e-3 else '')
                                          for c, (a, b, f) in S1['range'].items())]
    if 'map' in S1:
        L += [f'- Scope clock: edge map from {S1["map"]["n"]} large edges, scope s per FE s {S1["map"]["B"]:.6f}, '
              f'scatter {S1["map"]["rms_ms"]:.2f} ms']
    L += [f'- Alignment check: located edge minus edge-map prediction, median {S1["dte"][0]:+.2f} ms, p5-p95 '
          f'{S1["dte"][1]:+.2f} to {S1["dte"][2]:+.2f} ms (edges are located on the trace within +-15 ms of the prediction)']
    L += [f'- Electrode skew within multi-electrode steps (50 % crossing minus the earliest): '
          + (f'median {np.median(sk):.2f} ms, p95 {np.percentile(sk, 95):.2f} ms, max {sk.max():.2f} ms (n {sk.size})' if sk.size else 'none')]
    okg = all(REFIT[0] * 0.9 <= p['gain_med'] <= REFIT[1] * 1.1 for p in S1['per_chan'].values())
    okt = all(abs(r['tau'] / TAU_W2[c] - 1) <= 0.10 for c, r in S1['fit'].items())
    L += [f'- Handoff mark (printed, not decided): step V/count within 10 % of the refit {REFIT[0]}-{REFIT[1]}: '
          f'{"yes" if okg else "no"}; tau within 10 % of W2: {"yes" if okt else "no"}.',
          f'- Expected, for comparison: AWG-path gain {AWG[0]}-{AWG[1]} V/count (11-03).']
    return '\n'.join(L)


def plots(R, res, F, E, sc, outdir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(outdir, exist_ok=True)
    files = []
    col = {2: 'C0', 4: 'C1', 3: 'C2'}; name = {2: 'V2 (A)', 4: 'V4 (B)', 3: 'V3 (C)'}
    t_dq = F['t_dq']; dq = R['dq']
    for b in sorted(R['rate']):
        ws = [w for w in R['W'] if w['block'] == b]
        a0, a1 = min(w['m'] for w in ws) - 1.0, max(w['m'] for w in ws) + (4.5 if R['pat'][b] == 'hold' else 1.0)
        fig, ax = plt.subplots(len(F['ch']), 1, figsize=(13, 2.6 * len(F['ch']) + 1), sharex=True)
        for k, c in enumerate(F['ch']):
            r = F['ch'][c]; a = ax[k]
            y = np.asarray(sc[SCOPE_CH[c]], float); ts = np.asarray(sc[f'{SCOPE_CH[c]}_t'], float)
            Mp = F['map']
            tfe = (ts - Mp['A']) / Mp['B'] + Mp['t_mid']   # scope -> FE through the edge map
            m = (tfe >= a0) & (tfe <= a1)
            step = max(1, m.sum() // 20000)
            a.plot(tfe[m][::step] - a0, y[m][::step], color=col[c], lw=1, label='scope (electrode, V)')
            md = (t_dq >= a0) & (t_dq <= a1)
            hp = r['G'] * S.highpass(F['x'][c], dq['fs'], r['tau']) + r['dc']
            a.plot(t_dq[md] - a0, hp[md], 'k--', lw=0.9, label=f'model: G x highpass(applied), tau {r["tau"]:.2f} s')
            a.plot(t_dq[md] - a0, r['G'] * F['x'][c][md], color='grey', lw=0.8, alpha=0.7, label='G x applied counts (no AC coupling)')
            a.set_ylabel(f'{name[c]}\nvolts')
        ax[0].legend(fontsize=7, loc='upper right')
        ax[-1].set_xlabel('s from block start (FE time)')
        fig.suptitle(f'S1 block {b}: {R["pat"][b]}, {R["rate"][b]:g} steps/s: electrode voltage (scope) vs model', fontsize=11)
        fig.tight_layout(); f = os.path.join(outdir, f's1_block{b:02d}_{R["pat"][b]}.png'); fig.savefig(f, dpi=100); plt.close(fig)
        files.append(f)
    # edge shape: scope vs OUT_DQ, normalised, overlaid
    fig, ax = plt.subplots(1, len(F['ch']), figsize=(15, 4.2), sharey=True)
    for k, c in enumerate(F['ch']):
        y = np.asarray(sc[SCOPE_CH[c]], float); ts = np.asarray(sc[f'{SCOPE_CH[c]}_t'], float)
        x = dq[f'V{c}']; a = ax[k]
        for e in [e for e in E if e['chan'] == c and abs(e['dv']) >= 800][:60]:
            w = (ts >= e['te'] - 0.005) & (ts <= e['te'] + 0.03)
            pre = np.median(y[(ts >= e['te'] - 0.025) & (ts < e['te'] - 0.003)])
            a.plot(1e3 * (ts[w] - e['te']), (y[w] - pre) / e['h'], color=col[c], lw=0.5, alpha=0.4)
            i = e['tick']
            seg = np.arange(i - 5, i + 31)
            a.plot(1e3 * (seg - i) / dq['fs'], (x[seg] - x[i - 5]) / e['dv'], color='k', lw=0.5, alpha=0.25)
        a.axhline(1, color='grey', lw=0.6); a.set_xlabel('ms from edge'); a.set_title(f'{name[c]}: scope (colour) vs OUT_DQ (black)')
    ax[0].set_ylabel('normalised step')
    fig.tight_layout(); f = os.path.join(outdir, 's1_edges.png'); fig.savefig(f, dpi=100); plt.close(fig); files.append(f)
    # V/count per edge
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for c in F['ch']:
        g = [e['gain'] for e in E if e['chan'] == c and abs(e['dv']) >= 400]
        ax.hist(g, bins=40, histtype='step', color=col[c], lw=1.5, label=f'{name[c]} edges (n {len(g)})')
    ax.axvspan(*REFIT, color='grey', alpha=0.2, label='refit, offset path (derived)')
    ax.axvspan(*AWG, color='C4', alpha=0.15, label='AWG path (11-03)')
    ax.set_xlabel('step at electrode / step in counts (V/count)'); ax.legend(fontsize=8)
    fig.tight_layout(); f = os.path.join(outdir, 's1_gain.png'); fig.savefig(f, dpi=100); plt.close(fig); files.append(f)
    return files


def run(rd, outdir=None, quiet=False):
    R = vss.load(rd)
    res = vss.score(R)
    sc, meta, fn = load_scope(rd)
    F = fit(R, res, sc)
    F['map'] = edge_map(R, res, F, sc)
    E = edges(R, res, F, sc)
    S1 = summarise(R, res, F, E)
    S1['map'] = F['map']
    S1['range'] = {}
    for c in CHANS:                               # clipping: a saturated trace pins at its extreme value
        y = np.asarray(sc[SCOPE_CH[c]], float)
        S1['range'][c] = (float(y.min()), float(y.max()), float(np.mean((y == y.max()) | (y == y.min()))))
    txt = report(S1)
    if not quiet:
        print(vss.table(res)); print(); print(txt)
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        open(os.path.join(outdir, 's1_summary.md'), 'w').write(txt + '\n')
        open(os.path.join(outdir, 'summary.md'), 'w').write(vss.table(res) + '\n')
        fl = plots(R, res, F, E, sc, outdir) + vss.plots(R, res, outdir)
        if not quiet:
            for f in fl:
                print('  ', f)
    return R, res, F, E, S1


def selftest():
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as d:
        for label, kw in (('clean', {}), ('ringing', dict(ring=0.18, skew={2: 0.0, 4: 0.0, 3: 0.002}))):
            rd, fe = vs.mock_run(os.path.join(d, label), mode='every2', preset='s1', scope_kw=kw, seed=11)
            sc_true = vs.MockScope(fe, **kw)
            R, res, F, E, S1 = run(rd, os.path.join(d, label, 'plots') if label == 'clean' else None, quiet=True)
            print(f'\n== mock S1, {label} electrode edges')
            print(report(S1))
            for c in CHANS:
                r, p = F['ch'][c], S1['per_chan'][c]
                okc = abs(r['G'] / sc_true.G[c] - 1) < 0.02 and abs(r['tau'] / sc_true.tau[c] - 1) < 0.05
                okc &= abs(p['gain_med'] / sc_true.G[c] - 1) < 0.02
                okc &= abs(p['rise_med'] - 2.2 * sc_true.rise) < 0.3e-3
                if label == 'clean':
                    okc &= p['ovs_med'] < 0.02
                else:
                    okc &= p['ovs_med'] > 0.05
                if not okc:
                    print(f'   CHECK FAILED V{c}: G {r["G"]:.5f} vs {sc_true.G[c]}, tau {r["tau"]:.2f} vs {sc_true.tau[c]}, '
                          f'edge gain {p["gain_med"]:.5f}, rise {1e3 * p["rise_med"]:.2f} ms vs {2.2e3 * sc_true.rise:.2f}, ovs {p["ovs_med"]:.3f}')
                ok &= okc
            seen = [r['seen'] for r in S1['blocks'].values()]
            okb = min(seen) == 1.0 and len(S1['blocks']) == 4
            sk = np.array(S1['skew'])
            okb &= (np.percentile(sk, 95) < 0.3) if label == 'clean' else (1.5 < np.max(sk) < 2.5)
            if not okb:
                print(f'   CHECK FAILED: seen {seen}, skew p95 {np.percentile(sk, 95):.2f} max {sk.max():.2f} ms')
            ok &= okb
            if label == 'clean':
                n = len(os.listdir(os.path.join(d, label, 'plots')))
                print(f'   plots written: {n}')
                ok &= n >= 7
    print('\nSELFTEST %s' % ('PASSED' if ok else 'FAILED'))
    return 0 if ok else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        return selftest()
    import argparse
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('rundir')
    p.add_argument('--outdir', help='default: RUNDIR/score_s1')
    a = p.parse_args()
    run(a.rundir, a.outdir or os.path.join(a.rundir, 'score_s1'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
