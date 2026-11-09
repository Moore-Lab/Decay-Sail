#!/usr/bin/env python3
"""G0 checker for OSC_CHIRP_RUNBOOK.md: is the oscillator chirp what we think it is? (outputs-off data)

    python3 osc_chirp_check.py V2.h5 V3.h5 V4.h5 [--fs 1024] [--f-start 0.40] [--f-end 0.15] [--amp 6400]
    python3 osc_chirp_check.py selftest

Inputs: the three Y1:RDS-OUTS_V{2,3,4}_OUT_DQ files from batch_fetch.fetch_channel (h5: 'data', 'segments/gps_start').
Phasor z = (2/3) sum V_n exp(-i phi_n) / amp, phi = 0 / -120 / -240 for V2 / V4 / V3; the pedestal cancels.
Checks (each prints its numbers and PASS/FAIL):
  1. pedestal: the three channels' 50 % crossings within 0.5 s of each other; level 6400 +- 50 before any AC
  2. AC ramp-in: |z| 10-90 % rise >= 2 s (a ramp, not a step); plateau within +-5 %
  3. phase: no sample-to-sample phase step > 10 deg while |z| > 0.5
  4. frequency (0.5 s smoothing): starts at f_start +- 0.01, ends at f_end +- 0.01, never rises by > 0.005 Hz,
     no flat stretch longer than 1.0 s between the first and last step
  5. teardown: |z| below 0.02 before the pedestal starts to drop
"""
import sys

import numpy as np

PHI = {'V2': 0.0, 'V4': -120.0, 'V3': -240.0}


def load(fn):
    import h5py
    with h5py.File(fn, 'r') as h:
        return float(h['segments/gps_start'][0]), np.asarray(h['data'][:], float)


def check(V, fs=1024.0, f_start=0.40, f_end=0.15, amp=6400.0, quiet=False):
    """V: dict 'V2','V3','V4' -> arrays (same start, same rate). Returns (all_pass, results)."""
    out = {}
    def rep(name, ok, msg):
        out[name] = ok
        if not quiet:
            print(f'  {name:<10} {"PASS" if ok else "FAIL"}  {msg}')
    n = min(len(v) for v in V.values()); t = np.arange(n) / fs
    V = {k: v[:n] for k, v in V.items()}
    z = sum(V[k] * np.exp(-1j * np.radians(PHI[k])) for k in PHI) * 2 / 3 / amp
    a = np.abs(z)
    cm = (V['V2'] + V['V3'] + V['V4']) / 3
    # 1. pedestal
    on = np.where(a > 0.05)[0]
    if on.size == 0:
        rep('pedestal', False, 'no AC found (|z| never > 0.05)'); return False, out
    i_ac = on[0]
    cross = {k: (np.argmax(V[k][:i_ac] > 0.5 * amp) / fs if np.any(V[k][:i_ac] > 0.5 * amp) else np.nan) for k in V}
    spread = np.nanmax(list(cross.values())) - np.nanmin(list(cross.values()))
    lvl = np.median(cm[max(0, i_ac - int(fs)):i_ac])
    rep('pedestal', bool(np.isfinite(spread) and spread < 0.5 and abs(lvl - amp) < 50),
        f'50% crossings spread {spread:.2f} s; level before AC {lvl:.0f} (want {amp:.0f} +- 50)')
    # 2. AC ramp-in and plateau
    plat_i = on[-1]
    top = np.median(a[i_ac:plat_i])
    i10 = i_ac + np.argmax(a[i_ac:] > 0.1 * top); i90 = i_ac + np.argmax(a[i_ac:] > 0.9 * top)
    rise = (i90 - i10) / fs
    body = a[i90:plat_i]
    i_down = i90 + (np.argmax(body < 0.9 * top) if np.any(body < 0.9 * top) else body.size)
    pl = a[i90 + int(fs):i_down - int(fs)]          # 1 s in from each end of the plateau
    dev = np.max(np.abs(pl / top - 1)) if pl.size else np.nan
    rep('ramp-in', bool(rise >= 2.0 and dev < 0.05), f'|z| 10-90% rise {rise:.2f} s (want >= 2); plateau {top:.3f}, max dev {dev * 100:.1f}% (want < 5)')
    # 3. phase steps
    ph = np.unwrap(np.angle(z)); live = a > 0.5
    dph = np.degrees(np.abs(np.diff(ph)))[live[1:] & live[:-1]]
    rep('phase', bool(dph.size and dph.max() < 10), f'max sample-to-sample phase step {dph.max():.2f} deg (want < 10)')
    # 4. frequency
    seg = slice(i90, i_down)
    k = int(0.5 * fs)
    f = np.convolve(np.gradient(ph[seg]) * fs / (2 * np.pi), np.ones(k) / k, mode='valid')
    fa = np.abs(f)
    rises = np.max(np.maximum.accumulate(fa[::-1])[::-1] - fa) if False else np.max(fa[1:] - np.minimum.accumulate(fa)[:-1])
    flat = np.abs(np.diff(fa)) * fs < 1e-4                      # |df/dt| < 1e-4 Hz/s
    inner = (fa < f_start - 0.005) & (fa > f_end + 0.005)
    run = best = 0
    for fl, inn in zip(flat, inner[1:]):
        run = run + 1 if (fl and inn) else 0; best = max(best, run)
    ok4 = abs(fa[0] - f_start) < 0.01 and abs(np.median(fa[-k:]) - f_end) < 0.01 and rises < 0.005 and best / fs <= 1.0
    rep('frequency', bool(ok4), f'start {fa[0]:.3f} Hz, end {np.median(fa[-k:]):.3f} Hz (want {f_start}/{f_end} +- 0.01); '
        f'largest rise {rises:.4f} Hz (want < 0.005); longest flat stretch {best / fs:.2f} s (want <= 1.0)')
    # 5. teardown
    i_off = on[-1]
    after = cm[i_off:]
    drop = np.argmax(after < amp - 100) if np.any(after < amp - 100) else None
    if drop is None:
        rep('teardown', False, 'pedestal never drops in the data (fetch longer?)')
    else:
        rep('teardown', bool(drop > 0), f'pedestal starts to drop {drop / fs:.2f} s after |z| < 0.05 (want > 0)')
    allok = all(out.values())
    if not quiet:
        print('  G0', 'PASS' if allok else 'FAIL')
    return allok, out


