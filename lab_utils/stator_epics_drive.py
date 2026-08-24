#!/usr/bin/env python3
"""
EPICS-only three-phase drive for the rev G under-rotor stator.

Written to answer one question first: DOES THE STATOR DO ANYTHING AT ALL?

Everything here goes through slow EPICS records (_OFFSET, _TRAMP, DRVON) and
nothing else. No AWG, no diag, no test points. That is a deliberate choice:

  * the command values are themselves archived EPICS records, so the stimulus
    sits next to the V{n}_OUT_DQ response in the same NDS fetch;
  * it sidesteps the AWG slot limit (MAX_NUM_AWG = 9), the test-point grant,
    and -- most importantly -- the cymac GPS clock offset (measured 7630 s
    ahead of true GPS on 2026-08-21, and drifting). An AWG excitation needs an
    absolute GPS start time to make three phases coherent; if that timestamp is
    interpreted in the wrong clock frame the phases are silently randomised.
    Writing offsets from Python has no absolute-time dependence at all.

The cost is bandwidth. These are software-timed writes, so the drive is good to
a few Hz electrical and no more (see --rate). Since rotor speed = f_elec / 8:

    f_mech      f_elec     samples/cycle at 200 Hz     verdict
    detent      DC         --                          ideal, pure caput
    0.05 Hz     0.4 Hz     500                         comfortable
    0.5  Hz     4   Hz     50                          fine
    2    Hz     16  Hz     12                          coarse
    10   Hz     80  Hz     2.5                         not possible

Every first-article test is DC or a fixed frequency below capture, so this
covers the whole near-term programme. AWG only becomes necessary for real speed.

    status      read back every channel this script touches
    calibrate   DC staircase on one electrode to find the amp's saturation
    detent      first-article test 3: DC detent / 15 deg-per-step
    hold        fixed-frequency three-phase
    spinup      catch at rest, ramp to a target frequency
    stop        ramp down and zero everything

Nothing touches hardware without --live.

References: stator_flex/flex_spec.md, CLAUDE.md ("THE STATOR").
"""

import argparse
import math
import signal
import sys
import time

import numpy as np

try:
    from epics import caget, caput
except ImportError:          # dry run still works without pyepics
    caget = caput = None


# ===========================================================================
# ELECTRODE MAP -- CONFIRMED 2026-08-24 by continuity check at the terminals
# ===========================================================================
# V1 IS THE CENTRE ELECTRODE. Established conclusively at the chamber opening on
# 2026-08-24. This supersedes the earlier guess-and-corroborate reasoning, and
# stator_drive.py (which had CTR = V4) has been corrected to match.
#
# The old assignment was never a wiring record: it came from reading
# flex_spec.md's terminal table (15/105/195/285 deg -> A/B/C/CTR) and assigning
# V1..V4 in order. The spec names terminal AZIMUTHS and never says which V{n}
# is landed on which terminal. Do not re-derive the map that way.
#
# Measured, all four terminals: going CLOCKWISE (viewed from above / the rotor
# side, which is the face the pads are on) they read  V1, V3, V4, V2.
#
# The board's own convention, from generate_flex_revG.py (NOT from flex_spec.md
# prose, which does not state a sign):
#     pol()  -> (cos, sin)                      => azimuth is CCW-POSITIVE
#     SEC_CTR = [7.5 + 15*k];  NET = PHASE[k%3] => sectors run A,B,C,A,B,C...
#                                                  with INCREASING azimuth
#     PAD_AZ  = A 15, B 105, C 195, CTR 285     => pads agree: A->B->C is CCW
# So going CLOCKWISE the four terminals are, by net:  CTR, C, B, A.
#
# Lining that up against the measurement:
#     V1 = CTR (285 deg)      V3 = C (195 deg)
#     V4 = B   (105 deg)      V2 = A (15 deg)
# =>  (A, B, C) = (V2, V4, V3)  -- which is the tuple below.
#
# NOTE (2, 3, 4) IS WRONG, and was wrong here until 2026-08-24. It swaps B and
# C, i.e. it is a TRANSPOSITION of the truth, not a cyclic rotation. It still
# produces a clean travelling wave -- a transposition is exactly what
# flex_spec.md means by "Reverse by swapping any two phases" -- so the drive
# would have WORKED, but it would have run BACKWARDS relative to the board's
# A->B->C sense and mislabelled every phase (commanding "B" while energising
# net C). Cyclic rotations of (2,4,3) -- (4,3,2) and (3,2,4) -- are the ones
# that are free: they add a uniform phase constant, i.e. a shift of t=0.
#
# DIRECTION, as derived above: with the tuple below, A->B->C advances
# COUNTERCLOCKWISE seen from the rotor side. One empirical check is still worth
# doing, because the whole chain rests on "clockwise" having been read off the
# board viewed from above. That assumption was CROSS-CHECKED 2026-08-24: read
# COUNTERCLOCKWISE the terminals are V1, V2, V4, V3, exactly as the derivation
# requires, so the map is settled in both directions. Still open, and the only
# end-to-end test against hardware: drive slowly at low counts and confirm the
# rotor turns CCW seen from the camera. Record the result here.
#
# Geometry, from flex_spec.md. NOTE this is NOT three big sectors at 120 deg;
# that model is wrong and produces wrong torque and direction reasoning:
#   24 sectors on a 15 deg pitch, interleaved 3-phase, 8 sectors per phase,
#   synthesising a rotating m = 8 potential. Rotor speed = f_electrical / 8.
#   15 deg pitch x m=8 = exactly 120 deg electrical per sector, so ABCABC...
#   around the ring is a uniform travelling wave by construction.
#   CTR is a disk of r = 0.58 mm PLUS a 0.08 mm in-plane trace running out
#   through the sector boundary at az 285 deg. Inside the active annulus that
#   arm is ~0.10 mm^2, about 2.9% of a phase's electrode area, and it is the
#   ONLY part of V1 with angular authority. So V1 is not perfectly symmetric:
#   a WEAK V1 detent is the feed arm, not evidence of a mis-mapping.
PHASE_ELECTRODES = (2, 4, 3)     # A, B, C -- sector phases, 8 sectors each
                                 # (2,3,4) would swap B/C -> runs reversed
