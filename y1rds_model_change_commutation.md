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

Settings (EPICS): `OUTS_COMM_M` (8), `_SIGN` (±1), `_LEAD` (electrical deg), `_LATENCY` (s), `_ENABLE`,
`_WDOG_S` (s).

Per cycle: `theta_pred = THETA + OMEGA · (time since THETA last changed + LATENCY)`;
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
- **`PARTICLE/PLL`, a phase-locked loop running in the model.** A sensor input is multiplied by
  the output of a VCO, filtered (`FILT`), integrated (`INT`) and fed back through a unit delay into the
  VCO's input. The VCO is **`cdsOscSetPhase`**, an oscillator whose phase or frequency input is a
  *model signal* updated every cycle. That is the part a commutation block needs: sin/cos of a
  computed angle at model rate, without custom C.
- **`PARTICLE` phase detection.** An input ("charge in") is demodulated against a digital LO (`DIGLO`
  cos/sin) into I and Q. **`cdsAtan2`** gives the phase (`PHI`) and `cdsSqrt` the amplitude (`CHARGE`).
  That is the template for extracting an angle from a periodic sensor (e.g. LES) in real time.
- **`PARTICLE/SPIN`, a separate oscillator with sin/cos outputs** (`spinS`, `spinC`), which looks like
  her rotating-field drive.
- Other parts in the library that may help: `cdsUnwrapPhase`, `cdsDemodRotate`, `cdsEpicsIn`,
  `cdsProduct`, `cdsFunctionCall` (user C).

Consequence for this proposal (interpretation, not approved): the commutation block can probably
be built from `cdsEpicsIn` (THETA, OMEGA) → arithmetic → `cdsOscSetPhase` (phase input) → DRVMTRX.
Alma's PLL is also a template for a camera-free option: lock a VCO to a sensor signal that turns
with the rotor.

## Questions for Molly and Alma

- Is a model change and restart acceptable now? Who builds it?
- Are there free ADC channels on the cymac1 I/O chassis, for a possible analog angle path?
- Alma: what exactly are `cdsOscSetPhase`'s inputs (phase, frequency, or both), and what does your
  `PARTICLE/PLL` lock to? Could the same structure commutate our stator?
- Can a 2048 Hz test point of `OUTS_V{n}_OUT` be read over NDS on worker2? That would settle whether the
  post-step ringing in `OUT_DQ` is only the DAQ's decimation filter.
