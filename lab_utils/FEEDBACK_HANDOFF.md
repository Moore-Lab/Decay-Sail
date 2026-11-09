# Feedback drive: handoff

**Goal:** spin the rotor up with the stator by pointing the field from the camera's live angle,
instead of rotating it at a fixed rate. Serves the spin-up directive (`../measurement_objective.md`).
- **Branch:** `feedback-drive`.
- **Plan:** gates F0–F4, proposed 2026-11-02. Molly approved trying the no-model-change route first;
  if it fails, the next step is a front-end model change.
- **Background:** the C2 results it builds on are in `../analysis/c2_20261102/README.md`.

## Current state (end of 2026-11-04): read this first

**Where we are:**
- **Model change paused (Molly):** Problem 1 passed (`WAVEFORM_HANDOFF.md`). The EPICS route is being pushed as far as it goes first.
  `commutate.c` now has a `COMM_TFRAME` input (13 inputs), with `fake_rotor.py` + `fe1_check.py` for FE1.
- **F3 on the EPICS route** (runbook below; results in `../analysis/f3_20261104/README.md`):
  - **Spin-up works,** strongly: over the top in ~5 s.
  - **0.53 rev/s was reached and coasted in band, but the controller never acted.** The field stayed off above push_max.
  - **Braking failed twice** (live 2, brake-only 1). The rotor was left turning −0.6 rev/s, drive off, at ~21:05Z on 11-04.
- **Measured today:**
  - push angles −54 / +170 at an effective command-to-field delay of **0.10 s** (`../analysis/f3_20261104/push_angles.py`);
  - trap barrier 9.4 rad²/s² at ~−165° from rest, from the coasting;
  - matrix loads land only every ~2nd 16 Hz tick, whatever `--mtramp` is (pre-flights 2 and 3).
- **Brake mechanism** (interpretation, not approved, from the per-push energy table):
  - the controller predicts 0.07 s ahead but the field acts ~0.10 s later;
  - at 60–150°/s that misplaces the field by ~48°;
  - for negative motion, 84–88% of the "brake" pushes then add energy.
- **Tracker setup now** (log 2026-11-04):
  - the camera moved on 11-03; the derived centre (122.8, 179.6) is confirmed;
  - **Stale centre (2026-11-06):** the camera was moved and the tilt stage adjusted after this run, so `--centre 122.8,179.6` no longer fits. Re-derive it (replay check, median ncc ≳ 0.9) and note the rest angle before the next tracked run; candidates from 11-06: (117.5, 165.1) clicked, (119.1, 167.7) automatic, both rotor-body centres (`analysis/rotor_centering/README.md`, "Final state", on `main`; see `docs/STATUS.md`).
  - new light plus the adjusted second light, exposure 15 ms; ncc 0.79–0.98 over 360°;
  - rest angle ~229.8.

**Step 1 (sim vs brake 1), worked 2026-11-04 late, Mac only. Results: `../analysis/f3_20261104/README.md`,
"Simulator check":**
- **Plant model:**
  - `f3_check.TRAP_CU`: joint trap fit, barrier 9.61 at −160°;
  - `COUPLING_HOLD`: per-hold fit against the measured OUT_DQ field; held out on brake 1, R² 0.38; no constant term;
  - `simulate_measured()`, `repro_brake1()`, CLI `python3 f3_check.py repro [--coupling hold|010]`.
- **Open loop** (measured field replayed, `outdq_replay.py` on main): the pumping is reproduced.
  Over the top negative at 5.4–6.0 s (live 5.57 s), of 9 cells each:
  - `COUPLING_HOLD`: 2/9 (and 3/9 positive);
  - with c0 = −0.79 ± 0.51 (undetermined): 3/9;
  - `COUPLING_010`: 3/9.
- **Closed loop:** the failure to brake is reproduced; the swing stays at 0.8–1.0 of the barrier for 20 s. **The 5.6 s tip-over is not**
  (hold coupling 0/12; commanded-fit coupling 5/12 at 10–22 s).
- **Needs Molly:** is "reproduces the failure to brake" enough to gate step 2? The alternative is to require the tip-over time,
  which may not be reachable (the rotor was at 0.82 of the barrier).
- **Also measured:**
  - OUT_DQ timestamps sit 3.3–4.2 s later than LES's (cause unknown);
  - about every second matrix write lands (8 Hz);
  - why closed loop (0/12) is worse than open loop (2/9): not found. Next check: compare the sim's applied field with OUT_DQ
    in window 3 (4.83–5.63 s), where live gained the energy to tip.

