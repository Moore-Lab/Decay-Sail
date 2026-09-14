"""
check_settled(): programmatic settling test for the laser step-down.

Deliberately simple (per Molly, 2026-09-14): pull the most recent window of
LES_YAW, get a handful of frequency estimates across it with the same
band-following tracker already validated in the spindown notebooks, then two
independent tests -- both must pass to call it settled:

  1. linear-fit slope across the window consistent with zero
  2. first-half-of-window mean vs second-half-of-window mean consistent

Window = 20 min, not 10: the July laser step-down's stability notebook
(`laser_stepdown_stability.ipynb`) found a persistent ~10-min quasi-periodic
oscillation on the high-power plateau. A 10-min check window can land on a
rising or falling phase of that cycle and look artificially flat or sloped
depending on luck; 20 min covers ~2 full periods.

VALIDATED 2026-09-14 against known ground truth from the 09-11 laser-driven
run (GPS 1473204000_1473376497, LES_YAW), on this dev Mac (data via the
synced Dropbox folder, not live NDS2 -- this machine has NO live network path
to cymac1:8088, confirmed by a direct connectivity test. This module must run
somewhere with NDS2 access, i.e. worker2, same as laser_step_down.py itself):

    case                                          expect   got
    t=+20h, deep in the known-steady 09-11 hold   PASS     SETTLED
      slope +0.0002+-0.0001 mHz/s, halves agree to the 4th decimal
    t=+20min, mid spin-up ramp                    FAIL     NOT SETTLED
      slope +0.35+-0.005 mHz/s (70 sigma from zero), halves differ by 0.19 Hz
    t=+55min, tail end of spin-up                 boundary SETTLED
      independently confirms the ~45-60 min spin-up estimate from a
      completely different method (spectrogram dominant-line read)
    t=+35h, a different steady point              PASS     SETTLED

All four came out correct. Not yet tested against live/real-time data --
verify NDS2 "how recent is queryable" latency on worker2 before trusting the
check cadence in an unattended loop.
"""
import numpy as np
from scipy.signal import decimate


def peak_in_band(x, fsx, lo, hi):
    ac = x - x.mean()
    X = np.abs(np.fft.rfft(ac * np.hanning(len(ac))))
    fr = np.fft.rfftfreq(len(ac), 1 / fsx)
    m = (fr > lo) & (fr < hi)
    if not m.any():
        return np.nan, 0.0
    i = np.flatnonzero(m)[np.argmax(X[m])]
    if i == 0 or i >= len(X) - 1:
        return fr[i], 0.0
    y0, y1, y2 = X[i - 1], X[i], X[i + 1]
    den = y0 - 2 * y1 + y2
    fpk = fr[i] + (0.5 * (y0 - y2) / den if den else 0) * (fr[1] - fr[0])
    snr = X[i] / (np.median(X[max(0, i - 60):i + 60]) or 1)
    return fpk, snr


def check_settled(les, fs, f_guess, window_min=20.0, sub_win_s=180.0,
                   sub_step_s=90.0, k_sigma=3.0, verbose=True):
    """
    les: most recent `window_min` minutes of LES_YAW samples (1D array)
    fs:  sample rate (Hz)
    f_guess: rough expected line frequency (Hz) to seed the band search --
             use the last known track, or the target f_ss if you have a
             forward-model prediction (see laser_stepdown_forward_model.ipynb)
    Returns a dict: pass/fail + every diagnostic number, ready to log verbatim
    -- log every call, not just the final verdict, per the 2026-09-14 plan.
    """
    y16 = decimate(decimate(les - les.mean(), 8, ftype='fir'), 8, ftype='fir')
    fs16 = fs / 64
    nw, sw = int(sub_win_s * fs16), int(sub_step_s * fs16)
    rows, track = [], f_guess
    for i in range(0, len(y16) - nw, sw):
        tc = i / fs16
        fpk, snr = peak_in_band(y16[i:i + nw], fs16, max(track * 0.85, 0.02), track * 1.15)
        if np.isnan(fpk) or fpk <= 0 or snr < 5:
            continue
        rows.append((tc, fpk, snr))
        track = fpk
    if len(rows) < 4:
        return {'pass': False, 'reason': f'only {len(rows)} usable points, need >=4', 'n': len(rows)}

    T = np.array([r[0] for r in rows])
    F = np.array([r[1] for r in rows])

    # test 1: slope consistent with zero
    p, cov = np.polyfit(T, F, 1, cov=True)
    slope, slope_err = p[0], np.sqrt(cov[0, 0])
    slope_ok = abs(slope) < k_sigma * slope_err

    # test 2: first half vs second half mean
    mid = T[-1] / 2
    h1, h2 = F[T < mid], F[T >= mid]
    m1, m2 = h1.mean(), h2.mean()
    e1 = h1.std(ddof=1) / np.sqrt(len(h1)) if len(h1) > 1 else np.inf
    e2 = h2.std(ddof=1) / np.sqrt(len(h2)) if len(h2) > 1 else np.inf
    half_ok = abs(m1 - m2) < k_sigma * np.sqrt(e1 ** 2 + e2 ** 2)

    verdict = bool(slope_ok and half_ok)
    result = {'pass': verdict, 'n': len(rows), 'f_mean': F.mean(),
              'slope_hz_per_s': slope, 'slope_err': slope_err, 'slope_ok': slope_ok,
              'half1_mean': m1, 'half1_err': e1, 'half2_mean': m2, 'half2_err': e2,
              'half_ok': half_ok}
    if verbose:
        print(f"  n={result['n']:2d}  f_mean={result['f_mean']:.4f} Hz  "
              f"slope={slope*1e3:+.4f}+-{slope_err*1e3:.4f} mHz/s [{'OK' if slope_ok else 'FAIL'}]  "
              f"half1={m1:.4f}+-{e1:.4f}  half2={m2:.4f}+-{e2:.4f} [{'OK' if half_ok else 'FAIL'}]  "
              f"=> {'SETTLED' if verdict else 'NOT SETTLED'}")
    return result
