# `y1rds` model change proposal: front-end commutation for the feedback drive

> **DRAFT, 2026-11-02, written by Claude for Molly and Alma to review. Nothing here is approved or built.**
> Interpretations are Claude's. The measured facts it rests on are in
> `lab_utils/FEEDBACK_HANDOFF.md` (branch `feedback-drive`, F1/F1b results).

## Why

The feedback drive points the stator field from the camera's rotor angle. Without a model change,
worker2 writes the DRVMTRX matrix over EPICS. On 2026-11-02 (outputs off) that route measured:
- the field follows the commands step for step;
- **the front end applies EPICS-written values only at 16 Hz** (all 852 output steps sat on the
  same 1/16 s grid), so the field moves in 62.5 ms steps;
- the camera-to-field delay was not measured (the only front-end clock reading available,
  `DAQ-DC0_GPS`, is not trustworthy to seconds).

16 Hz steps are probably enough to pump the swing (~50 updates per 3 s swing, derived). They are
not enough to commutate a spinning rotor. At 1 rev/s, one 62.5 ms step is 22° of rotor angle, or
180° electrical at m = 8 (derived).

## What the model would do

A **commutation block** computes the field angle every model cycle (2048 Hz) and feeds sin/cos of it
into the existing DRVMTRX inputs in place of the oscillator. A selector picks the oscillator (today's
drive) or the commutation block. The matrix, pedestals, LIMITs and output switches are unchanged, so
every existing safety step and script still applies.

Inputs, written by worker2 each camera frame:

