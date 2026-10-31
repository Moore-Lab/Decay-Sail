"""Score an angle file against the hand labels (gate 4).

    python score_angles.py ANGLES.csv GPS [--offset DEG]
    python score_angles.py selftest GPS

ANGLES.csv: any CSV with `frame` and `angle_deg` columns ('#' lines ignored; a `status`
column other than 'ok' counts as no answer). Labels: labels/labels_gps<GPS>.csv.

--offset is added to the detector's angles before comparing. It is the DECLARED angle from
the detector's reference point to the labelled point, fixed per detector + template from
geometry, never fitted per run: a fitted offset would let a copy rotated by 180 deg pass.
The fitted offset is printed only as a check (a warning if it differs by more than 2 deg).
For blob_track.py with template frame 0 at 257 deg, the declared offset is
point_gps<GPS>.json ref_angle (mod 360) - 257 (the reference image is frame 0's orientation).
This rule holds only because label_frames.py select de-rotates the reference image to frame 0
and blob_track was run with REF_FRAME = 0. With another REF_FRAME the two angles are in different
orientations and the rule silently gives a wrong offset.

Reports, over frames Molly labelled: % within 5 deg, rms, max, wrong-feature rate (error
within 10 deg of a nonzero multiple of 45 deg: the 180 deg sail and 45 deg arm aliases),
% with no answer, and the same split by why the frame was selected. PASS needs >= 95%
within 5 deg and < 1% wrong-feature (gate-5 marks, provisional), with no-answer frames
counted as misses. Exit status 0 = PASS, 1 = FAIL.
"""
import csv, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.join(HERE, 'labels')
WITHIN, WRONG_TOL, PASS_WITHIN, PASS_WRONG = 5.0, 10.0, 95.0, 1.0

def read_angles(f):
    rows = csv.DictReader(l for l in open(f) if not l.startswith('#'))
    out = {}
    for r in rows:
        if r.get('status', 'ok') == 'ok' and r['angle_deg'] not in ('', 'nan'):
            out[int(r['frame'])] = float(r['angle_deg'])
    return out

def wrap(x): return (np.asarray(x) + 180) % 360 - 180

def score(det, gps, offset, name, quiet=False):
    lab = read_angles(os.path.join(LAB, 'labels_gps%s.csv' % gps))
    sel = {int(r['frame']): r['reason'].split('_bin')[0]
           for r in csv.DictReader(open(os.path.join(LAB, 'selection_gps%s.csv' % gps)))}
    frames = sorted(lab); have = np.array([f in det for f in frames])
    err = np.array([wrap(det[f] + offset - lab[f]) if f in det else np.nan for f in frames])
    e = err[have]; k = np.round(e / 45)
    wrong = (k != 0) & (np.abs(e - 45 * k) < WRONG_TOL)
    within = np.abs(e) < WITHIN
    n = len(frames)
    pct_within = 100 * within.sum() / n                     # no-answer frames count as misses
    pct_wrong = 100 * wrong.sum() / n
    fit = np.degrees(np.angle(np.mean(np.exp(1j * np.deg2rad(e))))) if len(e) else np.nan
    ok = pct_within >= PASS_WITHIN and pct_wrong < PASS_WRONG
    if not quiet:
        print('== %s vs labels_gps%s (%d labelled frames), declared offset %+.2f deg' % (name, gps, n, offset))
        print('  within %.0f deg: %.1f%%   wrong-feature: %.1f%%   no answer: %.1f%%' % (
            WITHIN, pct_within, pct_wrong, 100 * (~have).mean()))
        if len(e):
            print('  rms %.2f deg, max |err| %.2f deg; rms of non-wrong-feature %.2f deg' % (
                np.sqrt(np.mean(e**2)), np.abs(e).max(), np.sqrt(np.mean(e[~wrong]**2)) if (~wrong).any() else np.nan))
            print('  fitted offset would be %+.2f deg%s' % (offset - fit, '   WARNING: differs from declared by >2 deg' if abs(fit) > 2 else ''))
            cats = np.array([sel.get(f, '?') for f in frames])[have]
            for c in sorted(set(cats)):
                m = cats == c
                print('    %-11s n=%3d  within %5.1f%%  rms %6.2f  max %6.2f' % (
                    c, m.sum(), 100 * within[m].mean(), np.sqrt(np.mean(e[m]**2)), np.abs(e[m]).max()))
        print('  %s (needs >= %.0f%% within %.0f deg and < %.0f%% wrong-feature)' % (
            'PASS' if ok else 'FAIL', PASS_WITHIN, WITHIN, PASS_WRONG))
    return ok

def selftest(gps):
    lab = read_angles(os.path.join(LAB, 'labels_gps%s.csv' % gps))
    rng = np.random.default_rng(0); fs = sorted(lab)
    cases = [('labels themselves', lab, True),
             ('labels rotated 180 deg', {f: a + 180 for f, a in lab.items()}, False),
             ('labels rotated 45 deg', {f: a + 45 for f, a in lab.items()}, False),
             ('labels + 1 deg rms noise', {f: a + rng.normal(0, 1.0) for f, a in lab.items()}, True),
             ('6% of frames flipped 180', {f: a + (180 if i % 16 == 0 else 0) for i, (f, a) in enumerate(lab.items())}, False),
             ('6% of frames missing', {f: a for i, (f, a) in enumerate(lab.items()) if i % 16}, False)]
    good = True
    for name, det, expect in cases:
        r = score(det, gps, 0.0, name)
        print('  -> expected %s: %s\n' % ('PASS' if expect else 'FAIL', 'ok' if r == expect else 'SELFTEST FAILED'))
        good &= (r == expect)
    print('SELFTEST %s' % ('PASSED' if good else 'FAILED')); return good

if __name__ == '__main__':
    if sys.argv[1] == 'selftest': sys.exit(0 if selftest(sys.argv[2]) else 1)
    off = float(sys.argv[sys.argv.index('--offset') + 1]) if '--offset' in sys.argv else 0.0
    sys.exit(0 if score(read_angles(sys.argv[1]), sys.argv[2], off, os.path.basename(sys.argv[1])) else 1)
