#!/usr/bin/env python3
"""Play a test waveform (waveforms.py) on V2/V3/V4 through the front-end AWG. Gate W1/W2.

    python3 awg_waveform_drive.py --wave pulse --amp 500 --pedestal 1000              # dry run
    python3 awg_waveform_drive.py --wave pulse --amp 500 --pedestal 1000 --live       # W1: outputs stay OFF
    python3 awg_waveform_drive.py --wave pulse --amp 500 --pedestal 1000 --live --outputs-on   # W2

Why the AWG: the front end applies EPICS writes only at 16 Hz (F1b), so nothing written over EPICS
can carry 10 Hz. The AWG daemon plays a pre-loaded sample array into V{n}_EXC at the 2048 Hz model
rate (sines verified this way 2026-08-28, stator_awg_drive.py). All three channels share one start
time in the FRONT-END clock (Y1:DAQ-DC0_GPS + lead; true GPS silently never plays).

What it does, in order:
  checks   DRVON 0 and DRV gains 0 (else refuse: the oscillator would sum in); LES/MON isolated from
           V1..V4 (else refuse, same check as stator_osc_drive.py); V2..V4 GAIN 1; the pedestal keeps
           the amplifier input inside 0..12800 for the whole waveform (pedestal >= amp*max(-w),
           pedestal + amp*max(w) <= 12800).
  outputs  W1 (no --outputs-on): REFUSES if any V2..V4 output switch is on, and never touches them.
           W2 (--outputs-on): output bit on (with OFFSET still 0), then the pedestal ramps up.
  pedestal V{n}_TRAMP set to --ramp, the three OFFSETs written back to back, wait --ramp + 1 s.
  play     the three excitations armed with one shared start; wait out the waveform.
  stop     stop(wait=True) (frees the AWG slot), then the pedestal ramps down to 0, then TRAMP and the
           output switches are put back as they were. The pedestal always outlives the AC.
  save     OUT_DIR/command.npz (the exact samples, amp, pedestal, start) and, after --nds-lag s,
           OUT_DIR/out_dq.npz (OUTS_V2..V4_OUT_DQ, 1024 Hz) for waveform_check.py.

Ctrl-C at any point goes through the same stop sequence. Nothing touches hardware without --live.
If nothing comes out (OUT_DQ flat), the AWG slots may be leaked: run awg_reclaim.py as its own
process, then try again (stator_awg_drive.py docstrings, 2026-08-28).
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import waveforms  # noqa: E402

try:
    from epics import caget, caput
except ImportError:
    caget = caput = None

PREFIX = 'Y1:RDS-OUTS'
ELECTRODES = waveforms.ELECTRODES          # (2, 3, 4): array row order
LIMIT = 12800.0
SW2_OUTPUT_ON = 1024
INPUT_SOURCE = {1: 'LES_PIT', 2: 'LES_YAW', 3: 'LES_SUM', 4: 'MON'}


def put(pv, val, dry):
    print(f'    {"[dry] " if dry else ""}{pv:<34} <- {val:g}')
    if not dry:
        caput(pv, float(val), wait=True, timeout=3.0)


def fe_gps():
    return float(caget('Y1:DAQ-DC0_GPS'))


def local_gps():
    """worker2's own GPS time (awgbase.GPSnow, ns -> s), the clock libSIStr itself uses."""
    import awgbase
    return awgbase.GPSnow() / 1e9


TAIL_S = 12   # zeros after the waveform: SIStr sends ~7 s ahead (SIStr_LEADTIME), and ArbitraryLoop
              # repeats the array until stopped, so we stop inside this silence and nothing repeats.


def padded(samples):
    """Waveform + TAIL_S s of zeros, padded to whole seconds (ArbitraryLoop sends 1 s chunks)."""
    fs = int(waveforms.FS)
    n = len(samples) + TAIL_S * fs
    n = int(np.ceil(n / fs)) * fs
    out = np.zeros(n, np.float32)
    out[:len(samples)] = samples
    return out


