# Spin-up gate G1: what limits the spin-ups, from the 11-14/15 overnight drive logs

**Status: G1 NOT passed (2026-11-16).** The sim does not yet reproduce the live phase times (criterion: within ~30 %).
Main finding (measured): the tracker centre was 3.0 px off all night. Interpretations are not approved. Mac only, no
hardware. Plan and gate: Molly's go 2026-11-15 ("you start g1").

Data: Dropbox `spinup/2026-11-14/overnight/series/brake_*.csv` (61 brake_offsets runs: 60 spin-ups at level 800, final
brake at 1600; 691,563 usable frames, 113,329 writes, 29,054 pushes) and `.../tracker/blob_live_gps1478746563.csv`.
Code: `drive_fit.py` (joint fit), `map_bins.py` (binned push map), `sim_overnight.py` (closed-loop sim); outputs
`*.json`, `*_stdout.txt`; plots in `plots/` (gitignored). Live phase times: medians from the brake logs (method as
`sim_overnight.py`; numbers in `LIVE` there).

## Live spin-up phases (derived from the logs; on-target runs)

| median (s) | + (29) | − (20) |
|---|---|---|
| brake the old rotation, reverse | 70 (4–200) | 31 (6–82) |
| reversed → 0.45 Hz | 28 | 25 |
| 0.45 → 0.49 Hz | 58 | 59 |
| 0.49 Hz → on target (3 turns within 1 %) | 17 | 30 |
| total | 199 | 158 |

- Pushes land mostly at 30–90° (near the barrier top; the push map was measured only at 167–267°).
- The stalled runs (− O04, O20, O56, O60; long + reversals) sit in a ±100–160° swing about ~222° for minutes while the
  governor pushes ~3/s; over the top needs ~±160°.

## 1. Tracker centre 3.0 px off (measured, two independent ways)

- **Dot circle:** the tracker's own `r_px` varied 19.9–26.1 px once per turn. A circle fit to all 2.8 M dot positions
  gives centre **(128.98, 176.60)**, radius 23.46 px; the run used (131.03, 178.79): offset (−2.05, −2.19) px. About the
  new centre the radius is flat to ±0.5 px (the remaining m = 2 is consistent with an oblique view).
- **Dynamics:** fitting the drive logs needs an ω²·B(θ) term (rms residual 0.90 → 0.51 rad/s²) whose m = 1 part implies a
  5.9° once-per-turn angle error, i.e. a 2.6 px offset, 90° in phase from the `r_px` modulation, as the geometry requires.
- **So the angle the controller acted on was wrong by up to ±7.2° once per turn.**
- History of the same `r_px` test: 11-12 before the camera move (centre 117.5, 165.1): 0.45–0.50 px (ncc 0.95–0.96);
  11-12 after the move (131.03, 178.79): 1.2–1.3 px; 11-14/15: 3.0 px (ncc 0.905). The image drifts ~1 px/day; the
  centre needs checking before each live run (`camera_utils/tracking/blob_core.register_centre`). This plausibly also
  explains the lower ncc and the 0.4° rest-angle shift of 11-14 (not shown).
- **The camera moved, not the rotor's axis (measured 2026-11-16).** Static-board registration
  (`blob_core.register_centre`, rotor masked) of the 11-14 21:55 start clip (`tracker/first_try/`, median of 34 frames)
  against the 11-12 15:00 re-centring still (`camera_check/2026-11-12b/median_new_first300.png`): board shift
  (−2.07, −0.88) px (response 0.93; controls with known shifts (2, −1), (0, 3) recovered to 0.1 px). The dot-circle
  centre moved (−1.90, −0.96) px over the same interval ((130.88, 177.56) from the 11-12 afternoon `r_px` fit →
  (128.98, 176.60)). They agree to ~0.2 px, so the rotor's axis stayed put relative to the stator board; the image
  shifted. The remaining 1.2 px of 11-12 was in the centre chosen at the re-centring itself.
- **Damping results are unaffected:** per-turn rates use whole turns (the bias cancels); the LES has no angle.

## 2. Push map and timing, with corrected angles (derived)

- Corrected angles (first order, `drive_fit.correct`): residual rms 0.46 rad/s².
- **Push map = the G1 map's shape and size, offset −2.50° (A), −2.45° (B), −1.50° (C).** Fitted |m8| 0.25–0.28,
  |m16| 0.51–0.53 rad/s² (G1: 0.248, 0.537); after the offset the coefficients agree to 0.01–0.02 rad/s². So the 45°
  periodic extrapolation outside 167–267° holds (the earlier suspicion was wrong). The binned map (`map_bins.py`) still
  disagrees with the m 0/8/16 Fourier fit (χ² ~50 per bin): structure the 3-harmonic map does not hold.
- **8 Hz grid confirmed:** the fitted tick phase per run steps steadily through the night (wrapping twice), i.e. one grid
  with the front-end clock running fast by 0.1237 % (as the G1 pulse refit, 1.001237, and the coast-series clock check).
  Writes act **10 ms after the tick** (51 of 61 runs). Grid model beats a fixed delay (0.4603 vs 0.4711 rad/s²).
  The controller assumes a fixed 155 ms look-ahead; the real write-to-mid-hold time is ~70–200 ms (where in the tick a
  write falls), ±7° at 120°/s.
- Remaining model problems: the ω² term (B rms 0.43) is dominated by m 19–24, so it is absorbing structure at speed,
  not only tracker geometry; the fitted trap differs from `coast_trap.json` (barrier 6.31 vs 6.50 rad²/s², minimum 206°
  vs 219°, shape rms 1.36 rad/s² — the coast trap is from 11-11, before the camera move).

## 3. Closed-loop sim (`sim_overnight.py`; NOT validated)

Plant from section 2; controller = live `choose_spin`; start rotating 0.37 Hz against DIR; 24 runs per row.

| case | dir | total to on target (s) | 0.48 Hz reached (median) | stalls |
|---|---|---|---|---|
| live (old-centre angles, G1 map) | + / − | no stop on target | 196 s (6/24) / 136 s (16/24) | 11 / 7 |
| live, measured | + / − | 199 / 158 | — | 0 / 4 (of 30) |
| centre fixed, map offset applied | + / − | 106 / 83 | 83 / 67 s | 0 / 0 |
| + tick-synchronous look-ahead | + / − | 77 / 80 | 59 / 54 s | 0 / 0 |
| centre fixed, level 1600 | + / − | 108 / 87 | 46 / 40 s | 0 / 0 |
| tick-synchronous, level 1600 | + / − | 47 / 73 | 31 / 32 s | 0 / 0 |

- The 'live' case is 3–5× worse than the live runs (stalls, no stops) and has the direction asymmetry the wrong way,
  so **G1's pass criterion is not met** and the lower rows are what the current model says, not forecasts.

## Next (G1 continued, Mac only)

1. Open-loop replay against the logs: (a) feed the logged frames into `choose_spin` and compare with the logged choice
   (is the sim's controller the live one?); (b) from each landing, integrate the fitted plant over one hold and compare
   with the angle 125 ms later, by angle bin (where is the plant wrong?).
2. Plant suspects: the push map's extra structure (use the binned map), the trap shape (fitted vs coast), the ω² term.
3. Only then controller changes (centre check before each run, map offset, tick-synchronous look-ahead, level 1600,
   end at ≥ 0.48 Hz) and a live trial series (Molly's go).