CTR_ELECTRODE    = 1             # centre disk + feed arm: DC trim / charge drive

PREFIX = 'Y1:RDS-OUTS'
PHASE_PVS  = [f'{PREFIX}_V{n}_OFFSET' for n in PHASE_ELECTRODES]
PHASE_TRAMP = [f'{PREFIX}_V{n}_TRAMP' for n in PHASE_ELECTRODES]
# _OUT does NOT exist as an EPICS record -- it is a fast test point, NDS-only.
# _OUTMON is the slow readback of the module output; _INMON reads its input.
PHASE_OUT   = [f'{PREFIX}_V{n}_OUTMON' for n in PHASE_ELECTRODES]
PHASE_IN    = [f'{PREFIX}_V{n}_INMON'  for n in PHASE_ELECTRODES]
PHASE_SW1   = [f'{PREFIX}_V{n}_SW1R'   for n in PHASE_ELECTRODES]
PHASE_SW2   = [f'{PREFIX}_V{n}_SW2R'   for n in PHASE_ELECTRODES]

# cdsFilt switch-register bits (from Aaron's measure_actuator_gain_config.yml,
# verified on y1dmd -- these are RCG-generic, but y1rds is not y1dmd, so treat
# as strong prior rather than fact).
SW1_INPUT_ON  = 4        # SW1 bit 2
SW2_OUTPUT_ON = 1024     # SW2 bit 10
CTR_PV     = f'{PREFIX}_V{CTR_ELECTRODE}_OFFSET'
CTR_TRAMP  = f'{PREFIX}_V{CTR_ELECTRODE}_TRAMP'
DRVON_PV   = f'{PREFIX}_DRVON'

PHASE_NAMES = ('A', 'B', 'C')


# ===========================================================================
# CALIBRATION -- UNKNOWN. Do not invent a number here.
# ===========================================================================
# The HV amplifier tops out at about 80 V (Molly, 2026-08-21) -- an 80 V swing,
# not the 200 V the design table assumes. What is NOT known is how many DAC
# counts that corresponds to, i.e. VOLTS_PER_COUNT.
#
# stator_drive.py carries VOLTS_PER_COUNT = 0.03125 ("6400 counts -> 200 V").
# That cannot be right: it would put 6400 counts at 200 V on an amp that stops
# at 80. Driving the old 6400 DC + 6400 AC default would therefore command deep
# into saturation. Clipping is especially damaging here -- it flattens the peaks,
# which shifts the DC/AC balance, and the m=8 torque channel is precisely the one
# that depends on the product V_dc * V_ac. The drive would look correct on the
# commanded values and be both weaker and harmonically dirty.
#
# A HYPOTHESIS worth testing, not a value to trust: sweep_oscillator.py drove
# 0 -> 12800 counts on this same amplifier, and three_phase_drive.py notes the
# electrodes were "found sitting at 12000 counts". If 12800 counts is the 80 V
# ceiling then VOLTS_PER_COUNT ~ 0.00625 -- five times smaller than the
# placeholder above. `calibrate` is here to measure it rather than guess.
#
# Until it is measured this script REFUSES to print torque, capture bandwidth or
# ramp limits, because all three would be fiction. Pass --volts-per-count once
# you have measured it and the physics reporting switches on.
VOLTS_PER_COUNT = None

# Hard ceiling on the commanded peak (dc + amp). 12800 counts is the largest
# value known to have been driven on this amplifier. Not a safety limit derived
# from the hardware -- just "no further than has already been done".
MAX_TOTAL_COUNTS = 12800.0

# Conservative default until the saturation point is known.
DEFAULT_AMP = 2000.0


# ===========================================================================
# Machine constants
# ===========================================================================
M_DRIVE = 8                  # rotor speed = f_elec / M_DRIVE; also the detent count
I_KGM2  = 1.88e-11           # ASSUMED, never measured -- see apparatus_log.md
GAP_MM  = 0.37               # 0.37 = no shim (current state); 0.27 with a 0.1 mm shim

# tau at V_dc = V_ac = 100 V, from the design notes, per gap.
TAU_REF_100V = {0.27: 3.8e-12, 0.37: 1.2e-12}

