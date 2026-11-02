# Feedback drive: handoff

**Goal:** spin the rotor up with the stator by pointing the field from the camera's live angle,
instead of rotating it at a fixed rate. Serves the spin-up directive (`../measurement_objective.md`).
- **Branch:** `feedback-drive`.
- **Plan:** gates F0–F4, proposed 2026-11-02. Molly approved trying the no-model-change route first;
  if it fails, the next step is a front-end model change.
- **Background:** the C2 results it builds on are in `../analysis/c2_20261102/README.md`.

## Current state (2026-11-02)

- **F0 (design and code, Mac): built.** Selftests pass; not yet run on worker2.
  - `feedback_drive.py`: the controller. Its `selftest` uses a simulated rotor and covers
    11 checks: pump/damp, the lead scan, over the top, latency, chatter.
  - `feedback_f1_check.py`: the F1 scorer, with a synthetic selftest.
  - Stub-EPICS runs pass all applicable checks:
    - bring-up order, with the pedestal before any AC;
    - FREQ 0 written with TRAMP 0, then a 1.1 s wait;
    - no gain until a fresh angle arrives;
    - teardown: the gains ramp out, the matrix is restored, the offsets go to 0, and the
      output bit is cleared only after the pedestal ramp.
  - `../camera_utils/tracking/live_blob_track.py` gets two new flags: `--publish HOST:PORT`
    (UDP, one datagram per frame) and `--replay-realtime`.
- **F1 ran 2026-11-02 (worker2 agent; outputs off; report in Dropbox `data/feedback/`): FAIL.**
  Measured from `OUT_DQ` FE 1477701634–781 against log `feedback_1477686313.csv`:
  - **Field size and shape:** a clean three-phase pattern, size 6400 (5–95% range 6346–6457).
    The three pedestals now ramp together, with no differential field during the ramp.
  - **Timing:** the measured field follows the commanded sequence with coherence 0.9 (first half)
    and 0.8 (second half), but **~2.6 s late**. That is relative to the loop-start clock pair, which
    is good to ~1 s, so the real delay is ~1.5–2.6 s. Feedback needs ~0.04 s.
  - **Update steps:** 7984 field steps for 3006 commanded updates, so updates are not landing as
    single atomic steps.
  - **Out of range:** after each step the outputs ring for several samples, and transients
    reached V2 −1458 and V4 14567, outside the amplifier input range 0–12800. Outputs were off,
    so nothing reached the chamber. **Do not run F2 like this.**
  - The worker2 loop itself was fast: p99 13 ms.
  - **Clean-start fix:** the echoed order is right. The no-glide check is not yet scored.
- **Cause: not established.** One candidate (assumed, not checked): the front end takes in EPICS
  setpoints at a fixed slow rate, so 200 non-blocking writes/s queue up. If so, *any*
  camera→EPICS→front-end loop is limited to that rate. That includes option 2 (the model
  change) if the angle reaches the front end by EPICS. The possible check is an F1 rerun at a low,
  paced update rate (e.g. 10 Hz, waiting on each write), to see whether the delay drops to ~0.1 s.
  That is Molly's call.

## How it points the field (no model change)

The front-end oscillator has no phase input. A FREQ change waits for the next GPS second and
restarts at phase 0 (RCG cdsOsc, LIGO-T080135 §7.6.3). So the controller does three things:
- It freezes the oscillator at FREQ 0, where SIN = 0 and COS = COSGAIN.
- It points the field with DRVMTRX column 2, with TRAMP 0, so each load is a step:
  `SETTING_n_2 = cos(psi + phi_n)`, with phi = 0 / −120 / −240 for V2 / V4 / V3.
- It updates once per camera frame: three SETTING writes plus LOAD_MATRIX, sent without waiting.

A field *direction* is sent each frame; the waveform is not streamed.

**Control law:** `psi = sign·m·theta_pred + dir(w)·lead`. In words:
- `theta_pred` is the angle predicted ahead by `--latency`, from a line fitted to the last 5 frames.
- `dir(w)` is the sign of the velocity, with a 6°/s hysteresis.
- `sign = −1` follows from the board direction measurement (assumes the 08-24 channel map).
- `m = 8`.
- The lead that pumps is unknown, and the F2 scan finds it. The simulation suggests 45° for a
  V² coupling to an m = 16 rotor pattern, and 90° for a coupling linear in V (derived).