**Next (gate: no drive runs until step 2 passes in the measured-model sim):**
1. (Once Molly OKs the step-1 mark.) Score each fix with `simulate_measured` using both couplings, and the tick phase scanned:
   - prediction horizon: the effective delay is known only from the rotor response (fits peak at 0.10 s on commands);
     OUT_DQ can't give an absolute write-to-field delay (timestamp offset). Scan the latency in the sim;
   - not the push angles: −88 / +167 are within 6% / 0.5% of `COUPLING_HOLD`'s best (−76 / +170);
   - brake only mid-swing, with the predicted velocity keeping its sign;
   - a lower brake amplitude, so one mistimed push can't tip the rotor over the top.
   Pass: from brake 1's start, the swing is below 30° within 60 s in every cell.
   Braking from rotation above ~0.45 rev/s is out of reach on this route: the loads (~8 Hz) are too slow for ~3.6 Hz electrical.
2. Then a brake-only run from a coasted-down swing, with Molly's go typed in the worker2 session.

## Earlier state (end of 2026-11-02)

- **EPICS matrix route:**
  - F0 built; F1 and F1b ran on worker2 with outputs off.
  - The field follows the commands, but EPICS writes apply only at 16 Hz (measured).
  - The latency is not measured, and the post-step ringing is probably only the DAQ decimation filter.
- **Model change approved (Molly builds it; `docs/DECISIONS.md` 2026-11-02):**
  - `rcg/commutate.c` (tests: `rcg/test_commutate.py`, all pass).
  - Simulink steps: `rcg/SIMULINK_EDITS.md`.
  - worker2 side: `feedback_drive.py frontend`.
- **Next, 2026-11-03 in the lab:**
  1. The small-swing trap measurement, camera only:
     - quiet the rotor; both lights on; no drive;
     - run `/home/controls/.conda/envs/ueye/bin/python live_blob_track.py --outdir ~/stator_detent --show`
       from `camera_utils/tracking` for ~10 min;
     - rclone the video, its `.csv` and `blob_live` to `dropbox:Microspheres/TFINER/videos/`.
     It gives the trap frequency at small swing (Mac: `analysis/ringdown_20261102/ringdown.py` method).
  2. **F2** through the EPICS route (runbook below; Molly watching).
  3. Then the model change and **FE1**, outputs off (runbook below), on the same day or later.

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
- **F1b (Molly OK 2026-11-02): rerun at a paced rate.** `--rate 10` (the new default) sends at most
  10 updates per second and waits for each write to complete. Same runbook as F1, but run step 4
  as `python3 feedback_drive.py run --lead 45 --duration 60 --rate 10 --live`. Pass: the field follows
  the commands with a delay ≲ 0.15 s (measured by the scorer's lag fit; the clock pair is good only
  to ~1 s, so a clear drop from ~2.6 s is the result that matters), and one output step per update.
  The out-of-range transients may get worse with paced updates, because each step is larger.
  Watch for them in OUT_DQ.
- **F1b ran 2026-11-02 (worker2 agent, outputs off; Dropbox `data/feedback/f1b/`).**
  Measured:
  - **Writes:** 536 updates in 60 s, median interval 117 ms. Each write took 2.4 ms median (p99 8.9);
    frame to written took 11 ms median (p99 18).
  - **Steps:** with the commands shifted by +3.84 s, the measured field angle matches them step for
    step (`scratchpad` plot; reproduce with `feedback_f1_check.py`).
  - **Every output step lands on a 1/16 s grid:** in F1 and F1b, 424/424 and 428/428 step onsets sit
    at the same position within the 62.5 ms tick, and step intervals are multiples of 1/16 s.
    **So the front end applies EPICS-written matrix values only at 16 Hz.** That is the update limit
    of this route, whatever rate worker2 writes at.
  - **Ringing:** after each step the outputs ring (about ±400 counts, decaying over ~12 samples, with
    1000 counts of overshoot). There is no ringing before a step, so the filter is causal. Whether the
    ringing is in the real output or only in the DQ recording's anti-alias filter is not known.