TORQUE_MARGIN = 0.5

DRY_RUN = True
_DRY_STATE: dict = {}
_STOPPING = False


# ===========================================================================
# EPICS
# ===========================================================================
def put(pv, value, wait=False, echo=True):
    value = float(value)
    if DRY_RUN:
        _DRY_STATE[pv] = value
        if echo:
            print(f'    [dry-run] {pv} <- {value:.1f}')
        return
    caput(pv, value, wait=wait, timeout=2.0)


def get(pv, default=0.0, live=False):
    """Read a PV.

    Under DRY_RUN this normally answers from _DRY_STATE so a rehearsal never
    depends on the machine being up. Pass live=True for READ-ONLY diagnostics
    that must reflect the real machine.

    This bit once: `status` used the plain path, so a dry-run `status` printed
    an all-zero FICTION that looked exactly like a readback -- including false
    'SW2 = 0 has no output bit' warnings on a machine whose output switches
    were on (SW2R = 1792), and false reassurance that TRAMP was 0 when every
    channel was actually at 1.0 s. A diagnostic that invents its readings is
    worse than one that refuses to run.
    """
    if DRY_RUN and not live:
        return _DRY_STATE.get(pv, default)
    if caget is None:
        return default
    value = caget(pv)
    return default if value is None else value


def zero_all(echo=True):
    """Known safe state: every electrode this script drives goes to 0 counts."""
    for pv in PHASE_PVS:
        put(pv, 0.0, wait=True, echo=echo)
    put(CTR_PV, 0.0, wait=True, echo=echo)


def guard_tramp():
    """Force TRAMP = 0 on every driven electrode -- right HERE, wrong elsewhere.

    TRAMP is the interpolation time for a commanded setpoint change. Which way
    you want it depends entirely on WHO is generating the waveform:

      * Waveform synthesised in SOFTWARE -- what this script does, writing
        V{n}_OFFSET at --rate Hz. Every write is a commanded change, so a
        nonzero TRAMP low-passes the sinusoid into a smaller, phase-lagged,
        distorted version of itself, while the commanded values (and anything
        this script logs) still look perfect.  ==> TRAMP MUST BE 0.

      * Hardware OSCILLATOR moved between setpoints, e.g. DRV_FREQ f1 -> f2.
        A positive TRAMP gives a smooth, PHASE-CONTINUOUS modulation from f1 to
        f2 over TRAMP seconds. TRAMP = 0 makes it a discrete step with NO phase
        matching -- a phase discontinuity that kicks the rotor and breaks lock.
        ==> TRAMP MUST BE POSITIVE.

    So do not read "TRAMP = 0" off this function as a general rule. It applies
    to the electrode filter modules for as long as this script owns the
    waveform, and the previous values are restored afterwards. This function
    deliberately does not touch DRV_TRAMP -- zeroing that would break exactly
    the phase continuity an oscillator sweep depends on.

    Returns the previous values so they can be restored.
    """
    previous = {}
    for pv in list(PHASE_TRAMP) + [CTR_TRAMP]:
        previous[pv] = get(pv, 0.0)
        put(pv, 0.0, wait=True, echo=False)
    nonzero = {k: v for k, v in previous.items() if v}
    if nonzero:
        print('  TRAMP was nonzero and has been zeroed: ' +
              ', '.join(f'{k.split("_")[-2]}={v:g}s' for k, v in nonzero.items()))
    return previous


def restore_tramp(previous):
    for pv, value in previous.items():
        put(pv, value, wait=True, echo=False)


def guard_oscillator():
    """The model hardwires the DRV oscillator onto all four electrodes as
    (sin, cos, -sin, -cos) -- traced from y1rds.mdl:

        V1 = In1 + s    V2 = In2 + c    V3 = In3 - s    V4 = In4 - c

    gated by DRVON through a pair of switches that pass Constant = 0 when it is
    off. That fan-out is 2 degrees of freedom across 4 electrodes, cannot make
    120-degree phases, and would sum into whatever we write. DRVON = 0 removes it
    entirely, which also frees the centre electrode to do something independent.
    """
    if get(DRVON_PV, 0.0):
        print('  DRVON was ON -- the DRV oscillator is summed into all four '
              'electrodes.\n  Turning it off so only our offsets drive.')
        put(DRVON_PV, 0.0, wait=True, echo=False)


# ===========================================================================
# Physics -- only reports when a calibration has been supplied
# ===========================================================================
def tau_max(dc_counts, ac_counts, gap_mm=GAP_MM):
    """Peak m=8 drive torque, or None if counts->volts is unmeasured.

    The m=8 channel amplitude goes as V_dc * V_ac (NOT V^2 -- they coincide only
    at the balanced split). Keeping the product explicit is what makes --dc a
    real diagnostic: m=8 scales with V_dc, the m=16 channel does not.

    Gap interpolation is log-linear because the underlying attenuation is
    exp(-m h / r).
    """
    if VOLTS_PER_COUNT is None:
        return None
    h0, h1 = 0.27, 0.37
    t0, t1 = TAU_REF_100V[h0], TAU_REF_100V[h1]
    decay = np.log(t1 / t0) / (h1 - h0)
    tau_ref = t0 * np.exp(decay * (gap_mm - h0))
    if not (h0 <= gap_mm <= h1):
        print(f'  ! gap {gap_mm} mm is outside the documented range '
              f'[{h0}, {h1}] -- torque is extrapolated')
    v_dc = dc_counts * VOLTS_PER_COUNT
    v_ac = ac_counts * VOLTS_PER_COUNT
    return tau_ref * (v_dc * v_ac) / (100.0 * 100.0)


