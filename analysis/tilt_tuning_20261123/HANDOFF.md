# Tilt tuning to lower the drag (started 2026-11-23)

Goal (Molly): bring the drag back to the Sept/Oct level (tau ~82 min at 0.5 Hz) by adjusting the chamber tilt stage under
vacuum, measuring gamma after each step. Labels: M measured, D derived, A assumed. Interpretations not approved.

## Why (evidence)

- **Drag doubled between 2026-10-11 and 2026-11-12 (M).** gamma at ~0.435 Hz: 224-229 uHz (Sept 13, Oct 11, LES) vs
  483-493 uHz every November night (tracker). No usable coasts in the gap. `analysis/drag_timeline_20261123/` (agent
  worktree output, not yet merged).
- **The added drag is friction-like (D).** Sept/Oct gamma is flat with speed (viscous, ~175-186 uHz); November gamma rises
  as speed falls: gamma = a + b/f with b ~7-15 (Sept/Oct) vs ~130-280 uHz*Hz (Nov), i.e. a speed-independent torque
  ~1e-14 N m, ~70 % of the drag at 0.435 Hz. Viscous part a looks unchanged (11-21 only).
- **Ruled out (M/Molly):** spin-up method (11-21 was a laser spin-up and shows the doubled drag; Sept/Oct were
  electrostatic then laser). Electrodes: Molly measured them grounded with a multimeter before the runs (open: same state
  as during coasts? AC ripple not checked).
- **Gas unlikely (D):** chamber ~1e-7 mbar (Molly, 2026-11-23, not logged continuously). In a similar diamagnetic rotor
  (arXiv 2506.03803, graphite, electrodes underneath) gas damping falls below the intrinsic floor under ~3e-5 mbar; their
  residual damping is eddy currents from spin-axis wobble, measured at 5-15 Hz, not our 0.5 Hz.
- **Candidates in the gap:** 10-15 rebuild (new tilt stage, chamber off the table, board and magnet centred), 10-26 chamber
  on the stage, 10-27 shims, 11-11 HV amp DC-coupled, the white paint blob (date: ask Molly).
- **Hypothesis (A, not approved):** off-centre paint blob x tilted rotor axis = a once-per-turn gravitational hill; the hill
  (and any loss in it) may set the friction-like drag. The hill is exactly once per turn and identical in both directions.

## Hardware

- Chamber sits on a 125 x 125 mm tilt stage (eBay, Chinese drawing), two corner thumbwheels "0.25/圈" = 0.25 per turn,
  assumed mm per turn -> ~0.13 deg per turn with a ~110 mm lever arm (D). Check: one full turn vs the bubble level on the
  top flange. Wheels tilt about diagonals. Names (Molly, 2026-11-23): **X** = front-corner wheel (by the post, IMG_1881); **Y** = back-corner wheel by the pump bellows (IMG_1882; reach in without leaning on the bellows or the Thorlabs mount).
- **Units: holes.** Each wheel has 6 holes round its rim (Molly, 2026-11-23): 1 hole = 1/6 turn ~0.02 deg, 3 holes = 1/2 turn ~0.07 deg (D, assuming 0.25 mm/turn). Give every move in holes (e.g. "X +3 holes"); backlash: finish each move with a + turn (going -, overshoot 1-2 holes then come back +).
- Molly marks each wheel (pointer + zero mark on the stage, +/- direction). Log turns from today's start position.
- Camera, laser and LES optics are on the table, not the stage: tilting moves the rotor in the view. Watch r_px and ncc.
- Turn wheels only between steps (rotor coasting slowly or at rest), never during a spin-up or brake. Always finish a move
  in the same direction (backlash).

## Readout (`tilt_readout.py`, this folder; numpy only, reads files only)

    python3 tilt_readout.py --run-dir <outdir> --note "X +3 Y 0"     # newest finished coast -> one line + tilt_log.csv

