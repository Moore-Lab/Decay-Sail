#!/usr/bin/env python3
"""Does the rotor lock to the stator drive? Video angle vs drive phase (gates D1-D2, C1).

    python3 drive_coupling.py ANGLES.csv FRAMES.csv V2.h5 V4.h5 V3.h5 --tau S [--out PREFIX]
    python3 drive_coupling.py selftest

READ-ONLY analysis; commands nothing.
  ANGLES.csv  blob_track.py / live_blob_track.py output (frame, angle_deg, ...)
  FRAMES.csv  the recorder's timestamps (output_basler_gps<GPS>.csv); host_time is Unix
  V2/V4/V3    Y1:RDS-OUTS_V{2,4,3}_OUT_DQ files (phases A, B, C) from NDS, front-end time
  --tau       front-end GPS minus true GPS at the recording (from les_compare.py's
              alignment, or a live read of Y1:DAQ-DC0_GPS at the time)

Drive (D1): the three phases' space vector A + B e^{i120} + C e^{i240} gives the field
phase phi (positive = A->B->C), the electrical frequency f and the amplitude.

Segments: drive-off stretches and drive-on plateaus (f steady within 1%, amplitude full)
of at least --min-seg seconds. For each, and each candidate k in (8, 4), sign s = +/-1:
  speed_ratio  mean rotor speed / (s f / k)
  lag drift    change of psi = theta - s*phi/k over the segment, in units of one drive
               pattern step (360/k deg of rotor angle): a lock keeps it under 1
  LOCKED       speed within 5% AND lag drift < 1 step  (a rotor that slips or swings
               through the pattern fails the second test even if its mean speed matches)
Also per segment: the swing frequency (spectral peak of the detrended angle, 0.05-2 Hz).
With the drive on, a shift from the drive-off value measures the drive's stiffness
against the trap's: k_drive / k_trap = (f_on / f_off)^2 - 1 (if the drive acts as a
spring at all; reported, not assumed).

Rotor sign: + = increasing image angle (x right, y down). On the board (2026-11-01,
measured on the median frame of gps1477428272): the sector tabs end at three via radii,
one per phase (A 4.27 < B 4.96 < C 5.66 mm, generate_flex_revG.py); in increasing image
angle they run short, long, mid = A, C, B, ratios 1 : 1.17 : 1.32 vs 1 : 1.16 : 1.33.
So increasing image angle = the C->B->A sector direction, and with phi positive for an
A->B->C field, a rotor turning WITH the field sequence has s = -1 (WITH_FIELD_SIGN).
  -f8  with the sequence at f/8: the m = 16 V^2 term, or the term linear in V (net
       rotor charge) on the m = 8 pattern
  +f4  against it at f/4: the m = 8 V^2 term (docs/STATUS.md, "which harmonic")
  +f8, -f4  not predicted by that derivation; scored anyway.
  Not scored: the linear term on m = 16 runs against at f/16; V^2 also has a static
  m = 24 part (a detent, no direction). Derivation and image reading re-checked
  independently by a reviewer, 2026-11-01 (AGREE).
Assumes the channel map A, B, C = V2, V4, V3 (docs/DECISIONS.md, continuity check
2026-08-24) still holds for the rev G wiring. The board shows in every video, so re-check
per recording if the camera moves (polar unwrap of the median frame).
Writes PREFIX_segments.csv and PREFIX.png.
"""
import argparse, csv, sys
import numpy as np

GPS_UNIX_OFF = 315964800 - 18
KS = (8, 4)
WITH_FIELD_SIGN = -1      # s of a rotor turning with the A->B->C field sequence (see docstring)


def drive_phase(a, b, c):
    """Field phase (rad, unwrapped, + = A->B->C) and amplitude (fraction of a +/-6400 swing)."""
    z = a + b * np.exp(2j * np.pi / 3) + c * np.exp(4j * np.pi / 3)
    return np.unwrap(np.angle(z)), np.abs(z) / (1.5 * 6400)


def smooth_rate(x, dt, sigma_s=0.5):
    from scipy.ndimage import gaussian_filter1d
    return np.gradient(gaussian_filter1d(x, sigma_s / dt), dt)


def segments(t, f, amp, min_seg):
    """(start, stop, kind) with kind 'off' or 'hold'; plateaus of f at full amplitude."""
    on = amp > 0.99
    df = np.abs(np.gradient(f, t[1] - t[0]))
    steady = on & (df < 0.01 * np.maximum(np.abs(f), 0.05) / 1.0)
    off = amp < 0.01
    out = []
    for mask, kind in ((off, 'off'), (steady, 'hold')):
        edges = np.flatnonzero(np.diff(np.r_[0, mask.astype(int), 0]))
        for i0, i1 in zip(edges[::2], edges[1::2]):
            if t[i1 - 1] - t[i0] >= min_seg:
                out.append((t[i0], t[i1 - 1], kind))
    return sorted(out)