def f_capture_mech(tau):
    """Pull-in bandwidth, Hz mechanical. Stiffness is m*tau_max, so
    omega_lib = sqrt(m*tau_max/I). The design notes' sqrt(2*tau/I)/2pi is the
    SIDE-POST case -- that 2 is the induced dipole's 2-fold symmetry."""
    return np.sqrt(M_DRIVE * tau / I_KGM2) / (2 * np.pi)


def max_ramp_rate_mech(tau, margin=TORQUE_MARGIN):
    return margin * tau / (2 * np.pi * I_KGM2)


def banner(dc, amp):
    print('=' * 72)
    print(f'  electrodes  phases A/B/C = V{PHASE_ELECTRODES[0]}/V{PHASE_ELECTRODES[1]}'
          f'/V{PHASE_ELECTRODES[2]}   centre = V{CTR_ELECTRODE}   '
          f'(confirmed 2026-08-24 by continuity check)')
    print(f'  drive       {amp:.0f} counts AC on {dc:.0f} DC  '
          f'-> swing [{dc - amp:.0f}, {dc + amp:.0f}]   gap {GAP_MM} mm')
    if dc == 0:
        print('  ! DC pedestal is 0 -- the m=8 torque channel is OFF, only m=16 drives')

    tau = tau_max(dc, amp)
    if tau is None:
        print('  calibration  VOLTS_PER_COUNT UNMEASURED -- torque, capture and')
        print('               ramp limits cannot be computed. Run `calibrate`,')
        print('               then pass --volts-per-count to switch this on.')
        print('=' * 72)
        return None, None
    f_cap, rate = f_capture_mech(tau), max_ramp_rate_mech(tau)
    print(f'  voltage     V_dc {dc * VOLTS_PER_COUNT:.1f} V, '
          f'V_ac {amp * VOLTS_PER_COUNT:.1f} V, peak '
          f'{(dc + amp) * VOLTS_PER_COUNT:.1f} V')
    print(f'  tau_max     {tau:.2e} N*m')
    print(f'  capture     {f_cap:.4f} Hz mech   (start below this from rest)')
    print(f'  max ramp    {rate:.2e} Hz mech/s at {TORQUE_MARGIN:.0%} margin')
    print('=' * 72)
    return f_cap, rate


# ===========================================================================
# The drive loop
# ===========================================================================
def phases_rad(reverse=False):
    """A/B/C at 0 / -120 / -240 degrees. Reversing swaps B and C, which is how
    the design prescribes reversal -- structural, not a sign flip.
    (sweep_oscillator_reverse.py negated COS to reverse the OLD drive, but the
    forward script already ran COS = -GAIN, so it cancelled and drove the same
    way. There is no sign convention here left to get backwards.)"""
    order = [0.0, -4 * math.pi / 3, -2 * math.pi / 3] if reverse else \
            [0.0, -2 * math.pi / 3, -4 * math.pi / 3]
    return order


def check_amplitude(dc, amp):
    peak = dc + amp
    if peak > MAX_TOTAL_COUNTS:
        print(f'! commanded peak {peak:.0f} counts exceeds the {MAX_TOTAL_COUNTS:.0f} '
              f'count ceiling.\n  Nothing larger has been driven on this amplifier. '
              f'Raise MAX_TOTAL_COUNTS\n  deliberately if you mean it.')
        return False
    if amp < 0 or dc < 0:
        print('! negative counts -- the amplifier is unipolar.')
        return False
    return True