def make_excitation(chan, samples, start_s):
    """THE ONLY PLACE THAT TOUCHES THE awg API (python-awg 4.2.3 on worker2, source read 2026-11-03):
    ArbitraryLoop(chan, data, scale=1, rate=0, start=0) streams `data` through libSIStr in 1 s chunks
    (rate samples each), looping until stop(). `start` is an integer GPS second given to SIStrOpen.
    Started with ramptime=0 (no 1 s gain ramp, so the samples play as written) and wait=False (so the
    three channels are armed without one waiting on another)."""
    import awg
    return awg.ArbitraryLoop(chan, padded(samples), rate=int(waveforms.FS), start=int(start_s))


# ---- Built-in AWG waveforms (Molly OK 2026-11-03, after W0): generated inside the AWG server, so no
# streaming and no dependence on worker2's clock. python-awg 4.2.3 (worker2, source read 2026-11-03):
#   Sine(chan, ampl, freq, phase[rad], offset, start[GPS s], duration[s], restart[s])
#   SweptSine(chan, ampl1, freq1, phase1, offset1, ampl2, freq2, phase2, offset2, amplramp, freqramp,
#             start, sweeptime)   sweeptime sets duration AND restart (it repeats unless stopped)
#   Excitation.compose([...]) puts several components (<= 5000) on one channel.
# The header says a component's phase is "relative to the last GPS one-day boundary", and whether the
# periodic signal is sin or cos is not documented. So every component starts on a whole second with an
# integer frequency (or the scorer fits the phase), and builtin_check.py measures, model-free:
# relative phases/lags between electrodes, amplitudes, and the sin-or-cos shape.
# Phases are given as electrical lags A=0, B=120, C=240 deg (A,B,C = V2,V4,V3); whether awg's phase
# enters with + or - sign (stator_awg_drive.py found it inverted on 2026-08-28) is reported by the scorer.
BUILTIN = {
    # name: (duration s, description)
    'bsine': (10.0, 'three-phase Sine 2 Hz, 10 s, phases 0/-120/-240 deg (A/B/C), 0.5 s linear phase-in'),
    'bchirp': (60.0, 'three-phase SweptSine 0.1 -> 12 Hz, log, 60 s, phases 0/-120/-240 deg, 0.5 s linear phase-in'),
    'bburst': (6.0, 'one-cycle 10 Hz Sine bursts: V2 at 1 s, V3 at 2 s, V4 at 3 s, all three at 4 s'),
}


def builtin_excitations(name, amp, start):
    import awg
    out = []
    for n in ELECTRODES:
        chan = f'{PREFIX}_V{n}_EXC'
        ph = -np.radians(waveforms.DELTA[n])
        if name == 'bsine':
            e = awg.Sine(chan, ampl=amp, freq=2.0, phase=ph, start=start, duration=BUILTIN[name][0])
            e.set_phase_in(ramp='linear', ramptime=0.5)
        elif name == 'bchirp':
            e = awg.SweptSine(chan, ampl1=amp, freq1=0.1, phase1=ph, ampl2=amp, freq2=12.0, phase2=ph,
                              amplramp='linear', freqramp='log', start=start, sweeptime=BUILTIN[name][0])
            e.set_phase_in(ramp='linear', ramptime=0.5)   # W1: a full-amplitude start stepped V3/V4 by ~4300 counts
        elif name == 'bburst':
            ts = {2: (1, 4), 3: (2, 4), 4: (3, 4)}[n]
            comps = [awg.Sine(chan, ampl=amp, freq=10.0, phase=0.0, start=start + k, duration=0.1) for k in ts]
            e = awg.Excitation.compose(comps)
        out.append(e)
    return out


