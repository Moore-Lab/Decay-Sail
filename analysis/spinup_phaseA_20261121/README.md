# Phase A: spin-up governor parameter scan (simulation only, 2026-11-21)

Sim (D = derived from the simulator; plant parts are M/A as in `analysis/spinup_spin_20261111/spin_sim.py`). No hardware.
Controller = the existing `brake_offsets.choose_spin` (unmodified) at 8 Hz, coast trap, 3 plant variants x C 15/30 ms x
dir +-1 = **12 cells per setting** (seed alternates 0/1, identical cells for every setting), T = 600 s (A3: 300 s), w-cap 500.
Scripts: `phaseA.py` (scan), `summarize.py`, `gates.py` (-> `phaseA_summary.md`, selected rows); raw cells `cells_*.json`;
tier-2 controller `tier2.py`. "t3" = time at which 3 consecutive turns are within 1 % of target (live
`--stop-on-target 3 --stop-tol 0.01`), from linearly interpolated turn crossings of the 20 ms trace, my own wrapper.
Level above 1600 not used; **level 1600 is the edge of the push model's basis (A), and `brake_offsets --level` help says
"1600 failed in B3"**: ask Molly what failed there before any live use of 1600.

## Coverage (what was and was not scanned)
Coarse-to-fine, not the full 108-setting grid. Coarse: w_push_max {120..320} x level {800,1200,1600}, tol 0.05, c 0.030 (all
targets 0.5/0.55, A3 0.44/0.37). Refine: w_push_max {100,120,140,160} x level {800,1200,1600} x tol {0.05,0.1} x c {0.030,0.060}.
0.60/0.65: w_push_max {140,160,200,240} x level {800,1600} x tol {0.05,0.1}, c 0.030. **c_assumed 0.045 was not run**; tol 0.1
not run for w_push_max 200-320 at 0.5/0.55. Where coarse and refine overlap, cells are duplicated (counts like 22/24 = 11/12).

## Verdicts (all D, sim)
| gate | verdict | best setting (w_push_max, level, tol, c) | result |
|---|---|---|---|
| A1 0.55 Hz | **PASS** (needs >= 8/12) | 140, 1600, 0.1, 0.030 | 10/12 ok; also 140/1200/0.05 and 140/800/0.05: 10/12 |
| A1 0.60 Hz | **FAIL** (quick check, max 7/12) | 160, 1600, 0.1, 0.030 | 7/12, plateau 0.59 Hz |
| A1 0.65 Hz | **FAIL** (quick check, max 6/12) | 240, 1600, 0.1, 0.030 | 6/12, plateau 0.60 Hz |
| A2 0.5 Hz, t_reach <= 60 s and >= 10/12 | **PASS** | 140, 1600, 0.1, 0.030 | median t_reach 39 s, 11/12 ok |
| A3 0.44 Hz reversal, median t3 <= 90 s, >= 10/12 | **PASS** | 160, 800, 0.1, 0.030 (level 800) | median t3 73 s, 12/12 |
| A3 0.37 Hz reversal | **PASS** | 160, 800, 0.1, 0.030 | median t3 79 s, 12/12 |

One setting passes A1 0.55, A2, A3 (both): **140, 1600, 0.1, 0.030** (level 1600, A). The level-800 alternative passes A3 and A1 0.55
(different w_push_max/tol) but **fails A2** (t_reach 103 s).

## Tables (best 3 + live baseline 120/800/0.05/0.030; `ok` = spin_sim pass; full rows in `phaseA_summary.md`)

**A1, 0.55 Hz from rest (pass >= 8/12)**
| setting (wpm, level, tol, c) | ok | median t_reach (s) | mean last 300 s (Hz) | pass |
|---|---|---|---|---|
| 140, 1600, 0.1, 0.030 | 10/12 | 56 | 0.552 | yes |
| 140, 1200, 0.05, 0.030 | 10/12 | 86 | 0.558 | yes |
| 140, 800, 0.05, 0.030 | 10/12 | 138 | 0.551 | yes |
| live 120, 800, 0.05, 0.030 | 4/12 | 263 | 0.524 | no |

**A1, 0.60 Hz (quick check)**: best live-controller 7/12 (160, 1600, 0.1, 0.030), 160/800/0.05 and 160/800/0.1 6/12;
fail. **0.65 Hz**: best 6/12 (240, 1600, 0.1), fail; tol 0.05 settings 0-4/12. Baseline not run at 0.60/0.65.

**A2, 0.5 Hz from rest (pass: median t_reach <= 60 s and >= 10/12)**
| setting | ok | median t_reach (s) | median t3 (s) (n reaching) | pass |
|---|---|---|---|---|
| 140, 1600, 0.1, 0.030 | 11/12 | 39 | 77 (12) | yes |
| 160, 1200, 0.1, 0.030 | 10/12 | 59 | 75 (12) | yes |
| 140, 1200, 0.1, 0.030 | 11/12 | 63 | 75 (12) | no (t_reach) |
| live 120, 800, 0.05, 0.030 | 11/12 | 120 | 193 (11) | no (t_reach) |

