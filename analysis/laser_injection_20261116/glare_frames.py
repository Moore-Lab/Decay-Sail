#!/usr/bin/env python3
"""Does the top camera see the 660 nm laser? Laser-on minus laser-off mean images at the same rotor angle. (2026-11-19)
Read-only analysis of a coast_series run's saved tracker video (every 10th frame) + tracker CSV + coast files.
Written to run on worker2 (cv2 with FFV1; the Mac's OpenCV may not read it):

    nice -n 19 python3 glare_frames.py --run ~/spinup/2026-11-18/laser/nd2_run \
        --avi ~/scratch_glare/output_basler_gps1479055848.avi --out ~/scratch_glare/out

Frames: AVI frame j = camera frame n = 10 j + 1 = tracker CSV frame k = 10 j (live_blob_track.py writes the frame when
(n - 1) % video_every == 0; CSV frame = n - 1). Only frames inside a coast (field off + 5 s to coast end - 2 s) with
ncc >= 0.5 are used; each is put in a 10 deg bin of the tracker angle and summed per group:
  on   = laser-on coasts;  offA / offB = laser-off coasts alternately (A - B is the no-laser noise image).
Both rotation directions are pooled (the glare, if any, depends on the rotor angle, not the direction).
Outputs (--out): glare_frames.npz (mean images per bin and group, counts); glare_onoff.png (on - off per bin),
glare_noise.png (offA - offB per bin, same colour scale), glare_summary.png (mean off image, all-angle on - off and
offA - offB); glare_summary.txt (numbers). Observations only.
"""
import argparse
import csv
import glob
import os
import sys
import time

import numpy as np

NB = 36
EVERY = 10


