#!/usr/bin/env python3
"""Read traces from the R&S RTB2004 over USB-TMC (worker2, /dev/usbtmc1). Read-only by default.

    python3 scope_rtb.py idn
    python3 scope_rtb.py settings                 # timebase, channel scales, probe factors, state
    python3 scope_rtb.py read OUT_DIR [--label L] # all four channels -> OUT_DIR/scope_<host time>.npz/.csv

Setup (2026-11-03): worker2 sees the scope as /dev/usbtmc1 (USB mode TMC; udev rule
/etc/udev/rules.d/99-rs-scope.rules gives group plugdev rw). Channel map (Molly 2026-11-03):
CH1 = LES YAW, CH2 = V2, CH3 = V3, CH4 = V4. Probes 10x on the amplifier outputs.

`read` takes what the scope has ACQUIRED. Stop the scope (Run/Stop key) after the waveform
has played, then run `read`. It refuses if the scope is still running, unless --stop is given,
which sends STOP (the only acquisition state change this script makes; printed).
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


class Scope:
    def __init__(self, dev=DEV):
        self.fd = os.open(dev, os.O_RDWR)

    def write(self, cmd, echo=False):
        if echo:
            print(f'  scope <- {cmd}')
        os.write(self.fd, (cmd + '\n').encode())

    def read_raw(self):
        out = b''
        while True:
            chunk = os.read(self.fd, 1 << 20)
            out += chunk
            if out.startswith(b'#') and len(out) >= 2:
                nd = int(out[1:2])
                if len(out) >= 2 + nd:
                    n = int(out[2:2 + nd])
                    if len(out) >= 2 + nd + n:
                        return out
            elif out.endswith(b'\n'):
                return out

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
        return np.frombuffer(data, '<f4').astype(float)

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


def settings(s):
    out = {'idn': s.q('*IDN?'), 'acq_state': s.q('ACQ:STAT?'),
           'tim_scale': s.q('TIM:SCAL?'), 'tim_pos': s.q('TIM:POS?'), 'tim_ref': s.q('TIM:REF?'),
           'acq_points': s.q('ACQ:POIN?'), 'srate': s.q('ACQ:SRAT?')}
    for ch in CHANNELS:
        for key, cmd in (('state', 'CHAN{}:STAT?'), ('scale', 'CHAN{}:SCAL?'), ('offset', 'CHAN{}:OFFS?'),
                         ('position', 'CHAN{}:POS?'), ('coupling', 'CHAN{}:COUP?'),
                         ('probe', 'PROB{}:SET:ATT:MAN?')):
            out[f'ch{ch}_{key}'] = s.q(cmd.format(ch))
    out['errors'] = s.errors()
    return out


def read(s, out_dir, label, stop):
    st = s.q('ACQ:STAT?')
    if 'STOP' not in st.upper() and 'COMP' not in st.upper() and 'BRE' not in st.upper():
        if not stop:
            sys.exit(f'! scope acquisition state is {st!r}: press Run/Stop on the scope after the waveform has '
                     f'played, then read again (or pass --stop).')
        s.write('STOP', echo=True)
        time.sleep(0.5)
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
        heads[ch] = (x0, x1, int(npts))
        traces[ch] = y
        print(f'  CH{ch} ({CHANNELS[ch]}): {y.size} points, {x0:+.4g} .. {x1:+.4g} s')
    info['errors_after'] = s.errors()
    if info['errors_after']:
        print('  scope errors:', info['errors_after'])
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, f'scope_{int(host_time)}' + (f'_{label}' if label else ''))
    arrays = {}
    for ch, y in traces.items():
        x0, x1, n = heads[ch]
        arrays[f'CH{ch}'] = y
        arrays[f'CH{ch}_t'] = np.linspace(x0, x1, y.size, endpoint=False)
    np.savez(stem + '.npz', host_time=host_time, label=label, **arrays)
    with open(stem + '.json', 'w') as f:
        json.dump(dict(info, host_time=host_time, label=label, channels=CHANNELS,
                       heads={str(k): v for k, v in heads.items()}), f, indent=1)
    print(f'  saved {stem}.npz / .json (worker2 host time {host_time:.3f})')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('cmd', choices=('idn', 'settings', 'read'))
    p.add_argument('out_dir', nargs='?')
    p.add_argument('--label', default='')
    p.add_argument('--stop', action='store_true', help='send STOP if the scope is still running')
    p.add_argument('--dev', default=DEV)
    a = p.parse_args()
    s = Scope(a.dev)
    try:
        if a.cmd == 'idn':
            print(s.q('*IDN?'))
        elif a.cmd == 'settings':
            for k, v in settings(s).items():
                print(f'  {k:16s} {v}')
        else:
            if not a.out_dir:
                sys.exit('read needs OUT_DIR')
            read(s, a.out_dir, a.label, a.stop)
    finally:
        s.close()


if __name__ == '__main__':
    main()