- **Filter state (worker2, read-only, 2026-11-02 ~20:55 UTC; Dropbox `data/feedback/filter_state_2026-11-02.md`):**
  - **Modules:** OUTS_V1..V4 all read SW1R 12 (input, offset), SW2R 768 (limit, decimation, output off),
    GAIN 1, LIMIT 12800. No FM stage is engaged, and the foton file defines no filters for V1..V4.
  - **Rates:** the model runs at 2048 Hz, and `OUT_DQ` is recorded at 1024 Hz.
  - **So the post-step ringing is most likely the DAQ's 2048 → 1024 Hz anti-alias filter (derived, not
    proven):** it is causal, alternates near Nyquist and decays over ~12 samples. The real output
    should step cleanly.
  - **To prove it:** read the module output as a 2048 Hz test point during an outputs-off replay loop.
    Until then, run F2 at `--amp 5000 --pedestal 6400` (range 1400–11400, ±1400 counts of margin). `--pedestal` was
    added 2026-11-02 evening; before that the pedestal equalled `--amp`, which would have left no margin.
- **Correction to the F1 "~1.5–2.6 s late" finding.** That delay, and F1b's 3.84 s, are relative to the
  front-end time read from `Y1:DAQ-DC0_GPS` at loop start. DC0 is the data concentrator, and its
  GPS may itself lag the front end by seconds (assumed, not checked). The 1.2 s difference between
  F1 and F1b matches the front-end clock drift over the 16 min between them (~1 ms/s). **So the true
  camera-to-field delay is not measured.** It is at least the wait for the next 1/16 s tick (0–62.5 ms)
  plus the write time.
- **Verdict on the no-model-change route.** The field direction is right, and updates now land whole
  at 16 Hz (measured). The latency is unknown, and the ringing is unresolved. 16 Hz is probably enough
  to pump the swing: a ~3 s period is ~50 updates (derived). It is not enough for fast spinning.
  A model change is needed for anything faster, and it only helps if the angle reaches the front end
  by a path other than EPICS.

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

## F2 runbook: first outputs-on test, EPICS matrix route (Molly in the lab and watching)

Goal: does pushing along the motion grow the swing, and which lead does it? Pass mark (agreed 2026-11-02):
one lead grows the swing and its opposite shrinks it, in two scans.
1. `cd ~/rds-code/Decay-Sail && git fetch && git checkout feedback-drive && git pull`, then
   `python3 lab_utils/feedback_drive.py selftest` → `SELFTEST PASSED`.
2. Both lights on. Close `grab_basler.py`. Live tracker with publishing, in the `ueye` env:
   `cd camera_utils/tracking && /home/controls/.conda/envs/ueye/bin/python live_blob_track.py --outdir ~/stator_detent --show --publish 127.0.0.1:5005`
   Molly checks the red circle is on the blob. After 30 s, the median ncc must be ≥ 0.9 (the controller's
   watchdog trips at 0.8).
3. **The swing must be ±10–30°.**
   - If the rotor is nearly still, give it a swing first with one C2-style hold:
     `cd lab_utils && python3 stator_osc_drive.py hold --felec 0.1 --amp 6400 --duration 30 --enable-outputs --live`.
     On 2026-11-02 that took the rotor from rest to ~±40°.
   - Then wait ≥ 60 s with the drive off.
   - If it is swinging more than ±40°, wait or record it as is (it decays with τ ≈ 1.5–4 h).
4. **Scan 1:**
   `cd lab_utils && python3 feedback_drive.py run --scan default --dwell 10 --amp 5000 --pedestal 6400 --rate 10 --live --enable-outputs`
   That is 8 leads × 10 s = 80 s. The banner must print `range 1400..11400`, which leaves ±1400 counts of margin
   for the output ringing. Molly watches the window. Ctrl-C stops it with a full teardown.
5. Wait ≥ 60 s with the drive off. **Scan 2:** the same command.
6. If neither scan moves the swing visibly, run one more scan with `--sign 1` (it covers a changed channel map).
7. Stop the tracker. Fetch `Y1:RDS-OUTS_V2,V3,V4_OUT_DQ` over the whole session.
   - rclone to `dropbox:Microspheres/TFINER/data/feedback/f2/`: the video, its `.csv`, `blob_live_gps*.csv`, the
     `feedback_*.csv` logs and the h5 files.
   - Write a raw report: commands, front-end GPS per run, anything odd.
8. `git checkout main`.

On the Mac: swing amplitude per 10 s step from `blob_live` against the lead in the log (growth − decay per pair).

## F3 runbook (EPICS route, Molly OK 2026-11-04): spin up from rest, hold 0.5 rev/s mean, brake

**Target (Molly):**
1. Go over the top from rest.
2. Then for 60 s, every full turn at 0.4–0.6 rev/s, no reversal.
3. Then brake to a swing under 30°.

