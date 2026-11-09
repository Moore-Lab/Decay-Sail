#!/usr/bin/env python3
"""Score and plot a voltage_steps.py run (S0; S1 adds the scope): what limits fast offset steps.

    python3 voltage_steps_score.py RUNDIR [--outdir analysis/voltage_steps_<date>] [--fit-max-rate 8]
    python3 voltage_steps_score.py selftest

Mac, analysis only. RUNDIR holds plan.csv, writes.csv, blocks.csv, outmon.csv (from `run`) and out_dq.npz
(from `fetch`: Y1:RDS-OUTS_V{2,3,4}_OUT_DQ, 1024 Hz, front-end time). Plan: VOLTAGE_STEPS_HANDOFF.md.

WHAT IT MEASURES (S0 table; there is no pass threshold, the numbers are the result):
  1. landed fraction per block (each channel write: did its value appear in OUT_DQ before a later write
     replaced it?) and the achieved rate (landings/s) against the requested rate;
  2. landing times on the 16 Hz grid: OUT_DQ sample index mod fs/16, in OUT_DQ's own time base, so no
     clock mapping is involved; and the spacing between successive landings (1 tick or 2);
  3. same tick or split: for steps that change 2-3 channels, whether all landed on one sample, against
     the chance that a tick falls inside the write burst (burst length / 62.5 ms);
  4. write-to-OUTMON delay, host side (outmon.csv), per rate. Only absolute delay available: OUT_DQ
     carries an unexplained 3-4 s offset (F3 11-04), so from OUT_DQ only the SPREAD of write-to-landing
     delay is measured (step 5);
  5. host -> FE mapping t_fe = a + b (t_host - t0), fitted from the low-rate blocks: b - 1 is the clock
     drift; a mixes the clock offset with the latency and is not interpreted. Relative delay =
     landing - mapped write - its minimum: ~0..62.5 ms if every tick applies, ~0..125 ms if every 2nd;
  6. TRAMP found at each block start (the reset).
OUT_DQ is upstream of the output switch, so with outputs off this is when the front end APPLIES a write.
"""
import argparse
import csv
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voltage_steps as vs  # noqa: E402

GPS_UNIX = 315964800 - 18
CHANS = vs.CHANS
TICK = vs.TICK


def load(rd):
    rows = lambda f: list(csv.DictReader(open(os.path.join(rd, f))))
    plan = vs.read_plan(os.path.join(rd, 'plan.csv'))
    rate = {r['block']: r['rate'] for r in plan}
    pat = {r['block']: r['pattern'] for r in plan}
    W = []                                        # one row per channel write
    bursts = []
    for r in rows('writes.csv'):
        b = int(r['block']); ch = [int(c) for c in r['chans']]
        if not ch:
            continue
        t0, t1 = float(r['host_t0']), float(r['host_t1'])
        bi = len(bursts)
        bursts.append(dict(block=b, step=int(r['step']), t0=t0, t1=t1, chans=ch, late=float(r['late_ms'])))
        for c in ch:
            W.append(dict(burst=bi, block=b, chan=c, v=float(r[f'V{c}']), h=t0))
    om = [(float(r['host_t']), int(r['chan']), float(r['value'])) for r in rows('outmon.csv')]
    bl = rows('blocks.csv')
    o = np.load(os.path.join(rd, 'out_dq.npz'))
    dq = dict(gps0=float(o['gps0']), fs=float(o['fs']), **{f'V{c}': np.asarray(o[f'V{c}'], float) for c in CHANS})
    return dict(plan=plan, rate=rate, pat=pat, W=W, bursts=bursts, om=om, bl=bl, dq=dq)


def onsets(x, big=5.0, quiet=1.0):
    """Samples where a step starts from a settled level (OUT_DQ edges ring for ~45 samples: 11-09 S0)."""
    d = np.abs(np.diff(x))
    i = np.nonzero(d > big)[0]
    i = i[i >= 4]
    ok = np.array([d[j - 4:j].max() < quiet for j in i], bool) if len(i) else np.zeros(0, bool)
    return i[ok] + 1