def swing_freq(theta, dt):
    x = theta - np.polyval(np.polyfit(np.arange(len(theta)), theta, 1), np.arange(len(theta)))
    n = len(x); F = np.fft.rfftfreq(8 * n, dt); P = np.abs(np.fft.rfft(x * np.hanning(n), 8 * n))**2
    b = (F > 0.05) & (F < 2.0)
    return F[b][np.argmax(P[b])] if b.any() else np.nan


def score(t, theta, phi, f, amp, min_seg=6.0):
    dt = t[1] - t[0]
    fr = smooth_rate(theta, dt) / (2 * np.pi)
    rows = []
    for t0, t1, kind in segments(t, f, amp, min_seg):
        m = (t >= t0 + 1.0) & (t <= t1 - 1.0)    # trim 1 s at each end (transitions, smoothing)
        if m.sum() < 50: continue
        net = (theta[m][-1] - theta[m][0]) / (2 * np.pi); dur = t[m][-1] - t[m][0]
        row = dict(t0=t0, t1=t1, kind=kind, f_elec=f[m].mean(),
                   rotor_rev_s=net / dur,              # exact mean speed, not the smoothed rate
                   net_rev=net,
                   swing_hz=swing_freq(theta[m], dt))
        locked = []
        for k in KS:
            for s in (1, -1):
                key = '%sf%d' % ('+' if s > 0 else '-', k)
                if kind == 'hold' and abs(f[m].mean()) > 1e-3:
                    target = s * f[m].mean() / k
                    psi = theta[m] - s * phi[m] / k
                    drift = abs(psi[-1] - psi[0]) / (2 * np.pi / k)
                    ratio = (net / dur) / target
                    ok = abs(ratio - 1) < 0.05 and drift < 1.0
                    row[key + '_speed_ratio'] = ratio; row[key + '_lag_drift_steps'] = drift
                    if ok: locked.append(key)
                else:
                    row[key + '_speed_ratio'] = np.nan; row[key + '_lag_drift_steps'] = np.nan
        row['locked_to'] = ' '.join(locked) if locked else ('-' if kind == 'off' else 'none')
        fm = f[m].mean()
        row['net_vs_field'] = ('' if kind != 'hold' or abs(fm) < 1e-3 or abs(net) < 0.5 else
                               'with' if np.sign(net) * np.sign(fm) == WITH_FIELD_SIGN else 'against')
        rows.append(row)
    return rows, fr


def load(args):
    import h5py
    rows = list(csv.DictReader(l for l in open(args.angles) if not l.startswith('#')))
    theta = np.unwrap(np.deg2rad([float(r['angle_deg']) for r in rows]))
    ts = np.genfromtxt(args.frames, delimiter=',', names=True)
    cam = (ts['cam_timestamp_ns'] - ts['cam_timestamp_ns'][0]) * 1e-9
    host = ts['host_time'] - ts['host_time'][0]
    c, *_ = np.linalg.lstsq(np.c_[np.ones(len(cam)), cam], host, rcond=None)
    t_true0 = ts['host_time'][0] - GPS_UNIX_OFF + c[0] + (host - c[0] - c[1] * cam).min()
    n = min(len(theta), len(cam)); t = cam[:n] * c[1]; theta = theta[:n]
    ph = []
    for fn in (args.v2, args.v4, args.v3):
        with h5py.File(fn) as h:
            ph.append(h['data'][:].astype(float)); fs = h.attrs['sample_rate']; fe0 = h['segments/gps_start'][0]
    a, b, cc = (x - 6400 for x in ph)
    phi_d, amp_d = drive_phase(a, b, cc)
    td = fe0 + np.arange(len(a)) / fs - args.tau - t_true0       # drive time on the video clock
    phi = np.interp(t, td, phi_d); amp = np.interp(t, td, amp_d)
    f = smooth_rate(phi, t[1] - t[0]) / (2 * np.pi)
    print('frames %d, first frame true GPS %.3f; drive covers %.1f..%.1f s of video time' % (n, t_true0, td[0], td[-1]))
    return t, theta, phi, f, amp


def report(rows, out):
    keys = list(rows[0].keys())
    with open(out + '_segments.csv', 'w') as fh:
        w = csv.DictWriter(fh, keys); w.writeheader(); w.writerows(rows)
    off = [r['swing_hz'] for r in rows if r['kind'] == 'off' and not np.isnan(r['swing_hz'])]
    f_off = np.median(off) if off else np.nan
    print('rotor/net: + = increasing image angle; net_vs_field: net rotation with or against the'
          ' field sequence; -f8 = with at f/8, +f4 = against at f/4 (docstring)')
    print('%7s %7s %5s %7s %8s %7s %8s %7s %9s  %s' % ('t0', 't1', 'kind', 'f_elec', 'rotor', 'net', 'vs_field', 'swing', 'kd/kt', 'locked_to'))
    for r in rows:
        kk = (r['swing_hz'] / f_off)**2 - 1 if r['kind'] == 'hold' else np.nan
        print('%7.1f %7.1f %5s %7.3f %+8.3f %+7.2f %8s %7.3f %9.2f  %s' % (
            r['t0'], r['t1'], r['kind'], r['f_elec'], r['rotor_rev_s'], r['net_rev'], r['net_vs_field'],
            r['swing_hz'], kk, r['locked_to']))
    print('drive-off swing frequency (median) %.3f Hz' % f_off)


