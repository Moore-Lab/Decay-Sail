#!/usr/bin/env python3
"""Three-phase stator drive via the front-end oscillator and DRVMTRX.

THE drive as of 2026-09-08, replacing the AWG route entirely.

The y1rds model was changed that evening: the hardwired (sin, cos, -sin, -cos)
fan-out -- inherited from four side posts in quadrature -- was replaced with
Mux -> DRVMTRX (cdsRampMuxMatrix 2x4) -> Demux. The matrix mixes the
oscillator's two quadratures into arbitrary per-electrode phase, so a genuine
three-phase field comes straight from the front end over plain EPICS.

Verified at DRV_FREQ 0.32 Hz, gains 2000, outputs disabled:
    V2 (A) 2000.0 counts,    0.00 deg
    V4 (B) 2000.0 counts, -120.00 deg
    V3 (C) 2000.0 counts, +120.00 deg
    V1     0.0 -- silent, as the matrix specifies
Amplitudes to five significant figures, phases to the hundredth of a degree.

WHAT THIS MAKES UNNECESSARY -- all of it existed to work around the missing
matrix, and none of it applies here:
  * AWG arming (intermittent and never explained), slot leaks, awg_reclaim.py
  * the front-end-vs-true-GPS clock frame trap
  * stator_chirp.py's stepped phase-continuous sweep -- DRV_FREQ moved with
    DRV_TRAMP is phase-continuous natively, which is what sweep_oscillator.py
    always relied on
  * awg.SweptSine's restart=sweeptime looping bug

WHAT STILL APPLIES:

  * THE DC PEDESTAL IS STILL REQUIRED. The oscillator swings +/-amp about zero,
    and the HV amp input must stay POSITIVE within 0-2 V. So V{n}_OFFSET = amp,
    giving a commanded swing of 0 -> 2*amp counts. 12800 counts = 2.1 V at VIN
    and V{n}_LIMIT is 12800, so amp = 6400 exactly fills the input range and is
    the maximum. The matrix replaced the PHASING, not the pedestal.
  * Rotor speed = f_elec / 8 (m=8 stator). --felec states the electrical
    frequency; -f states the rotor frequency.
  * The amp maps any input DC to its 0 V output, so the pedestal never appears
    at the electrode -- it exists purely to keep the input in range.

COMMISSIONING FINDINGS, all three of which this script enforces:

  1. THE MATRIX IS GATED BY EACH MODULE'S SW1 INPUT BIT. The matrix feeds
     Sum*[2], upstream of the filter module, so the input switch blocks it.
     V1/V2 were dead at SW1R=8 while V3/V4 worked at 12. All four need bit 4.
  2. THAT SAME INPUT ALSO CARRIES LES/MON (V1<-LES_PIT, V2<-LES_YAW,
     V3<-LES_SUM, V4<-MON). The inputs must be ON for the matrix, so isolate
     each source at ITS OWN OUTPUT SWITCH (SW2R 512) and leave its gain at 1.0.
     Preferred over zeroing the gain: the switch is boolean and unambiguous in
     SW2R, the gain is a calibration value worth keeping, and gain changes are
     ramped over TRAMP while the switch acts in one sample. Sensing is
     unaffected either way -- LES_*_IN1_DQ records upstream of both.
  3. THE PEDESTAL MUST OUTLIVE THE AC, ON EVERY EXIT PATH. DRV_SINGAIN/COSGAIN
     are RAMPED over DRV_TRAMP, so a caput returning does not mean the AC has
     stopped. Dropping V{n}_OFFSET straight after commanding the gains to zero
     leaves the amp input NEGATIVE for up to DRV_TRAMP seconds. ramp_down()
     is the only correct order and every exit -- normal, Ctrl-C, exception,
     and the stop subcommand -- goes through it.

Nothing touches hardware without --live.
"""

import argparse
import math
import sys
import time

import numpy as np

try:
    from epics import caget, caput
except ImportError:
    caget = caput = None

