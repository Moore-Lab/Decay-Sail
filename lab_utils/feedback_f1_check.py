#!/usr/bin/env python3
"""Gate F1 scorer (outputs off): did the field the front end produced follow the controller's commands?

    python3 feedback_f1_check.py FEEDBACK_LOG.csv V2.h5 V3.h5 V4.h5
    python3 feedback_f1_check.py selftest

Mac, analysis only. Inputs: the feedback_drive.py log and Y1:RDS-OUTS_V{2,3,4}_OUT_DQ (1024 Hz,
front-end time) fetched over the run. The field angle in OUT_DQ is arg(sum_n V_n e^{-i phi_n})
(phi = 0, -120, -240 for V2, V4, V3; the common pedestal cancels), its size |.|*2/3 = COSGAIN.

Clocks: the log is in worker2 host time; OUT_DQ in front-end time, which drifts ~1 ms/s against
true time (FE - true GPS went 15368.7 -> 15380.9 s over 3.1 h on 2026-11-02) and is read over
EPICS only to 1 s. So the scorer FITS the mapping t_fe = t_host + c + r (t_host - t0): c within
-1.5..+4 s of the logged loop-start pair, r within +-3e-3. The fitted c mixes clock offset and the
write-to-DAC latency, so absolute latency is NOT measured here (it is set by --latency and
tuned in F2).

Pass marks (proposed, Molly to agree):
  1. after alignment, |psi_OUT_DQ - psi_cmd| <= 5 deg for >= 99% of 1024 Hz samples, excluding
     5 ms after each commanded step;
  2. >= 99% of commanded updates appear as a distinct step in OUT_DQ;
  3. field size within 1% of COSGAIN while the loop runs;
  4. worker2 loop time (frame host time -> writes issued) p99 <= 15 ms.
Exit 0 = pass, 1 = fail.
"""
import sys
import numpy as np

GPS_UNIX_OFF = 315964800 - 18
PHI = {'V2': 0.0, 'V4': -120.0, 'V3': -240.0}


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def score(t_host, psi_cmd, fe_start, fs, V, loop_start, frame_host, amp_expected):
    """t_host: write times (unix s); psi_cmd deg; V: dict of OUT_DQ arrays; loop_start (host, fe)."""
    n = min(len(v) for v in V.values())
    z = sum(V[k][:n] * np.exp(-1j * np.radians(PHI[k])) for k in PHI) * 2 / 3
    t_fe = fe_start + np.arange(n) / fs
    psi_m = np.degrees(np.angle(z)); size = np.abs(z)
    h0, f0 = loop_start
    base = f0 - (h0 - GPS_UNIX_OFF)                       # FE - true GPS, to ~1 s
    tm = t_host - GPS_UNIX_OFF + base                     # first guess of the FE time of each write
    sel = (t_fe >= tm[0] - 2) & (t_fe <= tm[-1] + 2)
    tf, pm = t_fe[sel], psi_m[sel]

    def resid(c, r):
        tw = tm + c + r * (tm - tm[0])
        k = np.searchsorted(tw, tf, side='right') - 1     # last write before each sample
        ok = (k >= 0) & (tf <= tw[-1] + 0.1)
        since = tf[ok] - tw[k[ok]]
        d = np.abs(wrap(pm[ok] - psi_cmd[k[ok]]))
        return d[since > 0.005], ok
    # objective: fraction of samples within 2 deg (the median is degenerate: 0 for many fits)
    best = (-1.0, 0, 0)
    for c in np.arange(-1.5, 4.0, 0.002):        # +4 s: F1 2026-11-02 measured ~2.6 s
        d, _ = resid(c, 0.0)
        if len(d) and np.mean(d <= 2) > best[0]:
            best = (np.mean(d <= 2), c, 0.0)
    c0 = best[1]
    for r in np.linspace(-3e-3, 3e-3, 61):
        for c in np.arange(c0 - 0.03, c0 + 0.03, 0.0005):
            d, _ = resid(c, r)
            if len(d) and np.mean(d <= 2) > best[0]:
                best = (np.mean(d <= 2), c, r)
    d, ok = resid(best[1], best[2])
    frac = float(np.mean(d <= 5.0))
    # distinct steps: sample-to-sample changes of psi in OUT_DQ vs commanded changes
    dp = np.abs(wrap(np.diff(pm))) > 0.05
    n_steps = int(np.sum(dp)); n_cmd = int(np.sum(np.abs(wrap(np.diff(psi_cmd))) > 0.05))
    run = (tf >= tm[0] + best[1] + 1) & (tf <= tm[-1] + best[1] - 0.2)
    sz = size[sel][run]
    loop_ms = 1e3 * (t_host - frame_host)
    res = dict(frac=frac, med=float(np.median(d)), c=best[1], r=best[2], n_steps=n_steps, n_cmd=n_cmd,
               size_err=float(np.max(np.abs(sz / amp_expected - 1))) if len(sz) else np.nan,
               loop_p99=float(np.percentile(loop_ms, 99)), loop_med=float(np.median(loop_ms)))
    res['pass'] = [res['frac'] >= 0.99, n_steps >= 0.99 * n_cmd, res['size_err'] <= 0.01, res['loop_p99'] <= 15]
    return res


