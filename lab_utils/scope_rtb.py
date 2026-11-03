#!/usr/bin/env python3
"""Read traces from the R&S RTB2004 over USB-TMC (worker2, /dev/usbtmc1). Read-only by default.

    python3 scope_rtb.py idn
    python3 scope_rtb.py probe                    # one query at a time; stops at the first silent one
    python3 scope_rtb.py settings                 # timebase, channel scales, probe factors, state
    python3 scope_rtb.py read OUT_DIR [--label L] # all four channels -> OUT_DIR/scope_<host time>.npz/.csv

Setup (2026-11-03): worker2 sees the scope as /dev/usbtmc1 (USB mode TMC; udev rule
/etc/udev/rules.d/99-rs-scope.rules gives group plugdev rw). Channel map (Molly 2026-11-03):
CH1 = LES YAW, CH2 = V2, CH3 = V3, CH4 = V4. Plain BNC coax from the amplifier outputs (1x), DC coupled.

`read` takes what the scope has ACQUIRED. Molly keeps the scope running, so by default `read` sends
STOP (freezing the last screenful, e.g. ~60 s at 5 s/div), transfers the traces, then sends RUN to put
it back as it was (Molly 2026-11-03). Both are printed. --no-restart leaves it stopped; --no-stop refuses
to read a running scope instead.
It does change two TRANSFER settings, printed when sent: FORM REAL,32 (binary floats) and
CHANn:DATA:POIN DMAX (the full acquired record, not just the display points). Neither changes
what the scope acquires or shows.

SCPI spellings follow the RTB2000 manual as remembered; `settings` checks them on the real scope
before `read` relies on them (any SYST:ERR? content is printed).

Timing: the scope has no GPS. Each read records worker2's clock (NTP) just before the transfer;
the trace is aligned to the front-end record afterwards by cross-correlation with the commanded
waveform (waveform_check.py), not by clock.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

DEV = '/dev/usbtmc1'
CHANNELS = {1: 'LES_YAW', 2: 'V2', 3: 'V3', 4: 'V4'}
MAX_RATE = 20000.0      # saved samples/s per channel (block-averaged down from the record)


class Scope:
    def __init__(self, dev=DEV):
        self.fd = os.open(dev, os.O_RDWR)

    def write(self, cmd, echo=False):
        if echo:
            print(f'  scope <- {cmd}')
        os.write(self.fd, (cmd + '\n').encode())

    def read_raw(self):
        out = bytearray()
        while True:
            chunk = os.read(self.fd, 1 << 20)
            out += chunk
            if out.startswith(b'#') and len(out) >= 2:
                nd = int(out[1:2])
                if len(out) >= 2 + nd:
                    n = int(out[2:2 + nd])
                    if len(out) >= 2 + nd + n:
                        return bytes(out)
            elif out.endswith(b'\n'):
                return bytes(out)

    def q(self, cmd):
        self.write(cmd)
        return self.read_raw().decode(errors='replace').strip()

    def block(self, cmd):
        """IEEE 488.2 definite-length block of little-endian float32."""
        self.write(cmd)
        raw = self.read_raw()
        if not raw.startswith(b'#'):
            raise RuntimeError(f'{cmd}: expected a binary block, got {raw[:60]!r}')
        nd = int(raw[1:2]); n = int(raw[2:2 + nd])
        data = raw[2 + nd:2 + nd + n]
        # The RTB2004 sends REAL,32 MSB-first (W2 2026-11-03: '<f4' gave 1e-41..6e23, '>f4' gave volts).
        y = np.frombuffer(data, '>f4').astype(np.float32)
        if y.size and not np.all(np.abs(y[np.isfinite(y)]) < 1e4):
            raise RuntimeError(f'{cmd}: values outside +-1e4 V after big-endian parse; byte order wrong?')
        return y

    def errors(self):
        errs = []
        for _ in range(10):
            e = self.q('SYST:ERR?')
            if e.startswith('0') or e.startswith('+0'):
                break
            errs.append(e)
        return errs

    def close(self):
        os.close(self.fd)


# Answered 2026-11-03: *IDN? ACQ:STAT? TIM:SCAL? CHAN2:STAT? CHAN2:SCAL? CHAN2:OFFS?.
# CHAN2:POS? got NO REPLY and wedged the link (removed everywhere). Next, the ones `read` needs most first.
PROBE = ['*IDN?', 'FORM?', 'CHAN2:DATA:HEAD?', 'CHAN2:DATA:POIN?', 'TIM:POS?', 'TIM:REF?', 'ACQ:POIN?',
         'ACQ:SRAT?', 'CHAN2:COUP?', 'PROB2:SET:ATT:MAN?']


def probe(s):
    """One query at a time, printed as it answers; stops at the first one that gets no reply, since a
    timed-out query has left the scope's USB link stuck twice (2026-11-03; a power-cycle cleared it)."""
    for c in PROBE:
        print(f'  {c:22s}', end=' ', flush=True)
        try:
            print(s.q(c)[:120], flush=True)
        except OSError as err:
            print(f'NO REPLY ({err}). Stopping here: this spelling is the suspect. Power-cycle the scope before '
                  f'the next query.')
            return False
    return True