**Why a mean rate (derived, F2's 1× trap only):** the 4.94 rad/s² once-per-turn trap means going over the top needs ≥0.71 rev/s at the bottom. A slow mean rate is set by the energy, not the speed.

**Controller:** `feedback_drive.py run --f3` (SpeedController).
- It regulates the energy: push along the motion below the band, brake above it.
- It pushes only while |ω| < 0.3 rev/s, with the field off through the fast bottom, so the 16 Hz updates keep up.
- Push angles −88 / +167 come from F2's fit (R² 0.165).
- The camera rotated ~1.9° on 11-03, which shifts the push angles by ~15° electrical (derived, sign not checked).

**Simulation (`f3_check.py sim`; the controller logic only, push angles exact by construction there):**
- Over the top in ~40 s; per-turn 0.43–0.54 rev/s; brake to ±5°.
- Robust to: the staircase (no ramp), +50 ms latency, amp 3000, a trap of 4.0 or 6.0 vs 4.94, and push angles off by 30°.
- **Braking fails if the push angles are off by 60°.** The rotor would then be left turning ~0.5 rev/s for hours (Q ~ 10⁴).

**Tracker match at speed (F2, measured):** median ncc 0.87–0.95 up to 1.17 rev/s, never more than 2 frames in a row below 0.8.

**Pre-flight 1 (2026-11-04, outputs off, fake rotor; Molly's go; Dropbox `data/feedback/f3/preflight/`), measured:**
- The whole EPICS path ran: spin-up, over the top at 17 s, hold, brake, end, clean stop.
- **The matrix ramp works:** each update moves the field linearly over ~1/16 s. Outputs stayed in 2400..10400, with no sample step above 200 counts. F2's out-of-range transients are absent.
- **But at 10 updates/s the field held still ~40% of the time** (a ramped staircase).
- The field went to 0 smoothly whenever the fake speed exceeded 0.3 rev/s.
- **Braking a resting rotor held a constant field.**
- Fixed in a77c6a3: F3 writes 20/s, so each tick's ramp joins the next; the field turns off once braked below ~3°.

**Pre-flight 2 (2026-11-04, outputs off, 16.7 writes/s; `data/feedback/f3/preflight2/`), measured:**
- No spikes; outputs in range.
- The field still ramps over one tick and then holds 1–2 ticks: new matrix loads land only every 2nd–3rd tick.
  (Interpretation, not checked: a LOAD isn't taken while the matrix is still ramping. A ~40 ms ramp may fix it.)
- The fake rotor stopped away from the rest angle and kept a held brake field. Fixed in c3865d9: field off when |ω| < vmin.

**Tracker for F3 (2026-11-04, read-only checks; `data/feedback/f3/tracker_checks/`):**
- The old flashlight had dimmed (ncc 0.80). Molly put in a new light.
- At 15 ms: ncc 0.97, but the spot saturates.
- **At 8 ms: ncc 0.958, no saturation, rest angle 229.9°** (std 0.14).
- **F3 uses `--exposure 8 --centre 122.8,179.6` and `--rest-deg 229.9`.**
- **Stale centre (2026-11-06):** the camera was moved and the tilt stage adjusted after this run, so `--centre 122.8,179.6` no longer fits. Re-derive it (replay check, median ncc ≳ 0.9) and note the rest angle before the next tracked run; candidates from 11-06: (117.5, 165.1) clicked, (119.1, 167.7) automatic, both rotor-body centres (`analysis/rotor_centering/README.md`, "Final state", on `main`; see `docs/STATUS.md`).

Steps (worker2; each `--live` needs Molly's go):
0. `cd ~/wt_wave && git checkout feedback-drive && git pull` (or a fresh worktree), then `cd lab_utils`.
1. **Pre-flight, outputs OFF (rotor untouched): the whole EPICS path with a known rotor.**
   - `python3 fake_rotor.py profile --duration 200 &`
   - `python3 feedback_drive.py run --f3 --amp 4000 --pedestal 6400 --mtramp 0.0625 --rest-deg 227 --live`
     (no `--enable-outputs`; the fake rotor's rest is 227).
   - Fetch `OUTS_V2–V4_OUT_DQ`. Check that the field turns piecewise-linearly between updates, with no 1/16 s staircase and no out-of-range transients, and that it goes to 0 while the fake speed exceeds 0.3 rev/s. That's the first look at how the matrix ramp behaves when an update arrives mid-ramp.
2. **Tracker re-pin (a gate).**
   - A candidate centre from board features is (122.8, 179.6). Check it by replay on a still video: median ncc ≳ 0.9.
   - If that fails: run the F2 prep swing (`stator_osc_drive.py hold --felec 0.1 --amp 6400 --duration 30 --enable-outputs --live`) while recording, then `camera_utils/tracking/centre_from_swing.py`, then replay check again.
   - **The rest angle for `--rest-deg` comes from the tracker** (its angle at rest), not from `centre_from_swing`.
3. **F3 live, starting from rest:**
   - tracker: `live_blob_track.py --exposure 8 --centre 122.8,179.6 --outdir ~/stator_detent --publish 127.0.0.1:5005 --show`
   - drive: `python3 feedback_drive.py run --f3 --amp 4000 --pedestal 6400 --mtramp 0.0625 --rest-deg R --enable-outputs --live`
   - It brakes by itself after the hold, or if it never gets over the top within 180 s. Ctrl-C ramps down safely, but may leave the rotor turning.
4. **Score:** `python3 f3_check.py score <blob_live csv> <feedback log> --rest-deg R`. Upload both, with the OUT_DQ, to Dropbox `data/feedback/f3/`.

## FE1 runbook: after the y1rds model change, outputs off (nothing reaches the chamber)

Preconditions: the model is rebuilt and restarted with the edits in `rcg/SIMULINK_EDITS.md`, and
`commutate.c` is at `/opt/rtcds/userapps/mastqg/src/commutate.c`.
1. **The old path is unchanged:**
   - `cd lab_utils && python3 stator_osc_drive.py status` (forward matrix, gains 0).
   - `caget Y1:RDS-OUTS_COMMSEL Y1:RDS-OUTS_COMM_ENABLE Y1:RDS-OUTS_COMM_WDOG Y1:RDS-OUTS_COMM_AMP` → all 0.
   - Clean-start hold, outputs off: `python3 stator_osc_drive.py hold --felec 0.1 --amp 6400 --duration 20 --live`.
2. **Known-angle source (no camera, no rotor):** `python3 fake_rotor.py profile --duration 100` (also `spin --rev-s 1.2`,
   `swing --amp-deg 80`). It sends a known angle in the tracker's UDP format and writes the truth to `~/fe1/`.
   With it, the front end's field can be scored against the truth with `fe1_check.py` (step 5).
   With TFRAME, `--latency` is the delay from the frame's timestamp to the fastest arrival: use `--latency 0.003` with
   `fake_rotor.py`, whose timestamps are exact. For the camera, use ~exposure/2 + readout (~0.015, assumed; FE1/FE2 measure it).
   Alternatively, a replayed video, as in F1:
   `cd camera_utils/tracking && python3 live_blob_track.py --replay /home/controls/stator_detent/output_basler_gps1477428272.avi --replay-realtime --centre 132.3,180.6 --outdir /tmp/fe1 --snapshot "" --publish 127.0.0.1:5005`
3. **Commutation, outputs off:**
   `cd lab_utils && python3 feedback_drive.py frontend --lead 45 --duration 60 --latency 0.06 --live`
4. **Front-end watchdog test, outputs off:**
   `python3 feedback_drive.py frontend --lead 45 --duration 15 --freeze-at 8 --live`
   It stops sending at 8 s and leaves ENABLE at 1. Pass: the printed `COMM_GAIN` falls to 0 within ~1 s
   (WDOG 0.5 s + 0.5 s ramp) and stays 0.
5. Stop the tracker. Fetch `OUTS_V2,V3,V4_OUT_DQ` over steps 1–4 (npz as `awg_waveform_drive.fetch_dq` writes).
   Score each fake-rotor run on the Mac: `python3 fe1_check.py ~/fe1/truth_<...>.csv <feedback log> <out_dq.npz>`
   (`selftest` passes: it passes a timestamped block and fails the EPICS staircase and the arrival-time prediction). rclone them with the `feedback_*.csv` logs to
   `dropbox:Microspheres/TFINER/data/feedback/fe1/`, with a raw report. Then `git checkout main`.

Pass marks (Mac, proposed):
- The OUT_DQ field angle turns smoothly between the 16 Hz updates (≤ 2° per sample, no 1/16 s staircase).
  At each update a correction is applied, by design. `test_commutate.py` gives median 8° and 95th percentile
  26°, so the pass is 95% < 30°. Direction flips (2 × lead) are excluded.
- It follows −8·θ + lead from the log, with coherence ≥ 0.9 at the best lag.
- The field size equals `--amp` within 1%.
- The step 4 field drops to 0 within 1 s of the freeze.
- The step 1 hold starts at 0.1000 Hz with no glide.
