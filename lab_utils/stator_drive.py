#!/usr/bin/env python3
"""
Three-phase drive for the rev G under-rotor stator.

Replaces sweep_oscillator.py, which drove the four side posts in quadrature.
The stator is a different machine, so this is a different tool:

  * 24 sectors on a 15 deg pitch, driven 3-phase (A/B/C at 0/120/240 deg),
    synthesising a rotating m = 8 potential.
  * ROTOR SPEED = f_electrical / 8. Every frequency in this file is MECHANICAL;
    the electrical frequency handed to the oscillator is derived from it.
  * Capture bandwidth is 0.12-0.41 Hz mech, against a few mHz for the posts.
    You therefore no longer SWEEP to hunt for capture -- you catch the rotor at
    rest, below capture, and carry it up. The quantity that matters is the ramp
    RATE, which is bounded by torque and which this script derives rather than
    taking on faith.
  * Reverse by swapping two phases. Note this is structural, not a sign flip:
    sweep_oscillator_reverse.py tried to reverse the OLD drive by negating COS,
    but the forward script already ran COS = -GAIN, so the negation cancelled
    and it drove the same direction. Handedness here lives in the phase
    ORDERING, where there is no sign convention left to get backwards.

Commands:
    status              read back frequency, gains, direction
    spinup  -f 2.0      ramp from rest to 2.0 Hz mech at the torque limit
    hold    -f 0.2      sit at a fixed frequency (must be inside capture)
    reverse             ramp through zero, swap phases, ramp back up
    sweep   -f 4.0      stepped frequency response, dwelling at each step
    detent              first-article test 3: DC detent / 15 deg-per-step
    stop                ramp down, then A/B/C to ground

Nothing drives hardware without --live. Default is a dry run that prints every
EPICS write. The drive reaches 200 V and all four mounting screws are live at
that potential.

References: stator_flex/flex_spec.md, stator_flex/spinup_note.md, and the
"Stator for underneath drive" page in the moorelab Notion.
"""

import argparse
import sys
import time

import numpy as np

try:
    from epics import caget, caput
except ImportError:      # no pyepics off the control machines -- dry run still works
    caget = caput = None

# ===========================================================================
# CONFIRM BEFORE FIRST USE -- none of this is in the design notes
# ===========================================================================
# The stator needs three phase-locked outputs. sweep_oscillator.py used ONE
# oscillator (Y1:RDS-OUTS_DRV) whose sin/cos quadrature pair the RTS model
# fanned out to the four posts as (sin, cos, -sin, -cos). That routing is
# hardcoded in the model and is a 4-post, 2-phase pattern -- it cannot make
# 120 deg phases, so the model needs per-phase gains on the sin/cos pair.
#
# Three phases ARE synthesisable from two quadrature signals (see
# phase_gains()), so what is needed is a 2xN output matrix, not three
# oscillators. Set these to whatever the model ends up exposing.
PHASE_GAIN_PVS = {
    'A': ('Y1:RDS-OUTS_V1_SINGAIN', 'Y1:RDS-OUTS_V1_COSGAIN'),   # terminal 15 deg
    'B': ('Y1:RDS-OUTS_V2_SINGAIN', 'Y1:RDS-OUTS_V2_COSGAIN'),   # terminal 105 deg
    'C': ('Y1:RDS-OUTS_V3_SINGAIN', 'Y1:RDS-OUTS_V3_COSGAIN'),   # terminal 195 deg
}
PHASE_OFFSET_PVS = {
    'A': 'Y1:RDS-OUTS_V1_OFFSET',
    'B': 'Y1:RDS-OUTS_V2_OFFSET',
    'C': 'Y1:RDS-OUTS_V3_OFFSET',
}
CTR_OFFSET_PV = 'Y1:RDS-OUTS_V4_OFFSET'   # centre disk: DC height trim / charge drive

# Counts -> volts at the electrode, through the HV amplifier. UNMEASURED.
# Torque goes as V^2, so a factor 2 error here is a factor 4 in every limit
# this script computes. Worth pinning down before trusting the ramp rate.
VOLTS_PER_COUNT = 0.03125   # placeholder: 6400 counts -> 200 V

PV       = 'Y1:RDS-OUTS_DRV'
PV_ON    = 'Y1:RDS-OUTS_DRVON'
FREQ_PV  = f'{PV}_FREQ'
TRAMP_PV = f'{PV}_TRAMP'

