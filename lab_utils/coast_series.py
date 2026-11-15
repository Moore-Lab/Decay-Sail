#!/usr/bin/env python3
"""Overnight coast series: repeat (spin-up +, coast, spin-up -, coast) pairs for damping stability over hours (2026-11-14).

    python3 coast_series.py --pairs 25 --outdir ~/spinup/2026-11-14/overnight            # dry: brake_offsets without --live
    python3 coast_series.py --pairs 25 --outdir ~/spinup/2026-11-14/overnight --live     # Molly's go, typed on worker2

Launch detached on worker2 (tmux does not work there), so a closed terminal or Claude session cannot kill it:
    setsid nohup python3 lab_utils/coast_series.py --pairs 40 --outdir DIR --live > DIR/series_console.txt 2>&1 &
    watch: tail -f DIR/series_console.txt        end early: touch DIR/STOP
brake_offsets.py turns the field off on SIGTERM/SIGHUP as on Ctrl-C (2026-11-14). If this script itself is killed
mid-run, series.csv lacks that step's row: the console files have it. If the series stopped early, check the
tracker first (a dead tracker stops the next spin-up on stale frames, safely).

Needs the tracker running first, publishing to 127.0.0.1:5005 (from ~/wt_fb):
    camera_utils/tracking/live_blob_track.py --centre 131.03,178.79 --publish 127.0.0.1:5005 --video-every 10 --outdir DIR

Each step is one brake_offsets.py run, the same settings as the 11-12 coast pairs C1-C6:
    run --map g1 --level 800 --w-push-max 120 --spin-to 0.5 --dir D --stop-on-target 3 --stop-tol 0.01
        --duration 360 --ncc-min 0.70 --enable-outputs [--live] --outdir OUTDIR
then --coast s (default 600) of free coast with nothing written. Directions alternate +1, -1, +1, ... The spin-up
against the current rotation brakes first (brake_offsets' reversal), as in C2/C4/C6.

THIS SCRIPT WRITES NO EPICS CHANNEL. All writes are brake_offsets.py's own (field off in its finally block on every
exit). Here: subprocess runs, read-only cagets (front-end GPS, OFFSET/SW2R/TRAMP/OUTMON per channel) and files.

Stops:
  - spin-up 'on target'                 -> coast, continue
  - spin-up 'duration' (not on target)  -> the field is off anyway: coast, logged as not on target, continue
  - anything else (ncc, stale tracker, speed cap, error, refusal, Ctrl-C, nonzero OFFSET after a run)
                                        -> STOP THE SERIES. No more runs, no final brake; the rotor coasts free.
  - --pairs done, or the file OUTDIR/STOP exists (checked once a second during coasts and before each spin-up),
    or free disk below --min-free-gb    -> the current coast finishes, then one final brake (as D6 on 11-12:
    --level 1600 --spin-to 0.001, --duration 300) and exit.

Files in OUTDIR, per step n (O01, O02, ...; odd = +1, even = -1):
  console_On.txt   brake_offsets output        brake_<host>.csv  brake_offsets log
  coast_On.txt     field_off_host, end_state, coast_end_host, fe_gps (coast_pairs.py format, plus extras)
  series.csv       one row per step: name, dir, start/field-off/coast-end host times, FE GPS, stop reason, last turns
"""
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PREFIX = 'Y1:RDS-OUTS'
GPS_PV = 'Y1:DAQ-DC0_GPS'
CHANS = (2, 3, 4)
SPIN = ['--map', 'g1', '--level', '800', '--w-push-max', '120', '--spin-to', '0.5', '--stop-on-target', '3',
        '--stop-tol', '0.01', '--duration', '360', '--enable-outputs']
FINAL = ['--map', 'g1', '--level', '1600', '--w-push-max', '120', '--spin-to', '0.001', '--duration', '300',
         '--enable-outputs']