def settings(s):
    out = {'idn': s.q('*IDN?'), 'acq_state': s.q('ACQ:STAT?'),
           'tim_scale': s.q('TIM:SCAL?'), 'tim_pos': s.q('TIM:POS?'), 'tim_ref': s.q('TIM:REF?'),
           'acq_points': s.q('ACQ:POIN?'), 'srate': s.q('ACQ:SRAT?')}
    for ch in CHANNELS:
        for key, cmd in (('state', 'CHAN{}:STAT?'), ('scale', 'CHAN{}:SCAL?'), ('offset', 'CHAN{}:OFFS?'),
                         ('coupling', 'CHAN{}:COUP?'),
                         ('probe', 'PROB{}:SET:ATT:MAN?')):
            out[f'ch{ch}_{key}'] = s.q(cmd.format(ch))
    out['errors'] = s.errors()
    return out


def arm(s):
    """Single acquisition: the scope waits for its trigger (Molly sets it on the panel: CH2 rising edge on the
    pedestal step, Normal mode, trigger position near the left edge), records one screen, then stops (COMP)."""
    s.write('SING', echo=True)
    errs = s.errors()
    if errs:
        print(f'  ! scope errors after SING: {errs}')
    # The scope fills its pre-trigger buffer first (screen shows "Pre nn%"); a trigger during that fill is
    # ignored (W2 bchirp 2026-11-03: the pedestal step was missed and it triggered ~45 s into the chirp).
    # Pre-trigger time = 12 divisions x timebase x (trigger reference %).
    try:
        pre = 12 * float(s.q('TIM:SCAL?')) * float(s.q('TIM:REF?')) / 100.0
    except Exception:
        pre = 0.0
    return pre