# ===========================================================================
# Machine constants
# ===========================================================================
M_DRIVE = 8              # rotor speed = f_elec / M_DRIVE; also the detent count
I_KGM2  = 1.88e-11       # ASSUMED, never measured (see apparatus_log.md)
GAP_MM  = 0.27           # 0.27 with the 0.1 mm shim, 0.37 without
DRIVE_COUNTS = 6400.0    # peak AC amplitude per phase

# DC pedestal per phase. NOT a workaround for a unipolar amplifier -- it is what
# switches the m=8 torque channel on. Expanding tau = 1/2 (dC/dtheta) V^2 for
# V_k = V_dc + V_ac*cos(phi + delta_k) over the 24-sector/3-phase pattern gives two
# channels, and both lock the rotor at the same speed f_elec/8:
#     rotor m=8   <- amplitude V_dc * V_ac   (winds 1x per electrical cycle)
#     rotor m=16  <- amplitude V_ac^2        (winds 2x per electrical cycle)
# At V_dc = 0 the m=8 channel vanishes identically, leaving only m=16 -- which is the
# stronger rotor harmonic but suffers twice the gap attenuation exp(-m h / r).
# Maximising V_dc*V_ac subject to V_dc + V_ac <= V_max gives V_dc = V_ac = V_max/2,
# hence DRIVE_DC == DRIVE_COUNTS: the same 6400/6400 split sweep_oscillator.py
# already used on the old posts. Override with --dc only to separate the two
# channels -- m=8 scales with V_dc, m=16 does not.
DRIVE_DC = DRIVE_COUNTS

TORQUE_MARGIN = 0.5      # fraction of tau_max used while ramping ("<=50%")

# tau_max at 100 V, from the design notes. Torque goes as V^2.
TAU_100V = {0.27: 3.8e-12, 0.37: 1.2e-12}   # N*m

DRY_RUN = True           # flipped by --live


# ===========================================================================
# Physics
# ===========================================================================
def tau_max(volts, gap_mm=GAP_MM):
    """Peak drive torque (N*m). Interpolates log-linearly in the gap between the
    two documented points -- the underlying attenuation is exp(-m h / r), so an
    exponential in h is the right form. Extrapolation is flagged, not silently
    trusted."""
    h0, h1 = 0.27, 0.37
    t0, t1 = TAU_100V[h0], TAU_100V[h1]
    decay = np.log(t1 / t0) / (h1 - h0)
    tau_100 = t0 * np.exp(decay * (gap_mm - h0))
    if not (h0 <= gap_mm <= h1):
        print(f'  ! gap {gap_mm} mm is outside the documented range '
              f'[{h0}, {h1}] -- torque is extrapolated')
    return tau_100 * (volts / 100.0) ** 2


def f_capture_mech(tau):
    """Pull-in bandwidth (Hz mech). The drive torque is tau_max*sin(m*(th-th0)),
    so the restoring stiffness is m*tau_max and omega_lib = sqrt(m*tau_max/I).

    Reproduces all four capture figures in the design notes (0.41 / 0.23 / 0.20
    / 0.12 Hz). The notes' own sqrt(2*tau/I)/2pi is the SIDE-POST case -- that 2
    is the induced dipole's 2-fold symmetry, not a universal constant."""
    return np.sqrt(M_DRIVE * tau / I_KGM2) / (2 * np.pi)


def max_ramp_rate_mech(tau, margin=TORQUE_MARGIN):
    """Fastest mechanical spin-up the drive can carry without slipping (Hz/s).
    Reproduces the notes' 0 -> 10 Hz mech times (2.6 / 7.9 / 10 / 32 min) at
    margin = 0.5."""
    return margin * tau / (2 * np.pi * I_KGM2)


def phase_gains(reverse=False):
    """Sin/cos coefficients that turn one quadrature pair into three phases:

        A = cos(t)            -> ( 0.000,  1.000)
        B = cos(t - 120 deg)  -> (+0.866, -0.500)
        C = cos(t - 240 deg)  -> (-0.866, -0.500)

    using cos(t - d) = cos(d)cos(t) + sin(d)sin(t). The three sum to zero, so
    the drive is balanced and puts no net monopole on the rotor -- which matters:
    a monopole gives a rotating FORCE, which heats the orbit, rather than a
    torque (spinup_note.md, mechanism 4).

    Reversing swaps B and C, as "reverse by swapping any two phases" prescribes.
    Which handedness is "forward" in camera coordinates depends on how the ring
    terminals are clocked and is only settled by the detent test."""
    order = ['A', 'C', 'B'] if reverse else ['A', 'B', 'C']
    return {name: (np.sin(np.deg2rad(d)), np.cos(np.deg2rad(d)))
            for name, d in zip(order, (0.0, 120.0, 240.0))}