class Reader:
    """Read-only cagets. None everywhere when EPICS is unavailable (--no-epics, Mac tests)."""

    def __init__(self, on):
        self.e = None
        if on:
            import epics
            self.e = epics

    def get(self, pv):
        return self.e.caget(pv, timeout=3.0, use_monitor=False) if self.e else None

    def gps(self):
        return self.get(GPS_PV)

    def state(self):
        out = {}
        for n in CHANS:
            out[n] = tuple(self.get(f'{PREFIX}_V{n}_{f}') for f in ('OFFSET', 'SW2R', 'TRAMP', 'OUTMON'))
        return out


def fmt_state(st):
    return ' '.join(f'V{n}:' + ','.join('' if v is None else f'{v:g}' for v in st[n]) for n in sorted(st))


def offsets_zero(st):
    return all(st[n][0] is None or abs(st[n][0]) < 0.5 for n in st)


def stop_requested(a):
    return os.path.exists(os.path.join(a.outdir, 'STOP'))


def free_gb(path):
    return shutil.disk_usage(path).free / 1e9


def run_brake(a, args, console):
    """One brake_offsets run; output to the terminal and the console file. -> (stop reason, last-turns text, rc)."""
    cmd = [sys.executable, a.brake_script, 'run'] + args + (['--live'] if a.live else []) + ['--outdir', a.outdir]
    with open(console, 'w') as fh:
        fh.write('# ' + ' '.join(cmd) + '\n'); fh.flush()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        txt = []
        for line in p.stdout:
            sys.stdout.write(line); fh.write(line); txt.append(line)
        rc = p.wait()
    txt = ''.join(txt)
    if not a.live and 'dry: nothing written' in txt:
        return 'dry', '', rc
    m = re.search(r'stop: ([^;\n]*)', txt)
    reason = m.group(1).strip() if m else f'no stop line (rc {rc})'
    turns = re.search(r'\(([0-9., ]+)\)', reason)
    return reason, (turns.group(1) if turns else ''), rc


