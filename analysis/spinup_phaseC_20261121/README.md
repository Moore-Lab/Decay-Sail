# Phase C: faster, repeatable reversals (simulation only, Mac only, 2026-11-21)

No hardware, no lab_utils edits. All sim numbers are **derived** (D); live numbers are **measured** (M, Phase B logs, 50 fps).
Own sim copy `sim_c.py` (from `spinup_spin_20261111/spin_sim.run`, controller = `brake_offsets.choose_spin` of branch
`laser-interleave`, byte-identical to `decay_sail_wt_vs`), `variants.py` (code variant), `live_metrics.py`, `calib*.py`, `scan.py`,
`vscan*.py`, `rank.py`; results `calib_result.json`, `calib_scan.json`, `scan_{grid,sel,oat,variant,variant2}.json`, `live_metrics.json`.
Times are from **field on** (first `brake` row of the log). `table.txt` `t_to_target_s` is about 5-8 s longer (observe phase, default 5 s).
"Brake end" = first time `f_against` <= 0.05 Hz (the governor's own flag); it is **not** `table.txt` `brake_s` (13-20 s).

## 1. Calibration: the stall is reproduced; the cause was the sim's START STATE
Diagnosis (1)-(3) confirmed (M): rotation stops at 3-12 s (median 8.8 s, R1-R6), the brake runs on to 21-28 s (14.7-15.9 s after rotation
stopped; the 30 s mean lags), the rotor sits near rest (smoothed |w| minimum 4-23 deg/s after brake end), then pumps a swing for 18-57 s before it escapes.
**Why Phase A missed it (D):** Phase A started the coast at the trap bottom with w = 1.08 x mean = 171 deg/s. Live, the speed at the bottom is about
220-235 deg/s (slowest ~60-100 deg/s at the barrier top; live d*w at t = 0.5-1 s is -200..-235). With 171 deg/s the sim rotor was stopped by the trap alone in ~1 s,
the brake never over-ran, and it reversed in 59 s. Fix (smallest): start from a free coast of the same trap whose turn time is 1/0.44 s, random phase (`sim_c.coast_start`).
No plant change was needed for the stall. Plant knob `push_x` (global push scale) only sets the pump-up time: **push_x 0.5-0.8, unresolved** (0.65 used).
R1-R4 alone (first turn 70 s, total 110 s) prefer 0.5, the grid edge; R5-R7 (58 s, 80 s) prefer 0.65-0.8. trap_x 1.0-1.2 indistinguishable; C 15/30 ms not resolved.

| (s from field on) | live R1-R6 (stop-tol 0.01), median (min-max) | sim, 24 cells, median (p10-p90) | live R7 (stop-tol 0.1) | sim stop-tol 0.1 |
|---|---|---|---|---|
| rotation along -d stops | 8.8 (5.4-12.3) | 10.0 (8.5-14.5) | 3.2 | 10.0 |
| brake end (f_against <= 0.05) | 24.0 (20.9-27.8) | 25.3 (24.5-29.0) | 5.4 | 25.3 |
| first full turn along d | 59 (43-81) | 55 (33-80) | 62 | 55 |
| f_mean within 5 % of 0.5 Hz | 67 (57-88) | 70 (45-106) | 74 | 65 (17/24 reach it) |
| hunting (reach -> stop) | 18 (7-75) | 12 (6-50) | 20 | 3 (1-6) |
| **total, field on -> stop** | **86 (74-140)** | **84 (53-139)** | **93** | 72 (47-102) |

Sim brakes to near rest too (smoothed |w| minimum 3-27 deg/s, median 18, in the 20 s after brake end; live 4-23 in 30 s: windows differ).
Figure `calib_fig.png` (regenerate: `python3 calib_fig.py`): live R1/R3 and R2/R4 vs one sim cell each; turns, f_against and f_mean agree in shape.
Not reproduced: live scatter is wider (hunt 7-75 s, R7 shorter brake because it started from a different state); stop-tol 0.1 is a **miss with n = 1**
(R7 hunted 20 s, sim 3 s). R5-R7 were used only as a check (sim sits inside their range, except R7's hunt). Cell set: `calib.py` (nominal plant, dir +-1, C 15/30 ms, seeds 0-5).

## 2. Parameter-only scan (existing flags, level 1600 only, calibrated plant)
24 cells per setting: 12 Phase A cells (3 variants x C x dir) with push scale x 0.65 (0.49-0.81) + 12 nominal cells (dir x C x 3 seeds).
Reversal = 0.44 Hz coast against dir to 0.5 Hz; time = field on -> stop (T = 300 s; a non-stop counts as 300 and is counted as `fail`). Spin-up from rest on the same cells.
123 settings: w-push-max 140-320, tol 0.05-0.2, stop-tol {0.05, 0.08, 0.12}, stop-on-target {2, 3}, plus the live recipe (stop-tol 0.01). Then one-at-a-time at the best.
**A looser stop rule is a trade, not a free gain** (the coast starts at 0.48-0.49 Hz instead of 0.50): rate at field-off is shown. Compare rows with the same stop rule.

| setting (wpm, tol, stop-tol, n) | rev median / p90 (s) | fails | peak f_mean med/max (Hz) | rate at stop, median (Hz) | spin-up from rest median / p90 (s) |
|---|---|---|---|---|---|
| live recipe 140, 0.1, 0.01, 3 | 81 / 147 | 0 | 0.50/0.51 | 0.500 | 90 / 99 |
| live recipe, tol 0.05 (Phase B had tol 0.1; old default) 140, 0.05, 0.01, 3 | 146 / 300 | 7 | - | - | - |
| 140, 0.1, **0.05**, 3 | 67 / 114 | 0 | 0.50/0.51 | 0.491 | 79 / 95 |
| 180, 0.1, 0.05, 3 | 80 / 138 | 0 | 0.50/0.51 | 0.491 | 78 / 112 |
| **220**, 0.1, 0.05, 3 | 69 / 103 | 0 | 0.50/0.51 | 0.494 | 73 / 108 |
| 220, 0.1, 0.08, 3 | 69 / 91 | 0 | 0.50/0.51 | 0.484 | 67 / 103 |
| 220, 0.1, 0.05, **2** | 67 / 91 | 0 | 0.50/0.51 | 0.490 | 70 / 106 |
| 260, 0.1, 0.05, 3 | 81 / 149 | 1 | 0.50/0.52 | 0.493 | 69 / 129 |
| 220, 0.1, 0.01, 3 | 83 / 126 | 0 | 0.50/0.51 | 0.501 | 111 / 179 |

Observed (D): (a) stop-tol 0.05-0.12 is the main lever at wpm 140 (81 -> 67 median, 147 -> 114 p90); 0.05, 0.08, 0.12 differ by < 4 s; n = 2 vs 3 by ~2 s.
(b) tol 0.05-0.15 gives identical results at wpm 140-220 (the deadband is not reached before the stop); tol 0.2 widens p90; tol 0.05 with wpm >= 260 fails 4-6/24.
(c) w-push-max 140 and 220 are equivalent in the median; 220 has the better p90 only at stop-tol 0.08-0.12 (87-91 vs 104); 180 and 260-320 are worse (80-87 median, fails at 260+).
(d) One-at-a-time at 220/0.1/0.05/3: min-push 0.15 (default) is best-or-equal (0.05: 2 fails, p90 186; 0.1: 82; 0.2: 78; 0.3: 75/98, within noise);
c-assumed 0.030 is best, 0.015 gives 82/137, **0.045 gives 4/24 failures, 0.06 8/24, 0.09 12/24** (live default 0.030: keep). Level 800: 116/187, 1200: 85/170, 1600: 69/103.
Cell-to-cell noise is ~+-5 s on a median of 24; do not rank rows within 5 s.

**Recommended (existing flags; Phase B flags otherwise: `--map g1 --level 1600 --spin-to 0.5`):**
1. `--tol 0.1 --w-push-max 140 --stop-on-target 3 --stop-tol 0.05`: reversal 67/114 s (live recipe 81/147), spin-up 79/95. Smallest change from what ran.
2. `--tol 0.1 --w-push-max 220 --stop-on-target 3 --stop-tol 0.05`: reversal 69/103, spin-up 73/108. Peak f_mean max 0.51 (wpm 220 was not run live; Phase A saw overshoot at >= 200 for 0.5 Hz targets in a different sim).
3. `--tol 0.1 --w-push-max 220 --stop-on-target 2 --stop-tol 0.05`: reversal 67/91, spin-up 70/106 (only two turns checked; the coast may start 2-3 % off 0.5 Hz).
Parameter-only cannot fix the mechanism: first full turn stays at ~46-51 s in every row (it is set by braking to rest, then pumping from rest).

## 3. Code variant (sim only; own copy `variants.fast`; lab_utils untouched; needs branch + worker2 test before any live use)
Handover: while the live reverse flag (`f_against > 0.05`) is on, stop braking as soon as the fitted w has been against d (< -30 deg/s) and then turns to along d;
the flag is ignored until the 30 s mean falls below 0.05 again (the live rule then applies). The rotor keeps its swing and is pumped immediately.
Optional `wpm_pump`: larger push-speed gate while pumping, only until the rotor turns along d (f_mean < 0.1); braking gate unchanged.
Safety kept: w-cap (500, harness), pushes only inside the gate, field off on target, no state outside the call. Peak f_mean max 0.52, no w-cap trips in any cell.

| setting | rev median / p90 (s) | first turn med (s) | fails | spin-up from rest median / p90 | rate at stop |
|---|---|---|---|---|---|
| live controller 140, stop-tol 0.05 | 67 / 114 | 51 | 0 | 79 / 95 | 0.491 |
| **fast** 140, stop-tol 0.05 | **35 / 65** | 14 | 0 | 79 / 95 (identical: flag never fires from rest) | 0.489 |
| fast 140, stop-tol 0.08 | 34 / 52 | - | 0 | - | 0.482 |
| fast 140, stop-tol **0.01** (live rule) | **50 / 80** | - | 0 | - | 0.499 |
| fast 220, stop-tol 0.05 | 37 / 84 | 14 | 0 | 73 / 108 | 0.495 |
| fast 140 + wpm_pump 200, 0.05 | 34 / 73 | 13 | 0 | 69 / 94 | 0.486 |
| fast 220 + wpm_pump 200, 0.05 | 34 / 70 | 14 | 0 | 70 / 97 | 0.495 |
`wpm_pump` 260/320 adds nothing (36 / 81). Its spin-up gain (79 -> 69-74) is within noise: **not recommended on its own**. Handover alone halves the reversal.
Caveats (D, untested live): the 14 s first turn assumes the live push map pumps the leftover swing as in the sim; the sim brake-to-turn-around timing came from the calibrated coast start;
if the rotor is not actually stopped when w crosses zero (noise on a 8-frame fit) the rule hands over early, which only costs pumping against residual motion (pumping needs w along d).

Minimal diff to `choose_spin` (state dict kept by the caller; `w_e` is the existing fit `p2[1]`):
```diff
+    st = state if state is not None else {}
+    if f_against <= f_rev:
+        st['seen'] = False; st['off'] = False
+    elif d * w_e < -30.0:
+        st['seen'] = True
+    elif st.get('seen') and d * w_e > 0.0:
+        st['off'] = True                     # rotation along -d has stopped: hand over now
-    if f_against > f_rev:                    # REVERSE: rotating the other way -> brake first
+    if f_against > f_rev and not st.get('off'):
         want = -1
```
Flags needed: none for the controller change itself (caller passes `state={}`); an optional `--w-pump-max` would be a new flag.

## Checks
Ran: sim reproduces live timings within live scatter (table above); coast-start energy check (sim d*w -222..-225 deg/s at t = 0 vs live -60..-235 over the first 14 s, modulated by the trap);
variant spin-up identical to live where the flag never fires; failure diagnosis of an earlier variant version (latched flag, 3/24 up-fails) fixed and re-run; confirmed brake_offsets identical to the branch copy.
Skipped: independent re-implementation, real-measured start energies, more seeds than 24 cells, level > 1600, push_x fit beyond 0.5-0.8, fitting trap depth/latency (not needed), spin-up variants of stop rules at all grid points.
Not approved interpretations: the cause of live hunt scatter (7-75 s) is unexplained here.