# ===========================================================================
# EPICS
# ===========================================================================
# Dry-run shadow of the control system: every put is remembered so a later get reads
# it back. Without this, get() always returned its default, current_f_mech() always
# read 0.0, and `spindown`, `reverse` and `stop` all bailed out with "drive is at
# zero" -- the three commands most worth rehearsing were the three the dry run could
# not exercise. Seeded from --dry-freq so they have a running rotor to act on.
_DRY_STATE: dict = {}


def put(pv, value, wait=False):
    if DRY_RUN:
        _DRY_STATE[pv] = float(value)
        print(f'    [dry-run] {pv} <- {value}')
        return
    caput(pv, float(value), wait=wait, timeout=2.0)


def get(pv, default=0.0):
    if DRY_RUN:
        value = _DRY_STATE.get(pv, default)
        print(f'    [dry-run] read {pv} -> {value}')
        return value
    return caget(pv)


def set_phase_gains(counts, reverse=False, quiet=False):
    for name, (s, c) in phase_gains(reverse).items():
        sin_pv, cos_pv = PHASE_GAIN_PVS[name]
        put(sin_pv, s * counts)
        put(cos_pv, c * counts)
        if not quiet:
            print(f'  phase {name}: sin {s * counts:+9.1f}  '
                  f'cos {c * counts:+9.1f} counts')


def current_f_mech():
    return get(FREQ_PV, 0.0) / M_DRIVE


def ground_phases():
    """Protocol step 4: A/B/C to ground, so the board becomes a clean ground
    plane with no drive systematic during a science run."""
    for name in ('A', 'B', 'C'):
        sin_pv, cos_pv = PHASE_GAIN_PVS[name]
        put(sin_pv, 0.0)
        put(cos_pv, 0.0)
        put(PHASE_OFFSET_PVS[name], 0.0, wait=True)
    print('  A/B/C grounded')


def ramp(f_from, f_to, rate, label='Ramping'):
    """Ramp the oscillator between two mechanical frequencies at `rate` Hz/s.

    One TRAMP does the whole thing: the model interpolates the oscillator
    frequency linearly and keeps phase continuous. That continuity is the whole
    reason for driving this from the oscillator rather than from AWG buffers --
    a buffer swap mid-ramp steps the phase and drops the rotor out of lock."""
    duration = abs(f_to - f_from) / rate
    print(f'{label} {f_from:.3f} -> {f_to:.3f} Hz mech '
          f'over {duration / 60:.1f} min at {rate:.4f} Hz/s')
    put(TRAMP_PV, duration)
    put(FREQ_PV, M_DRIVE * f_to)
    if DRY_RUN:
        return
    t0 = time.time()
    while (elapsed := time.time() - t0) < duration:
        f_now = f_from + (elapsed / duration) * (f_to - f_from)
        print(f'\r  {elapsed:6.0f}/{duration:.0f} s   {f_now:.3f} Hz mech',
              end='', flush=True)
        time.sleep(2.0)
    print(f'\r  {duration:6.0f}/{duration:.0f} s   {f_to:.3f} Hz mech')


def enable(reverse=False):
    """Bring the drive up: DC pedestal, phase gains, oscillator on.

    The pedestal is applied HERE rather than once at setup because
    ground_phases() zeroes the offsets and both `stop` and the Ctrl-C handler call
    it. Setting it only at setup meant every run after the first drove bipolar and
    silently lost the m=8 channel -- the drive would look correct and just be
    mysteriously feeble, and weaker after a restart than on the first run.
    """
    put(TRAMP_PV, 0.0)
    for name in ('A', 'B', 'C'):
        put(PHASE_OFFSET_PVS[name], DRIVE_DC)
    print(f'  DC pedestal {DRIVE_DC:.0f} counts/phase -> swing '
          f'[{DRIVE_DC - DRIVE_COUNTS:.0f}, {DRIVE_DC + DRIVE_COUNTS:.0f}]')
    set_phase_gains(DRIVE_COUNTS, reverse)
    put(PV_ON, 1)


# ===========================================================================
# Reporting
# ===========================================================================
def drive_limits():
    volts = DRIVE_COUNTS * VOLTS_PER_COUNT
    tau = tau_max(volts)
    return volts, tau, f_capture_mech(tau), max_ramp_rate_mech(tau)


