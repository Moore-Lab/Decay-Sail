#!/usr/bin/env python3
"""Nudge the rotor: set it swinging about its rest angle (or calm it back down), with electrodes off afterwards.
A thin wrapper around brake_offsets.py with the recipe used on 2026-11-17 (worker2, Molly's go): kick phase A, then
pump along the motion until the swing reaches the target, field off. (2026-11-17)

    python3 lab_utils/nudge.py                  # check the tracker, print the plan (dry; nothing written)
    python3 lab_utils/nudge.py --live           # do it: swing to +-25 deg (default), electrodes back to 0
    python3 lab_utils/nudge.py --swing 15 --live
    python3 lab_utils/nudge.py --calm --live    # brake an existing swing down (brake mode, up to 120 s)

Needs the live tracker publishing angles to 127.0.0.1:5005, e.g.
    python3 camera_utils/tracking/live_blob_track.py --centre 128.62,176.54 --publish 127.0.0.1:5005 --outdir DIR

Before launching, the wrapper listens on the port for ~2 s and refuses if: no fresh angles arrive (tracker not
running, or the camera held by another process, as in the 11-17 first attempt); the port is already taken (another
controller, e.g. coast_series, is running); the image match ncc is below --ncc-min; or the swing target would leave
the g1 map's safe range (176-258 deg) around the present angle. Kick only if the rotor is nearly still (swing below
--kick-below); otherwise pump from the present swing. Everything else (preflight of the front end, field off on
every exit, outputs and TRAMP restored, SIGTERM/SIGHUP handling) is brake_offsets.py's own.
Exit code: brake_offsets.py's (0 = target reached / duration; 2 = a safety stop, electrodes already at 0).
"""
import argparse
import os
import socket
import subprocess
import sys
import time
from datetime import datetime

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SAFE = (176.0, 258.0)         # brake_offsets MAPS['g1']['safe']


def listen(port, secs):
    """Collect (host_time, angle, ncc) datagrams for secs. Returns (rows, error)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(('127.0.0.1', port))
    except OSError as e:
        return [], f'port {port} is in use ({e}): another controller (coast_series / brake_offsets) may be running'
    s.settimeout(0.1)
    rows, t_end = [], time.time() + secs
    try:
        while time.time() < t_end:
            try:
                k, ht, ang, ncc = s.recv(256).decode().split(',')
                rows.append((float(ht), float(ang), float(ncc)))
            except socket.timeout:
                continue
            except ValueError:
                continue
    finally:
        s.close()
    return rows, None


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--swing', type=float, default=25.0, help='deg: target swing amplitude (half peak-to-peak), default 25 (max ~29 about the 207 deg rest angle)')
    p.add_argument('--calm', action='store_true', help='brake the present swing down instead of pumping it up')
    p.add_argument('--kick', type=float, default=2400.0, help='counts on phase A for the starting kick (11-17 recipe: 2400)')
    p.add_argument('--kick-below', type=float, default=5.0, help='deg: kick only if the present swing is below this')
    p.add_argument('--duration', type=float, default=None, help='s of pumping/braking at most (default 90 pump, 120 calm)')
    p.add_argument('--ncc-min', type=float, default=0.7)
    p.add_argument('--port', type=int, default=5005)
    p.add_argument('--listen', type=float, default=3.5, help='s to listen to the tracker before launching (> one swing, ~3.1 s)')
    p.add_argument('--outdir', default=os.path.expanduser(f'~/spinup/{datetime.now():%Y-%m-%d}/nudge'))
    p.add_argument('--no-check', action='store_true', help='skip the tracker check (dry plan only; refused with --live)')
    p.add_argument('--live', action='store_true')
    a = p.parse_args()

    if not a.no_check:
        rows, err = listen(a.port, a.listen)
        if err:
            print('! ' + err); return 1
        if len(rows) < 20:
            print(f'! only {len(rows)} tracker angles in {a.listen:g} s on port {a.port}: is the tracker running with '
                  f'--publish 127.0.0.1:{a.port}, and does it have the camera?'); return 1
        r = np.array(rows)
        age = time.time() - r[-1, 0]
        ang = r[:, 1]
        med, half = float((ang.max() + ang.min()) / 2), float((ang.max() - ang.min()) / 2)   # swing centre, amplitude
        print(f'  tracker: {len(rows)} angles in {a.listen:g} s, last {age * 1e3:.0f} ms old, swing centre {med:.1f} deg, '
              f'swing +-{half:.1f} deg (over {a.listen:g} s only), ncc min {r[:, 2].min():.3f}')
        if age > 0.5:
            print('! tracker angles are stale'); return 1
        if r[:, 2].min() < a.ncc_min:
            print(f'! ncc {r[:, 2].min():.3f} below {a.ncc_min}: check the lights and the camera image'); return 1
        if not a.calm:
            room = min(med - SAFE[0], SAFE[1] - med) - 2.0
            if a.swing > room:
                print(f'! swing +-{a.swing:g} deg about {med:.1f} would leave the safe range {SAFE[0]:g}-{SAFE[1]:g} deg '
                      f'(room +-{room:.1f}); use --swing {max(room, 0):.0f} or less'); return 1
        kick = (not a.calm) and half < a.kick_below
    else:
        if a.live:
            print('! --no-check is for a dry plan only'); return 1
        kick = not a.calm

    cmd = [sys.executable, os.path.join(HERE, 'brake_offsets.py'), 'run', '--map', 'g1', '--ncc-min', f'{a.ncc_min:g}',
           '--outdir', a.outdir, '--enable-outputs', '--port', str(a.port)]
    if a.calm:
        cmd += ['--duration', f'{a.duration or 120:g}']
    else:
        cmd += ['--pump-to', f'{a.swing:g}', '--duration', f'{a.duration or 90:g}']
        if kick:
            cmd += ['--kick', f'{a.kick:g}']
    if a.live:
        cmd.append('--live')
    print('  ' + ('CALM (brake)' if a.calm else f'NUDGE to +-{a.swing:g} deg' + (' (kick first)' if kick else ' (pump from the present swing)'))
          + ('' if a.live else '  [dry: add --live to do it]'))
    print('  $ ' + ' '.join(cmd))
    sys.stdout.flush()
    return subprocess.call(cmd)


if __name__ == '__main__':
    sys.exit(main())
