#!/usr/bin/env python3
"""Tilt check: trap strength from the rotor's free swing, live or from a recorded tracker CSV. READ ONLY: no EPICS, no
writes to anything (2026-11-12).

    python3 tilt_check.py live   [--port 5005] [--window 60] [--every 30]       # listens to live_blob_track --publish
    python3 tilt_check.py replay BLOB_CSV [--window 60] [--every 30] [--t0 S] [--t1 S]

Prints, every --every s over the last --window s of tracked angle:
  f0       swing frequency (Hz) from the mean time between successive turning points (two per period). Trap stiffness
           goes as f0^2, so the tilt that minimises f0 (at a matched amplitude) gives the weakest trap.
  amp      half peak-to-peak swing (deg). The trap is anharmonic: f0 falls with amplitude, so compare tilt settings at
           similar amp (e.g. +-10-30 deg). A small electrode kick sets an amplitude, but that is a write: Molly's go.
  centre   swing centre (deg, mean of the turning points); moves with tilt (its direction tells which way to go).
  ncc      tracker match quality min / median (if the image shifts as the chamber tilts, ncc drops: re-check the centre).
Rotation (full turns) in the window is reported as such; f0 then is not a swing frequency.
"""
import argparse
import csv
import socket
import sys
import time

import numpy as np


def analyse(t, th, ncc):
    """t (s), th (unwrapped deg), ncc arrays for one window -> dict."""
    out = dict(n=len(t), ncc_min=float(np.min(ncc)), ncc_med=float(np.median(ncc)))
    if len(t) < 50:
        return out
    net = th[-1] - th[0]
    if abs(th.max() - th.min()) >= 360.0:
        out.update(rotating=True, rate_hz=float(net / 360.0 / (t[-1] - t[0])))
        return out
    k = max(3, int(round(0.1 / np.median(np.diff(t)))))                  # ~0.1 s smoothing
    y = np.convolve(th, np.ones(k) / k, mode='same')
    d = np.diff(y)
    tp = np.where(np.sign(d[1:]) != np.sign(d[:-1]))[0] + 1
    tp = tp[(tp > k) & (tp < len(y) - k)]
    if tp.size >= 2:                                                       # keep alternating max/min, drop jitter
        keep = [tp[0]]
        for i in tp[1:]:
            if abs(y[i] - y[keep[-1]]) > 0.5:
                keep.append(i)
        tp = np.array(keep)
    if tp.size < 3:
        out.update(amp=float((th.max() - th.min()) / 2), note='fewer than 3 turning points (swing too slow/small)')
        return out
    half = np.diff(t[tp])
    out.update(f0=float(1.0 / (2 * np.mean(half))), f0_sd=float(np.std(1.0 / (2 * half))),
               amp=float(np.mean(np.abs(np.diff(y[tp]))) / 2), centre=float(np.mean(y[tp]) % 360.0),
               n_half=int(half.size))
    return out


def fmt(r):
    s = f'n {r["n"]:5d}  ncc {r["ncc_min"]:.3f}/{r["ncc_med"]:.3f}'
    if r.get('rotating'):
        return s + f'  ROTATING {r["rate_hz"]:+.3f} Hz (not a swing)'
    if 'f0' in r:
        return s + (f'  f0 {r["f0"]:.4f} Hz (sd {r["f0_sd"]:.4f}, {r["n_half"]} half-periods)  amp {r["amp"]:5.1f} deg'
                    f'  centre {r["centre"]:6.1f} deg')
    return s + f'  amp {r.get("amp", float("nan")):.1f} deg  {r.get("note", "")}'


def windows(t, th, ncc, window, every, emit):
    last = t[0]
    for j in range(len(t)):
        if t[j] - last >= every and t[j] - t[0] >= window:
            last = t[j]
            m = t > t[j] - window
            emit(t[j], analyse(t[m] - t[m][0], th[m], ncc[m]))


def replay(a):
    rows = [r for r in csv.DictReader(l for l in open(a.csv) if not l.startswith('#'))]
    k = np.array([int(r['frame']) for r in rows], float)
    t = (k - k[0]) * 0.02                                                    # frame index x 20 ms (50 fps)
    th = np.degrees(np.unwrap(np.radians([float(r['angle_deg']) for r in rows])))
    ncc = np.array([float(r['ncc']) for r in rows])
    m = (t >= a.t0) & (t <= (a.t1 if a.t1 > 0 else t[-1]))
    windows(t[m], th[m], ncc[m], a.window, a.every, lambda tt, r: print(f't {tt:7.1f} s  ' + fmt(r)))


def live(a):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(('127.0.0.1', a.port)); sock.settimeout(1.0)
    buf = []; prev = None; t_last = time.time()
    print(f'listening on 127.0.0.1:{a.port}; window {a.window:g} s, report every {a.every:g} s (Ctrl-C to stop)')
    while True:
        try:
            kk, ht, ang, nc = sock.recv(256).decode().split(',')
        except socket.timeout:
            continue
        except KeyboardInterrupt:
            break
        kk, ang, nc = int(kk), float(ang), float(nc)
        u = ang if prev is None else prev + ((ang - prev + 180.0) % 360.0 - 180.0)
        prev = u
        buf.append((kk * 0.02, u, nc))
        buf = [b for b in buf if buf[-1][0] - b[0] <= a.window]
        if time.time() - t_last >= a.every and buf[-1][0] - buf[0][0] >= 0.9 * a.window:
            t_last = time.time()
            arr = np.array(buf)
            r = analyse(arr[:, 0] - arr[0, 0], arr[:, 1], arr[:, 2])
            print(time.strftime('%H:%M:%S') + '  ' + fmt(r), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sp = p.add_subparsers(dest='cmd', required=True)
    lv = sp.add_parser('live'); lv.add_argument('--port', type=int, default=5005)
    rp = sp.add_parser('replay'); rp.add_argument('csv'); rp.add_argument('--t0', type=float, default=0.0)
    rp.add_argument('--t1', type=float, default=0.0)
    for q in (lv, rp):
        q.add_argument('--window', type=float, default=60.0); q.add_argument('--every', type=float, default=30.0)
    a = p.parse_args()
    return live(a) if a.cmd == 'live' else replay(a)


if __name__ == '__main__':
    sys.exit(main())