def banner():
    volts, tau, f_cap, rate = drive_limits()
    print('=' * 68)
    print(f'  drive      {DRIVE_COUNTS:.0f} counts AC on {DRIVE_DC:.0f} DC '
          f'= {volts:.1f} V pk   gap {GAP_MM} mm')
    if DRIVE_DC == 0:
        print('  ! DC pedestal is 0 -- the m=8 torque channel is OFF, only m=16 drives')
    print(f'  tau_max    {tau:.2e} N*m')
    print(f'  capture    {f_cap:.3f} Hz mech   (start below this from rest)')
    print(f'  max ramp   {rate:.4f} Hz mech/s at {TORQUE_MARGIN:.0%} torque margin')
    print('=' * 68)
    return f_cap, rate


# ===========================================================================
# Commands
# ===========================================================================
def cmd_status(args):
    banner()
    f_mech = current_f_mech()
    on = get(PV_ON, 0)
    print(f'  drive {"ON" if on else "OFF"} at {f_mech:.3f} Hz mech '
          f'({M_DRIVE * f_mech:.2f} Hz elec)')
    for name in ('A', 'B', 'C'):
        sin_pv, cos_pv = PHASE_GAIN_PVS[name]
        print(f'  {name}: sin {get(sin_pv):+9.1f}  cos {get(cos_pv):+9.1f}  '
              f'offset {get(PHASE_OFFSET_PVS[name]):+9.1f}')
    print(f'  CTR offset {get(CTR_OFFSET_PV):+9.1f}')


def cmd_spinup(args):
    f_cap, rate_max = banner()
    rate = args.rate or rate_max
    f_from = args.start if args.start is not None else min(0.5 * f_cap, args.freq)

    if f_from > f_cap:
        print(f'! start {f_from:.3f} Hz is above the {f_cap:.3f} Hz capture '
              f'bandwidth.\n  A standing start will not capture -- the average '
              f'torque is zero unless\n  the rotor already co-rotates. Start '
              f'below {f_cap:.3f} Hz.')
        return 1
    if args.freq <= f_from:
        print(f'! target {args.freq:.3f} Hz is at or below the {f_from:.3f} Hz '
              f'catch frequency,\n  so there is nothing to ramp. It is inside '
              f'capture -- use `hold -f {args.freq:.3f}`.')
        return 1
    if rate > rate_max:
        print(f'! {rate:.4f} Hz/s exceeds the {rate_max:.4f} Hz/s torque limit; '
              f'the rotor will slip.')
        return 1

    print(f'\nCatching the rotor at {f_from:.3f} Hz mech '
          f'(capture {f_cap:.3f} Hz)...')
    enable(args.reverse)
    put(FREQ_PV, M_DRIVE * f_from)
    if not DRY_RUN:
        time.sleep(args.settle)
    print(f'  settled {args.settle:.0f} s\n')

    ramp(f_from, args.freq, rate, 'Spinning up')
    print(f'\nAt {args.freq:.3f} Hz mech. Drive left enabled.')
    return 0


def cmd_hold(args):
    f_cap, _ = banner()
    if args.freq > f_cap:
        print(f'! {args.freq:.3f} Hz is above the {f_cap:.3f} Hz capture '
              f'bandwidth.\n  Use `spinup` to carry the rotor there instead.')
        return 1
    enable(args.reverse)
    put(FREQ_PV, M_DRIVE * args.freq)
    print(f'\nHolding {args.freq:.3f} Hz mech ({M_DRIVE * args.freq:.2f} Hz elec).')
    return 0


def cmd_spindown(args):
    """Slow the rotor under drive, keeping it locked the whole way.

    This is what sweep_oscillator_reverse.py was reaching for and missed twice
    over: its np.arange(0.1, 4.0, 0.2) ascends, so it swept UP, and at 0.2 Hz
    per 1 s dwell it was ~900x faster than the posts could torque and stepped
    ~17x wider than their 12 mHz capture -- the rotor decoupled on step one and
    coasted on gas damping. Deceleration is torque-limited exactly like
    acceleration, so the same bound applies going down.

    For a FREE spindown (drive off, coasting -- the damping measurement) use
    `stop --now` instead: that grounds A/B/C without braking."""
    f_cap, rate_max = banner()
    rate = args.rate or rate_max
    f_now = current_f_mech()

    if f_now <= 0:
        print('! drive is at zero -- nothing to spin down.')
        return 1
    if args.freq >= f_now:
        print(f'! target {args.freq:.3f} Hz is at or above the current '
              f'{f_now:.3f} Hz.\n  Use `spinup` to go faster.')
        return 1
    if rate > rate_max:
        print(f'! {rate:.4f} Hz/s exceeds the {rate_max:.4f} Hz/s torque limit; '
              f'the rotor will\n  decouple and coast instead of following the '
              f'drive down.')
        return 1

    ramp(f_now, args.freq, rate, 'Spinning down')
    if args.freq == 0:
        print('\nAt rest, still locked in a detent. Drive enabled -- '
              '`stop` to ground.')
    else:
        print(f'\nAt {args.freq:.3f} Hz mech. Drive left enabled.')
    return 0