## Gates (proposed 2026-11-02; pass marks for Molly to edit)

| Gate | Where | What | Pass |
|---|---|---|---|
| F0 | Mac | design + code + selftests | done (above) |
| F1 | worker2, **outputs off** | loop on a replayed video; `OUT_DQ` vs the commanded field | `feedback_f1_check.py`: field direction within 5° on ≥ 99% of samples; ≥ 99% of updates seen; field size within 1%; worker2 loop p99 ≤ 15 ms |
| F2 | outputs on, rotor swinging ±10–30°; both lights on and median ncc ≥ 0.9 over 30 s before starting (the watchdog trips at 0.8; the ring-down recording's lighting gave a median of 0.84) | lead scan `--scan default` (45, −45, 90, −90, 135, −135, 0, 180; 10 s each) | one lead grows the swing and its opposite shrinks it, in two scans. If no lead moves the swing, repeat with `--sign 1` before concluding anything (`sign` assumes the 08-24 channel map) |
| F3 | outputs on | pump at the best lead | ≥ 10 consecutive full turns one way |
| F4 | outputs on | raise the speed | Molly's target |

**F1 does not measure the absolute latency.** The front-end clock is read only to 1 s and drifts
~1 ms/s, so the fit mixes the clock offset with the latency. The camera-to-field delay is estimated
at 30–45 ms (not measured), and `--latency` is tuned in F2. In simulation, prediction is essential:
without it the rotor never gets over the top (derived, `selftest`).

## F1 runbook (worker2; nothing reaches the chamber)

1. `cd ~/rds-code/Decay-Sail && git fetch && git checkout feedback-drive && git pull`. This branch
   includes `drive-gps-second`, the 1.1 s clean-start wait.
2. `python3 lab_utils/feedback_drive.py selftest` → `SELFTEST PASSED`.
   Then test the clean start, outputs off, as in `DRIVE_LOCK_HANDOFF.md` step 0:
   `cd lab_utils && python3 stator_osc_drive.py hold --felec 0.1 --amp 6400 --duration 20 --live`.
   Check that the echoed order is DRV_TRAMP←0, DRV_FREQ←0.1, a 1.1 s wait, DRV_TRAMP←5, then the gains.
   Note its front-end GPS lines; the OUT_DQ fetch in step 6 should cover it too.
3. Terminal 1 replays a recorded video in real time (no camera; the rotor is not involved):
   ```
   cd camera_utils/tracking && python3 live_blob_track.py --replay /home/controls/stator_detent/output_basler_gps1477428272.avi --replay-realtime --centre 132.3,180.6 --outdir /tmp/f1 --snapshot "" --publish 127.0.0.1:5005
   ```
4. Terminal 2, within ~1 min, with **no** `--enable-outputs`:
   `cd lab_utils && python3 feedback_drive.py run --lead 45 --duration 60 --live`
   (run `feedback_drive.py` and `stator_osc_drive.py` from `lab_utils/`)
   - It prints `tracker heard`, then `loop start, front-end GPS …`, then `end of run`.
   - Teardown should end with offsets 0.
   - Note both front-end GPS lines and the log path (`~/stator_detent/feedback_<gps>.csv`).
5. `stator_osc_drive.py status` should show gains 0, DRVON 0, the forward matrix and outputs off.
   DRV_FREQ is left at 0; the next `stator_osc_drive.py` run jumps it cleanly.
6. Fetch `Y1:RDS-OUTS_V2,V3,V4_OUT_DQ` from the loop start − 5 s to the end + 5 s
   (`batch_fetch.fetch_channel`), then rclone them and the log to `Dropbox:Microspheres/TFINER/data/feedback/`.
7. `git checkout main`.

Then, on the Mac: `python3 lab_utils/feedback_f1_check.py LOG V2.h5 V3.h5 V4.h5`, plus the
no-glide check on the clean-start hold (`../analysis/c2_20261102/c2_checks.py` part 4 method).
Also check in OUT_DQ whether the three pedestals now ramp together. They are written back-to-back;
in C2 sequential writes staggered them by up to 125 ms (`c2_checks.py` part 6 does this check).
If check 2 sees only ~1 step for many commanded changes, the LOAD_MATRIX record probably acts
only on a 0 → 1 edge: rerun step 4 with `--load-toggle`.
