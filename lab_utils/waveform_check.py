#!/usr/bin/env python3
"""Gate W1 scorer (analysis only): did the front end output the waveform the AWG was given?

    python3 waveform_check.py RUN_DIR          # RUN_DIR has command.npz and out_dq.npz
    python3 waveform_check.py selftest

command.npz (written by awg_waveform_drive.py): name, fs, t, w (3 x N, V2/V3/V4, peak 1), amp,
pedestal, start_gps (front-end frame, the shared AWG start).
out_dq.npz (same script, fetched from NDS after the run): gps0, fs, V2, V3, V4 (OUTS_V{n}_OUT_DQ).

Per electrode, fits   measured(t) = pedestal + gain * amp * w(t - start - lag)
over the waveform +-0.5 s, with lag found to ~0.01 ms (coarse cross-correlation, then a fine grid).
Reports gain, lag, residual rms and max (% of amp), and the recorded range against the amplifier's
0..12800 input range. For `step` it also reports the residual away from the jumps and the size of
the post-jump ringing separately: that is the F2 out-of-range question.

Pass mark (PROPOSED 2026-11-03, Molly agreed "matches + 1 ms"; the numbers are Claude's proposal):
  |gain - 1| <= 1 %, residual rms <= 1 % of amp (for `step`, away from the jumps),
  and every electrode's lag within 1 ms of V2's.
Printed, not decided: Molly makes the call.
"""
import sys
import numpy as np

ELECTRODES = (2, 3, 4)
EDGE_S = 0.015             # step: residual "near a jump" = within 15 ms after it


def model_on(tm, t_cmd, c, start, lag):
    """Command c (sampled at t_cmd from `start`) evaluated at measured times tm, shifted by lag."""
    return np.interp(tm - start - lag, t_cmd, c, left=0.0, right=0.0)


def fit_channel(tm, m, t_cmd, c, start, max_lag=1.0):
    """-> dict(gain, ped, lag, resid). Linear LSQ for (ped, gain) at each trial lag."""
    win = (tm > start - 0.5) & (tm < start + t_cmd[-1] + 0.5)
    tw, mw = tm[win], m[win]

    def solve(lag):
        x = model_on(tw, t_cmd, c, start, lag)
        A = np.column_stack([np.ones_like(x), x])
        (ped, g), *_ = np.linalg.lstsq(A, mw, rcond=None)
        r = mw - ped - g * x
        return float(r @ r), ped, g, r

    dt = np.median(np.diff(tm))
    coarse = np.arange(-max_lag, max_lag + dt / 2, dt)
    # Coarse: correlate the demeaned record with the command on the measured grid
    md = mw - mw.mean()
    best = max(coarse, key=lambda L: abs(np.dot(md, np.interp(tw - start - L, t_cmd, c, 0, 0))))
    fine = np.arange(best - 2 * dt, best + 2 * dt, 1e-5)
    errs = [solve(L)[0] for L in fine]
    lag = float(fine[int(np.argmin(errs))])
    _, ped, g, r = solve(lag)
    return dict(gain=g, ped=ped, lag=lag, resid=r, t=tw, m=mw, x=model_on(tw, t_cmd, c, start, lag))


