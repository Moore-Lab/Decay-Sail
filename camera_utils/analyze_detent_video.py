#!/usr/bin/env python3
"""
Measure rotor motion from a stator detent/drive recording (grab_basler.py output).

Answers two questions per run:
  * WHEN did the rotor move -- which drive phase was live at the time
  * At WHAT FREQUENCY is it oscillating, per phase window

and prints the two control checks that stop you fooling yourself.

    python3 analyze_detent_video.py VIDEO.avi --drive-offset 15 --dwell 180
    python3 analyze_detent_video.py A.avi B.avi        # compare two runs

--drive-offset is the video time (s) at which the drive command started; get it
from the process start times (`ps -eo lstart,cmd`) or the launch wall clock minus
the recording start. The .avi filename encodes the recording start as TRUE GPS
(Unix - 315964782), NOT cymac GPS -- the front end runs thousands of seconds
ahead, so do not compare the two directly.

------------------------------------------------------------------------------
TWO TRAPS, both hit for real on 2026-08-21 -- the checks below exist because of
them and are printed on every run:

1. ILLUMINATION IS NOT MOTION. Selecting the highest-variance pixels finds steep
   spoke edges, where a ~0.1% global brightness ripple looks like large motion.
   That produced a confident, completely wrong "the rotor is oscillating at
   0.78 Hz" from a clip in which nothing moved. Guards: every frame is
   brightness-normalised before differencing, and `frame-mean flicker` is
   reported so you can see the lamp ripple directly.

2. COHERENCE ALONE DOES NOT PROVE ARTEFACT. The rotor occupies a few percent of
   the frame, so when it really moves it modulates the frame mean too -- giving
   genuine motion a high coherence with brightness. The discriminator is not
   coherence but LOCALISATION: real rotor motion shows up as spoke-structured
   difference confined to the rotor disc, while a lamp change lights the whole
   frame including the static mounts. `rotor-localisation` below is that ratio.
   Trust it over coherence.
------------------------------------------------------------------------------
"""
import argparse
import os

import cv2
import numpy as np

GPS_UNIX_OFFSET = 315964782      # true GPS; cymac GPS runs thousands of s ahead


def load(path):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
    cap.release()
    if not frames:
        raise SystemExit(f"no frames read from {path}")
    return np.array(frames, dtype=np.uint8), fps


def normed(g):
    g = g.astype(np.float32)
    return (g - g.mean()) / (g.std() + 1e-9)


def rotor_mask(A, pct=97):
    """Where does the image actually change? That is the rotor.

    Built from brightness-normalised differences so a lamp ripple does not
    define the mask. Falls back to the whole frame if nothing stands out.
    """
    acc = np.zeros(A[0].shape, np.float32)
    idx = range(0, len(A) - 20, max(1, len(A) // 80))
    for i in idx:
        acc += np.abs(normed(A[i + 20]) - normed(A[i]))
    m = cv2.GaussianBlur(acc, (21, 21), 0)
    return m > np.percentile(m, pct)


def analyse(path, drive_offset, dwell, ncycles, quiet=False):
    A, fps = load(path)
    n = len(A)
    t = np.arange(n) / fps
    base = os.path.basename(path)
    gps = None
    if 'gps' in base:
        try:
            gps = int(base.split('gps')[1].split('.')[0])
        except ValueError:
            pass
    print(f"\n=== {base}")
    print(f"  {A.shape[2]}x{A.shape[1]}  {fps:g} fps  {n} frames  {n/fps:.1f} s")
    if gps:
        import time
        print(f"  recording started {time.strftime('%H:%M:%S', time.localtime(gps + GPS_UNIX_OFFSET))}"
              f"  (true GPS {gps})")

    mask = rotor_mask(A)
    ys, xs = np.where(mask)
    print(f"  rotor mask {mask.sum()} px  centroid ({xs.mean():.0f},{ys.mean():.0f})")

    # --- control 1: lamp ripple -------------------------------------------
    bright = np.array([A[i].mean() for i in range(n)])
    b = bright - bright.mean()
    print(f"  frame-mean flicker  rms {b.std():.4f} cts on {bright.mean():.2f} "
          f"({100*b.std()/bright.mean():.3f}%)")

    # --- control 2: is the change ON the rotor, or everywhere? -------------
    i0 = n // 2
    d = np.abs(normed(A[min(i0 + 20, n - 1)]) - normed(A[i0]))
    on, off = d[mask].mean(), d[~mask].mean()
    print(f"  rotor-localisation  on-rotor {on:.4f} vs off-rotor {off:.4f}  "
          f"ratio {on/(off+1e-9):.1f}x   <- >>1 means real motion, ~1 means illumination")

    # --- signal: masked, brightness-normalised, PCA -----------------------
    X = np.empty((n, int(mask.sum())), np.float32)
    for i in range(n):
        X[i] = normed(A[i])[mask]
    X -= X.mean(0)
    u, s, _ = np.linalg.svd(X, full_matrices=False)
    pc = u[:, 0] * s[0]
    print(f"  PC1 explains {s[0]**2/(s**2).sum()*100:.1f}%")

    # --- per-phase windows ------------------------------------------------
    names = ['A', 'B', 'C']
    print(f"\n  {'window':>16} {'phase':>6} {'rms':>8} {'peak Hz':>9} {'2nd':>8}")
    rows = []
    edges = [('pre', 0.0, drive_offset)]
    for c in range(ncycles):
        for k, nm in enumerate(names):
            a = drive_offset + (3 * c + k) * dwell
            edges.append((nm, a, a + dwell))
    edges.append(('post', drive_offset + 3 * ncycles * dwell, t[-1]))
    for nm, a, bnd in edges:
        sel = (t >= a) & (t < min(bnd, t[-1]))
        if sel.sum() < fps * 10:
            continue
        x = pc[sel] - pc[sel].mean()
        w = np.hanning(len(x))
        F = np.abs(np.fft.rfft(x * w))
        f = np.fft.rfftfreq(len(x), 1 / fps)
        lo = (f > 0.03) & (f < min(3.0, fps / 2 * 0.9))
        order = np.argsort(F[lo])[::-1]
        f1, f2 = f[lo][order[0]], f[lo][order[1]]
        print(f"  {a:6.0f}-{min(bnd,t[-1]):6.0f}s {nm:>6} {x.std():8.2f} "
              f"{f1:9.3f} {f2:8.3f}")
        rows.append((nm, a, x.std(), f1))
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('videos', nargs='+')
    p.add_argument('--drive-offset', type=float, default=0.0,
                   help='video time (s) when the drive command started')
    p.add_argument('--dwell', type=float, default=180.0, help='s per phase step')
    p.add_argument('--cycles', type=int, default=1)
    args = p.parse_args()
    for v in args.videos:
        analyse(v, args.drive_offset, args.dwell, args.cycles)
    print("\nInterpreting the frequency:")
    print("  For a DC detent tau ~ V^2, so f_lib ~ counts: HALVING the drive should")
    print("  HALVE the frequency. A magnetic trap mode will not move at all. That is")
    print("  the test that says whether you are measuring the electrode or the trap.")
    print("  If it is the detent:  tau = (2 pi f)^2 * I / m   with m = 8,")
    print("  which needs no VOLTS_PER_COUNT calibration -- see CLAUDE.md.")


if __name__ == '__main__':
    main()