def report(res):
    names = ['field direction within 5 deg (>= 99% of samples)', 'commanded updates seen as steps (>= 99%)',
             'field size within 1% of COSGAIN', 'worker2 loop time p99 <= 15 ms']
    vals = ['%.2f%% (median error %.2f deg)' % (100 * res['frac'], res['med']),
            '%d steps for %d commanded changes' % (res['n_steps'], res['n_cmd']),
            'max error %.2f%%' % (100 * res['size_err']),
            'p99 %.1f ms (median %.1f)' % (res['loop_p99'], res['loop_med'])]
    for n, v, p in zip(names, vals, res['pass']):
        print('  %-52s %s  %s' % (n, 'PASS' if p else 'FAIL', v))
    print('  alignment: c %+.4f s, drift %+.2e (offset + latency together; latency not separated)' % (res['c'], res['r']))
    print('F1: %s' % ('PASS' if all(res['pass']) else 'FAIL'))
    return all(res['pass'])


def synth(latency=0.03, drift=1.1e-3, offset=15380.9, drop=0.0, seed=0):
    rng = np.random.default_rng(seed)
    h0 = 1793650000.0; T = 30.0
    frame_host = h0 + np.arange(0, T, 0.02) + rng.normal(0, 0.001, int(T / 0.02))
    t_host = frame_host + 0.004 + np.abs(rng.normal(0, 0.002, len(frame_host)))
    th = 227 + 25 * np.sin(2 * np.pi * 0.33 * (frame_host - h0))
    psi = (-8 * th + 45) % 360
    fs = 1024.0; fe_start = np.floor(h0 - GPS_UNIX_OFF + offset) - 2
    t_fe = fe_start + np.arange(int((T + 4) * fs)) / fs
    t_app = (t_host - GPS_UNIX_OFF + offset) + latency
    t_app = t_app + drift * (t_app - t_app[0])
    keep = rng.random(len(t_app)) >= drop
    k = np.searchsorted(t_app[keep], t_fe, side='right') - 1
    p = np.where(k >= 0, psi[keep][np.clip(k, 0, None)], 0.0)
    V = {n: 6400 + 6400 * np.cos(np.radians(p + PHI[n])) for n in PHI}
    loop_start = (h0, np.round(h0 - GPS_UNIX_OFF + offset))
    return t_host, psi, fe_start, fs, V, loop_start, frame_host


def selftest():
    print('clean synthetic run (30 ms latency, 1.1 ms/s drift):')
    ok1 = report(score(*synth(), amp_expected=6400.0))
    print('broken: 5% of updates lost:')
    ok2 = report(score(*synth(drop=0.05), amp_expected=6400.0))
    good = ok1 and not ok2
    print('SELFTEST %s' % ('PASSED' if good else 'FAILED'))
    return 0 if good else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        sys.exit(selftest())
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    import h5py
    logf, files = sys.argv[1], sys.argv[2:5]
    loop_start = None
    with open(logf) as fh:
        for line in fh:
            if line.startswith('# loop_start'):
                w = line.split(); loop_start = (float(w[3]), float(w[5]))
    if loop_start is None:
        sys.exit('! no loop_start line in the log')
    import csv
    rows = list(csv.DictReader(l for l in open(logf) if not l.startswith('#')))
    d = {k: np.array([float(r[k]) for r in rows]) for k in ('host_time', 'psi_deg', 'frame_host_time')}
    V = {}
    for f in files:
        with h5py.File(f) as h:
            ch = h.attrs['channel']; key = [k for k in PHI if '_%s_' % k in ch][0]
            V[key] = h['data'][:].astype(float); fs = h.attrs['sample_rate']; fe_start = h['segments/gps_start'][0]
    res = score(d['host_time'], d['psi_deg'], fe_start, fs, V, loop_start, d['frame_host_time'], 6400.0)
    sys.exit(0 if report(res) else 1)


if __name__ == '__main__':
    main()