PREFIX = 'Y1:RDS-OUTS'
MTRX = f'{PREFIX}_DRVMTRX'
M_DRIVE = 8
PHASE_ELECTRODES = (2, 4, 3)          # A, B, C -- confirmed 2026-08-24
PHASE_NAMES = ('A', 'B', 'C')
SW1_INPUT_ON = 4
SW2_OUTPUT_ON = 1024
MAX_AMP = 6400.0                      # amp + pedestal = 12800 = V{n}_LIMIT
VOLTS_PER_COUNT = 0.0134

# Matrix rows are ELECTRODE ORDER V1..V4; columns are (sin, cos).
# For a waveform cos(wt + phi):  cos coeff = cos(phi),  sin coeff = -sin(phi).
# V1 off; V2 = phase A (0 deg); V3 = phase C (-240); V4 = phase B (-120).
# NOTE rows 3 and 4 are NOT in phase order -- V3 carries C, V4 carries B.
S3 = math.sqrt(3) / 2                 # 0.8660
MATRIX_FWD = {1: (0.0, 0.0), 2: (0.0, 1.0), 3: (-S3, -0.5), 4: (S3, -0.5)}
MATRIX_REV = {1: (0.0, 0.0), 2: (0.0, 1.0), 3: (S3, -0.5), 4: (-S3, -0.5)}

# What is summed into each electrode ahead of its filter module.
INPUT_SOURCE = {1: 'LES_PIT', 2: 'LES_YAW', 3: 'LES_SUM', 4: 'MON'}


def put(pv, val, dry, wait=True):
    if dry:
        print(f'    [dry] {pv} <- {val:g}')
        return
    caput(pv, float(val), wait=wait, timeout=3.0)


def load_matrix(reverse, dry, tramp=2.0):
    """Stage SETTING_* then trigger LOAD_MATRIX.

    Writing DRVMTRX_{r}_{c} directly does NOTHING -- measured 2026-09-08. Values
    take effect only via SETTING_* + LOAD_MATRIX, which ramps all eight elements
    TOGETHER over TRAMP, so the phasing never passes through an inconsistent
    intermediate state.
    """
    m = MATRIX_REV if reverse else MATRIX_FWD
    print(f'\n  loading matrix ({"REVERSE" if reverse else "forward"}), '
          f'TRAMP {tramp:g} s:')
    put(f'{MTRX}_TRAMP', tramp, dry)
    for row, (s, c) in sorted(m.items()):
        print(f'    V{row}:  sin {s:+.4f}   cos {c:+.4f}')
        put(f'{MTRX}_SETTING_{row}_1', s, dry)
        put(f'{MTRX}_SETTING_{row}_2', c, dry)
    put(f'{MTRX}_LOAD_MATRIX', 1, dry)
    if dry:
        return True
    time.sleep(tramp + 2.5)
    ok = True
    for row, (s, c) in sorted(m.items()):
        gs = caget(f'{MTRX}_{row}_1')
        gc = caget(f'{MTRX}_{row}_2')
        if abs(gs - s) > 1e-3 or abs(gc - c) > 1e-3:
            print(f'    ! V{row} readback {gs:+.4f}/{gc:+.4f} != '
                  f'{s:+.4f}/{c:+.4f}')
            ok = False
    print('    matrix verified.' if ok else '    ! MATRIX DID NOT LOAD')
    return ok


def check_isolation():
    """LES/MON must not reach the electrodes.

    The matrix needs V1..V4 inputs ON, and that same node carries LES/MON. So
    isolation has to happen at the SOURCE: either its output switch off, or its
    gain zero. Checks both.
    """
    bad = []
    for n, src in INPUT_SOURCE.items():
        g = caget(f'Y1:RDS-{src}_GAIN')
        sw2 = caget(f'Y1:RDS-{src}_SW2R')
        if g is None or sw2 is None:
            continue
        live = abs(g) > 1e-6 and (int(sw2) & SW2_OUTPUT_ON)
        if live:
            bad.append(f'V{n} <- {src} (GAIN {g:g}, output ON)')
    if bad:
        print('! LES/MON is NOT isolated from the drive:\n    ' +
              '\n    '.join(bad))
        print('  Switch that module\'s OUTPUT off, or zero its GAIN. Sensing is\n'
              '  unaffected -- LES_*_IN1_DQ records upstream of both.')
        return False
    return True