def drive_loop(f_mech_fn, dc, amp, rate, ramp_s, duration, reverse, label):
    """Write three sinusoids to the phase offsets until interrupted.

    f_mech_fn(t) returns the mechanical frequency at elapsed time t, which is
    what lets `hold` and `spinup` share this loop. Phase is accumulated
    (not recomputed as f*t) so that a changing frequency stays phase-continuous
    -- recomputing would step the phase every time f moved and drop the rotor
    out of lock.
    """
    ph = phases_rad(reverse)
    print(f'\n{label}. Ctrl-C to ramp down and stop.\n')
    t0 = time.time()
    theta = 0.0                     # accumulated electrical phase, radians
    t_prev = 0.0
    period = 1.0 / rate
    next_tick = t0
    last_print = -1e9
    tick = 0
    # A dry run advances a VIRTUAL clock instead of sleeping, so a 65-minute
    # spin-up rehearses in a second. Without this the dry run is as slow as the
    # real thing, which means nobody rehearses the long commands -- exactly the
    # trap the last round of fixes to stator_drive.py had to dig out of.
    virtual = DRY_RUN
    # A dry run with no duration would spin forever; give it something to finish.
    if virtual and duration <= 0:
        duration = 120.0
    inline = sys.stdout.isatty()
    print_every = 2.0 if not virtual else max(2.0, duration / 20.0)

    while not _STOPPING:
        t = tick * period if virtual else time.time() - t0
        if duration > 0 and t >= duration:
            break
        f_mech = f_mech_fn(t)
        f_elec = M_DRIVE * f_mech
        theta += 2 * math.pi * f_elec * (t - t_prev)
        t_prev = t
        env = min(1.0, t / ramp_s) if ramp_s > 0 else 1.0
        a = amp * env
        for pv, p in zip(PHASE_PVS, ph):
            put(pv, dc + a * math.cos(theta + p), echo=False)
        if t - last_print >= print_every:
            end, lead = ('', '\r') if inline else ('\n', '  ')
            print(f'{lead}  {t:7.1f} s   {f_mech:.4f} Hz mech '
                  f'({f_elec:.3f} Hz elec)   amp {a:.0f} cts   ',
                  end=end, flush=True)
            last_print = t
        tick += 1
        if virtual:
            continue
        next_tick += period
        sleep_for = next_tick - time.time()
        if sleep_for > 0:
            time.sleep(sleep_for)
        else:
            next_tick = time.time()     # we fell behind; resynchronise
    print()
    if virtual:
        print(f'  [dry-run] simulated {t:.0f} s of drive in {tick} updates '
              f'({tick * 3} EPICS writes)')
    ramp_down(dc, amp, ramp_s, theta, ph, rate)


def ramp_down(dc, amp, ramp_s, theta, ph, rate):
    """Ease the AC amplitude to zero, then drop the pedestal and ground."""
    if ramp_s > 0 and not DRY_RUN:
        print('  ramping amplitude down...')
        t0 = time.time()
        while (elapsed := time.time() - t0) < ramp_s:
            a = amp * (1.0 - elapsed / ramp_s)
            for pv, p in zip(PHASE_PVS, ph):
                put(pv, dc + a * math.cos(theta + p), echo=False)
            time.sleep(1.0 / rate)
    zero_all(echo=False)
    print('  all phase offsets at 0 counts.')


# ===========================================================================
# Commands
# ===========================================================================
def cmd_status(args):
    # status NEVER writes, so it always reads the real machine -- including
    # under --dry-run, where answering from _DRY_STATE would print a fiction.
    if caget is None:
        print('! pyepics is not importable, so nothing can be read back.\n'
              '  Refusing to print a status table rather than invent one.')
        return 1
    rget = lambda pv, d=0.0: get(pv, d, live=True)

    banner(args.dc if args.dc is not None else args.amp, args.amp)
    if DRY_RUN:
        print('  (readbacks below are LIVE -- status never writes)')
    print(f'  DRVON            {rget(DRVON_PV, 0.0):.0f}'
          f'   (must be 0, or the hardwired sin/cos fan-out sums in)')
    warn = []
    for name, n, pv, tr, out, inp, s1, s2 in zip(
            PHASE_NAMES, PHASE_ELECTRODES, PHASE_PVS, PHASE_TRAMP,
            PHASE_OUT, PHASE_IN, PHASE_SW1, PHASE_SW2):
        tramp, sw1, sw2 = rget(tr), rget(s1), rget(s2)
        print(f'  phase {name} (V{n})    offset {rget(pv):+9.1f}   '
              f'tramp {tramp:>5.2f}   outmon {rget(out):+9.1f}   '
              f'inmon {rget(inp):+8.1f}   sw1 {sw1:.0f} sw2 {sw2:.0f}')
        if tramp:
            warn.append(f'V{n} TRAMP = {tramp:g} s')
        if not int(sw2) & SW2_OUTPUT_ON:
            warn.append(f'V{n} SW2 = {sw2:.0f} has no output bit ({SW2_OUTPUT_ON})')
    print(f'  centre  (V{CTR_ELECTRODE})    offset {rget(CTR_PV):+9.1f}   '
          f'tramp {rget(CTR_TRAMP):>5.2f}')
    if warn:
        print('\n  ! ' + '\n  ! '.join(warn))
        print('\n  A nonzero TRAMP low-passes any software sinusoid into a smaller,\n'
              '  phase-lagged, distorted version while the COMMANDED values still look\n'
              '  perfect -- this script zeroes it for the duration of a drive and puts\n'
              '  it back afterwards.\n'
              '  If the output switch is off, offsets never reach the DAC at all.\n'
              '  Verify with one small `calibrate` step and watch OUTMON follow.')
    return 0