def score(cmd, dq, quiet=False):
    t_cmd, w, amp, start = cmd['t'], cmd['w'], float(cmd['amp']), float(cmd['start_gps'])
    fs_m = float(dq['fs'])
    name = str(cmd['name'])
    res = {}
    for k, n in enumerate(ELECTRODES):
        m = np.asarray(dq[f'V{n}'], float)
        tm = float(dq['gps0']) + np.arange(m.size) / fs_m
        f = fit_channel(tm, m, t_cmd, amp * w[k], start)
        r = f['resid']
        f['rms_pct'] = 100 * r.std() / amp
        f['max_pct'] = 100 * np.abs(r).max() / amp
        f['lo'], f['hi'] = float(f['m'].min()), float(f['m'].max())
        if name == 'step':
            jumps = t_cmd[1:][np.any(np.abs(np.diff(w, axis=1)) > 0.05, axis=0)]
            tt = f['t'] - start - f['lag']
            near = np.zeros(tt.size, bool)
            for tj in jumps:
                near |= (tt >= tj - 1 / fs_m) & (tt < tj + EDGE_S)
            f['rms_away_pct'] = 100 * r[~near].std() / amp
            f['ring_pct'] = 100 * np.abs(r[near]).max() / amp if near.any() else 0.0
        res[n] = f
    lag0 = res[2]['lag']
    ok = True
    if not quiet:
        print(f'{name}: amp {amp:g}, pedestal {float(cmd["pedestal"]):g}, OUT_DQ at {fs_m:g} Hz')
        hdr = '  elec   gain    lag ms  rel ms  resid rms%  max%   recorded range'
        print(hdr + ('   away rms%  ring%' if name == 'step' else ''))
    for n in ELECTRODES:
        f = res[n]
        rel = 1e3 * (f['lag'] - lag0)
        rms = f.get('rms_away_pct', f['rms_pct'])
        good = abs(f['gain'] - 1) <= 0.01 and rms <= 1.0 and abs(rel) <= 1.0
        ok &= good
        if not quiet:
            line = (f'  V{n}  {f["gain"]:7.4f} {1e3 * f["lag"]:+8.2f} {rel:+7.2f} {f["rms_pct"]:10.2f} '
                    f'{f["max_pct"]:6.1f}   {f["lo"]:7.0f}..{f["hi"]:<7.0f}')
            if name == 'step':
                line += f'  {f["rms_away_pct"]:9.2f}  {f["ring_pct"]:5.1f}'
            out = f['lo'] < 0 or f['hi'] > 12800
            print(line + ('   OUT OF 0..12800' if out else '') + ('' if good else '   <- misses mark'))
    if not quiet:
        print(f'W1 by the proposed mark: {"PASS" if ok else "not met"}')
    return ok, res


def load(run_dir):
    import os
    c = dict(np.load(os.path.join(run_dir, 'command.npz'), allow_pickle=False))
    d = dict(np.load(os.path.join(run_dir, 'out_dq.npz'), allow_pickle=False))
    return c, d


def selftest():
    sys.path.insert(0, __import__('os').path.dirname(__file__))
    import waveforms
    rng = np.random.default_rng(1)
    all_ok = True

    def synth(name, lags_ms, gains, ring=False, amp=500.0, ped=1000.0):
        t, w = waveforms.make(name)
        start = 1477800000.25
        gps0 = 1477799998.0
        fs = 1024.0
        tm = gps0 + np.arange(int((t[-1] + 4) * fs)) / fs
        dq = dict(gps0=gps0, fs=fs)
        for k, n in enumerate(ELECTRODES):
            x = ped + gains[k] * amp * np.interp(tm - start - lags_ms[k] / 1e3, t, w[k], 0, 0)
            if ring:   # decimation-like ringing: a decaying alternating tail after every jump
                d = np.diff(x, prepend=x[0])
                h = 0.25 * (-0.6) ** np.arange(12)
                x = x + np.convolve(d, h)[:x.size]
            dq[f'V{n}'] = x + rng.normal(0, 0.5, x.size)
        cmd = dict(name=name, t=t, w=w, amp=amp, pedestal=ped, start_gps=start, fs=2048.0)
        return cmd, dq

    print('-- sine, small equal lags: expect PASS')
    ok, res = score(*synth('sine', [0.4, 0.45, 0.4], [1, 1, 1]))
    good = ok and all(abs(1e3 * res[n]['lag'] - v) < 0.05 for n, v in zip(ELECTRODES, [0.4, 0.45, 0.4]))
    print('   lags recovered within 0.05 ms:', good); all_ok &= good
    print('-- chirp, V4 2.5 ms late: expect not met')
    ok, _ = score(*synth('chirp', [0.0, 0.0, 2.5], [1, 1, 1])); all_ok &= not ok
    print('-- pulse, V3 gain 0.95: expect not met')
    ok, _ = score(*synth('pulse', [0.2, 0.2, 0.2], [1, 0.95, 1])); all_ok &= not ok
    print('-- step with ringing after jumps: expect PASS away from jumps, ring% > 0')
    ok, res = score(*synth('step', [0.3, 0.3, 0.3], [1, 1, 1], ring=True))
    good = ok and all(res[n]['ring_pct'] > 5 for n in ELECTRODES)
    print('   ringing seen and kept out of the pass mark:', good); all_ok &= good
    print('-- spinup, clean: expect PASS')
    ok, _ = score(*synth('spinup', [0.1, 0.1, 0.1], [1, 1, 1])); all_ok &= ok
    print('SELFTEST', 'PASSED' if all_ok else 'FAILED')
    return 0 if all_ok else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        sys.exit(selftest())
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ok, _ = score(*load(sys.argv[1]))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