gamma at 0.465 Hz (band 0.44-0.49, quadratic in ln f, jackknife), hill depth (mean detrended w^2 profile, J), h1_J/h1_deg
(once-per-turn hill size and phase), ncc, dropped turns, r_px. Tested on all 80 coasts of 11-22: gamma matches
g3_frozen_test to < 0.05 uHz; 0.2-1.5 s per coast. Baseline scatter coast to coast (`baseline_1122.json`, M):

| quantity | 11-22 mean | sd per coast | a real change (3 sd) |
|---|---|---|---|
| gamma | 454.8 uHz | 3.9 uHz (+ dir ~5.5 uHz above -) | > 12 uHz (compare same direction, or pair means) |
| depth_J | 6.571e-11 J | 1.6e-13 (0.24 %) | > 0.5e-12 (0.7 %) |
| h1_J | 5.211e-11 J | 3-5e-14 (0.08 %) | > 1.5e-13 (0.3 %) |
| h1_deg | 162.8 deg | 0.05 deg | > 0.15 deg |
| r_px | 23.35 px | 0.004 px | > 0.02 px (view moved) |

## Procedure (one step = one coast pair, ~12 min; Molly turns the knob between steps, worker2 waits for her "go")

On worker2, each step: `coast_series.py --spin-fast --coast 300 --pairs 1 --outdir ~/spinup/2026-11-23/tilt/step_NN --live`
(fast-handover branch, laser 0, tracker headless, no --show): spin-up from rest to 0.5 Hz (+), 5-min coast, reversal to 0.5 Hz (-), 5-min coast, final brake to rest; Molly turns the knob only with the rotor at rest. Then `tilt_readout.py --run-dir <step dir> --coast O01/O02 --tracker-csv <the running tracker CSV> --note "X .. Y .."`.
1. Baseline: 2 steps at the start position.
2. Knob X +3 holes, 1 step. Knob X to -3 holes (go to -4, back +1), 1 step.
3. Same for knob Y. From the four moves, see how depth, h1_J and h1_deg move per knob; if the hill behaves like a tilt
   arrow, estimate the X,Y combination that shrinks it and go there.
4. Halve the step near the best point; confirm with 2 steps. Steer by gamma; the hill numbers only guide.
Stop and re-centre the tracker if ncc falls below ~0.8 or r_px moves by > 0.5 px.

## Tracking (required, every step)

- `--note` always carries BOTH wheels' absolute positions from today's zero marks, in holes, plus the move just made: `"X +3 Y 0; move X +3"` (going -: `"X -3 Y 0; move X -6 (to -7, back +1)"`). The positions are the record; the move is a check.
- worker2 appends each readout to `~/spinup/2026-11-23/tilt/tilt_log.csv` (pass `--run-dir` per step but the same log:
  run the readout with `--run-dir ~/spinup/2026-11-23/tilt/step_NN`; it writes `step_NN/tilt_log.csv`, so also `cat` that
  line into the shared log) and sends both lines to the tuning session; uploads `spinup/2026-11-23/tilt/` at the end.
