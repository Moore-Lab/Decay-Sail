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
| 11 (2026-11-24; diagonal; pin 6 = 130.10,188.50; coast 420 s) | 11:09-11:33 | +15 | +15 | 307.45 +- 0.22 | 302.62 +- 0.66 | 305.0 | 5.031/5.040e-11 | 4.534/4.534e-11 | 178.68/178.67 | 0.830 | 23.45/23.45 | gamma -12.6 vs step 10 (diagonal: -45.5, -34.0, -32.8, -28.0, -12.6 per +3/+3: gain halved, at the 12 uHz threshold); -152.9 (-33 %) vs X 0 Y 0; tau 54-55 min. +/- split 4.8. Tracking: all pass (0 dropped, median 0.948, 0.00 % < 0.8, A1 0.05-0.06 px; predicted pin within 0.05 px). Next: single-axis probes from here (pairs) to see which knob still helps: X +18 Y +15 first, then Y probe |
| 12 (X-only probe; pin 7 = 128.85,190.15; coast 420 s) | 11:45-12:08 | +18 | +15 | 298.85 +- 0.59 | 292.56 +- 0.18 | 295.7 | 5.755/5.744e-11 | 4.958/4.959e-11 | -178.48/-178.43 | 0.833 | 23.45/23.46 | gamma -9.3 vs step 11 from X +3 alone (the +3/+3 step before gave -12.6, so if effects still add Y contributed only ~-3); -162 (-35 %) vs X 0 Y 0. +/- split 6.3. Tracking: all pass (A1 0.18 px; X-only shift (-1.22,+1.44) px). Hill depth +14 %, h1_J +9 % vs step 11 (gamma not steered by these). Next: Y-only probe X +18 Y +18, pin 130.75,190.90 |
| 13 (Y-only probe; pin 8 = 130.75,190.90; coast 420 s) | 12:4x-13:26 | +18 | +18 | 294.39 +- 0.39 | 287.07 +- 0.28 | 290.7 | 4.900/4.888e-11 | 4.113/4.125e-11 | -177.22/-177.23 | 0.821 | 23.44/23.44 | gamma -5.0 vs step 12 from Y +3 alone (X +3 alone gave -9.3; sum -14.3 vs -12.6 for the last +3/+3, so still roughly additive): both knobs still help, X about 2x more per hole; -167 (-37 %) vs X 0 Y 0. +/- split 7.3 with ext_T equal within 0.03 C in both coasts. Tracking: all pass (A1 0.44 px). Hill depth -15 %, h1_J -17 % vs step 12 (h1 lowest so far). TSP01B over steps 01-13: ext_T cycles 23.2-24.7 C (HVAC-like), slow drift +0.4 C, RH 48 -> 17 %; pair means and splits do not follow ext_T (M, worker2). Next: step along the measured gradient, X +21 Y +20 (X +3, Y +2), pin 130.0,193.0 |
| 14 (gradient X +3 Y +2; pin 9 = 130.00,193.00; coast 420 s) | 13:30-13:51 | +21 | +20 | 283.49 +- 0.41 | 279.08 +- 0.44 | 281.3 | 6.058/6.044e-11 | 4.667/4.669e-11 | -174.49/-174.51 | 0.817 | 23.52/23.52 | gamma -9.4 vs step 13 (additive prediction from the probes -12.6; got ~75 % of it: still falling); -177 (-39 %) vs X 0 Y 0; tau 59-60 min. +/- split 4.4, ext_T equal within 0.02 C. Tracking: all pass (A1 0.24 px). Hill depth +24 %, h1 +13 % vs step 13 (observed pattern: X moves deepen the hill, Y moves shallow it). Next: same gradient step X +24 Y +22, pin 130.1,195.3. Threshold changed (Claude, 2026-11-24): with the probes 2 steps old and the gain 9.4, keep stepping; go to smaller steps / back off when a step gains < ~5 uHz |
| 15 (gradient X +3 Y +2; pin 10 = 130.10,195.30; coast 420 s) | 14:02-14:24 | +24 | +22 | 279.69 +- 0.80 | 275.87 +- 0.75 | 277.8 | 6.550/6.545e-11 | 4.528/4.529e-11 | -170.62/-170.66 | 0.834 | 23.43/23.43 | gamma -3.5 vs step 14 (same move gave -9.4): below the 5 uHz threshold, near the minimum along this direction; -180 (-39 %) vs X 0 Y 0; tau ~60 min. +/- split 3.8, ext_T equal within 0.01 C. Tracking: all pass (A1 0.10 px). Hill depth +8 %, h1 -3 %, h1_deg rotating ~4 deg per step since step 12. Next: single-axis probes from here to find which knob is at its minimum: X-only X +27 Y +22 first, pin 128.80,196.75 |
| 16 (X-only probe; pin 11 = 128.80,196.75; coast 420 s) | 14:27-14:49 | +27 | +22 | 273.52 +- 1.82 | 269.82 +- 0.82 | 271.7 | 7.279/7.272e-11 | 4.977/4.987e-11 | -169.54/-169.47 | 0.821 | 23.46/23.47 | gamma -6.1 vs step 15 from X +3 alone (step 12's X-only gave -9.3): X still helps. If effects add, step 15's Y +2 cost ~+2.6 (X +3 should have given ~-6), so Y may be past its best; -186 (-41 %) vs X 0 Y 0; tau ~61 min. +/- split 3.7. O01 handed over high (0.514 Hz), only 109 turns in band, error 1.8. Tracking: all pass (A1 0.03-0.04 px). Hill depth +11 % (48 % above steps 10-13; X moves keep deepening it). Molly: the bubble level on the chamber top now reads off-level; the rotor's best tilt need not match the chamber top. Next: Y-only probe the other way, X +27 Y +19 (Y -3, approached from below to finish on +), pin 127.40,195.85 |
| 17 (Y-only probe, Y -3 approached from +17; pin 12 = 127.40,195.85; coast 420 s) | 14:53-15:19 | +27 | +19 | 275.62 +- 0.68 | (spin-up failed) | (+ only) | 7.434e-11 | 5.273e-11 | -171.19 | 0.829 | 23.44 | + coast 2.1 above step 16's + (273.52 +- 1.82): Y -3 did not help, within ~split jitter. With step 15 (Y +2 cost ~2.6 if additive), Y looks near its minimum between +19 and +22, flat to a few uHz. O02 (dir -1) reversal spin-up ran out of its 300 s: brake held the rotor at +0.20..0.23 Hz in the original direction for ~240 s, crossed zero at ~260 s, reached -0.43 Hz at 280 s, ended at ~-0.37 Hz (ncc median dipped to 0.90 on the plateau). Second failed reversal; both came right after a knob moved down (step 04 X -3, here Y -3), not seen on 12 up-moves; at step 04 the pin was off, here A1 0.23 px. Not explained. Y -3 shift (-1.61,-0.97) px vs +3 (+1.39,+0.93): backlash <= 0.2 px. Next: Y to its middle (+21, from +19 up, finishing on +) and X +3: X +30 Y +21, pin 126.90,197.85 |
| 18 (X +3 Y +2 back to middle; pin 13 = 126.90,197.85; coast 420 s) | 15:22-15:43 | +30 | +21 | 279.06 +- 0.33 | 270.99 +- 0.88 | 275.0 | 8.062/8.039e-11 | 5.654/5.652e-11 | -169.62/-169.63 | 0.811 | 23.51/23.51 | gamma +3.3 vs step 16 (first rise): past the minimum in X. Steps 16/17/18 = 271.7 / 275.6 (+ only) / 275.0: the bowl is flat to ~3-4 uHz over +-3 holes, comparable to split jitter. Best measured: step 16, X +27 Y +22. +/- split 8.1. Reversal fine this time (zero crossing < 20 s). Tracking: all pass (A1 0.25 px; ncc median drifting down slowly 0.948 -> 0.942 over the day). Hill depth +8 % (65 % above steps 10-13; not validated). Next: tuning done; return to X +27 Y +22 (X down to +25 then up to +27; Y up 1) and run repeat pairs there (confirms the best point, gives gamma and split scatter, and drift vs step 16 at 14:27), pin 128.80,196.80 |
| 19 (return to best, repeat 1; X from +25 up; pin 14 = 128.78,196.78; coast 420 s) | 15:50-16:12 | +27 | +22 | 272.53 +- 2.44 | 272.83 +- 0.56 | 272.7 | 7.340/7.305e-11 | 5.021/5.033e-11 | -169.80/-169.81 | 0.833 | 23.44/23.44 | Reproduces step 16 (271.7) within 1.0 uHz after the knob excursion and ~1.5 h: no sign of drift; knob return error (+0.05,+0.18) px (~0.3 hole). +/- split -0.3 vs 3.7 at step 16, same knobs: split scatter ~4 uHz at a fixed position. Hill agrees with step 16 to ~1 %. Reversal quick. O01 handed over high (0.508 Hz), 129 turns, error 2.4. Tracking: all pass (A1 0.18 px). Next: repeat 2 at the same knobs (no move) |
| 20 (repeat 2, no knob change; pin 14; coast 420 s) | 16:21-16:42 | +27 | +22 | 279.13 +- 0.36 | 266.32 +- 1.56 | 272.7 | 7.325/7.326e-11 | 5.029/5.028e-11 | -169.85/-169.94 | 0.836 | 23.44/23.44 | Mean identical to step 19. +/- split 12.8, largest yet. Three pairs at X +27 Y +22 (steps 16, 19, 20): means 271.7 / 272.7 / 272.7 (SD 0.6); splits 3.7 / -0.3 / 12.8 (SD 6.7, derived): the scatter is almost all in the one-way (split) part, + and - coasts move opposite ways while their mean holds. One-way torque scatter ~ 6.7e-6 x I w / 2 ~ 1e-16 N m per pair (D, I = 1.1e-11, w at 0.465 Hz). Cause not known. Tracking: all pass (A1 0.19-0.20 px). Next: lamp test (Molly in lab), then restore lamp and repeat remotely |
| 21 (LIGHT TEST: imaging beam OFF by power switch, Molly; lamps on; pin 14; coast 420 s) | 16:49-~17:11 | +27 | +22 | | | | | | | | | LES_SUM fell only 2.5-3.0 -> 1.9-2.6 with the beam off: the LES has a blue-only filter, so the rest is lamp/overhead light (Molly); the LES cannot certify the beam state, Molly's word is the record. Pending readout |

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
  with 11-21/11-22 (a + b/f); (3) continue the diagonal: X +15 Y +15 (+3/+3), coast 420 s, re-centre first; (2026-11-24 rule, Claude, Molly asked how we'd know if only one knob still helps) when a diagonal step gains < 12 uHz, first probe one axis at a time from the best point (X +3 alone, back, Y +3 alone; pairs), follow whichever axis still helps; if neither, halve the step or back off 1-2 holes. Then halve the step
  when a step gains < 12 uHz; confirm the best point with 2 steps; (4) ND2 laser run only after tuning (Molly's choice tonight).
- Molly 2026-11-24 ~16:50: the +/- split scatter is also very important to her, not only gamma. Split SD (D, from the table): steps 01-06 (X 0 Y 0 and single probes, 5 pairs) 0.8 uHz, mean 3.7; steps 07-20 (13 pairs) 3.8, mean 5.5; best point X +27 Y +22 (steps 16/19/20) 6.7. Grew from step 07 on; also changed at step 07: pre-emptive pin re-centring, then overnight (RH 48 -> 17 %). Plan: ~8 pairs at the best point (SD known to ~27 %), then the same number at X 0 Y 0 with today's tracking to see whether tilt drives the scatter; correlate split with handover speed, brake swing, temperature, time of day.
- Split-scatter check (worker2, read-only, 18 valid pairs, table worker2:~/spinup/2026-11-23/tilt/split_scatter_check.csv): no candidate tracks the split beyond chance (26 Spearman tests, best |rho| 0.45-0.47, p 0.05-0.07: how far above the band the + coast started relative to the -). Nothing in handover speed, pre-spin-up swing, temperatures, time of day, hill depth (depth was similar at steps 01-06). The three best-point pairs show no pattern either.
- CORRECTION (2026-11-24 ~17:05, Claude): the 0.8 uHz split SD at steps 01-06 (5 pairs, ~2 h) is not the X 0 Y 0 norm. The interleaved laser nights at X 0 Y 0 (`analysis/laser_injection_20261116/HANDOFF.md`) had pair scatter sd 2.6 (ND4), 3.3-3.9 (ND3), 5.0 (ND2) uHz, and the + minus - offset was ~+1.1-1.3 % of gamma (same sign as today). So today's 6.7 (3 pairs) at the best point is not clearly worse than ND2's 5.0; tilt-made-scatter-worse is NOT established. Proposed (Molly deciding): repeat the interleaved laser night at X +27 Y +22 with the same protocol for a like-for-like comparison of gamma, split scatter and the laser response.
- Hill numbers NOT validated (2026-11-24, Claude, Molly agreed we have no good hill monitor): depth_J (4.9-7.3e-11 J) is comparable to or above the rotor KE at 0.465 Hz (1/2 I w^2 ~ 4.7e-11 J), so taken literally w would swing by tens of % per turn, which the coasts do not show; the hill changes most with X moves, which also move the camera view most (~1.9 px per +3), so part may be view/dot geometry. Check after tuning against LES within-turn speed or hand-timed video quarters. Steer by gamma only.
- Open, not explained: +/- split 11.0 (step 07) and -0.3 (step 08) vs usual 3-4 uHz; step 04 reversal stall (X -3, largest
  pin offset 2.2 px). Which of +/- is CW is not recorded here.