def check_inputs():
    """All four electrode inputs must be ON or the matrix cannot reach them."""
    off = [n for n in (1, 2, 3, 4)
           if not int(caget(f'{PREFIX}_V{n}_SW1R') or 0) & SW1_INPUT_ON]
    if off:
        print(f'! electrode input switch OFF on: ' +
              ', '.join(f'V{n}' for n in off) +
              '\n  The matrix feeds Sum*[2], upstream of the filter module, so the\n'
              '  input switch blocks it. Set SW1S to include bit 4.')
        return False
    return True


def ramp_down(drvtramp, sw2_before=None):
    """Stop the drive in the ONLY safe order.

    THE PEDESTAL MUST OUTLIVE THE AC. The HV amp input has to stay positive, and
    V{n}_OFFSET is the only thing holding it there. DRV_SINGAIN/COSGAIN are
    RAMPED over DRV_TRAMP, so caput returning does NOT mean the AC has stopped --
    zeroing the offsets straight afterwards can leave the input negative for up
    to DRV_TRAMP seconds. So: gains to zero, wait the ramp out, confirm the
    readbacks, DRVON off, and only then drop the pedestal.
    """
    print('\n  ramping down:')
    caput(f'{PREFIX}_DRV_SINGAIN', 0, wait=True, timeout=3.0)
    caput(f'{PREFIX}_DRV_COSGAIN', 0, wait=True, timeout=3.0)
    wait = max(drvtramp, 0.0) + 3.0
    print(f'    gains commanded to 0 -- waiting {wait:.0f} s for the ramp '
          f'BEFORE touching the pedestal')
    time.sleep(wait)

    g = [caget(f'{PREFIX}_DRV_SINGAIN'), caget(f'{PREFIX}_DRV_COSGAIN')]
    if any(abs(v or 0) > 1e-6 for v in g):
        print(f'    ! gains still reading {g} -- waiting {wait:.0f} s more')
        time.sleep(wait)
        g = [caget(f'{PREFIX}_DRV_SINGAIN'), caget(f'{PREFIX}_DRV_COSGAIN')]
    print(f'    gains now {g[0]:g} / {g[1]:g}')

    caput(f'{PREFIX}_DRVON', 0, wait=True, timeout=3.0)
    time.sleep(1.0)

    print('    AC down; dropping the pedestal.')
    for n in (1, 2, 3, 4):
        caput(f'{PREFIX}_V{n}_OFFSET', 0, wait=True, timeout=3.0)

    if sw2_before:
        print('    restoring output switches to their pre-run state.')
        for n, sw2 in sorted(sw2_before.items()):
            caput(f'{PREFIX}_V{n}_SW2S', sw2, wait=True, timeout=3.0)

    time.sleep(2)
    left = {n: caget(f'{PREFIX}_V{n}_OFFSET') for n in (1, 2, 3, 4)}
    bad = {n: v for n, v in left.items() if abs(v or 0) > 1}
    print(f'  ! offsets NOT zero: {bad}' if bad
          else '  all offsets confirmed at 0.')
    if sw2_before:
        still = {n: int(caget(f'{PREFIX}_V{n}_SW2R') or 0) for n in (1, 2, 3, 4)}
        on = [n for n, v in still.items() if v & SW2_OUTPUT_ON]
        print(f'  ! outputs still ENABLED on {on}' if on
              else '  all outputs confirmed off.')