**A3, reversal to +0.5 Hz (pass: median t3 <= 90 s, >= 10/12 within 300 s, no abort, first turn along dir)**
| setting | start 0.44 Hz: median t3 (s), n | start 0.37 Hz: median t3 (s), n | pass |
|---|---|---|---|
| 160, 1600, 0.1, 0.030 | 59, 12/12 | 57, 12/12 | yes |
| 140, 1600, 0.1, 0.030 | 61, 12/12 | 62, 12/12 | yes |
| 160, 800, 0.1, 0.030 (level 800) | 73, 12/12 | 79, 12/12 | yes |
| live 120, 800, 0.05, 0.030 | 95, 12/12 | 148, 9/12 | no |

No aborts in any cell; first-turn-along-dir held in all A3 cells counted.

## What moved the result (observed)
- **tol 0.1 (deadband +-5 %)** is what fixes reversal (t3 95 -> 73 s at level 800 and 12/12 instead of 9/12 at 0.37) and shortens the
  hold-to-1 % time at 0.5 Hz; with tol 0.05 the t3 stays 170-250 s for the same w_push_max/level.
- **Level 1600 vs 800** cuts t_reach about 2-3x (39 vs 103 s at 0.5 Hz, w_push_max 140, tol 0.1). Level 1600 is extrapolated (A).
- **w_push_max 140-160** is the sweet spot at 0.5-0.55 Hz; >= 200 overshoots (0.5 target holds at 0.58-0.7 Hz because the
  brake cannot act at speed). 120 is the best for 0.5 Hz level 800 but cannot reach 0.55 (plateau 0.52).
- **c_assumed 0.060** was worse than 0.030 in most pairs (e.g. 0.55 Hz, 140/1600/0.1: 8/12 vs 10/12). 0.045 not run.
- Results at 12 cells are noisy: neighbouring settings differ by +-2/12 (e.g. 0.55 Hz 140/1600 tol 0.05 9/12 vs tol 0.1 10/12). Treat 10/12 vs
  8/12 as equivalent; the pass at 0.55 is a margin of two cells.

## Mechanism of the A1 ceiling (live controller) at 0.60-0.65 Hz
Observed: with the live controller the speed plateaus at about 0.59 Hz (0.60 target) and 0.60 Hz (0.65 target) for any
w_push_max 160-320 and level 800/1600; peak speed is about 285-300 deg/s. At wpm 120 the plateau is 0.52-0.53 Hz. The
w_push_max gate explains the 120 and 140 plateaus (pushes occur only where the predicted speed is below it). It does not
explain the 0.6 Hz plateau: tier 2 with the gate removed (wpm 300 and 1000 give identical cells, i.e. the gate no longer
binds) reaches 0.64 Hz, not 0.65. **Hypothesis, not tested:** one 125 ms hold at 290 deg/s sweeps 36 deg, nearly a full
45-deg push period, so the push averaged over the hold has little net sign and the commutation cannot add energy.

## Tier 2 (CODE CHANGE: would need a branch + worker2 test before live use; sim only)
`tier2.py: choose_spin_avg`: same prediction/want logic, no speed gate, phase chosen by the push averaged over the angular
span the hold sweeps (9 samples over w_p x 125 ms). Own copy; `brake_offsets.py` untouched.
| target | setting (wpm, level, tol, c) | ok | median t_reach (s) | mean last 300 s (Hz) |
|---|---|---|---|---|
| 0.60 Hz | gate off, 1600, 0.1, 0.030 | 10/12 (live ctrl best 7/12) | 54 | 0.605 |
| 0.60 Hz | gate off, 800, 0.1, 0.030 | 9/12 | 119 | 0.595 |
| 0.65 Hz | gate off, 1600, 0.1, 0.030 | 6/12 (same as live ctrl) | 111 | 0.638 |
So tier 2 passes 0.60 Hz (>= 8/12) but still fails 0.65 Hz. With tol 0.05 tier 2 is worse (0-2/12 at 0.60). Not run at 0.5/0.55
or for A2/A3. The 0.65 Hz ceiling is not explained here.

## Flags for Molly to approve (nothing run live)
Existing `lab_utils/brake_offsets.py run` (other flags as in the current live recipe: `--map g1 --dir <+-1> --enable-outputs --live`,
`--w-cap 500`, `--c-assumed 0.030` default):
- Spin up to 0.5 or 0.55 Hz, all gates incl. reversal (level 1600, A): `--level 1600 --spin-to 0.55 --tol 0.1 --w-push-max 140 --stop-on-target 3 --stop-tol 0.01`
  (use `--spin-to 0.5` for A2/A3).
- Level 800 only (basis-valid): A1 0.55: `--level 800 --spin-to 0.55 --tol 0.05 --w-push-max 140`; reversal: `--level 800 --spin-to 0.5 --tol 0.1 --w-push-max 160`.
  These do not pass A2 (t_reach 94-138 s).

## Checks
Ran: baseline reproduction (live setting, 0.5 Hz: 11/12 ok, in line with the earlier sim's 10/12 with different seeds); wrapper
turn-crossing t3 definition on the same cells; duplicate-cell consistency (identical cells give identical results);
tier-2 gate-off equivalence (wpm 300 = 1000). Skipped: full 108-setting grid, c 0.045, more seeds, independent re-implementation of t3,
0.60/0.65 baseline at the live setting, plots.
Assumptions: seed assignment (alternating 0/1) instead of the earlier `len(out) % 5`; A2/A1 at 0.5 Hz share the same cells; for A3 the
`ok` column is not meaningful (scored on t3 within 300 s, not on `ok`).