def checks(amp, ped, w, outputs_on):
    bad = []
    if caget(f'{PREFIX}_DRVON'):
        bad.append('DRVON is on (the oscillator would sum in): stator_osc_drive.py stop first')
    for g in ('SINGAIN', 'COSGAIN'):
        v = caget(f'{PREFIX}_DRV_{g}') or 0.0
        if abs(v) > 1e-6:
            bad.append(f'DRV_{g} = {v:g}, not 0')
    for n, src in INPUT_SOURCE.items():
        g = caget(f'Y1:RDS-{src}_GAIN'); sw2 = caget(f'Y1:RDS-{src}_SW2R')
        if g is not None and sw2 is not None and abs(g) > 1e-6 and int(sw2) & SW2_OUTPUT_ON:
            bad.append(f'V{n} <- {src} is live (GAIN {g:g}, output on): switch its OUTPUT off')
    state = {}
    for n in ELECTRODES:
        b = f'{PREFIX}_V{n}'
        state[n] = {k: caget(f'{b}_{k}') for k in ('GAIN', 'OFFSET', 'TRAMP', 'SW1R', 'SW2R')}
        if abs((state[n]['GAIN'] or 0) - 1.0) > 1e-6:
            bad.append(f'V{n}_GAIN = {state[n]["GAIN"]}, expected 1')
        if abs(state[n]['OFFSET'] or 0) > 1.0:
            bad.append(f'V{n}_OFFSET = {state[n]["OFFSET"]:g}, expected 0 at the start')
        if not outputs_on and int(state[n]['SW2R'] or 0) & SW2_OUTPUT_ON:
            bad.append(f'V{n} output is ON but this is an outputs-off run (W1)')
    lo = ped + amp * w.min(); hi = ped + amp * w.max()
    if lo < 0 or hi > LIMIT:
        bad.append(f'amplifier input would span {lo:.0f}..{hi:.0f}, outside 0..{LIMIT:.0f}')
    return bad, state


def stop_all(exc, state, ramp, outputs_on, dry):
    """AC first (and wait for it), then the pedestal ramps down, then switches back."""
    print('\n  stopping:')
    # W0 (2026-11-03): ArbitraryLoop.stop() hung on "awgsendwaveform RPC error = 5" and never returned,
    # so the pedestal was left up. Each stop now runs in a daemon thread with a 10 s limit; a hung stop is
    # reported and abandoned (run awg_reclaim.py afterwards), and the pedestal only drops once EXCMON
    # confirms no AC on V2..V4.
    import threading
    hung = []
    for e in exc:
        def _stop(e=e):
            try:
                e.keep_running = False
                if hasattr(e, 'components'):    # built-in Excitation: 0.5 s gain ramp to 0, then stop + free the slot
                    e.stop(ramptime=0.5, wait=True)
                else:
                    e.stop(ramptime=0)          # ArbitraryLoop: joins the thread, aborts and closes the stream
            except Exception as err:
                print(f'    ! stop: {err}')
        th = threading.Thread(target=_stop, daemon=True)
        th.start()
        th.join(10.0)
        if th.is_alive():
            hung.append(getattr(e, 'chan', '?'))
    if hung:
        print(f'    ! stop did not return within 10 s on {hung}: abandoned. Run awg_reclaim.py as its own process.')
    if exc and not dry:
        quiet_since, t0 = None, time.time()
        while time.time() - t0 < 15.0:         # EXCMON is a 16 Hz monitor: require 3 s of continuous zero
            ex = {n: caget(f'{PREFIX}_V{n}_EXCMON') or 0.0 for n in ELECTRODES}
            if all(abs(v) < 1.0 for v in ex.values()):
                quiet_since = quiet_since or time.time()
                if time.time() - quiet_since >= 3.0:
                    break
            else:
                quiet_since = None
            time.sleep(0.1)
        else:
            print(f'    ! EXCMON still nonzero {ex}: AC may be live. Pedestal LEFT UP (it must outlive the AC).\n'
                  f'      Run awg_reclaim.py, check EXCMON is 0, then set V2..V4_OFFSET 0 by hand.')
            return
    if exc:
        time.sleep(1.0)
    for n in ELECTRODES:
        put(f'{PREFIX}_V{n}_OFFSET', 0.0, dry)
    if not dry:
        time.sleep(ramp + 1.0)
    for n in ELECTRODES:
        t0 = state[n]['TRAMP']
        if t0 is not None:
            put(f'{PREFIX}_V{n}_TRAMP', t0, dry)
        if outputs_on:
            cur = int(caget(f'{PREFIX}_V{n}_SW2R') or 0) if not dry else int(state[n]['SW2R'] or 0) | SW2_OUTPUT_ON
            want = (cur & ~SW2_OUTPUT_ON) | (int(state[n]['SW2R'] or 0) & SW2_OUTPUT_ON)
            if want != cur:
                put(f'{PREFIX}_V{n}_SW2S', want, dry)
    if not dry:
        time.sleep(1.0)
        left = {n: caget(f'{PREFIX}_V{n}_OFFSET') for n in ELECTRODES}
        bad = {n: v for n, v in left.items() if abs(v or 0) > 1}
        print(f'  ! OFFSET not 0: {bad}' if bad else '  offsets confirmed 0; TRAMP and switches restored.')