def verify(f_elec, gps_a, gps_b, lag=25.0):
    """Fit V{2,4,3}_OUT_DQ over an EXPLICIT window recorded during the drive.

    Pass = -120.00 deg spacing, matched amplitudes. The window is passed in
    rather than guessed backwards from 'now' -- anchoring to the clock at call
    time lands partly in the ramp-down and fits a decaying amplitude.
    """
    import nds2
    span = gps_b - gps_a
    if span < 30:
        print(f'\n  ! verify window is only {span:.0f} s -- too short to fit '
              f'{f_elec:g} Hz cleanly. Skipping.')
        return
    print(f'\n  verify: {span:.0f} s window inside the drive '
          f'[{gps_a} - {gps_b}], waiting {lag:.0f} s for frames...')
    time.sleep(lag)
    a, b = int(gps_a), int(gps_b)
    try:
        conn = nds2.connection('cymac1', 8088)
        conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')
        d = {}
        for buf in conn.fetch(a, b, [f'{PREFIX}_V{n}_OUT_DQ' for n in (1, 2, 3, 4)]):
            n = int(buf.channel.name.split('_V')[1].split('_')[0])
            d[n] = np.array(buf.data, float)
    except Exception as err:
        print(f'  ! verify fetch failed: {err}')
        return
    missing = [n for n in PHASE_ELECTRODES if n not in d]
    if missing:
        print(f'  ! no data for V{missing} -- cannot verify')
        return
    fs = 1024.0
    print(f'\n  {"":6} {"amp":>9} {"dc":>9} {"phase":>10} {"rel":>10} {"want":>8}')
    ref = None
    for name, n, want in zip(PHASE_NAMES, PHASE_ELECTRODES, (0.0, -120.0, 120.0)):
        x = d[n]
        t = np.arange(len(x)) / fs
        w = 2 * math.pi * f_elec
        M = np.column_stack([np.cos(w * t), np.sin(w * t), np.ones_like(t)])
        A, B, C = np.linalg.lstsq(M, x, rcond=None)[0]
        amp = math.hypot(A, B)
        ph = math.degrees(math.atan2(-B, A))
        if ref is None:
            ref = ph
        rel = (ph - ref + 180) % 360 - 180
        print(f'  {name} V{n} {amp:9.1f} {C:9.1f} {ph:+9.2f}d {rel:+9.2f}d '
              f'{want:+7.1f}d')
    if 1 in d:
        print(f'  V1 (CTR) rms {d[1].std():.1f}  (should be ~0)')