| channel (proposed) | meaning |
|---|---|
| `OUTS_COMM_THETA` | rotor angle at the frame time, deg (unwrapped) |
| `OUTS_COMM_OMEGA` | angular velocity, deg/s (from the tracker's line fit) |
| `OUTS_COMM_SEQ` | frame counter, for the watchdog |
| `OUTS_COMM_TFRAME` | worker2 time of the frame (added 2026-11-03; see below) |

Settings (EPICS): `OUTS_COMM_M` (8), `_SIGN` (±1), `_LEAD` (electrical deg), `_LATENCY` (s), `_ENABLE`,
`_WDOG_S` (s).

Per cycle: `theta_pred = THETA + OMEGA · τ (+ ½ ALPHA · τ²)`, with τ the frame's age + LATENCY.
The age comes from TFRAME and an offset the block learns from the fastest-arriving updates. Without TFRAME, τ would be
the time since the value landed, which varies by up to 62.5 ms because EPICS values land only on 16 Hz ticks.
That costs p95 ~69° of field angle on a spinning rotor, against ~23° with TFRAME (simulation, `lab_utils/rcg/test_commutate.py`
on branch `feedback-drive`). The full input list and the build steps are in `lab_utils/rcg/SIMULINK_EDITS.md` on that branch.
Then:
`dir` = sign of OMEGA with hysteresis; `psi = SIGN·M·theta_pred + dir·LEAD`; outputs `sin psi`, `cos psi`.
This is the law in `feedback_drive.py` (selftest-validated in simulation), moved into the model.
The prediction runs every cycle, so between camera updates the field turns smoothly with the
predicted rotor instead of stepping.

**Watchdog in the model:** if `SEQ` has not changed for `WDOG_S`, the block ramps its output
amplitude to 0. A stalled worker2 then cannot leave the field pointing somewhere stale.

## How the angle gets in: the open question

| route | update | delay | cost |
|---|---|---|---|
| EPICS (as now) | 16 Hz into the model, but the prediction fills in between | ≥ 0–62.5 ms + write; total unknown | none; model change only |
| Analog: worker2 → USB DAC → spare ADC on cymac1 (angle as two voltages, sin/cos) | every camera frame, 50 Hz | camera + tracking (~20–30 ms, estimated) + DAC | **purchase** + wiring; needs a free ADC channel |
| From a sensor already in the model (LES) | 2048 Hz | ~0 | research: can rotor angle be extracted from LES in real time? unknown |

**Suggested order (Claude's):**
1. Build the block with EPICS inputs. It is already a gain: smooth prediction instead of 16 Hz steps,
   plus the in-model watchdog.
2. Measure how far it gets (F2/F3).
3. Add the analog path only if commutation at speed fails.

## Test plan (outputs off first, as F1)

1. Build and restart on cymac1 (Molly or Alma; like the 09-08 DRVMTRX change). The selector defaults
   to the oscillator, so today's drive is unchanged.
2. Outputs off, replay tracker publishing: worker2 writes THETA/OMEGA/SEQ. Check against
   `OUT_DQ` and a 2048 Hz test point:
   - the field follows the predicted angle smoothly;
   - the watchdog zeroes the field when worker2 stops;
   - the electrode command stays within 0–12800.
3. Then F2 (lead scan, outputs on) through the new path.

## What Alma's y1dmd model already does (read from `y1dmd.mdl`, 2026-11-02; wiring read by Claude, part semantics not verified)

Copies are on Dropbox `Microspheres/TFINER/data/models/`: `y1dmd.mdl`, `y1rds.mdl`, and the RCG library `CDS_PARTS.mdl`.
- **`PARTICLE/PLL`** multiplies a sensor input by the COS output of a `cdsOscSetPhase` and filters
  it (`FILT`). The scaled result plus a nominal frequency goes to `freq`; a filter `INT` feeds the
  oscillator's single input through a unit delay.
- **What `cdsOscSetPhase` actually does (RCG source `OscSetPhase.pm`, advligorts 5.5 tree on worker2;
  Dropbox `data/models/rcg_osc/`).** Its one input is a **time offset in seconds**. It is read **only when
  the EPICS `FREQ` setting changes**, and then sets the phase to `2π·f·(cycle GPS time − input)`. In
  between, the oscillator free-runs at `FREQ`. With TRAMP ≤ 0 this variant applies the new phase at
  once; plain `cdsOsc` waits for the next GPS second. **It cannot follow an angle that changes every
  cycle,** and its frequency still arrives through EPICS (16 Hz). (Corrects Claude's earlier reading.)
- **`PARTICLE` phase detection.** An input ("charge in") is demodulated against a digital LO (`DIGLO`
  cos/sin) into I and Q. **`cdsAtan2`** gives the phase (`PHI`) and `cdsSqrt` the amplitude (`CHARGE`).
  That is the template for extracting an angle from a periodic sensor (e.g. LES) in real time.
- **`PARTICLE/SPIN`, a separate oscillator with sin/cos outputs** (`spinS`, `spinC`), which looks like
  her rotating-field drive.
- Other parts in the library that may help: `cdsUnwrapPhase`, `cdsDemodRotate`, `cdsEpicsIn`,
  `cdsProduct`, `cdsFunctionCall` (user C).

Consequence for this proposal (interpretation, not approved):
- No stock part gives sin/cos of a phase computed every cycle.
- The clean route is a **`cdsFunctionCall`** (user C, ~20 lines). It reads THETA/OMEGA/SEQ (via
  `cdsEpicsIn`) and every cycle computes the predicted ψ, the watchdog and sin/cos, outputting sin ψ
  and cos ψ to DRVMTRX.
- Possible but fiddly: a stock-part rotator (rotate a unit vector by a small angle per cycle with
  `cdsProduct`/sum blocks, renormalise with `cdsSqrt`).
- Alma's `cdsAtan2` phase detection on demodulated I/Q stays useful if a sensor-based angle is ever wanted.

## Questions for Molly and Alma

- Is a model change and restart acceptable now? Who builds it?
- Are there free ADC channels on the cymac1 I/O chassis, for a possible analog angle path?
- Is a `cdsFunctionCall` (user C) acceptable in y1rds, and who reviews the C?
- Can a 2048 Hz test point of `OUTS_V{n}_OUT` be read over NDS on worker2? That would settle whether the
  post-step ringing in `OUT_DQ` is only the DAQ's decimation filter.