def landings(dq, levels=None, per=None, snap=3.0, thr=3.0):
    """(tick-start sample, FE time, chan, new level) for each tick whose settled level changed.

    OUT_DQ does not step cleanly: each edge overshoots ~18 % and rings for ~45 samples (measured, S0 2026-11-09;
    the DQ decimation filter is the assumed cause). So: (1) edge onsets from a settled level give the tick phase
    (the earliest phase of the onset cluster); (2) each tick's level is the median of samples 40..62 after its
    start, settled to ~0.5 count; (3) a landing is a tick whose level differs from the previous one by > thr
    counts, snapped to the nearest commanded level of that channel within `snap` counts."""
    per = per or int(round(dq['fs'] * TICK))
    allon = np.concatenate([onsets(dq[f'V{c}']) for c in CHANS])
    h = np.bincount(allon % per, minlength=per)
    top = np.argsort(h)[::-1]
    clus = [p for p in top[:4] if h[p] > 0.05 * h.max()]
    # earliest phase of the (circular) cluster
    p0 = min(clus, key=lambda p: min((p - q) % per for q in clus) * 0 + ((p - top[0] + per // 2) % per))
    out = []
    for c in CHANS:
        x = dq[f'V{c}']
        s = np.arange(p0, len(x) - per, per)
        lev = np.array([np.median(x[k + 40:k + per - 1]) for k in s])
        lv = np.array(sorted(levels[c])) if levels and levels.get(c) else None
        for j in range(1, len(s)):
            if np.isfinite(lev[j]) and np.isfinite(lev[j - 1]) and abs(lev[j] - lev[j - 1]) > thr:
                v = float(lev[j])
                if lv is not None:
                    k = np.argmin(np.abs(lv - v))
                    if abs(lv[k] - v) <= snap:
                        v = float(lv[k])
                out.append((int(s[j]), dq['gps0'] + s[j] / dq['fs'], c, v))
    out.sort(key=lambda e: (e[0], e[2]))
    return out, h, p0


def fit_mapping(R, L, fit_max_rate=8.0, win=0.2):
    """Host -> FE. The offset drifts ~1 ms/s (0.4 s over a 6-min run, more than the match window), so:
    1. per low-rate block, scan a constant offset for the most writes matched by a landing of the same
       channel and value within `win` after the mapped write (~20 s blocks drift only ~20 ms);
    2. a line through the block offsets gives a first drift;
    3. the matched pairs under that line, refitted on their lower envelope (delays are one-sided)."""
    g = [(float(r['host_a']), float(r['fe_gps'])) for r in R['bl'] if r['fe_gps'] not in ('', 'None')]
    base = np.median([f - (h - GPS_UNIX) for h, f in g])
    low = [w for w in R['W'] if R['rate'][w['block']] <= fit_max_rate]
    keys = {}
    for e in L:
        keys.setdefault((e[2], round(e[3], 1)), []).append(e[1])
    lt = {k: np.array(sorted(v)) for k, v in keys.items()}
    h0 = min(w['h'] for w in low)

    def matches(ws, off):                          # off(h): FE - (host - GPS_UNIX)
        """(host, landing) for writes with a same-channel, same-value landing within win after the mapped write."""
        pairs = []
        grp = {}
        for w in ws:
            grp.setdefault((w['chan'], round(w['v'], 1)), []).append(w['h'])
        for k, hs in grp.items():
            t = lt.get(k)
            if t is None:
                continue
            hs = np.array(hs)
            m = hs - GPS_UNIX + off(hs)
            j = np.searchsorted(t, m)
            ok = j < len(t)
            ok[ok] &= t[j[ok]] < m[ok] + win
            pairs += list(zip(hs[ok], t[j[ok]]))
        return sorted(pairs)

    def scan_block(ws):
        sc = base + np.arange(-2.0, 6.0, 0.01)
        n = np.array([len(matches(ws, lambda h, s=s: s + 0 * h)) for s in sc])
        s0 = sc[n == n.max()]
        sc = np.arange(s0.min() - 0.01, s0.max() + 0.01, 0.001)
        n = np.array([len(matches(ws, lambda h, s=s: s + 0 * h)) for s in sc])
        best = sc[n == n.max()]
        return best[len(best) // 2], n.max(), np.ptp(best)

    pts = []
    for b in sorted({w['block'] for w in low}):
        ws = [w for w in low if w['block'] == b]
        c, n, flat = scan_block(ws)
        if n >= 0.5 * len(ws):
            pts.append((np.mean([w['h'] for w in ws]) - h0, c))
    pts = np.array(pts)
    if not len(pts):
        sys.exit('! no low-rate block had half its writes matched by OUT_DQ landings: check the fetch window '
                 '(out_dq.npz gps0, length) against fe_gps in blocks.csv, and that OUT_DQ moved at all')
    if len(pts) >= 2:
        r1, c1 = np.polyfit(pts[:, 0], pts[:, 1], 1)
    else:
        r1, c1 = 0.0, pts[0, 1]
    pr = np.array(matches(low, lambda h: c1 + r1 * (h - h0)))
    A = np.column_stack([np.ones(len(pr)), pr[:, 0] - h0])
    y = pr[:, 1] - (h0 - GPS_UNIX)
    keep = np.ones(len(y), bool)
    for _ in range(6):                            # lower envelope: refit on the earliest 30 % of landings, since
        (a, b), *_ = np.linalg.lstsq(A[keep], y[keep], rcond=None)   # delays are one-sided (0..1-2 ticks) and a
        e = y - (a + b * (pr[:, 0] - h0))         # late channel or every-2nd tick would bias a plain fit
        keep = e <= np.percentile(e, 30)
    a += e.min()                                  # mapped write = earliest landing: relative delays >= 0
    return dict(h0=h0, a=a, b=b, base=base, n_fit=len(pr), n_low=len(low), n_blocks=len(pts),
                block_drift=r1, block_resid_ms=1e3 * float(np.std(pts[:, 1] - (c1 + r1 * pts[:, 0]))) if len(pts) > 2 else np.nan)


def fe_of(M, h):
    return (M['h0'] - GPS_UNIX) + M['a'] + M['b'] * (np.asarray(h) - M['h0'])


def assign(R, L, M, back=0.6, tol=0.010):
    """Each OUT_DQ landing -> the latest write on that channel with that value mapped before it."""
    W = R['W']
    for w in W:
        w['m'] = float(fe_of(M, w['h'])); w['land'] = None; w['idx'] = None
    by = {c: sorted([w for w in W if w['chan'] == c], key=lambda w: w['m']) for c in CHANS}
    mt = {c: np.array([w['m'] for w in by[c]]) for c in CHANS}
    stray = 0
    for i, t, c, v in L:
        j = np.searchsorted(mt[c], t + tol, side='right') - 1
        hit = False
        while j >= 0 and mt[c][j] > t - back:
            w = by[c][j]
            if abs(w['v'] - v) < 0.5:
                if w['land'] is None:
                    w['land'] = t; w['idx'] = i
                hit = True
                break
            j -= 1
        stray += not hit
    return stray


def score(R, fit_max_rate=8.0):
    dq = R['dq']; fs = dq['fs']; per = int(round(fs * TICK))
    levels = {c: sorted({w['v'] for w in R['W'] if w['chan'] == c} | {0.0}) for c in CHANS}
    L, onset_hist, p0 = landings(dq, levels, per)
    M = fit_mapping(R, L, fit_max_rate)
    assign(R, L, M, tol=0.03)                     # pass 1, loose: the low-rate minimum delay overestimates the
    d = [w['land'] - w['m'] for w in R['W']       # true one (few writes); re-zero on all blocks <= 8/s, where a
         if w['land'] is not None and R['rate'][w['block']] <= 8]   # repeated value is >= 250 ms away (no ambiguity)
    if not d:
        sys.exit('! no write at <= 8/s matched an OUT_DQ landing after mapping')
    M['a'] += min(d); M['rezero_ms'] = 1e3 * min(d)
    stray = assign(R, L, M)
    hist = onset_hist                              # raw edge onsets mod one tick (filter spreads them ~3 samples)
    blocks = sorted(R['rate'])
    res = dict(M=M, L=L, ph_hist=hist, per=per, p0=p0, stray=stray, blocks=[])
    found = {int(r['block']): [r[f'tramp_found_V{c}'] for c in CHANS] for r in R['bl'] if r['edge'] == 'start'}
    by_burst = {}
    for w in R['W']:
        by_burst.setdefault(w['burst'], []).append(w)
    for i, x in enumerate(R['bursts']):
        x['i'] = i
    omg = {}                                      # OUTMON updates by (channel, value), sorted host times
    for t, c, v in R['om']:
        omg.setdefault((c, round(v, 1)), []).append(t)
    omg = {k: np.array(sorted(v)) for k, v in omg.items()}
    wg = {}                                       # writes by (channel, value), sorted host times
    for w in R['W']:
        wg.setdefault((w['chan'], round(w['v'], 1)), []).append(w['h'])
    wg = {k: np.array(sorted(v)) for k, v in wg.items()}
    for b in blocks:
        ws = [w for w in R['W'] if w['block'] == b]
        bs = [x for x in R['bursts'] if x['block'] == b]
        if not ws:
            continue
        T = (max(w['h'] for w in ws) - min(w['h'] for w in ws))
        landed = [w for w in ws if w['land'] is not None]
        lt = sorted({w['idx'] for w in landed})
        sp = np.diff(lt) / per if len(lt) > 1 else np.array([])
        d = np.array([w['land'] - w['m'] for w in landed]) * 1e3
        multi = [x for x in bs if len(x['chans']) > 1]
        split = n_multi = 0; xdiff = []
        for x in multi:
            wl = by_burst[x['i']]
            if all(w['idx'] is not None for w in wl):
                n_multi += 1
                ii = [w['idx'] for w in wl]
                split += len(set(ii)) > 1
                xdiff += [(i - min(ii)) / per for i in ii]
        chance = np.mean([(x['t1'] - x['t0']) / TICK for x in multi]) if multi else np.nan
        # write -> OUTMON (host side)
        od = []
        for w in ws:
            # first OUTMON update showing the value, before the next write of the SAME value on this channel
            k = (w['chan'], round(w['v'], 1))
            hw = wg[k]; j = np.searchsorted(hw, w['h'], side='right')
            stop = min(hw[j], w['h'] + 1.0) if j < len(hw) else w['h'] + 1.0
            to = omg.get(k)
            if to is not None:
                j = np.searchsorted(to, w['h'])
                if j < len(to) and to[j] <= stop:
                    od.append(1e3 * (to[j] - w['h']))
        res['blocks'].append(dict(
            block=b, pattern=R['pat'][b], rate=R['rate'][b], n_writes=len(ws), n_steps=len(bs),
            landed=len(landed) / len(ws), steps_landed=np.mean([all(w['land'] is not None for w in by_burst[x['i']]) for x in bs]),
            req_rate=(len(bs) - 1) / T if T > 0 else np.nan, ach_rate=len(lt) / T if T > 0 else np.nan,
            sp1=float(np.mean(sp == 1)) if len(sp) else np.nan, sp_min=float(sp.min()) if len(sp) else np.nan,
            d_p5=np.percentile(d, 5) if len(d) else np.nan, d_p95=np.percentile(d, 95) if len(d) else np.nan,
            n_multi=n_multi, split=split / n_multi if n_multi else np.nan, chance=chance, xdiff=xdiff,
            om_n=len(od), om_med=np.median(od) if od else np.nan, om_p95=np.percentile(od, 95) if od else np.nan,
            late_max=max(x['late'] for x in bs), tramp_found=found.get(b)))
    return res


def table(res):
    M = res['M']; h = res['ph_hist']
    lines = ['# voltage steps: measured numbers', '',
             f'- OUT_DQ landings (ticks whose settled level changed): {len(res["L"])}; not explained by any write: {res["stray"]}',
             f'- edge onsets (mod {res["per"]} samples): {h.sum()} total; {h[np.argsort(h)[::-1][:3]].sum() / max(h.sum(), 1):.1%} '
             f'on the 3 most common phases {sorted(int(p) for p in np.argsort(h)[::-1][:3])}; tick start taken at phase {res["p0"]}',
             f'- host -> FE mapping from {M["n_fit"]}/{M["n_low"]} low-rate writes: drift {1e3 * (M["b"] - 1):+.3f} ms/s; '
             f'(first estimate from {M["n_blocks"]} block offsets {1e3 * M["block_drift"]:+.3f} ms/s, scatter about the line '
             f'{M["block_resid_ms"]:.0f} ms); offset not interpreted (clock offset + latency); re-zeroed by {M.get("rezero_ms", 0):+.0f} ms', '',
             '| block | pattern | req/s | steps | writes landed | steps landed | achieved landings/s | spacing = 1 tick | '
             'min spacing (ticks) | rel. delay p5-p95 (ms) | multi-ch split | chance (if every tick applies) | OUTMON delay med / p95 (ms) | '
             'host lateness max (ms) | TRAMP found |',
             '|' + '---|' * 15]
    tail = ['', 'Writes landed: the value appeared in OUT_DQ before a later write replaced it. Relative delay: landing minus '
             'mapped write, zero at the earliest landing (absolute latency is in the OUTMON column, host side). '
             'Spacing: between successive landings in the block, in ticks. Chance: mean write-burst length / 62.5 ms. '
            'OUTMON delay counts only matches before the next same-value write, so at high rates it is biased short.']
    for r in res['blocks']:
        lines.append(
            f'| {r["block"]} | {r["pattern"]} | {r["rate"]:g} | {r["n_steps"]} | {r["landed"]:.1%} | {r["steps_landed"]:.1%} | '
            f'{r["ach_rate"]:.2f} | {r["sp1"]:.0%} | {r["sp_min"]:g} | {r["d_p5"]:.0f}-{r["d_p95"]:.0f} | '
            + (f'{r["split"]:.1%} of {r["n_multi"]}' if r['n_multi'] else '-') + ' | '
            + (f'{r["chance"]:.1%}' if r['n_multi'] else '-') + ' | '
            + (f'{r["om_med"]:.0f} / {r["om_p95"]:.0f} (n {r["om_n"]})' if r['om_n'] else 'no OUTMON match') + ' | '
            f'{r["late_max"]:.1f} | {",".join(r["tramp_found"] or [])} |')
    return '\n'.join(lines + tail)


# ------------------------------------------------------------------------------------------- plots
def plots(R, res, outdir, zoom=2.0):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(outdir, exist_ok=True)
    dq = R['dq']; M = res['M']
    tf = dq['gps0'] + np.arange(dq['V2'].size) / dq['fs']
    col = {2: 'C0', 4: 'C1', 3: 'C2'}
    name = {2: 'V2 (A)', 4: 'V4 (B)', 3: 'V3 (C)'}
    files = []
    for r in res['blocks']:
        b = r['block']; ws = sorted([w for w in R['W'] if w['block'] == b], key=lambda w: w['m'])
        t_a, t_b = ws[0]['m'] - 0.5, ws[-1]['m'] + 0.5
        sel = (tf >= t_a) & (tf <= t_b)
        t = tf[sel] - ws[0]['m']
        fig, ax = plt.subplots(4, 2, figsize=(13, 9), sharex='col', gridspec_kw=dict(height_ratios=[1, 1, 1, 0.8]))
        for k, c in enumerate(CHANS):
            wc = [w for w in R['W'] if w['chan'] == c and w['m'] <= t_b]
            mt = np.array([w['m'] for w in wc]); mv = np.array([w['v'] for w in wc])
            j = np.searchsorted(mt, tf[sel], side='right') - 1
            cmd = np.where(j >= 0, mv[np.clip(j, 0, None)], 0.0) if len(mt) else np.zeros(sel.sum())
            for col_i, xl in enumerate([(t[0], t[-1]), (-0.2, zoom)]):
                a = ax[k, col_i]
                a.step(t, cmd, where='post', color='k', lw=1, label='commanded (write time, mapped to FE)')
                a.plot(t, dq[f'V{c}'][sel], color=col[c], lw=1.2, label='OUT_DQ (front end)')
                a.set_xlim(*xl); a.set_ylabel(f'{name[c]}\ncounts')
                ax[3, col_i].plot(t, dq[f'V{c}'][sel] - cmd, color=col[c], lw=1, label=name[c])
        for col_i in (0, 1):
            ax[3, col_i].set_ylabel('OUT_DQ - cmd\ncounts'); ax[3, col_i].set_xlabel('s from first write (FE time)')
        ax[0, 0].legend(loc='upper right', fontsize=8); ax[3, 1].legend(fontsize=8, ncol=3)
        ax[0, 1].set_title(f'first {zoom:g} s')
        fig.suptitle(f'block {b}: {r["pattern"]}, {r["rate"]:g} steps/s requested; {r["landed"]:.0%} of writes landed '
                     f'(OUT_DQ is upstream of the output switch)', fontsize=11)
        fig.tight_layout()
        f = os.path.join(outdir, f'block{b:02d}_{r["pattern"]}_{r["rate"]:g}.png'); fig.savefig(f, dpi=110); plt.close(fig)
        files.append(f)

    fig, ax = plt.subplots(2, 2, figsize=(12, 8.5))
    h = res['ph_hist']
    ax[0, 0].bar(np.arange(h.size) / dq['fs'] * 1e3, h, width=1e3 / dq['fs'], color='C0')
    ax[0, 0].set_xlabel('landing time mod 1/16 s (ms, OUT_DQ sample phase)'); ax[0, 0].set_ylabel('landings')
    ax[0, 0].set_title('landing times on the 16 Hz grid')
    for pat, mk in zip(('single', 'all3', 'stepper'), 'osD'):
        rr = [r for r in res['blocks'] if r['pattern'] == pat]
        if rr:
            ax[0, 1].loglog([r['req_rate'] for r in rr], [r['ach_rate'] for r in rr], mk + '-', label=f'{pat}: landings/s')
            ax[0, 1].loglog([r['req_rate'] for r in rr], [r['req_rate'] * r['steps_landed'] for r in rr], mk + ':',
                            alpha=0.6, label=f'{pat}: landed steps/s')
    x = np.array([0.7, 50]); ax[0, 1].loglog(x, x, 'k-', lw=0.8, label='achieved = requested')
    ax[0, 1].axhline(16, color='grey', ls='--', lw=0.8); ax[0, 1].axhline(8, color='grey', ls=':', lw=0.8)
    ax[0, 1].set_xlabel('requested steps/s'); ax[0, 1].set_ylabel('achieved per s'); ax[0, 1].legend(fontsize=7)
    ax[0, 1].set_title('achieved vs requested (lines: 16 and 8 /s)')
    xd = [d for r in res['blocks'] for d in r['xdiff']]
    if xd:
        ax[1, 0].hist(xd, bins=np.arange(-0.5, max(xd) + 1.5, 1), color='C2', rwidth=0.8)
    ax[1, 0].set_xlabel('channel landing - earliest channel of the same step (ticks)'); ax[1, 0].set_ylabel('channel landings')
    ax[1, 0].set_title('multi-channel steps: same tick or split')
    for pat, mk in zip(('single', 'all3', 'stepper'), 'osD'):
        rr = [r for r in res['blocks'] if r['pattern'] == pat and r['om_n']]
        if rr:
            ax[1, 1].errorbar([r['rate'] for r in rr], [r['om_med'] for r in rr],
                              yerr=[[0] * len(rr), [r['om_p95'] - r['om_med'] for r in rr]], fmt=mk + '-', capsize=3, label=pat)
    ax[1, 1].set_xscale('log'); ax[1, 1].set_xlabel('requested steps/s'); ax[1, 1].set_ylabel('write -> OUTMON (ms)')
    ax[1, 1].set_title('host-side delay: median, bar to p95'); ax[1, 1].legend(fontsize=8)
    fig.tight_layout(); f = os.path.join(outdir, 'summary.png'); fig.savefig(f, dpi=110); plt.close(fig)
    files.append(f)
    return files


# ---------------------------------------------------------------------------------------- selftest
def chk(cond, what):
    if not cond:
        print('   CHECK FAILED:', what)
    return bool(cond)


def selftest():
    import tempfile
    ok = True
    def split_by_v3(R):
        """late3 truth: a landed multi-channel step splits iff V3 is among its channels."""
        good = n = 0
        for bi, x in enumerate(R['bursts']):
            wl = [w for w in R['W'] if w['burst'] == bi]
            if len(wl) < 2 or any(w['idx'] is None for w in wl) or R['rate'][x['block']] > 8:
                continue
            n += 1; good += (len({w['idx'] for w in wl}) > 1) == (3 in x['chans'])
        return good, n
    with tempfile.TemporaryDirectory() as d:
        out = {}
        for mode in ('tick', 'every2', 'late3'):
            rd, fe = vs.mock_run(os.path.join(d, mode), mode=mode, seed={'tick': 1, 'every2': 2, 'late3': 3}[mode])
            R = load(rd); res = score(R)
            out[mode] = (R, res)
            by = {(r['pattern'], r['rate']): r for r in res['blocks']}
            print(f'\n== mock {mode}: drift fitted {1e3 * (res["M"]["b"] - 1):+.3f} ms/s (true +1.100), '
                  f'onsets on top-3 phases {np.sort(res["ph_hist"])[::-1][:3].sum() / res["ph_hist"].sum():.0%}, stray {res["stray"]}')
            for p in ('single', 'all3', 'stepper'):
                print('   %-8s' % p + '  '.join('%g/s: %3.0f%% sp1 %3.0f%% split %s d95 %3.0f om %3.0f' % (
                    r, 100 * by[p, r]['landed'], 100 * by[p, r]['sp1'],
                    '-' if not by[p, r]['n_multi'] else '%3.0f%%' % (100 * by[p, r]['split']), by[p, r]['d_p95'],
                    by[p, r]['om_med']) for r in (1, 4, 16, 32)))
            ok &= chk(abs(1e3 * (res['M']['b'] - 1) - 1.1) < 0.1 and np.sort(res['ph_hist'])[::-1][:3].sum() == res['ph_hist'].sum(), 'drift within 0.1 ms/s and all edge onsets within 3 phases')
            ok &= chk(res['stray'] == 0, "res['stray'] == 0")
            low = [r for r in res['blocks'] if r['rate'] <= 4]
            ok &= chk(all(r['landed'] == 1.0 for r in low), "all(r['landed'] == 1.0 for r in low)")
            if mode == 'tick':
                ok &= chk(all(by[p, 8]['landed'] > 0.98 for p in ('single', 'all3', 'stepper')), "all(by[p, 8]['landed'] > 0.98 for p in ('single', 'all3', 'stepper'))")
                ok &= chk(all(by[p, 32]['landed'] < 0.7 for p in ('single', 'all3', 'stepper')), "all(by[p, 32]['landed'] < 0.7 for p in ('single', 'all3', 'stepper'))")
                ok &= chk(all(r['split'] < 0.08 for r in res['blocks'] if r['n_multi'] and r['rate'] <= 16), "all(r['split'] < 0.08 for r in res['blocks'] if r['n_multi'] and r['rate'] <= 16)")
                ok &= chk(all(r['d_p95'] < 70 for r in low) and all(0 < r['om_med'] < 75 for r in low), "all(r['d_p95'] < 70 for r in low) and all(0 < r['om_med'] < 75 for r in low)")
                ok &= chk(by['single', 16]['sp_min'] == 1, "by['single', 16]['sp_min'] == 1")
            if mode == 'every2':
                # square 0<->L at 16/s: both writes fall in one applied tick, last wins, nothing changes (~0 %)
                ok &= chk(all(abs(by[p, 16]['landed'] - 0.5) < 0.15 for p in ('all3', 'stepper')) and by['single', 16]['landed'] < 0.1,
                          'every2 at 16/s: all3/stepper ~50 % landed, square ~0 %')
                ok &= chk(all(r['sp_min'] >= 2 for r in res['blocks'] if r['rate'] >= 8), "all(r['sp_min'] >= 2 for r in res['blocks'] if r['rate'] >= 8)")
                ok &= chk(all(70 < r['d_p95'] < 135 for r in low), "all(70 < r['d_p95'] < 135 for r in low)")
            if mode == 'late3':
                g, n = split_by_v3(R)
                print(f'   late3: {g}/{n} landed multi-channel steps (<= 8/s) split exactly when V3 is among them')
                ok &= chk(g == n and n > 50, 'g == n and n > 50')
                ok &= chk(set(round(x) for r in res['blocks'] for x in r['xdiff']) <= {0, 1}, "set(round(x) for r in res['blocks'] for x in r['xdiff']) <= {0, 1}")
        rd, _ = vs.mock_run(os.path.join(d, 'stair'), patterns='single', rates='1,2,4,8,32', shape='stair', seed=4)
        res = score(load(rd))
        print('\n== mock tick, stair shape: landed', ['%g/s %.0f%%' % (r['rate'], 100 * r['landed']) for r in res['blocks']],
              'stray', res['stray'])
        ok &= chk(res['stray'] == 0 and all(r['landed'] == 1.0 for r in res['blocks'] if r['rate'] <= 8), "res['stray'] == 0 and all(r['landed'] == 1.0 for r in res['blocks'] if r['rate'] <= 8)")
        f = plots(*out['tick'], os.path.join(d, 'plots'))
        print(f'plots: {len(f)} files written')
        ok &= chk(len(f) == 19, 'len(f) == 19')
    print('\nSELFTEST %s' % ('PASSED' if ok else 'FAILED'))
    return 0 if ok else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        return selftest()
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('rundir')
    p.add_argument('--outdir', help='default: RUNDIR/score')
    p.add_argument('--fit-max-rate', type=float, default=8.0, help='blocks used to fit host -> FE')
    a = p.parse_args()
    R = load(a.rundir)
    res = score(R, a.fit_max_rate)
    out = a.outdir or os.path.join(a.rundir, 'score')
    os.makedirs(out, exist_ok=True)
    t = table(res)
    print(t)
    open(os.path.join(out, 'summary.md'), 'w').write(t + '\n')
    for f in plots(R, res, out):
        print('  ', f)
    return 0


if __name__ == '__main__':
    sys.exit(main())