def cmd_calibrate(args):
    """Find where the amplifier saturates, and get counts -> volts.

    A DC staircase on ONE electrode. Measure the actual electrode voltage at each
    step with a meter (or watch _OUT). Two things come out of it: the slope,
    which is VOLTS_PER_COUNT, and the count at which the slope goes flat, which
    is the real ceiling. Everything this script refuses to compute follows from
    those two numbers.
    """
    pv = f'{PREFIX}_V{args.electrode}_OFFSET'
    out_pv = f'{PREFIX}_V{args.electrode}_OUT'
    print(f'\nDC staircase on V{args.electrode} ({pv})')
    print(f'  {args.steps} steps to {args.max_counts:.0f} counts, '
          f'{args.dwell:.0f} s each')
    print('  Measure the electrode voltage at each step. The slope is '
          'VOLTS_PER_COUNT;\n  where it stops rising is the amplifier ceiling.\n')
    print(f'  {"counts":>10} {"OUT readback":>14}')

    guard_oscillator()
    guard_tramp()
    steps = np.linspace(0.0, args.max_counts, args.steps + 1)
    try:
        for counts in steps:
            if _STOPPING:
                break
            put(pv, float(counts), wait=True, echo=False)
            if not DRY_RUN:
                time.sleep(args.dwell)
            print(f'  {counts:>10.0f} {get(out_pv):>14.1f}')
    except KeyboardInterrupt:
        print('\n  stopped by user.')
    finally:
        put(pv, 0.0, wait=True, echo=False)
        print('\n  back to 0 counts.')
    print('\n  VOLTS_PER_COUNT = (volts at the last linear step) / (its counts)')
    return 0


def _phase_index(spec):
    """'A'/'B'/'C' or an electrode number -> index into PHASE_*, or None if the
    number is not one of the three phases (e.g. the centre electrode)."""
    s = str(spec).strip().upper()
    if s in PHASE_NAMES:
        return PHASE_NAMES.index(s)
    try:
        n = int(s)
    except ValueError:
        raise SystemExit(f"--phase must be A/B/C or an electrode number 1-4, got '{spec}'")
    if n < 1 or n > 4:
        raise SystemExit(f"--phase electrode number must be 1-4, got {n}")
    return PHASE_ELECTRODES.index(n) if n in PHASE_ELECTRODES else None


def cmd_detent(args):
    """First-article test 3 -- and the one measurement the missing shim does not
    degrade, because it is pure DC: no ramp, no capture bandwidth, no timing.

    Energise one phase: the rotor snaps to one of 8 detents. Step A -> B -> C and
    the field advances 120 deg electrical = 15 deg mechanical per step. A static
    detent is something the old side posts could not produce at any drive level
    -- their torque was synchronous and averaged to zero -- so this is the clean
    yes/no on whether the variable-capacitance mechanism works at all.

    It also calibrates tau against V^2 directly, and settles which handedness is
    'forward' in camera coordinates.
    """
    if not check_amplitude(0.0, args.counts):
        return 1
    banner(args.counts, 0.0)
    print(f'\nDC detent test: {args.counts:.0f} counts, {args.dwell:.0f} s per step')
    print(f'  {360.0 / M_DRIVE:.1f} deg mech between detents')
    if args.phase is None:
        print(f'  {120.0 / M_DRIVE:.1f} deg mech per A->B->C step')
        print('  Watch the rotor (or the camera) -- you are looking for a discrete '
              'snap,\n  then a repeatable 15 deg walk.\n')
    else:
        print('  Watch for CAPTURE: a moving rotor going quiet and staying quiet\n'
              '  while the electrode is on, then picking up again on release.\n')

    guard_oscillator()
    previous = guard_tramp()

    # --phase: repeated INDEPENDENT capture attempts on ONE electrode.
    #
    # The A->B->C walk cannot compare electrodes fairly. Whether a detent captures
    # depends on where the rotor is and how fast it is moving when the field
    # switches on, not on torque alone -- so in a walk the first electrode gets a
    # settled rotor and the later ones get one that the earlier steps just stirred
    # up. On 2026-08-21 V2 captured (rms 22.5 -> 8.6) while V3 and V4 appeared to
    # do nothing, but they only ever saw the hard case. This gives each electrode
    # the same test: energise, hold, release, let it recover, repeat.
    if args.phase is not None:
        idx = _phase_index(args.phase)
        pv = PHASE_PVS[idx] if idx is not None else \
            f'{PREFIX}_V{int(args.phase)}_OFFSET'
        label = (f'phase {PHASE_NAMES[idx]} (V{PHASE_ELECTRODES[idx]})'
                 if idx is not None else f'V{int(args.phase)}')
        print(f'\n  single-electrode test: {label}, {args.cycles} attempt(s) of '
              f'{args.dwell:.0f} s\n  with {args.release:.0f} s grounded between, so '
              f'each attempt is independent.')
        try:
            for cycle in range(args.cycles):
                if _STOPPING:
                    raise KeyboardInterrupt
                put(pv, args.counts, wait=True, echo=False)
                print(f'  attempt {cycle + 1}/{args.cycles}  {label} ON '
                      f'({args.counts:.0f} cts) for {args.dwell:.0f} s')
                if not DRY_RUN:
                    time.sleep(args.dwell)
                zero_all(echo=False)
                print(f'    released, {args.release:.0f} s grounded')
                if not DRY_RUN and cycle < args.cycles - 1:
                    time.sleep(args.release)
        except KeyboardInterrupt:
            print('\n  stopped by user.')
        finally:
            zero_all(echo=False)
            restore_tramp(previous)
            print('  all electrodes at 0 counts, TRAMP restored.')
        return 0

    order = [0, 2, 1] if args.reverse else [0, 1, 2]
    try:
        for cycle in range(args.cycles):
            for idx in order:
                if _STOPPING:
                    raise KeyboardInterrupt
                for j, pv in enumerate(PHASE_PVS):
                    put(pv, args.counts if j == idx else 0.0,
                        wait=True, echo=False)
                print(f'  cycle {cycle + 1}/{args.cycles}  phase '
                      f'{PHASE_NAMES[idx]} (V{PHASE_ELECTRODES[idx]}) energised '
                      f'-> expect +{120.0 / M_DRIVE:.1f} deg mech')
                if not DRY_RUN:
                    time.sleep(args.dwell)
    except KeyboardInterrupt:
        print('\n  stopped by user.')
    finally:
        zero_all(echo=False)
        restore_tramp(previous)
        print('  all electrodes at 0 counts, TRAMP restored.')
    return 0


