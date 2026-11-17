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

LASER INTERLEAVING (2026-11-16, branch laser-interleave; optional, off unless --laser-pattern is given):
    --laser-pattern off,on,on,off   cycled, one entry per PAIR. Before each pair's + spin-up the script writes
                                    Y1:RDS-OUTS_LASER_OFFSET = --laser-on (default 1000) or --laser-off (default 0),
                                    waits --laser-settle s (default 30), then spins up. The laser never changes during
                                    a pair. The beam path (ND filter, block) is untouched: set it by hand.
    This is the ONLY EPICS write this script makes, and only with --live (dry: printed, not written). On every exit
    (end, STOP, safety stop, error, Ctrl-C, SIGTERM/SIGHUP) the laser offset is restored to the value read at the
    start. laser.csv: one row per switch and per coast start/end: host, FE GPS, pair, state, setpoint, readback, PD.
"""
import argparse
import csv
import os
import re
import shutil
import signal
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
LASER_PV = 'Y1:RDS-OUTS_LASER_OFFSET'
PD_PV = 'Y1:RDS-PD_INMON'


class Laser:
    """Laser offset switching for --laser-pattern. Writes LASER_PV only when live; restore() puts back the start value."""

    def __init__(self, a, rd):
        self.a, self.rd = a, rd
        self.pattern = [s.strip() for s in a.laser_pattern.split(',')] if a.laser_pattern else []
        bad = [s for s in self.pattern if s not in ('on', 'off')]
        if bad:
            raise SystemExit(f'--laser-pattern entries must be on/off, got {bad}')
        self.start = rd.get(LASER_PV) if self.pattern else None
        self.state = None
        self.f = None
        if self.pattern:
            path = os.path.join(a.outdir, 'laser.csv')
            new = not os.path.exists(path)
            self.f = open(path, 'a', buffering=1)
            if new:
                self.f.write('host,fe_gps,pair,event,state,setpoint,readback,pd\n')
            self.log(0, 'start', None, self.start)

    def log(self, pair, event, state, setpoint):
        if self.f:
            self.f.write(f'{time.time():.3f},{self.rd.gps()},{pair},{event},{state or ""},'
                         f'{"" if setpoint is None else setpoint},{self.rd.get(LASER_PV)},{self.rd.get(PD_PV)}\n')

    def set_for_pair(self, pair):
        """pair counts from 1. Returns True if the laser changed (then settle)."""
        if not self.pattern:
            return False
        want = self.pattern[(pair - 1) % len(self.pattern)]
        val = self.a.laser_on if want == 'on' else self.a.laser_off
        changed = want != self.state
        if self.a.live:
            import epics
            epics.caput(LASER_PV, val, wait=True, timeout=3.0)
        else:
            print(f'  [dry] would write {LASER_PV} = {val:g}')
        self.state = want
        self.log(pair, 'set', want, val)
        print(f'  laser {want.upper()} for pair {pair} ({LASER_PV} = {val:g}, readback {self.rd.get(LASER_PV)})',
              flush=True)
        if changed and self.a.laser_settle > 0:
            time.sleep(self.a.laser_settle)
            self.log(pair, 'settled', want, val)
        return changed

    def restore(self):
        if not self.pattern or self.start is None:
            return
        if self.a.live:
            import epics
            epics.caput(LASER_PV, self.start, wait=True, timeout=3.0)
        self.log(0, 'restored', None, self.start)
        print(f'  laser offset restored to the start value {self.start:g} (readback {self.rd.get(LASER_PV)})')


def _sigexit(signum, frame):
    raise SystemExit(f'killed ({signal.Signals(signum).name})')


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
    p.add_argument('--laser-pattern', default='', help='per-pair laser states, cycled, e.g. off,on,on,off (default: '
                   'laser untouched)')
    p.add_argument('--laser-on', type=float, default=1000.0, help='LASER_OFFSET for "on" (default 1000)')
    p.add_argument('--laser-off', type=float, default=0.0, help='LASER_OFFSET for "off" (default 0)')
    p.add_argument('--laser-settle', type=float, default=30.0, help='s to wait after a laser change (default 30)')
    a = p.parse_args()
    signal.signal(signal.SIGTERM, _sigexit)
    signal.signal(signal.SIGHUP, _sigexit)
    os.makedirs(os.path.abspath(os.path.expanduser(a.outdir)), exist_ok=True)
    rd = Reader(not a.no_epics)
    a.outdir = os.path.abspath(os.path.expanduser(a.outdir))
    laser = Laser(a, rd)
    try:
        return series(a, rd, laser)
    finally:
        laser.restore()


def series(a, rd, laser):
    n_steps = 2 * a.pairs
    print('=' * 72)
    print(f'  coast_series: {a.pairs} pairs ({n_steps} spin-ups + {a.coast:g} s coasts, ~{a.pairs * 24 / 60:.1f} h), '
          f'first dir {a.first_dir:+d}; ncc-min {a.ncc_min:g}; {"LIVE" if a.live else "DRY (brake_offsets without --live)"}')
    print(f'  outdir {a.outdir}; free {free_gb(a.outdir):.1f} GB; touch {os.path.join(a.outdir, "STOP")} to end early')
    if laser.pattern:
        print(f'  laser pattern per pair {",".join(laser.pattern)} (cycled); on {a.laser_on:g} / off {a.laser_off:g}; '
              f'settle {a.laser_settle:g} s; start value {laser.start} (restored on exit)')
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
        if i % 2 == 1:
            laser.set_for_pair((i + 1) // 2)
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
                 f'end_state {fmt_state(st)}\n' + (f'laser {laser.state}\n' if laser.pattern else '')); cf.flush()
        laser.log((i + 1) // 2, f'coast_start {name}', laser.state, None)
        print(f'  {name}: {"on target" if on_target else reason}; coasting {a.coast:g} s (nothing written)', flush=True)
        asked = coast(a, a.coast)
        t_end = time.time()
        cf.write(f'coast_end_host {t_end:.9f}\nfe_gps_coast_end {rd.gps()}\n'); cf.close()
        laser.log((i + 1) // 2, f'coast_end {name}', laser.state, None)
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