def main():
    p = argparse.ArgumentParser(
        description='Three-phase stator drive via the oscillator + DRVMTRX.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('cmd', choices=('status', 'phasing', 'hold', 'sweep', 'stop'))
    p.add_argument('--live', action='store_true')
    p.add_argument('--felec', type=float, default=None,
                   help='ELECTRICAL frequency, Hz. Rotor = this / 8.')
    p.add_argument('-f', '--freq', type=float, default=None,
                   help='ROTOR frequency, Hz (f_elec = 8x this)')
    p.add_argument('--to-felec', type=float, default=None,
                   help='sweep: final electrical frequency')
    p.add_argument('--amp', type=float, default=2000.0,
                   help=f'oscillator gain = electrode amplitude in counts '
                        f'(max {MAX_AMP:.0f}; pedestal is set equal to it)')
    p.add_argument('--duration', type=float, default=120.0)
    p.add_argument('--reverse', action='store_true',
                   help='reverse rotation (swaps the B/C matrix rows)')
    p.add_argument('--mtramp', type=float, default=2.0,
                   help='matrix ramp time, s (default 2)')
    p.add_argument('--drvtramp', type=float, default=5.0,
                   help='oscillator frequency ramp time, s. NONZERO keeps a '
                        'frequency change PHASE-CONTINUOUS -- this is what makes '
                        'sweeps safe. Default 5.')
    p.add_argument('--enable-outputs', action='store_true',
                   help='set SW2 output bit so the drive actually reaches the '
                        'chamber. WITHOUT THIS NOTHING IS DRIVEN -- useful for '
                        'dry commissioning.')
    p.add_argument('--verify', action='store_true')
    args = p.parse_args()

    if caget is None:
        print('! pyepics not importable.')
        return 1
    dry = not args.live

    f_elec = args.felec if args.felec is not None else (
        M_DRIVE * args.freq if args.freq is not None else None)

    if args.cmd == 'status':
        print('  matrix (row = electrode, col = sin/cos):')
        for r in (1, 2, 3, 4):
            print(f'    V{r}  {caget(f"{MTRX}_{r}_1"):+9.4f}  '
                  f'{caget(f"{MTRX}_{r}_2"):+9.4f}')
        print(f'    TRAMP {caget(f"{MTRX}_TRAMP"):g}')
        print(f'\n  oscillator: DRVON {caget(f"{PREFIX}_DRVON")}  '
              f'FREQ {caget(f"{PREFIX}_DRV_FREQ"):g}  '
              f'SIN {caget(f"{PREFIX}_DRV_SINGAIN"):g}  '
              f'COS {caget(f"{PREFIX}_DRV_COSGAIN"):g}  '
              f'TRAMP {caget(f"{PREFIX}_DRV_TRAMP"):g}')
        print('\n  electrodes:')
        for n in (1, 2, 3, 4):
            sw2 = int(caget(f'{PREFIX}_V{n}_SW2R') or 0)
            print(f'    V{n}  OFFSET {caget(f"{PREFIX}_V{n}_OFFSET"):8.1f}  '
                  f'SW1R {caget(f"{PREFIX}_V{n}_SW1R"):.0f}  SW2R {sw2}  '
                  f'output {"ON" if sw2 & SW2_OUTPUT_ON else "off"}')
        print()
        ok_in, ok_iso = check_inputs(), check_isolation()
        if ok_in:
            print('  OK  all four electrode inputs are on (matrix can reach them)')
        if ok_iso:
            print('  OK  LES/MON isolated -- nothing but the matrix reaches the drive')
        return 0

    if args.cmd == 'stop':
        if dry:
            print('  [dry] would ramp gains to 0, wait out DRV_TRAMP, DRVON off,'
                  '\n        then zero offsets and switch all outputs off.')
            return 0
        # Same ordering rule as a normal run: the pedestal outlives the AC.
        # Waits on the LIVE DRV_TRAMP, not the argparse default, since a stop
        # may well be cleaning up after some other process's settings.
        live_tramp = float(caget(f'{PREFIX}_DRV_TRAMP') or 0.0)
        print(f'  stopping (live DRV_TRAMP {live_tramp:g} s)')
        # A stop that leaves the electrodes connected is not a stop.
        ramp_down(live_tramp, {n: 0 for n in (1, 2, 3, 4)})
        return 0

    if args.cmd == 'phasing':
        return 0 if load_matrix(args.reverse, dry, args.mtramp) else 1

    # hold / sweep
    if f_elec is None:
        print('! give --felec (electrical) or -f (rotor)')
        return 1
    if args.amp > MAX_AMP:
        print(f'! --amp {args.amp:.0f} exceeds {MAX_AMP:.0f}. amp + pedestal '
              f'must stay within V{{n}}_LIMIT = 12800 counts (0-2.1 V at the '
              f'amp input, which must stay positive).')
        return 1
    if args.amp <= 0:
        print(f'! --amp must be positive, got {args.amp:g}. The pedestal is set '
              f'equal to it; a zero or negative amplitude has no meaning here.')
        return 1
    if args.drvtramp < 0:
        print(f'! --drvtramp must be >= 0, got {args.drvtramp:g}.')
        return 1
    if args.cmd == 'sweep' and args.drvtramp <= 0:
        print('! sweep needs --drvtramp > 0. It is both the per-step dwell and '
              'what makes each frequency step phase-continuous; at 0 the steps '
              'are discontinuous and the step count divides by zero.')
        return 1

    print('=' * 70)
    print(f'  {args.cmd}   f_elec {f_elec:.4f} Hz   rotor {f_elec / M_DRIVE:.5f} Hz'
          + (f'  ->  {args.to_felec:.4f} Hz' if args.cmd == 'sweep' and
             args.to_felec else ''))
    print(f'  amplitude {args.amp:.0f} counts, pedestal {args.amp:.0f} '
          f'(peak {2 * args.amp:.0f} ~ {2 * args.amp * VOLTS_PER_COUNT:.0f} V)')
    print(f'  outputs {"ENABLED" if args.enable_outputs else "OFF -- nothing reaches the chamber"}')
    print('=' * 70)

    if not check_inputs() or not check_isolation():
        return 1
    if not load_matrix(args.reverse, dry, args.mtramp):
        return 1

    if args.cmd == 'sweep' and args.to_felec is None:
        print('! sweep needs --to-felec')
        return 1

    # Record what the output switches were BEFORE we touch them, so ramp_down
    # can put them back. --enable-outputs leaving the electrodes live after the
    # run is how LES ends up on the chamber the next time someone raises a gain.
    sw2_before = {}
    if args.enable_outputs and not dry:
        sw2_before = {n: int(caget(f'{PREFIX}_V{n}_SW2R') or 0)
                      for n in (1, 2, 3, 4)}

    print('\n  bringing up the drive:')
    for n in (1, 2, 3, 4):
        # PEDESTAL FIRST, AC SECOND -- the input must be positive before there
        # is any AC to make it negative. Pedestal only where there is AC to
        # keep positive: V1's matrix row is zero, so it needs none, and the amp
        # blocks DC anyway so a pedestal there would reach the electrode as 0 V.
        put(f'{PREFIX}_V{n}_OFFSET', args.amp if n in PHASE_ELECTRODES else 0, dry)
        if args.enable_outputs:
            sw2 = int(caget(f'{PREFIX}_V{n}_SW2R') or 0) if not dry else 0
            if not sw2 & SW2_OUTPUT_ON:
                put(f'{PREFIX}_V{n}_SW2S', sw2 | SW2_OUTPUT_ON, dry)
    put(f'{PREFIX}_DRV_TRAMP', args.drvtramp, dry)
    put(f'{PREFIX}_DRV_FREQ', f_elec, dry)
    put(f'{PREFIX}_DRV_SINGAIN', args.amp, dry)
    put(f'{PREFIX}_DRV_COSGAIN', args.amp, dry)
    put(f'{PREFIX}_DRVON', 1, dry)

    if dry:
        print(f'\n  [dry] would run {args.duration:.0f} s.')
        return 0

    # Window for --verify, in the FRONT END's frame (which is what NDS wants).
    # Opened after the gains have finished ramping in, closed before ramp-down,
    # so the fit sees steady-state drive only.
    time.sleep(args.drvtramp + 2.0)
    gps_a = gps_b = None
    verify_f = f_elec

    try:
        if args.cmd == 'sweep':
            n_steps = max(2, int(args.duration / args.drvtramp))
            print(f'\n  sweeping in {n_steps} steps of {args.drvtramp:.0f} s '
                  f'(DRV_TRAMP keeps each step phase-continuous)')
            for i, f in enumerate(np.linspace(f_elec, args.to_felec, n_steps)):
                caput(f'{PREFIX}_DRV_FREQ', float(f), wait=True, timeout=3.0)
                if i % max(1, n_steps // 10) == 0:
                    print(f'    f_elec {f:.4f} Hz  (rotor {f / M_DRIVE:.5f})')
                time.sleep(args.drvtramp)
            if args.verify:
                # A single-frequency fit across a sweep is meaningless, so dwell
                # at the final frequency and verify THAT.
                verify_f = args.to_felec
                print(f'\n  --verify: dwelling 120 s at the final '
                      f'{verify_f:.4f} Hz so there is something to fit')
                gps_a = int(caget('Y1:DAQ-DC0_GPS'))
                time.sleep(120)
                gps_b = int(caget('Y1:DAQ-DC0_GPS'))
        else:
            print(f'\n  holding {args.duration:.0f} s...')
            gps_a = int(caget('Y1:DAQ-DC0_GPS'))
            time.sleep(args.duration)
            gps_b = int(caget('Y1:DAQ-DC0_GPS'))
    except KeyboardInterrupt:
        print('\n  interrupted.')
        if gps_a is not None and gps_b is None:
            gps_b = int(caget('Y1:DAQ-DC0_GPS'))
    finally:
        ramp_down(args.drvtramp, sw2_before)

    if args.verify:
        if gps_a is None or gps_b is None:
            print('\n  ! no steady-state window was recorded -- nothing to verify')
        else:
            # Trim the edges: the window boundaries sit next to gain ramps.
            verify(verify_f, gps_a + 5, gps_b - 5)
    return 0


if __name__ == '__main__':
    sys.exit(main())
