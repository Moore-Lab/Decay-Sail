#!/usr/bin/env python3
"""Gate F2 scorer (Mac, analysis only): which lead grows the swing?

    python3 feedback_f2_check.py BLOB_LIVE.csv FEEDBACK_LOG.csv [FEEDBACK_LOG2.csv ...]
    python3 feedback_f2_check.py selftest

Inputs: the live tracker CSV (frame, host_time, angle_deg, ...) and one feedback_drive.py log per scan
(`run --scan default`: host_time, ..., lead, ...). Both are in worker2 host time, so no front-end clock
is needed.

Per lead step: the swing amplitude (sqrt2 x rms of the linearly detrended angle) over the first and last
3 s of the step. Growth = last - first, in deg per step. Leads come in +/- pairs (45/-45, 90/-90,
135/-135, 0/180); pair score = growth(+) - growth(-).
Pass (agreed 2026-11-02): in two scans, the same lead has the largest positive growth, its opposite
shrinks the swing (negative growth), and the pair score has the same sign and exceeds 3x the spread of
the 0/180 pair (a reference with no expected net effect for a V^2 coupling). Printed, not decided:
Molly makes the call from this table and the video.
"""
import csv, sys
import numpy as np


def load_blob(fn):
    rows = list(csv.DictReader(l for l in open(fn) if not l.startswith('#')))
    t = np.array([float(r['host_time']) for r in rows]); a = np.unwrap(np.radians([float(r['angle_deg']) for r in rows]))
    return t, np.degrees(a)


def load_steps(fn):
    rows = list(csv.DictReader(l for l in open(fn) if not l.startswith('#')))
    t = np.array([float(r['frame_host_time']) for r in rows]); lead = np.array([float(r['lead']) for r in rows])
    steps = []; k0 = 0
    for k in range(1, len(lead) + 1):
        if k == len(lead) or lead[k] != lead[k0]:
            steps.append((lead[k0], t[k0], t[k - 1])); k0 = k
    return steps


def swing(t, th, a, b):
    m = (t >= a) & (t < b)
    if m.sum() < 20:
        return np.nan
    x = t[m] - t[m].mean(); y = th[m]
    return np.sqrt(2) * (y - np.polyval(np.polyfit(x, y, 1), x)).std()


def score(t, th, steps, edge=3.0):
    out = {}
    for lead, a, b in steps:
        if b - a < 2 * edge + 1:
            continue
        out[lead] = swing(t, th, b - edge, b) - swing(t, th, a, a + edge)
    return out


def report(scans):
    leads = sorted({l for s in scans for l in s})
    print('growth per 10 s step (deg), one column per scan:')
    for l in leads:
        print('  lead %+5.0f: %s' % (l, '  '.join('%+6.1f' % s.get(l, np.nan) for s in scans)))
    best = [max(s, key=lambda k: s[k]) for s in scans]
    print('largest growth per scan at lead: %s' % ', '.join('%+.0f' % b for b in best))
    ok = len(scans) >= 2 and len(set(best)) == 1
    if ok:
        b = best[0]; opp = -b if b not in (0, 180) else (180 if b == 0 else 0)
        pair = [s[b] - s.get(opp, np.nan) for s in scans]
        ref = [abs(s.get(0, 0) - s.get(180, 0)) for s in scans]
        shrinks = all(s.get(opp, 1) < 0 for s in scans)
        big = all(p > 3 * max(r, 1.0) for p, r in zip(pair, ref))
        print('lead %+.0f vs %+.0f: pair score %s; opposite shrinks in every scan: %s; above 3x the 0/180 spread: %s'
              % (b, opp, ' '.join('%+.1f' % p for p in pair), shrinks, big))
        ok = shrinks and big
    print('F2 (by the agreed mark): %s' % ('PASS' if ok else 'not met'))
    return ok


def selftest():
    """Synthetic: a swing that grows at lead 45 and -135, shrinks at -45 and 135, nothing at 0/180/+-90."""
    rng = np.random.default_rng(0)
    eff = {45: 1.0, -45: -1.0, 90: 0.1, -90: -0.1, 135: -1.0, -135: 1.0, 0: 0.0, 180: 0.0}
    def make(order, t0):
        t = []; th = []; steps = []; A = 20.0
        for l in order:
            tt = t0 + np.arange(0, 10, 0.02)
            amp = A + eff[l] * 1.2 * (tt - t0)
            th.append(227 + amp * np.sin(2 * np.pi * 0.33 * tt) + rng.normal(0, 0.1, len(tt))); t.append(tt)
            steps.append((float(l), tt[0], tt[-1])); A = amp[-1]; t0 += 10
        return np.concatenate(t), np.concatenate(th), steps
    order = [45, -45, 90, -90, 135, -135, 0, 180]
    s1 = score(*make(order, 0.0)); s2 = score(*make(order, 1000.0))
    ok = report([s1, s2])
    s3 = {k: v * 0 + rng.normal(0, 0.5) for k, v in s1.items()}; s4 = {k: rng.normal(0, 0.5) for k in s1}
    print('-- null (no effect):')
    ok_null = not report([s3, s4])
    print('SELFTEST %s' % ('PASSED' if ok and ok_null else 'FAILED'))
    return 0 if ok and ok_null else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        sys.exit(selftest())
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    t, th = load_blob(sys.argv[1])
    sys.exit(0 if report([score(t, th, load_steps(f)) for f in sys.argv[2:]]) else 1)


if __name__ == '__main__':
    main()