def coast(a, secs):
    """Sleep secs, nothing written; True if a STOP file appeared (the coast still runs to the end)."""
    t_end = time.time() + secs
    asked = False
    while time.time() < t_end:
        time.sleep(min(1.0, max(0.0, t_end - time.time())))
        if not asked and stop_requested(a):
            asked = True
            print(f'  STOP file seen: finishing this coast ({t_end - time.time():.0f} s left), then the final brake')
    return asked


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--pairs', type=int, required=True, help='number of (+, -) pairs (about 24 min each)')
    p.add_argument('--coast', type=float, default=600.0, help='s of free coast after each spin-up (11-12: 600)')
    p.add_argument('--outdir', required=True)
    p.add_argument('--live', action='store_true', help='pass --live to brake_offsets (Molly\'s go)')
    p.add_argument('--ncc-min', type=float, default=0.70, help='tracker match stop for every brake_offsets run (11-12: '
                   '0.70; a lost dot reads ~0.5, ncc_elsewhere)')
    p.add_argument('--first-dir', type=int, default=1, choices=(1, -1))
    p.add_argument('--min-free-gb', type=float, default=5.0)
    p.add_argument('--no-final-brake', action='store_true', help='end without the final brake')
    p.add_argument('--no-epics', action='store_true', help='skip read-only cagets (Mac tests)')
    p.add_argument('--brake-script', default=os.path.join(HERE, 'brake_offsets.py'), help=argparse.SUPPRESS)
    a = p.parse_args()
    a.outdir = os.path.abspath(os.path.expanduser(a.outdir))
    os.makedirs(a.outdir, exist_ok=True)
    rd = Reader(not a.no_epics)
    n_steps = 2 * a.pairs
    print('=' * 72)
    print(f'  coast_series: {a.pairs} pairs ({n_steps} spin-ups + {a.coast:g} s coasts, ~{a.pairs * 24 / 60:.1f} h), '
          f'first dir {a.first_dir:+d}; ncc-min {a.ncc_min:g}; {"LIVE" if a.live else "DRY (brake_offsets without --live)"}')
    print(f'  outdir {a.outdir}; free {free_gb(a.outdir):.1f} GB; touch {os.path.join(a.outdir, "STOP")} to end early')
    print('=' * 72)
    st0 = rd.state()
    if not offsets_zero(st0):
        print('! refusing: an OFFSET is nonzero before the series: ' + fmt_state(st0)); return 1
    sfile = os.path.join(a.outdir, 'series.csv')
    new = not os.path.exists(sfile)
    sf = open(sfile, 'a', buffering=1)
    if new:
        sf.write('name,dir,spin_start_host,field_off_host,coast_end_host,fe_gps_field_off,stop_reason,last_turns_hz,'
                 'on_target,free_gb\n')
    end_why, d = 'pairs done', a.first_dir
    last_dir = d
    for i in range(1, n_steps + 1):
        name = f'O{i:02d}'
        if stop_requested(a):
            end_why = 'STOP file'; break
        if free_gb(a.outdir) < a.min_free_gb:
            end_why = f'free disk below {a.min_free_gb:g} GB'; break
        print(f'\n--- {name}: spin-up dir {d:+d}  ({time.strftime("%H:%M:%S")}, step {i}/{n_steps}) ---', flush=True)
        t_start = time.time()
        reason, turns, rc = run_brake(a, SPIN + ['--ncc-min', f'{a.ncc_min:g}', '--dir', str(d)], os.path.join(a.outdir, f'console_{name}.txt'))
        t_off = time.time()
        g_off = rd.gps()
        st = rd.state()
        on_target = reason.startswith('on target')
        ok = on_target or reason in ('duration', 'dry')
        if not offsets_zero(st):
            reason, ok = reason + ' + OFFSET NONZERO AFTER RUN: ' + fmt_state(st), False
        last_dir = d
        if not ok:
            sf.write(f'{name},{d},{t_start:.3f},{t_off:.3f},,{g_off},"{reason}","{turns}",0,{free_gb(a.outdir):.1f}\n')
            print(f'\n! SERIES STOPPED at {name}: {reason}. No more runs and no final brake; the rotor coasts free.')
            print('  End state ' + fmt_state(st))
            return 2
        cf = open(os.path.join(a.outdir, f'coast_{name}.txt'), 'w')
        cf.write(f'field_off_host {t_off:.9f}\nfe_gps_field_off {g_off}\ndir {d}\nstop {reason}\n'
                 f'end_state {fmt_state(st)}\n'); cf.flush()
        print(f'  {name}: {"on target" if on_target else reason}; coasting {a.coast:g} s (nothing written)', flush=True)
        asked = coast(a, a.coast)
        t_end = time.time()
        cf.write(f'coast_end_host {t_end:.9f}\nfe_gps_coast_end {rd.gps()}\n'); cf.close()
        sf.write(f'{name},{d},{t_start:.3f},{t_off:.3f},{t_end:.3f},{g_off},"{reason}","{turns}",{int(on_target)},'
                 f'{free_gb(a.outdir):.1f}\n')
        if asked:
            end_why = 'STOP file'; break
        d = -d
    print(f'\n--- series ends: {end_why} ({time.strftime("%H:%M:%S")}) ---')
    if a.no_final_brake:
        print('  no final brake (--no-final-brake): rotor left coasting'); return 0
    reason, _, rc = run_brake(a, FINAL + ['--ncc-min', f'{a.ncc_min:g}', '--dir', str(last_dir)], os.path.join(a.outdir, 'console_final.txt'))
    st = rd.state()
    print(f'  final brake: {reason}; end state {fmt_state(st)}')
    if reason not in ('duration', 'dry') or not offsets_zero(st):
        print('! final brake did not end cleanly: check the front end')
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