def cmd_reverse(args):
    """Protocol step 3: swap two phases, ramp through zero."""
    f_cap, rate_max = banner()
    rate = args.rate or rate_max
    f_now = current_f_mech()
    if f_now <= 0:
        print('! drive is at zero -- nothing to reverse. Use `spinup --reverse`.')
        return 1

    print(f'\nReversing from {f_now:.3f} Hz mech.')
    ramp(f_now, 0.0, rate, 'Spinning down')

    print('\nSwapping phases B and C...')
    set_phase_gains(DRIVE_COUNTS, reverse=True)
    if not DRY_RUN:
        time.sleep(args.settle)

    ramp(0.0, f_now, rate, 'Spinning up (reversed)')
    print(f'\nAt {f_now:.3f} Hz mech, reversed.')
    return 0


def cmd_sweep(args):
    """Stepped frequency response. Kept for measuring chi(f) -- the high-frequency
    asymptote gives I directly, which apparatus_log.md lists as never measured.
    Not the way to spin up: use `spinup`."""
    f_cap, rate_max = banner()
    steps = np.arange(args.start, args.freq + 1e-9, args.step)
    step_rate = args.step / args.dwell
    print(f'\n{len(steps)} steps of {args.step:.3f} Hz, {args.dwell:.0f} s dwell '
          f'-> {len(steps) * args.dwell / 60:.1f} min')

    if args.step > f_cap:
        print(f'! step {args.step:.3f} Hz exceeds the {f_cap:.3f} Hz capture '
              f'bandwidth; each step drops the rotor out of lock.')
        return 1
    if step_rate > rate_max:
        print(f'! averaged {step_rate:.4f} Hz/s exceeds the {rate_max:.4f} Hz/s '
              f'torque limit.')
        return 1

    enable(args.reverse)
    put(TRAMP_PV, args.dwell * 0.1)
    for f_mech in steps:
        put(FREQ_PV, M_DRIVE * float(f_mech))
        print(f'  {f_mech:.3f} Hz mech ({M_DRIVE * f_mech:.2f} Hz elec), '
              f'dwell {args.dwell:.0f} s')
        if not DRY_RUN:
            time.sleep(args.dwell)
    print('Sweep complete. Drive left enabled at the final frequency.')
    return 0


def cmd_detent(args):
    """First-article test 3. Energise one phase DC: the rotor snaps to one of 8
    detents. Stepping A -> B -> C advances the field 120 deg electrical = 15 deg
    mechanical per step. Calibrates tau_max against V^2 directly, and settles
    which handedness is 'forward' in camera coordinates."""
    banner()
    print(f'\nDC detent test: {args.counts:.0f} counts, {args.dwell:.0f} s per step')
    print(f'  {360.0 / M_DRIVE:.1f} deg mech between detents, '
          f'{120.0 / M_DRIVE:.1f} deg mech per A->B->C step\n')

    put(PV_ON, 0)                       # DC only -- oscillator off
    set_phase_gains(0.0, quiet=True)

    order = ['A', 'C', 'B'] if args.reverse else ['A', 'B', 'C']
    try:
        for cycle in range(args.cycles):
            for name in order:
                for other in ('A', 'B', 'C'):
                    put(PHASE_OFFSET_PVS[other],
                        args.counts if other == name else 0.0, wait=True)
                print(f'  cycle {cycle + 1}/{args.cycles}  phase {name} energised '
                      f'-> expect +{120.0 / M_DRIVE:.1f} deg mech')
                if not DRY_RUN:
                    time.sleep(args.dwell)
    except KeyboardInterrupt:
        print('\nStopped by user.')
    finally:
        ground_phases()
    return 0


