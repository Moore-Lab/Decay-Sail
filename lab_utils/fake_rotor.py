#!/usr/bin/env python3
"""Fake rotor: publish a KNOWN rotor angle to feedback_drive.py, in place of the camera tracker (gate FE1).

    python3 fake_rotor.py spin --rev-s 0.5 --duration 70
    python3 fake_rotor.py swing --amp-deg 60 --freq 0.35 --duration 70
    python3 fake_rotor.py replay --csv F2_blob_live.csv --duration 70     # a recorded angle trace (host_time, angle_deg)
    python3 fake_rotor.py profile --duration 90                          # rest -> swing -> over the top -> spin -> stop

Sends the same UDP datagram as live_blob_track.py --publish: "frame,host_time,angle_deg,ncc"
(angle wrapped to 0..360, ncc 1.0), at --fps (default 50, the tracker's cap) to 127.0.0.1:--port.
Writes the truth to --truth (default ~/fe1/truth_<time>.csv): host_time, theta_true (unwrapped deg),
angle_sent (deg, with --noise added). fe1_check.py compares the front end's output with this.

Touches nothing but a local UDP socket. Start it BEFORE `feedback_drive.py frontend` (which waits up
to 5 s for a fresh angle), and give it a --duration longer than the drive's.
"""
import argparse
import csv
import math
import os
import socket
import sys
import time

import numpy as np


def profile_angle(kind, a):
    """-> theta(t) in image degrees (unwrapped), t in s from the start."""
    if kind == 'spin':
        w = 360.0 * a.rev_s
        return lambda t: a.theta0 + w * t
    if kind == 'swing':
        return lambda t: a.theta0 + a.amp_deg * math.sin(2 * math.pi * a.freq * t)
    if kind == 'profile':
        # 0-10 s rest; 10-30 s swing growing 10 -> 170 deg at 0.35 Hz; then, continuing smoothly from the swing's
        # angle and velocity, accelerate to 1.2 rev/s by 60 s; decelerate to rest by 75 s; then rest.
        f = 0.35
        w_top = 360.0 * 1.2

        def swing(t):
            amp = 10 + 160 * (t - 10) / 20
            return a.theta0 + amp * math.sin(2 * math.pi * f * (t - 10))
        th30 = swing(30.0)
        v30 = (swing(30.0) - swing(30.0 - 1e-4)) / 1e-4
        acc1 = (w_top - v30) / 30.0
        th60 = th30 + v30 * 30 + 0.5 * acc1 * 30 ** 2
        acc2 = -w_top / 15.0
        th75 = th60 + w_top * 15 + 0.5 * acc2 * 15 ** 2

        def th(t):
            if t < 10:
                return a.theta0
            if t < 30:
                return swing(t)
            if t < 60:
                u = t - 30
                return th30 + v30 * u + 0.5 * acc1 * u ** 2
            if t < 75:
                u = t - 60
                return th60 + w_top * u + 0.5 * acc2 * u ** 2
            return th75
        return th
    if kind == 'replay':
        rows = list(csv.DictReader(l for l in open(a.csv) if not l.startswith('#')))
        tt = np.array([float(r['host_time']) for r in rows]); tt -= tt[0]
        aa = np.degrees(np.unwrap(np.radians([float(r['angle_deg']) for r in rows])))
        return lambda t: float(np.interp(t, tt, aa))
    raise SystemExit(f'unknown profile {kind}')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('kind', choices=('spin', 'swing', 'replay', 'profile'))
    p.add_argument('--rev-s', type=float, default=0.5, help='spin: rev/s (+ = increasing image angle)')
    p.add_argument('--amp-deg', type=float, default=60.0, help='swing amplitude, deg')
    p.add_argument('--freq', type=float, default=0.35, help='swing frequency, Hz')
    p.add_argument('--csv', default='', help='replay: CSV with host_time, angle_deg (live tracker output)')
    p.add_argument('--theta0', type=float, default=227.0, help='starting angle, deg (the rotor rest angle in the video)')
    p.add_argument('--noise', type=float, default=0.0, help='Gaussian angle noise added to what is sent, deg rms (tracker ~1 deg)')
    p.add_argument('--fps', type=float, default=50.0)
    p.add_argument('--duration', type=float, default=70.0)
    p.add_argument('--port', type=int, default=5005)
    p.add_argument('--truth', default='')
    a = p.parse_args()

    th = profile_angle(a.kind, a)
    out = a.truth or os.path.expanduser(f'~/fe1/truth_{a.kind}_{int(time.time())}.csv')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    rng = np.random.default_rng()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f'fake rotor: {a.kind}, {a.fps:g} fps for {a.duration:g} s -> udp 127.0.0.1:{a.port}; truth {out}')
    with open(out, 'w', buffering=1) as f:
        f.write(f'# fake_rotor.py {" ".join(sys.argv[1:])}\n')
        f.write('host_time,theta_true,angle_sent\n')
        t0 = time.time()
        k = 0
        try:
            while True:
                due = t0 + k / a.fps
                now = time.time()
                if due > now:
                    time.sleep(due - now)
                now = time.time()
                t = now - t0
                if t > a.duration:
                    break
                true = th(t)
                sent = true + (rng.normal(0, a.noise) if a.noise > 0 else 0.0)
                sock.sendto(f'{k},{now:.6f},{sent % 360.0:.4f},1.000'.encode(), ('127.0.0.1', a.port))
                f.write(f'{now:.6f},{true:.4f},{sent:.4f}\n')
                k += 1
        except KeyboardInterrupt:
            pass
    print(f'sent {k} angles')


if __name__ == '__main__':
    main()