def plot(t, theta, fr, f, amp, rows, out):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
    on = amp > 0.5
    ax[0].plot(t, fr, 'k', lw=.7, label='rotor (video), rev/s')
    for k, col in ((8, 'C0'), (4, 'C3')):
        ax[0].plot(t, np.where(on, f / k, np.nan), col, lw=.8, label='+f/%d' % k)
        ax[0].plot(t, np.where(on, -f / k, np.nan), col, lw=.8, ls='--', label='-f/%d' % k)
    for r in rows:
        if r['locked_to'] not in ('-', 'none'):
            ax[0].axvspan(r['t0'], r['t1'], color='C2', alpha=.2)
    ax[0].axhline(0, color='grey', lw=.5); ax[0].legend(ncol=5, fontsize=8); ax[0].set_ylabel('rev/s')
    ax[0].set_title('rotor speed vs drive candidates (green = segment scored LOCKED)')
    ax[1].plot(t, np.degrees(theta) / 360, lw=.8); ax[1].set_ylabel('rotor angle (rev)')
    ax[2].plot(t, f, lw=.8, label='f_elec (Hz, + = A->B->C)'); ax[2].plot(t, amp, lw=.8, label='drive amplitude (fraction)')
    for r in rows:
        ax[2].axvspan(r['t0'], r['t1'], color='C1' if r['kind'] == 'hold' else 'C7', alpha=.08)
    ax[2].legend(fontsize=8); ax[2].set_xlabel('video time (s)')
    plt.tight_layout(); plt.savefig(out + '.png', dpi=75)


def selftest():
    """Synthetic: three holds. 0.4 Hz: locked at -f/8 (small wobble). 0.8 Hz: swinging only.
    1.2 Hz: locked at -f/8 but slips 2 pattern steps mid-hold. Expect -f8, none, none."""
    dt = 0.02; t = np.arange(0, 120, dt)
    f = np.select([t < 10, t < 40, t < 50, t < 80, t < 90, t < 110], [0, 0.4, 0, 0.8, 0, 1.2], 0)
    amp = (f > 0).astype(float)
    phi = 2 * np.pi * np.cumsum(f) * dt
    theta = np.deg2rad(60) * np.sin(2 * np.pi * 0.3 * t)                  # trap swinging
    h1 = (t >= 10) & (t < 40); h3 = (t >= 90) & (t < 110)
    theta[h1] = -phi[h1] / 8 + 0.1 * np.sin(2 * np.pi * 0.3 * t[h1])
    theta[h3] = -phi[h3] / 8 - 2 * (2 * np.pi / 8) * ((t[h3] - 99) / 2).clip(0, 1)
    theta += np.random.default_rng(0).normal(0, 0.005, len(t))
    rows, fr = score(t, theta, phi, f, amp, min_seg=6.0)
    report(rows, '/tmp/drive_coupling_selftest')
    want = {0.4: '-f8', 0.8: 'none', 1.2: 'none'}
    ok = True
    for r in rows:
        if r['kind'] != 'hold': continue
        fe = round(r['f_elec'], 1); good = r['locked_to'] == want.get(fe); ok &= good
        print('  hold f=%.1f: got %s, expected %s -> %s' % (fe, r['locked_to'], want.get(fe), 'ok' if good else 'FAIL'))
    # Sign controls: forward (f > 0) and reverse (f < 0) holds, rotor exactly at
    # -phi/8 (with, f/8), +phi/4 (against, f/4), +phi/8 (against, f/8).
    for fs in (0.4, -0.4):
        for k, sgn, lab, rel in ((8, -1, '-f8', 'with'), (4, 1, '+f4', 'against'), (8, 1, '+f8', 'against')):
            ff = np.where((t >= 10) & (t < 110), fs, 0.0); ph = 2 * np.pi * np.cumsum(ff) * dt
            th = np.where(ff != 0, sgn * ph / k, 0.0)
            rr = [r for r in score(t, th, ph, ff, (ff != 0).astype(float), 6.0)[0] if r['kind'] == 'hold'][0]
            good = rr['locked_to'] == lab and rr['net_vs_field'] == rel; ok &= good
            print('  sign control f=%+.1f theta=%+d*phi/%d: got %s %s, expected %s %s -> %s' % (
                fs, sgn, k, rr['locked_to'], rr['net_vs_field'], lab, rel, 'ok' if good else 'FAIL'))
    print('SELFTEST %s' % ('PASSED' if ok else 'FAILED'))
    return ok


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        sys.exit(0 if selftest() else 1)
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('angles'); p.add_argument('frames'); p.add_argument('v2'); p.add_argument('v4'); p.add_argument('v3')
    p.add_argument('--tau', type=float, required=True)
    p.add_argument('--min-seg', type=float, default=6.0)
    p.add_argument('--out', default='drive_coupling')
    args = p.parse_args()
    t, theta, phi, f, amp = load(args)
    rows, fr = score(t, theta, phi, f, amp, args.min_seg)
    report(rows, args.out); plot(t, theta, fr, f, amp, rows, args.out)
