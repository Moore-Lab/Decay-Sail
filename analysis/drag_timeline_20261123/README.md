# Drag timeline, Sept -> Nov 2026 (analysis only, Mac; 2026-11-23)

Labels: M measured, D derived, A assumed. All interpretations are **not approved**.
Run: `python3 drag_timeline.py` (-> `drag_timeline.json`), `python3 plot_timeline.py` (-> `plots/drag_timeline.png`, `drag_timeline_pooled.json`).
`les_scan.py` decimates the Sept/Oct LES h5 to 8 Hz (cache in `plots/`).

## Method
- gamma = -dln f/dt in rotor-speed bands 0.33-0.40, 0.40-0.47, 0.47-0.50, 0.50-0.59, 0.59-0.73 Hz (0.73, not 0.75: the laser-hold plateau sits at 0.75-0.79 Hz). Quadratic in ln f over the band (linear if < 40 points), evaluated where f crosses the band centre; 10-block jackknife error; >= 20 points per band (D).
- Fit gamma = a + b/f per coast / per night (weighted LS; errors scaled by sqrt(chi2/dof) if > 1). tau(0.5 Hz) = 1/(a + 2b).
- **Sept 13, Oct 11 (LES_YAW)**: 2f line, rotor f = line/2 (**divisor 2 assumed**; confirmed 2026-10-09 by the comb, "unverified" after the 09-11 ND change), 40 s windows / 10 s step. Laser-off coasts from a ~0.75-0.79 Hz laser hold (the slide "Spindown: laser off").
- **Sept 9**: LES line seen at 0.75 Hz = rotor 0.375 Hz (divisor 2 assumed); laser/drive state not checked. One band only.
- **Nov (tracker, 50 fps, per-turn rates)**: window field off + 5 s .. coast end - 2 s (`coasts.py` method); coasts starting < 0.46 Hz, swings and short windows skipped. Per night: median over coasts (error = sd/sqrt(n)). All coasts used, laser on and off pairs together (laser <= ~30 uW, effect ~7 uHz at most, below the table's resolution).

## Table (gamma in uHz; "-" = band not covered)
| date | source (n coasts) | 0.33-0.40 | 0.40-0.47 | 0.47-0.50 | 0.50-0.59 | 0.59-0.73 | a (uHz) | b (uHz Hz) | tau(0.5 Hz) min |
|---|---|---|---|---|---|---|---|---|---|
| 09-09 | LES (1, 0.375 -> 0.18 Hz) | 193 +- 1 | - | - | - | - | - | - | - |
| 09-13 | LES (1, CCW) | 204 +- 1 | 224 +- 4 | 202 +- 2 | 199 +- 1 | 196 +- 1 | 186 +- 6 | 7 +- 3 | 83.5 +- 0.5 |
| 10-11 | LES (1, CW) | 213 +- 2 | 229 +- 4 | 204 +- 1 | 202 +- 1 | 194 +- 2 | 173 +- 10 | 15 +- 5 | 81.8 +- 0.8 |
| 11-12 | tracker (6) | 634 +- 4 | 493 +- 2 | 439 +- 1 | - | - | -217 +- 162 | 314 +- 74 | 40.5 +- 1.7 |
| 11-14/15 | tracker (55) | 626 +- 2 | 490 +- 1 | 438 +- 1 | - | - | -151 +- 159 | 283 +- 72 | 40.3 +- 1.7 |
| 11-16/17 ND4 | tracker (48) | 616 +- 3 | 491 +- 1 | 438 +- 1 | - | - | -96 +- 112 | 258 +- 52 | 39.7 +- 1.0 |
| 11-17/18 ND3 | tracker (48) | 616 +- 3 | 490 +- 1 | 437 +- 1 | - | - | -94 +- 108 | 256 +- 49 | 39.8 +- 1.0 |
| 11-18/19 ND2 | tracker (80) | 616 +- 3 | 489 +- 1 | 437 +- 1 | - | - | -114 +- 131 | 266 +- 61 | 39.8 +- 1.0 |
| 11-21 damping_1300 | tracker (1) | 651 +- 11 | 492 +- 3 | 431 +- 1 | 404 +- 0.3 | - | 159 +- 53 | 133 +- 28 | 39.2 +- 0.4 |
| 11-22 fast 5 min | tracker (80) | - | 483 +- 1 | 438 +- 1 | 425 +- 1 (band edge only, f ~ 0.50) | - | -118 +- 159 | 270 +- 77 | 39.4 +- 0.6 |

Pooled November (band means of all Nov rows): a = -134 +- 81, b = 275 +- 37 uHz Hz, tau(0.5) = 40.0 +- 0.7 min (`drag_timeline_pooled.json`).
Night fits use only bands 0.33-0.50 (a 1.5x span in 1/f), so a and b are strongly anti-correlated there; only 11-21 (4 bands, 0.33-0.59) and the Sept/Oct coasts constrain the split. Trust gamma per band first.

## Dated apparatus changes (apparatus_log.md, logs/2026-q3.md; recalled dates from the 2026-11-04 setup-history entry)
09-08 model change (DRVMTRX); 09-09 chamber on optical table, no tilt stage; 10-09 new pickoff / beam realignment (LES readout only); 10-15 new tilt stage on the table, chamber taken off: rebuild with shims, PCB and magnet centred, 10-21/22 rotor centred, board GND wired; 10-26 chamber on tilt stage; 10-27 shims under PEEK plate; 11-06 tilt stage adjusted; 11-11 HV amp DC-coupled; 11-12 camera moved. Also: Sept/Oct coasts follow a laser spin-up, Nov coasts follow an electrostatic spin-up (stator outputs connected). No pressure or temperature record found for this period (STATUS: logging not set up).

## Result (D)
- Sept 13 and Oct 11 agree: gamma ~ 195-205 uHz and nearly flat in 0.33-0.73 Hz (tau ~ 82-84 min at 0.5 Hz). Both show a bump in 0.40-0.47 Hz (+20-25 uHz, ~5 sigma jackknife), unexplained.
- By 11-12 gamma at 0.5 Hz is ~2x and rises as speed falls (633 uHz at 0.37 Hz vs 405-425 at 0.5-0.55 Hz): a 1/f term, b ~ 130-280 vs 7-15 in Sept/Oct. gamma at 0.435 Hz: 224/229 (Sept/Oct) -> 489-493 (every Nov night, constant to ~1 % over 11-12 .. 11-22).
- The change happened between 2026-10-11 and 2026-11-12: **no data in between** (the 11-02/04 feedback runs have only swings or < 3 min coasts), so step vs gradual cannot be told. The 10-15..10-27 rebuild (new stage, board GND, shims, centring) is in the gap; the 11-11 DC-coupling is only one day before the first Nov coast (11-12), so it cannot be excluded either, nor the laser- vs electrostatic-spin-up difference.

## Skipped
Aug data (not allowed); 09-08 spindown (0.17 Hz, below the bands); 09-10 files (rotor < 0.33 Hz or driven); 10-10/11 and 09-11..13 long laser holds (not coasts); 10-30 LES_video, 11-02/03 free swings, 11-04 F3 turns (short, brake-affected); brake/detent runs; 11-11 spin and 11-12 reversal/series runs (driven); 11-21 phaseB 5-min coasts (not analysed, same kind as 11-22); 11-21 laser plateau. 11-22 fast_dry (2 coasts).