def cmd_stop(args):
    _, rate_max = banner()
    f_now = current_f_mech()
    if f_now > 0 and not args.now:
        ramp(f_now, 0.0, args.rate or rate_max, 'Spinning down')
    print('\nGrounding...')
    ground_phases()
    put(CTR_OFFSET_PV, 0.0, wait=True)
    put(PV_ON, 0)
    put(FREQ_PV, 0.0)
    print('Drive disabled, A/B/C grounded, board is a clean ground plane.')
    return 0


# ===========================================================================
def build_parser():
    p = argparse.ArgumentParser(
        description='Three-phase drive for the rev G under-rotor stator.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--live', action='store_true',
                   help='actually drive the hardware (default is a dry run)')
    p.add_argument('--dc', type=float, default=None,
                   help=f'DC pedestal per phase in counts (default {DRIVE_DC:.0f} = '
                        f'the AC amplitude, which maximises the m=8 torque). Vary '
                        f'this at fixed amplitude to separate the torque channels: '
                        f'm=8 scales with it, m=16 does not.')
    p.add_argument('--dry-freq', type=float, default=1.0, metavar='HZ',
                   help='mechanical frequency the DRY RUN pretends the rotor is at, '
                        'so spindown/reverse/stop can be rehearsed (default 1.0)')
    sub = p.add_subparsers(dest='cmd', required=True)

    def common(sp, freq_default=None, freq_help='target, Hz MECHANICAL'):
        if freq_default is not None:
            sp.add_argument('-f', '--freq', type=float, default=freq_default,
                            help=freq_help)
        sp.add_argument('--reverse', action='store_true',
                        help='swap phases B and C')
        sp.add_argument('--rate', type=float, default=None,
                        help='ramp rate, Hz mech/s (default: torque-limited)')
        return sp

    sub.add_parser('status', help='read back frequency, gains, direction')

    sp = common(sub.add_parser('spinup', help='ramp from rest to a target speed'), 2.0)
    sp.add_argument('--start', type=float, default=None,
                    help='catch frequency (default: half the capture bandwidth)')
    sp.add_argument('--settle', type=float, default=30.0,
                    help='seconds to let the rotor lock before ramping')

    common(sub.add_parser('spindown', help='slow down under drive, staying locked'),
           0.0, 'target, Hz MECHANICAL (default 0)')

    common(sub.add_parser('hold', help='sit at a fixed frequency'), 0.2)

    sp = common(sub.add_parser('reverse', help='ramp through zero, swap, ramp up'))
    sp.add_argument('--settle', type=float, default=10.0,
                    help='seconds at zero after the swap')

    sp = common(sub.add_parser('sweep', help='stepped frequency response'), 4.0)
    sp.add_argument('--start', type=float, default=0.05, help='Hz mech')
    sp.add_argument('--step', type=float, default=0.05, help='Hz mech')
    sp.add_argument('--dwell', type=float, default=100.0, help='s per step')

    sp = sub.add_parser('detent', help='first-article DC detent test')
    sp.add_argument('--counts', type=float, default=DRIVE_COUNTS)
    sp.add_argument('--dwell', type=float, default=20.0, help='s per step')
    sp.add_argument('--cycles', type=int, default=3)
    sp.add_argument('--reverse', action='store_true')

    sp = common(sub.add_parser('stop', help='ramp down and ground A/B/C'))
    sp.add_argument('--now', action='store_true',
                    help='skip the ramp down and ground immediately')
    return p


def main():
    global DRY_RUN, DRIVE_DC
    args = build_parser().parse_args()
    DRY_RUN = not args.live
    if args.dc is not None:
        DRIVE_DC = args.dc
    if DRY_RUN:
        _DRY_STATE[FREQ_PV] = M_DRIVE * args.dry_freq
        _DRY_STATE[PV_ON] = 1.0 if args.dry_freq else 0.0
        print('DRY RUN -- no hardware will be touched. Pass --live to drive.')
        print(f'  assuming the rotor is at {args.dry_freq:.3f} Hz mech '
              f'(--dry-freq); reads are shadowed, not from EPICS.\n')
    elif caput is None:
        print('pyepics is not installed -- cannot drive. Run this on cymac1.')
        return 1

    handler = {'status': cmd_status, 'spinup': cmd_spinup, 'hold': cmd_hold,
               'spindown': cmd_spindown, 'reverse': cmd_reverse, 'sweep': cmd_sweep,
               'detent': cmd_detent, 'stop': cmd_stop}[args.cmd]
    try:
        return handler(args) or 0
    except KeyboardInterrupt:
        print('\nInterrupted -- spinning down and grounding.')
        ground_phases()
        put(PV_ON, 0)
        return 1


if __name__ == '__main__':
    sys.exit(main())