def meta(p):
    m = {}
    for line in open(p):
        q = line.split()
        if len(q) >= 2 and q[0] in ('field_off_host', 'coast_end_host'):
            m[q[0]] = float(q[1])
        elif len(q) >= 2 and q[0] == 'laser':
            m['laser'] = q[1]
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--run', required=True, help='run folder with coast_O*.txt and tracker/')
    ap.add_argument('--avi', required=True)
    ap.add_argument('--tracker', default=None, help='blob_live_gps*.csv (default: the one in RUN/tracker/)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--max-frames', type=int, default=0, help='stop after this many AVI frames (0 = all; for a quick test)')
    a = ap.parse_args()
    import cv2
    os.makedirs(a.out, exist_ok=True)
    tpath = a.tracker or glob.glob(os.path.join(a.run, 'tracker', 'blob_live_gps*.csv'))[0]

    t0 = time.time()
    K, H, ANG, NCC = [], [], [], []
    with open(tpath) as fh:
        for r in csv.DictReader(l for l in fh if not l.startswith('#')):
            try:
                K.append(int(r['frame'])); H.append(float(r['host_time'])); ANG.append(float(r['angle_deg'])); NCC.append(float(r['ncc']))
            except (ValueError, TypeError, KeyError):
                continue
    K, H, ANG, NCC = np.array(K), np.array(H), np.array(ANG), np.array(NCC)
    if not np.all(K == np.arange(len(K))):
        sys.exit('tracker CSV frames are not 0..N-1 without gaps; the frame mapping would be wrong')
    print(f'tracker: {len(K)} frames read in {time.time() - t0:.0f} s')

    wins = []   # (start, end, group)
    noff = 0
    for p in sorted(glob.glob(os.path.join(a.run, 'coast_O*.txt'))):
        m = meta(p)
        if 'coast_end_host' not in m or 'laser' not in m:
            continue
        if m['laser'] == 'on':
            g = 'on'
        else:
            g = 'offA' if noff % 2 == 0 else 'offB'; noff += 1
        wins.append((m['field_off_host'] + 5, m['coast_end_host'] - 2, g))
    ws = np.array([w[0] for w in wins]); we = np.array([w[1] for w in wins]); wg = [w[2] for w in wins]
    print(f'{len(wins)} coasts: ' + ', '.join(f'{g} {wg.count(g)}' for g in ('on', 'offA', 'offB')))

    cap = cv2.VideoCapture(a.avi)
    ok, f = cap.read()
    if not ok:
        sys.exit('cannot read the AVI')
    shp = f.shape[:2]
    S = {g: np.zeros((NB,) + shp) for g in ('on', 'offA', 'offB')}
    N = {g: np.zeros(NB, int) for g in S}
    j, used, t0 = 0, 0, time.time()
    while ok:
        k = EVERY * j
        if k >= len(K):
            break
        h = H[k]
        i = np.searchsorted(ws, h) - 1
        if i >= 0 and h <= we[i] and NCC[k] >= 0.5:
            img = f[:, :, 0] if f.ndim == 3 else f
            b = int(ANG[k] % 360 // (360 / NB))
            S[wg[i]][b] += img; N[wg[i]][b] += 1; used += 1
        j += 1
        if a.max_frames and j >= a.max_frames:
            break
        if j % 20000 == 0:
            print(f'  {j} frames, {used} used, {time.time() - t0:.0f} s'); sys.stdout.flush()
        ok, f = cap.read()
    print(f'AVI: {j} frames read, {used} used, {time.time() - t0:.0f} s; expected ~{len(K) // EVERY} frames')
    M = {g: S[g] / np.maximum(N[g], 1)[:, None, None] for g in S}
    off = (S['offA'] + S['offB']) / np.maximum(N['offA'] + N['offB'], 1)[:, None, None]
    np.savez_compressed(os.path.join(a.out, 'glare_frames.npz'), on=M['on'], offA=M['offA'], offB=M['offB'], off=off,
                        n_on=N['on'], n_offA=N['offA'], n_offB=N['offB'])
    d_on = M['on'] - off
    d_ab = M['offA'] - M['offB']
    lines = [f'frames used: on {N["on"].sum()}, offA {N["offA"].sum()}, offB {N["offB"].sum()}; min per bin '
             f'{min(N[g].min() for g in N)}',
             f'mean off image level {off.mean():.2f} counts (max {off.max():.0f})']
    for nm, d in (('on - off', d_on), ('offA - offB', d_ab)):
        allang = d.mean(axis=0)
        lines.append(f'{nm}: per-bin rms {np.sqrt(np.mean(d ** 2)):.3f} counts, per-bin max |d| {np.abs(d).max():.2f}; '
                     f'all-angle mean image: mean {allang.mean():+.4f}, max {allang.max():+.3f} at {np.unravel_index(allang.argmax(), allang.shape)}, '
                     f'min {allang.min():+.3f}')
    open(os.path.join(a.out, 'glare_summary.txt'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    plots(a.out, off, d_on, d_ab)


def plots(out, off, d_on, d_ab):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    lim = max(np.percentile(np.abs(d_ab), 99.9), np.percentile(np.abs(d_on), 99.5))
    for nm, d, title in (('glare_onoff', d_on, 'laser on − laser off'), ('glare_noise', d_ab, 'laser off: half A − half B (noise)')):
        fig, axs = plt.subplots(6, 6, figsize=(14, 15))
        for i, ax in enumerate(axs.flat):
            ax.imshow(d[i], cmap='RdBu_r', vmin=-lim, vmax=lim); ax.set_xticks([]); ax.set_yticks([])
            ax.set_title(f'{i * 10}–{i * 10 + 10}°', fontsize=8)
        fig.suptitle(f'{title}, mean image per 10° of rotor angle (counts, ±{lim:.2f})')
        fig.tight_layout(); fig.savefig(os.path.join(out, nm + '.png'), dpi=90); plt.close(fig)
    fig, ax = plt.subplots(1, 3, figsize=(15, 5))
    ax[0].imshow(off.mean(axis=0), cmap='gray'); ax[0].set_title('mean laser-off image (all angles)')
    l2 = max(np.abs(d_on.mean(axis=0)).max(), np.abs(d_ab.mean(axis=0)).max())
    for axx, d, t in ((ax[1], d_on, 'on − off, all angles'), (ax[2], d_ab, 'off A − off B, all angles')):
        im = axx.imshow(d.mean(axis=0), cmap='RdBu_r', vmin=-l2, vmax=l2); axx.set_title(t); fig.colorbar(im, ax=axx, shrink=0.8)
    fig.tight_layout(); fig.savefig(os.path.join(out, 'glare_summary.png'), dpi=110); plt.close(fig)


if __name__ == '__main__':
    main()