def cmd_hold(args):
    dc = args.dc if args.dc is not None else args.amp
    if not check_amplitude(dc, args.amp):
        return 1
    f_cap, _ = banner(dc, args.amp)
    f_elec = M_DRIVE * args.freq

    if args.rate < 20 * f_elec:
        print(f'! update rate {args.rate:.0f} Hz is under 20x the {f_elec:.2f} Hz '
              f'electrical\n  frequency -- the sinusoid will be too coarse to be a '
              f'clean rotating field.\n  Raise --rate or lower --freq.')
        return 1
    if f_cap is not None and args.freq > f_cap:
        print(f'! {args.freq:.4f} Hz is above the {f_cap:.4f} Hz capture '
              f'bandwidth.\n  From rest it will not lock. Use `spinup`, or pick a '
              f'lower frequency.')
        return 1
    if f_cap is None:
        print('  (capture bandwidth unknown without a calibration -- if the rotor '
              'does not\n  lock, try a lower frequency before assuming the drive '
              'is broken.)')

    guard_oscillator()
    previous = guard_tramp()
    try:
        drive_loop(lambda t: args.freq, dc, args.amp, args.rate, args.ramp,
                   args.duration, args.reverse,
                   f'Holding {args.freq:.4f} Hz mech ({f_elec:.3f} Hz elec)')
    finally:
        restore_tramp(previous)
    return 0


def cmd_spinup(args):
    dc = args.dc if args.dc is not None else args.amp
    if not check_amplitude(dc, args.amp):
        return 1
    f_cap, rate_max = banner(dc, args.amp)

    if args.rate_hz is None:
        if rate_max is None:
            print('! no --rate-hz given and the torque limit is unknown without a '
                  'calibration.\n  Pass --rate-hz explicitly (start slow: the '
                  'penalty for too fast is that\n  the rotor silently decouples '
                  'and coasts).')
            return 1
        ramp_rate = rate_max
    else:
        ramp_rate = args.rate_hz
        if rate_max is not None and ramp_rate > rate_max:
            print(f'! {ramp_rate:.2e} Hz/s exceeds the {rate_max:.2e} Hz/s torque '
                  f'limit; the rotor will slip.')
            return 1

    f_start = args.start if args.start is not None else \
        (0.5 * f_cap if f_cap is not None else 0.01)
    if args.freq <= f_start:
        print(f'! target {args.freq:.4f} Hz is at or below the {f_start:.4f} Hz '
              f'catch frequency.\n  Use `hold -f {args.freq:.4f}` instead.')
        return 1

    duration = (args.freq - f_start) / ramp_rate
    if args.duration > 0:
        print(f'  (--duration is ignored by spinup: the run length is set by the '
              f'ramp rate.\n   Use --rate-hz to change how long it takes.)')
    f_elec_end = M_DRIVE * args.freq
    if args.rate < 20 * f_elec_end:
        print(f'! update rate {args.rate:.0f} Hz cannot carry the final '
              f'{f_elec_end:.2f} Hz electrical\n  frequency (needs 20x). Lower the '
              f'target or raise --rate.')
        return 1

    print(f'\nCatch at {f_start:.4f} Hz, then {duration / 60:.1f} min to '
          f'{args.freq:.4f} Hz at {ramp_rate:.2e} Hz/s')
    guard_oscillator()
    previous = guard_tramp()

    def f_of_t(t):
        if t < args.settle:
            return f_start
        return min(args.freq, f_start + ramp_rate * (t - args.settle))

    try:
        drive_loop(f_of_t, dc, args.amp, args.rate, args.ramp,
                   args.settle + duration + args.hold_after, args.reverse,
                   f'Spinning up to {args.freq:.4f} Hz mech '
                   f'(settling {args.settle:.0f} s first)')
    finally:
        restore_tramp(previous)
    return 0


def cmd_stop(args):
    print('Grounding every electrode this script drives...')
    guard_oscillator()
    zero_all()
    print('Done -- A/B/C and the centre electrode at 0 counts.')
    return 0