def synth(fs=1024.0, amp=6400.0, glide=3.5, dwell=4.0, f_a=0.40, f_b=0.15, n=26, jump_deg=0.0, step_on=False):
    """Pedestal ramp 10 s, AC ramp-in over `glide` s, chained glides, ramp-out, pedestal down."""
    T = 12 + glide + 2 + n * dwell + glide + 12
    t = np.arange(int(T * fs)) / fs
    ped = np.clip(t / 10, 0, 1) * amp
    t_ac = 12.0; t_sw = t_ac + glide + 2; t_end = t_sw + n * dwell
    fs_ = np.linspace(f_a, f_b, n)
    f = np.full(t.size, f_a)
    for i in range(n - 1):
        m = (t >= t_sw + i * dwell)
        f[m] = fs_[i] + (fs_[i + 1] - fs_[i]) * np.clip((t[m] - t_sw - i * dwell) / glide, 0, 1)
    f[t >= t_sw + (n - 1) * dwell] = f_b
    psi = 2 * np.pi * np.cumsum(f) / fs + np.radians(jump_deg) * (t > t_sw + 10 * dwell)
    g = (np.clip((t - t_ac) / glide, 0, 1) if not step_on else (t >= t_ac).astype(float)) * np.clip((t_end + glide - t) / glide, 0, 1)
    ped = np.where(t > t_end + glide + 1, np.clip(ped * (1 - (t - t_end - glide - 1) / 10), 0, None), ped)
    return {k: ped + amp * g * np.cos(psi + np.radians(PHI[k])) for k in PHI}


def selftest():
    print('-- clean synthetic chirp (must PASS):'); ok1, _ = check(synth())
    print('-- with a 30 deg phase jump mid-sweep (must FAIL phase):'); ok2, r2 = check(synth(jump_deg=30))
    print('-- with the AC stepped on (must FAIL ramp-in):'); ok3, r3 = check(synth(step_on=True))
    good = ok1 and not r2['phase'] and not r3['ramp-in']
    print('SELFTEST', 'PASSED' if good else 'FAILED')
    return 0 if good else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        sys.exit(selftest())
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    opt = {k: float(sys.argv[sys.argv.index(f'--{k.replace("_", "-")}') + 1]) for k in ('fs', 'f_start', 'f_end', 'amp')
           if f'--{k.replace("_", "-")}' in sys.argv}
    g = {k: load(fn) for k, fn in zip(('V2', 'V3', 'V4'), sys.argv[1:4])}
    starts = {k: v[0] for k, v in g.items()}
    if len(set(starts.values())) != 1:
        sys.exit(f'! the three files start at different GPS: {starts}')
    ok, _ = check({k: v[1] for k, v in g.items()}, **opt)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