def wait_complete(s, timeout):
    """Poll until the single acquisition has completed, up to `timeout` s. True if it did."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = s.q('ACQ:STAT?').upper()
        if 'COMP' in st:                        # W2 bchirp: STOP right after SING did NOT mean a finished record
            return True
        time.sleep(1.0)
    return False


def diag(s, out_dir, force_after=10.0, timeout=180.0):
    """Scope-only test of the single-acquisition path (no drive): SING, log ACQ:STAT? every second, force a
    trigger (*TRG) after `force_after` s, wait for COMP, then read and print what came back."""
    s.write('SING', echo=True)
    print('  errors after SING:', s.errors())
    t0 = time.time(); forced = False; last = None
    while time.time() - t0 < timeout:
        st = s.q('ACQ:STAT?')
        if st != last:
            print(f'  {time.time() - t0:6.1f} s  ACQ:STAT? -> {st}')
            last = st
        if 'COMP' in st.upper():
            break
        if not forced and time.time() - t0 > force_after:
            s.write('*TRG', echo=True); forced = True
            print('  errors after *TRG:', s.errors())
        time.sleep(1.0)
    _read(s, out_dir, 'diag')


def read(s, out_dir, label, stop=True, restart=True, wait=0.0):
    if wait > 0:
        print(f'  waiting up to {wait:.0f} s for the scope acquisition to complete ...')
        print('  complete.' if wait_complete(s, wait) else '  ! not complete; stopping it and reading what is there.')
    st = s.q('ACQ:STAT?')
    stopped_here = False
    if 'STOP' not in st.upper() and 'COMP' not in st.upper() and 'BRE' not in st.upper():
        if not stop:
            sys.exit(f'! scope acquisition state is {st!r}: stop it first, or drop --no-stop.')
        s.write('STOP', echo=True)
        time.sleep(0.5)
        stopped_here = True
    try:
        _read(s, out_dir, label)
    finally:
        if stopped_here and restart:
            s.write('RUN', echo=True)


def _read(s, out_dir, label):
    host_time = time.time()
    info = settings(s)
    s.write('FORM REAL,32', echo=True)
    traces, heads = {}, {}
    for ch in CHANNELS:
        if not info[f'ch{ch}_state'].strip().upper().startswith(('1', 'ON')):
            continue
        s.write(f'CHAN{ch}:DATA:POIN DMAX', echo=True)
        head = s.q(f'CHAN{ch}:DATA:HEAD?')          # xstart, xstop, points, values per sample
        x0, x1, npts, vps = [float(v) for v in head.split(',')[:4]]
        y = s.block(f'CHAN{ch}:DATA?')
        if int(vps) != 1:
            print(f'  ! CH{ch}: {int(vps)} values per sample (peak-detect?); keeping every first value')
            y = y[::int(vps)]
        # keep at most MAX_RATE samples/s (block means: an anti-alias average), float32, to keep files small
        tt = np.linspace(x0, x1, y.size, endpoint=False)
        fs_rec = y.size / (x1 - x0) if x1 > x0 else 0
        k = int(fs_rec // MAX_RATE) if fs_rec > MAX_RATE else 1
        if k > 1:
            m = (y.size // k) * k
            y = y[:m].reshape(-1, k).mean(axis=1).astype(np.float32)
            tt = tt[:m].reshape(-1, k).mean(axis=1)
        heads[ch] = (x0, x1, int(npts))
        traces[ch] = (tt, y)
        print(f'  CH{ch} ({CHANNELS[ch]}): {int(npts)} points read, {y.size} saved, {x0:+.4g} .. {x1:+.4g} s, '
              f'{y.min():+.2f} .. {y.max():+.2f} V')
    info['errors_after'] = s.errors()
    if info['errors_after']:
        print('  scope errors:', info['errors_after'])
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, f'scope_{int(host_time)}' + (f'_{label}' if label else ''))
    arrays = {}
    for ch, (tt, y) in traces.items():
        arrays[f'CH{ch}'] = y
        arrays[f'CH{ch}_t'] = tt
    np.savez(stem + '.npz', host_time=host_time, label=label, **arrays)
    with open(stem + '.json', 'w') as f:
        json.dump(dict(info, host_time=host_time, label=label, channels=CHANNELS,
                       heads={str(k): v for k, v in heads.items()}), f, indent=1)
    print(f'  saved {stem}.npz / .json (worker2 host time {host_time:.3f})')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('cmd', choices=('idn', 'probe', 'settings', 'read', 'diag'))
    p.add_argument('out_dir', nargs='?')
    p.add_argument('--label', default='')
    p.add_argument('--no-stop', action='store_true', help='refuse to read a running scope instead of stopping it')
    p.add_argument('--no-restart', action='store_true', help='leave the scope stopped after the read')
    p.add_argument('--dev', default=DEV)
    a = p.parse_args()
    s = Scope(a.dev)
    try:
        if a.cmd == 'idn':
            print(s.q('*IDN?'))
        elif a.cmd == 'probe':
            probe(s)
        elif a.cmd == 'diag':
            if not a.out_dir:
                sys.exit('diag needs OUT_DIR')
            diag(s, a.out_dir)
        elif a.cmd == 'settings':
            for k, v in settings(s).items():
                print(f'  {k:16s} {v}')
        else:
            if not a.out_dir:
                sys.exit('read needs OUT_DIR')
            read(s, a.out_dir, a.label, stop=not a.no_stop, restart=not a.no_restart)
    finally:
        s.close()


if __name__ == '__main__':
    main()
