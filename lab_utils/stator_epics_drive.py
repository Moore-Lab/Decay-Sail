#!/usr/bin/env python3
"""
DC-only EPICS tool for the rev G under-rotor stator.

    status      read back every channel this script touches
    calibrate   DC staircase on one electrode to find the amp's saturation
    detent      first-article test 3: DC detent / 15 deg-per-step
    stop        zero every electrode

*** `hold` and `spinup` WERE REMOVED 2026-08-31. For any AC drive, use ***
***                lab_utils/stator_awg_drive.py                        ***

They synthesised a sine by rewriting V{n}_OFFSET from Python at a few hundred Hz.
That does not work, and -- worse -- it fails SILENTLY: the commanded values, and
everything the script printed, looked perfect throughout.

`_OFFSET` is the DC offset and is excellent at that job; what failed was using it
as a waveform generator. The front end only samples EPICS settings on its slow
cycle, so most of those writes are never seen. Measured 2026-08-28 at
f_elec = 4 Hz with 320 Hz writes: the electrodes emitted a SQUARE WAVE --
harmonics at 1/3, 1/5, 1/7 of the fundamental, THD 38.8%, relative phases
0/180/180 instead of 0/-120/-240, amplitudes 2324/1039/1272 against 2000
commanded. The DC pedestal in the same run was exact (2002/2001/1997), which is
the diagnostic tell: static settings get through, time-varying ones do not.

Where the technique breaks down is NOT bracketed: 0.16 Hz electrical was clean
(THD 0.03%, phases -120.0 deg, 2026-08-24) and 4 Hz was a square wave. That is a
factor of 25 with nothing measured in between, and it is why the flaw went
unnoticed -- the first test happened to be slow enough to look fine.

The commands were removed rather than fixed because no --rate value rescues them,
and leaving them in place invited someone to run a 2 Hz drive next month and
believe the numbers it printed.

Everything below goes through slow EPICS records (_OFFSET, _TRAMP, DRVON) and
nothing else -- which is exactly right for DC, where there is no waveform to
synthesise and the slow path is faithful.

Nothing touches hardware without --live.

References: lab_utils/stator_awg_drive.py, stator_flex/flex_spec.md,
CLAUDE.md ("THE STATOR"), apparatus_log.md (2026-08-28).
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
PREFIX_BASE = 'Y1:RDS'

# What is summed into each electrode AHEAD of its filter module, traced from
# y1rds.mdl at the top level 2026-08-28 (LES[1..3] -> OUTS In1..In3,
# MON -> OUTS In4). The module's SW1 input bit is the only thing gating it.
INPUT_SOURCE = {1: 'LES_PIT', 2: 'LES_YAW', 3: 'LES_SUM', 4: 'MON'}
INPUT_TOLERANCE_COUNTS = 1.0
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


def guard_tramp(tramp=0.0):
    """Set TRAMP on every driven electrode, and return the previous values.

    TRAMP is the LINEAR INTERPOLATION time for a commanded setpoint change,
    computed by the front end at the 2048 Hz model rate (y1rds.mdl:
    `host=cymac1 ifo=Y1 rate=2K`). That makes it a reconstruction filter, and
    the choice is NOT "0 or 1", it is "how does TRAMP compare to the interval
    between writes":

      * TRAMP = 0            -> zero-order hold. Every write lands as a hard
                                step, so the output is a staircase at --rate.
      * TRAMP ~ 1/rate       -> first-order hold: each write interpolates
                                linearly to the next over exactly one interval,
                                evaluated at 2048 Hz. This is the SMOOTH case,
                                and the amplitude/phase penalty is negligible
                                while f_elec * TRAMP << 1 (at 200 Hz writes and
                                0.16 Hz electrical that is 8e-4, an error of
                                order 1e-6).
      * TRAMP >> 1/rate      -> each write only travels a fraction of its step
                                before being superseded: severe attenuation and
                                phase lag, while the commanded values (and
                                anything this script logs) still look perfect.
                                This is the 1.0 s @ 200 Hz case found live on
                                2026-08-21, where each write advanced 1/200 of
                                the way to its target.

    An earlier version of this function forced TRAMP = 0 and asserted that was
    the only correct choice for a software-generated waveform. That is the
    wrong end of the trade: it removes the low-pass distortion by replacing a
    smooth wave with a staircase. Prefer TRAMP = 1/rate for AC drives; 0 is
    still right for the DC commands (`calibrate`, `detent`), where a step is
    the point.

    Deliberately does not touch DRV_TRAMP -- zeroing that would break exactly
    the phase continuity an oscillator frequency sweep depends on.
    """
    previous = {}
    for pv in list(PHASE_TRAMP) + [CTR_TRAMP]:
        previous[pv] = get(pv, 0.0)
        put(pv, float(tramp), wait=True, echo=False)
    changed = {k: v for k, v in previous.items() if v != tramp}
    if changed:
        print(f'  TRAMP set to {tramp:g} s (was: ' +
              ', '.join(f'{k.split("_")[-2]}={v:g}s' for k, v in changed.items()) + ')')
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
def check_inputs():
    """Refuse to drive if a phase electrode's module INPUT is on.

    Traced from y1rds.mdl 2026-08-28. The four electrode filter modules are not
    fed only by what we write -- each has a signal summed in AHEAD of the
    module, so the module's own SW1 input bit is the only thing gating it:

        LES.PIT -> OUTS In1 -> V1 = LES_PIT + s      (CTR)
        LES.YAW -> OUTS In2 -> V2 = LES_YAW + c      <- phase A
        LES.SUM -> OUTS In3 -> V3 = LES_SUM - s      <- phase C
        MON     -> OUTS In4 -> V4 = MON     - c      <- phase B

    Measured live on 2026-08-28: LES_PIT_OUT 5761 counts, LES_YAW_OUT -2552,
    both with GAIN = 1 -- i.e. genuinely live. Against a drive amplitude of a
    few thousand counts that is a huge uncommanded pedestal on ONE phase, which
    destroys precisely the amplitude balance and 120 deg phasing that the
    2026-08-24 run verified to four significant figures.

    LES_SUM and MON currently read 0, but NOT because they are unwired: both
    have GAIN = 0, and LES_SUM has 636 counts sitting at its input (INMON).
    So V3/V4 are safe only for as long as nobody sets those two gains. Check
    the switch, not the readback.

    Do NOT infer "nothing is arriving" from INMON = 0 -- INMON is a slow
    monitor and a zero-mean AC signal reads ~0 through it. Use the fast
    V{n}_OUT_DQ / LES_*_OUT_DQ channels over NDS instead.
    """
    if caget is None:
        return True
    hot, armed = [], []
    for name, n, pv in zip(PHASE_NAMES, PHASE_ELECTRODES, PHASE_SW1):
        if not int(get(pv, 0.0, live=True)) & SW1_INPUT_ON:
            continue                      # input blocked -- nothing gets in
        src = INPUT_SOURCE[n]
        level = get(f'{PREFIX_BASE}-{src}_OUTMON', 0.0, live=True)
        gain = get(f'{PREFIX_BASE}-{src}_GAIN', 0.0, live=True)
        entry = f'phase {name} (V{n}) <- {src}: {level:+.1f} counts, GAIN {gain:g}'
        (hot if abs(level) > INPUT_TOLERANCE_COUNTS else armed).append(entry)

    for entry in armed:
        print(f'  note: input open but source is quiet -- {entry}')
    if armed:
        print(f'        ({INPUT_TOLERANCE_COUNTS:g} count tolerance. A quiet source '
              f'is not a safe one:\n         it is one GAIN write away from being '
              f'summed into that phase.)')
    if hot:
        print('! LIVE signal is summed into a drive phase:\n    ' +
              '\n    '.join(hot))
        print('  That is an uncommanded pedestal on ONE phase, which breaks the\n'
              '  amplitude balance and 120 deg phasing the drive depends on.\n'
              '  Turn that module\'s input off (clear bit %d), or pass\n'
              '  --allow-input if you really mean to drive with it connected.'
              % SW1_INPUT_ON)
        return False
    return True


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
    # _OUT does not exist as an EPICS record (fast test point, NDS-only) -- caget
    # on it fails and get() silently returns the 0.0 default, so every row of the
    # staircase printed "0.0" and looked like a dead channel. _OUTMON is the slow
    # readback. It is still only the FRONT-END output in counts: it shows the
    # filter module's own LIMIT clipping (12800, engaged via SW2 bit 256) but says
    # nothing about the HV amp downstream. Amp saturation needs a meter at the
    # electrode.
    out_pv = f'{PREFIX}_V{args.electrode}_OUTMON'
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
    if not args.allow_input and not check_inputs():
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
    p.add_argument('--allow-input', action='store_true',
                   help='drive even if a phase electrode has its module INPUT '
                        'switch on. Each V{n} has a signal summed in ahead of '
                        'the filter module (V1<-LES_PIT, V2<-LES_YAW, '
                        'V3<-LES_SUM, V4<-MON), so an open input adds an '
                        'uncommanded pedestal to that phase alone.')
    p.add_argument('--gap', type=float, default=GAP_MM,
                   help=f'rotor-electrode gap in mm (default {GAP_MM} = no shim)')
    p.add_argument('--amp', type=float, default=DEFAULT_AMP,
                   help=f'counts used only for the banner\'s physics summary '
                        f'(default {DEFAULT_AMP:.0f}). This script no longer '
                        f'drives AC -- see stator_awg_drive.py.')
    p.add_argument('--dc', type=float, default=None,
                   help='DC pedestal per phase, counts (default = --amp). Note '
                        'the amp input must stay POSITIVE within 0-2 V, so '
                        'dc >= amp is a hard constraint and dc = amp = 6400 '
                        'exactly fills that range (2026-08-31).')
    sub = p.add_subparsers(dest='cmd', required=True)

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
               'detent': cmd_detent, 'stop': cmd_stop}[args.cmd]
    try:
        return handler(args) or 0
    except KeyboardInterrupt:
        zero_all(echo=False)
        return 1


if __name__ == '__main__':
    sys.exit(main())