- The tuning session fills the table below after every step (and commits it with Molly's OK at the end), with the next
  move and why.

| step | time | X (holes) | Y (holes) | gamma + (uHz) | gamma - (uHz) | mean | depth_J | h1_J | h1_deg | ncc min | r_px | next move / why |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 11-22 ref | | 0 | 0 | | | 454.8 +- 3.9 | 6.571e-11 | 5.211e-11 | 162.8 | 0.83 | 23.35 | baseline from 80 coasts |
| 11-23 O19 (nd2_fast, laser ON, readout test) | ~13:45 | 0 | 0 | 459.1 | | | 6.542e-11 | 5.177e-11 | 162.68 | 0.833 | 23.33 | + dir as expected; h1_J -0.65 % vs 11-22 (> 3 sd), others within limits. Use today's baseline steps as the reference |
| 01 (baseline 1) | 14:04-14:17 | 0 | 0 | 459.18 +- 1.63 | 456.58 +- 0.95 | 457.9 | 6.511/6.515e-11 | 5.174/5.169e-11 | 162.77/162.69 | 0.832 | 23.35/23.34 | gamma = 11-22 (+3.1, < 12). Hill smaller than 11-22: depth -0.9 %, h1_J -0.8 % (both > 3 sd; matches O19), h1_deg same. Cause not known. Next: step 02, no turns (baseline 2) |
| 02 (baseline 2) | 14:25-14:36 | 0 | 0 | 459.93 +- 0.75 | 455.72 +- 0.71 | 457.8 | 6.541/6.521e-11 | 5.181/5.172e-11 | 162.76/162.75 | 0.832 | 23.34/23.34 | Repeats step 01. Today's reference (steps 01-02, 4 coasts): gamma + 459.6, - 456.2, mean 457.85; depth 6.522e-11 (sd 1.3e-13); h1_J 5.174e-11 (sd 5e-14); h1_deg 162.74 (sd 0.04). Next: X +3 (first probe) |
| 03 (X probe +) | 14:48-15:06 | +3 | 0 | 437.37 +- 2.35 | 433.08 +- 0.70 | 435.2 | 6.749/6.791e-11 | 4.628/4.639e-11 | 157.09/157.09 | 0.834 | 23.08/23.08 | gamma -22.6 uHz (~5 %, > 3 sd), real. h1_J -10.5 %, h1_deg -5.65 deg, depth +3.5-4.1 % (depth up while h1 down: not explained). r_px -0.27 px (over half the 0.5 px stop). ncc med 0.931 (was 0.954). Coasts ended at 0.456/0.449 Hz (lower drag), band still covers 0.465. Next: X -3 (to -4, back +1), per plan: gives the X slope over 6 holes and checks linearity; r_px should swing the other way |
| 04 (X probe -) | 15:11-15:33 | -3 | 0 | 488.4 +- 0.6 | (reversal failed) | (+ only: +28.8 vs + ref) | 6.75e-11 | 5.80e-11 | 167.55 | **0.799** | **22.55** | STOP: r_px -0.80 px, ncc_min 0.799. gamma (+) 437 / 460 / 488 at X +3 / 0 / -3: monotonic, ~ -8.5 uHz per hole. h1 vector moves linearly with X (~0.25e-11 J per hole). r_px fell at BOTH X +3 and X -3 (not symmetric: not explained). O02 reversal stalled (first today), cause not known. Next (Molly chose, 15:40): X +3 back to 0, step 05 = return-to-zero check, no re-centre |
| 05 (return to 0) | 15:42-15:58 | 0 | 0 | 459.29 +- 0.67 | 456.27 +- 1.26 | 457.8 | 6.527/6.554e-11 | 5.226/5.225e-11 | 163.10/163.03 | 0.830 | 23.36/23.36 | X 0 reproducible: gamma within 0.1 uHz of baselines; r_px back (the drift follows the tilt, not time; r_px fell at both X +-3, so X 0 sits near its maximum: not explained). h1 +1 %, +0.3 deg (stage returns to within ~0.2 hole, D). Reversal OK again. Next: Y +3 |
| 06 (Y probe +) | 16:01-16:18 | 0 | +3 | 433.83 +- 0.79 | 429.43 +- 0.73 | 431.6 | 8.072/8.101e-11 | 6.226/6.225e-11 | 163.47/163.42 | 0.806 | 24.07/24.08 | gamma -26.2 uHz (real, whole-turn timing). Hill numbers SUSPECT (tracker centre off): h1_J +20 %, depth +24 %, but pre-launch minus coast r_px = -2.4 px (steps at 0,0 ~0; X+3 +0.3; X-3 +1.0), suggesting a centre offset of >= 2.4 px on r 24; a 10 % once-per-turn angle error fakes h1 ~ 2 x 0.1 x 1/2 I w^2 ~ 0.9e-11 J (I 1.1e-11, 0.465 Hz; D, rough), comparable to the +1.05e-11 rise. Same caveat on X-probe hill numbers and the "X ~ +16 holes" hill estimate. r_px +0.72 in coast: STOP limit hit (Molly to decide); ncc min 0.806. Reversal OK. Next: Molly's call (re-centre; skip Y -3?): she chose re-centre + X +3 Y +3 (notes below the table) |
| 07 (diagonal; pin 2 = 129.36,178.80) | 16:31-16:48 | +3 | +3 | 417.81 +- 0.91 | 406.82 +- 0.70 | 412.3 | 5.891/5.904e-11 | 4.758/4.753e-11 | 164.08/163.97 | 0.834 | 23.37/23.36 | gamma -45.5 uHz vs X 0 Y 0; prediction (X and Y add) 409: within 3.3, so they add. + minus - split 11.0 uHz (3-4 at earlier steps; not explained). Pin offset A1 0.32 px (re-centre held). Hill (well-centred, new pin; not comparable with steps 03-06): depth -9.7 %, h1_J -8.0 %, h1_deg +1.3 deg vs baseline. Next: X +6 Y +6 (another +3 each along the diagonal; predicted ~367 if still linear), re-centre first to predicted pin 129.80,181.48 |
| 08 (diagonal; pin 3 = 129.80,181.48) | 16:54-17:10 | +6 | +6 | 378.11 +- 0.84 | 378.45 +- 2.04 | 378.3 | 5.044/5.012e-11 | 4.326/4.322e-11 | 167.65/167.73 | **0.702** (O01 brief dip; O02 0.817) | 23.43/23.43 | gamma -34.0 vs step 07 (first diagonal step -45.5); prediction (linear) 367: 11 above, so mild flattening. +/- split gone (0.3 uHz; 11.0 at step 07, 3-4 earlier): not explained. Pin off 0.77 px (prediction missed by -0.72,-0.27). ncc_min 0.702 below the 0.8 stop rule: one brief dip, 0 dropped turns, median 0.946 (flagged to Molly). Coasts end at 0.459 Hz, near the 0.465 evaluation point: lengthen coasts. Next: X +9 Y +9, pin 129.12,183.57, --coast 420 |
| 09 (diagonal; pin 4 = 129.12,183.57; coast 420 s) | 17:16-17:36 | +9 | +9 | 347.15 +- 0.19 | 343.93 +- 0.46 | 345.5 | 5.515/5.534e-11 | 5.078/5.077e-11 | 171.79/171.71 | 0.832 | 23.51/23.52 | gamma -32.8 vs step 08 (steps along the diagonal: -45.5, -34.0, -32.8: still falling, ~ -11 uHz per hole on each knob); -112 (-24 %) vs X 0 Y 0; tau 48 min. +/- split 3.2. New tracking rule: all pass (0 dropped, median 0.953, 0.00 % < 0.8, A1 0.43 px). 420 s coast spans the band (144 turns). Hill (well centred): depth -15 %, h1_J -2 %, h1_deg +9 deg vs baseline. Next: X +12 Y +12, pin 130.02,186.06, coast 420 |
| 10 (diagonal; pin 5 = 130.02,186.06; coast 420 s) | 17:42-18:03 | +12 | +12 | 321.18 +- 0.29 | 313.85 +- 0.23 | 317.5 | 4.926/4.931e-11 | 4.429/4.431e-11 | 174.74/174.75 | 0.834 | 23.39/23.39 | gamma -28.0 vs step 09 (diagonal: -45.5, -34.0, -32.8, -28.0 per +3/+3: still falling, maybe slowly flattening); -140 (-30 %) vs X 0 Y 0; tau 52-53 min. +/- split 7.3. Tracking: all pass (A1 0.27 px, 0.00 % < 0.8). Hill: depth -24 %, h1_J -14 %, h1_deg +12 deg vs baseline. Next: overnight long coast here (Molly's go) |

Pin-offset fits (worker2, 2026-11-23 ~16:20, M; r = r0 + A1 cos(a - phi) per coast, pin (128.62,176.54)): orbit radius r0 = 23.35 px in
every step (no real radius change). A1 = 0.3 px at X 0 (steps 01, 05), 1.72 px at X +3, 2.21 px at X -3, 1.90 px at Y +3: the view
shifts ~0.6 px per hole, X along (-1.1,+1.3) px per +3 holes, Y along (+1.8,+0.6). So the readout's r_px (median r) swings are pin-offset
artefacts, not radius changes, and the hill numbers at the probes are partly artefact (once-per-turn angle error up to A1/R = 4-5 deg).
Gamma is much less exposed. Fix options: restart the tracker with a fitted --centre (~1 min, between steps), or re-fit the angle offline per coast.

Molly 2026-11-23 ~16:20: re-centre the tracker before step 07 (pin predicted 129.36,178.80 assuming X and Y shifts add) and after any
step with A1 > ~1 px (replaces the r_px 0.5 px rule); skip the Y -3 probe; step 07 = X +3 Y +3. Steer by gamma; hill numbers secondary.
Molly 2026-11-23 ~17:15: new tracking stop rule (replaces "ncc_min < 0.8"; single-frame dips are harmless, e.g. step 08 O01 0.702 with
0 dropped turns): stop or re-centre if any dropped turns, ncc median < ~0.90, > ~1 % of coast frames with ncc < 0.8, or pin offset A1 > 1 px.
Thresholds are judgement, untested; loosen if one trips while the gamma fit is clean.
Prediction for step 07 if the X and Y effects add: gamma mean ~409 uHz (457.85 - 22.6 - 26.2); a miss > 12 uHz means they don't add.

## State (2026-11-23 ~18:10) — start here next session

- **Knobs now: X +12, Y +12 holes** (2 full turns each from today's zero marks, all moves finished on +). Best gamma so far:
  317.5 uHz (pair mean, step 10) vs 457.85 at X 0 Y 0 (-30 %); target ~225 (Sept/Oct). Still falling ~28 uHz per +3/+3
  diagonal step, no minimum seen. X and Y effects add (step 07).
- **Tracker:** pin 130.02,186.06 (step 10 fit says 129.75,186.10, A1 0.27 px). Each +3/+3 moves the view by ~(+0.2..0.5, +2.4) px:
  re-centre BEFORE each move to the predicted pin (last fitted centre + last measured shift). Tracking stop rule: see the
  Molly ~17:15 note above (A1 > 1 px, dropped turns, ncc median < 0.90, > 1 % frames < 0.8).
- **Overnight (Molly approved, go pending at 18:10):** one + spin-up to 0.5 Hz then an 8 h coast at X +12 Y +12, no reversal,
  no final brake, laser 0: `coast_series.py --spin-fast --coast 28800 --pairs 1 --no-final-brake --outdir
  ~/spinup/2026-11-23/tilt/overnight_coast --live` (fast-handover branch; worker2 touches STOP after O01 starts). Purpose:
  gamma vs speed at the tuned position (did the friction-like b/f part shrink?). Needs a g3-style fit on the tracker CSV.
- **Next session:** (1) upload + rclone check of `spinup/2026-11-23/tilt/`; (2) fit gamma(f) on the overnight coast, compare
  with 11-21/11-22 (a + b/f); (3) continue the diagonal: X +15 Y +15 (+3/+3), coast 420 s, re-centre first; halve the step
  when a step gains < 12 uHz; confirm the best point with 2 steps; (4) ND2 laser run only after tuning (Molly's choice tonight).
- Open, not explained: +/- split 11.0 (step 07) and -0.3 (step 08) vs usual 3-4 uHz; step 04 reversal stall (X -3, largest
  pin offset 2.2 px). Which of +/- is CW is not recorded here.