def fetch_dq(gps_a, gps_b, out_path):
    import nds2
    chans = [f'{PREFIX}_V{n}_OUT_DQ' for n in ELECTRODES]
    for attempt in range(4):
        try:
            conn = nds2.connection('cymac1', 8088)
            conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')
            bufs = conn.fetch(int(gps_a), int(np.ceil(gps_b)), chans)
            d = {'gps0': float(bufs[0].gps_seconds) + 1e-9 * bufs[0].gps_nanoseconds,
                 'fs': float(bufs[0].channel.sample_rate)}
            for b in bufs:
                n = int(b.channel.name.split('_V')[1].split('_')[0])
                d[f'V{n}'] = np.array(b.data, float)
            np.savez(out_path, **d)
            print(f'  saved {out_path} (FE {int(gps_a)}..{int(np.ceil(gps_b))})')
            return True
        except Exception as err:
            print(f'  NDS fetch attempt {attempt + 1}: {err}; retry in 15 s')
            time.sleep(15)
    print(f'  ! OUT_DQ not saved. Fetch {chans} FE {int(gps_a)}..{int(np.ceil(gps_b))} by hand.')
    return False


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--wave', required=True, choices=sorted(waveforms.WAVES) + sorted(BUILTIN),
                   help='streamed sample arrays (waveforms.py) or AWG built-ins: ' + '; '.join(f'{k}: {v[1]}' for k, v in BUILTIN.items()))
    p.add_argument('--amp', type=float, required=True, help='peak AC counts per electrode')
    p.add_argument('--pedestal', type=float, required=True, help='DC counts on V{n}_OFFSET')
    p.add_argument('--ramp', type=float, default=3.0, help='pedestal ramp, s (V{n}_TRAMP)')
    p.add_argument('--lead', type=float, default=12.0,
                   help='s from arming to the shared start; must exceed SIStr_LEADTIME (7 s)')
    p.add_argument('--outputs-on', action='store_true', help='W2: turn V2..V4 outputs on (electrodes driven)')
    p.add_argument('--out', default=os.path.expanduser('~/waveform_runs'), help='parent dir for run folders')
    p.add_argument('--nds-lag', type=float, default=30.0)
    p.add_argument('--clock', choices=('fe', 'local'), default='fe',
                   help='frame of the shared start time. fe = Y1:DAQ-DC0_GPS, which the old Excitation route '
                        'needed (2026-08-28); whether the SIStr stream route needs the same is untested: W0')
    p.add_argument('--live', action='store_true')
    a = p.parse_args()
    dry = not a.live

    builtin = a.wave in BUILTIN
    if builtin:
        dur = BUILTIN[a.wave][0]
        t, w = np.zeros(1), np.array([[-1.0, 1.0]] * 3)   # range check only: peak |AC| = amp
    else:
        t, w = waveforms.make(a.wave)
        dur = t[-1] + 1 / waveforms.FS
    print(('LIVE' if a.live else 'DRY RUN (add --live)') + f'  {a.wave}: {dur:.1f} s, {t.size} samples/ch, '
          f'amp {a.amp:g}, pedestal {a.pedestal:g}, outputs {"ON (W2)" if a.outputs_on else "stay OFF (W1)"}')
    print(f'  amplifier input range {a.pedestal + a.amp * w.min():.0f}..{a.pedestal + a.amp * w.max():.0f} counts')
    if caget is None:
        sys.exit('! pyepics not importable')
    bad, state = checks(a.amp, a.pedestal, w, a.outputs_on)
    for n in ELECTRODES:
        s = state[n]
        print(f'  V{n}: GAIN {s["GAIN"]}  OFFSET {s["OFFSET"]}  TRAMP {s["TRAMP"]}  SW1R {s["SW1R"]}  SW2R {s["SW2R"]}')
    if bad:
        print('! refusing:\n    ' + '\n    '.join(bad))
        return 1

    run_dir = os.path.join(a.out, f'{a.wave}_{int(time.time())}')
    exc = []
    try:
        print('\n  setup:')
        for n in ELECTRODES:
            put(f'{PREFIX}_V{n}_TRAMP', a.ramp, dry)
        if a.outputs_on:
            for n in ELECTRODES:
                put(f'{PREFIX}_V{n}_SW2S', int(state[n]['SW2R'] or 0) | SW2_OUTPUT_ON, dry)
        for n in ELECTRODES:                      # back to back: the three ramps start together
            put(f'{PREFIX}_V{n}_OFFSET', a.pedestal, dry)
        if dry:
            print(f'\n  [dry] would wait {a.ramp + 1:.0f} s, arm {len(ELECTRODES)} {"built-in excitations" if builtin else "ArbitraryLoop streams"} '
                  f'at {a.clock} GPS now + {a.lead:g} s, play {dur:.1f} s, then stop and ramp down:')
            return 0                              # the finally block prints the stop sequence
        time.sleep(a.ramp + 1.0)
        os.makedirs(run_dir, exist_ok=True)
        off = fe_gps() - local_gps()
        print(f'\n  front-end clock minus worker2 clock: {off:+.1f} s')
        if abs(off) > 5:
            print('  ! the clocks differ by more than 5 s. libSIStr paces on the worker2 clock, so with --clock fe the\n'
                  '    stream may wait |offset| s before sending, and with --clock local the front end may see the data\n'
                  '    as late. W0 decides which works; if nothing plays, Ctrl-C (the stop sequence still runs).')
        now = fe_gps() if a.clock == 'fe' else local_gps()
        start = float(np.ceil(now + a.lead))      # ArbitraryLoop takes an integer GPS second
        print(f'\n  shared start GPS {start:.0f} ({a.clock} clock; FE now {fe_gps():.1f}, local now {local_gps():.1f})')
        if builtin:
            exc = builtin_excitations(a.wave, a.amp, start)
        else:
            for k, n in enumerate(ELECTRODES):
                exc.append(make_excitation(f'{PREFIX}_V{n}_EXC', a.amp * w[k], start))
        for e in exc:
            e.start(ramptime=0, wait=False)
        if a.clock == 'local':                    # the scorer and the NDS fetch work in the FE frame
            start = start + (fe_gps() - local_gps())
        np.savez(os.path.join(run_dir, 'command.npz'), name=a.wave, builtin=builtin, duration=dur, fs=waveforms.FS, t=t, w=w,
                 amp=a.amp, pedestal=a.pedestal, start_gps=start, outputs_on=a.outputs_on,
                 host_time_armed=time.time())
        print(f'  armed; playing {dur:.1f} s ...')
        while fe_gps() < start + dur + 1.0:
            time.sleep(0.5)
        print(f'  waveform done at FE GPS {fe_gps():.0f}')
    except KeyboardInterrupt:
        print('\n  interrupted')
    finally:
        stop_all(exc, state, a.ramp, a.outputs_on, dry)
        try:
            import awg
            awg.awg_cleanup()
        except Exception:
            pass
    if dry or not os.path.exists(os.path.join(run_dir, 'command.npz')):
        return 0
    print(f'\n  waiting {a.nds_lag:g} s for NDS frames ...')
    time.sleep(a.nds_lag)
    fetch_dq(start - 3, start + dur + 3, os.path.join(run_dir, 'out_dq.npz'))
    print(f'\n  run folder: {run_dir}\n  score: python3 {"builtin_check.py" if builtin else "waveform_check.py"} {run_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
