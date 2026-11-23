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

## State (2026-11-23 ~13:40)

- nd2_fast attempt 3 running on worker2 (ND2, 45 pairs, off/on/on/off). Molly will stop it for tuning (stop message:
  finish the current coast, final brake, laser 0, keep tracker headless + PD log, upload).
- Not yet done: push `tilt_readout.py` so worker2 can run it (needs Molly's OK); merge the drag-timeline agent output.