# ===========================================================================
def build_parser():
    p = argparse.ArgumentParser(
        description='EPICS-only three-phase drive for the rev G under-rotor stator.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--live', action='store_true',
                   help='actually drive the hardware (default is a dry run)')
    p.add_argument('--volts-per-count', type=float, default=None,
                   help='measured DAC counts -> electrode volts. UNKNOWN by '
                        'default, which suppresses all torque/capture reporting. '
                        'Run `calibrate` to measure it.')
    p.add_argument('--gap', type=float, default=GAP_MM,
                   help=f'rotor-electrode gap in mm (default {GAP_MM} = no shim)')
    p.add_argument('--amp', type=float, default=DEFAULT_AMP,
                   help=f'peak AC amplitude per phase, counts (default {DEFAULT_AMP:.0f})')
    p.add_argument('--dc', type=float, default=None,
                   help='DC pedestal per phase, counts (default = --amp, which '
                        'maximises the m=8 channel and keeps an unipolar amp '
                        'non-negative). Vary at fixed --amp to separate the '
                        'channels: m=8 scales with it, m=16 does not.')
    sub = p.add_subparsers(dest='cmd', required=True)

    def ac_opts(sp):
        sp.add_argument('--rate', type=float, default=200.0,
                        help='EPICS update rate, Hz (default 200). Keep it above '
                             '20x the electrical frequency.')
        sp.add_argument('--ramp', type=float, default=5.0,
                        help='amplitude ramp up/down, s (default 5)')
        sp.add_argument('--duration', type=float, default=0.0,
                        help='run time in s (default 0 = until Ctrl-C)')
        sp.add_argument('--reverse', action='store_true',
                        help='swap phases B and C to reverse rotation')
        return sp

    sub.add_parser('status', help='read back every channel this script touches')

    sp = sub.add_parser('calibrate', help='DC staircase to find counts -> volts')
    sp.add_argument('--electrode', type=int, default=PHASE_ELECTRODES[0],
                    help=f'which V{{n}} to step (default {PHASE_ELECTRODES[0]})')
    sp.add_argument('--max-counts', type=float, default=MAX_TOTAL_COUNTS)
    sp.add_argument('--steps', type=int, default=16)
    sp.add_argument('--dwell', type=float, default=5.0, help='s per step')

    sp = sub.add_parser('detent', help='first-article DC detent test')
    sp.add_argument('--counts', type=float, default=DEFAULT_AMP)
    sp.add_argument('--dwell', type=float, default=20.0, help='s per step')
    sp.add_argument('--cycles', type=int, default=3,
                    help='A->B->C walks (or, with --phase, capture attempts)')
    sp.add_argument('--reverse', action='store_true')
    sp.add_argument('--phase', default=None, metavar='A|B|C|1-4',
                    help='energise ONE electrode instead of walking A->B->C, '
                         'repeatedly, releasing between attempts. This is how you '
                         'compare electrodes fairly -- in a walk, the first one gets '
                         'a settled rotor and the rest get one the earlier steps just '
                         'stirred up. Accepts the centre electrode too, which should '
                         'show NO capture at any drive level if it really is the '
                         'centre disk.')
    sp.add_argument('--release', type=float, default=20.0,
                    help='s grounded between attempts (default 20)')

    sp = ac_opts(sub.add_parser('hold', help='fixed-frequency three-phase'))
    sp.add_argument('-f', '--freq', type=float, default=0.02,
                    help='Hz MECHANICAL (default 0.02; f_elec = 8x this)')

    sp = ac_opts(sub.add_parser('spinup', help='catch at rest, ramp to a target'))
    sp.add_argument('-f', '--freq', type=float, default=0.2,
                    help='target, Hz MECHANICAL')
    sp.add_argument('--start', type=float, default=None,
                    help='catch frequency (default: half the capture bandwidth, '
                         'or 0.01 Hz if uncalibrated)')
    sp.add_argument('--rate-hz', type=float, default=None,
                    help='ramp rate in Hz mech/s (default: torque-limited, which '
                         'requires a calibration)')
    sp.add_argument('--settle', type=float, default=30.0,
                    help='s at the catch frequency before ramping')
    sp.add_argument('--hold-after', type=float, default=60.0,
                    help='s to hold at the target before stopping')

    sub.add_parser('stop', help='zero every electrode')
    return p


def _signal_handler(signum, frame):
    global _STOPPING
    if _STOPPING:
        print('\nSecond interrupt -- zeroing immediately.')
        zero_all(echo=False)
        sys.exit(1)
    _STOPPING = True
    print('\nInterrupted -- ramping down.')


def main():
    global DRY_RUN, VOLTS_PER_COUNT, GAP_MM
    args = build_parser().parse_args()
    DRY_RUN = not args.live
    VOLTS_PER_COUNT = args.volts_per_count
    GAP_MM = args.gap

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    # SIGHUP too: a 20-minute run is long enough that the terminal can be closed,
    # or an ssh session drop, while electrodes are energised. Without this the
    # process dies on the default SIGHUP action and leaves them live.
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, _signal_handler)

    if DRY_RUN:
        print('DRY RUN -- no hardware will be touched. Pass --live to drive.\n')
    elif caput is None:
        print('pyepics is not installed -- cannot drive.')
        return 1

    handler = {'status': cmd_status, 'calibrate': cmd_calibrate,
               'detent': cmd_detent, 'hold': cmd_hold, 'spinup': cmd_spinup,
               'stop': cmd_stop}[args.cmd]
    try:
        return handler(args) or 0
    except KeyboardInterrupt:
        zero_all(echo=False)
        return 1


if __name__ == '__main__':
    sys.exit(main())
