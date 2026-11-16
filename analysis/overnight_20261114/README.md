# Overnight coast series 2026-11-14/15: damping per coast (LES and tracker)

**Status: complete, all 60 steps (30 pairs, 23:06 to 12:54 EST). Interpretations are not approved.** Run log:
`apparatus_log.md` 2026-11-14 (night). Code: `les_coasts.py`, `tracker_coasts.py` (methods in their docstrings);
output `les_coasts.{json,csv}`, `les_coasts_stdout.txt`, `tracker_coasts.{json,csv}`, `tracker_coasts_stdout.txt`;
plots `plots/les_tau_vs_time.png`, `plots/tracker_vs_les.png` (gitignored).

Data: Dropbox `spinup/2026-11-14/overnight/`: `les/` (LES PIT and YAW `_OUT_DQ`, 1024 Hz, FE GPS
1478767437–1478817856, 15 files, no gaps), `series/` (`series.csv`, `coast_On.txt`, consoles), `tracker/`
(`blob_live_gps1478746563.csv`, 50 fps all night, 0 dropped frames, ncc min 0.725). Each coast: 600 s, field off,
nothing written; spin-up to 0.5 Hz before it (`lab_utils/coast_series.py`, voltage-steps 6e861aa).

## Run (measured)

- Spin-ups on target 49/60: +1 29/30 (O05 held 0.489), −1 20/30. Of the −1 misses, O04, O20, O56, O60 never went
  over the top (swing, no coast data); O08 made one turn at 0.41 Hz; O10, O22, O26, O38, O48 held 2–8 % low. No
  ncc, stale-tracker, speed-cap or error stops. Final brake ran 300 s; front end at rest after (OFFSET 0, SW2R 768,
  OUTMON 0).
- 56 coasts rotating. Band summaries use the 54 that started at ≥ 0.47 Hz (all but O08, O10); whole-coast summaries
  the 52 that started at ≥ 0.48 Hz.

## Damping (derived)

tau from a fit of f = f0 exp(−t/tau). LES: the 2 f_rot line, rate per 40 s window. Tracker: per-turn rates, as
`analysis/coast_pairs_20261112/coast_pairs.py`. Same coast windows (field off + 5 s to coast end − 2 s).

**Band 0.40–0.47 Hz** (min):

| readout | dir | coasts | mean tau | sd between coasts | trend (min/h) |
|---|---|---|---|---|---|
| LES | +1 | 30 | 34.03 | 0.13 | +0.016 ± 0.005 |
| LES | −1 | 24 | 34.41 | 0.17 | +0.039 ± 0.006 |
| tracker | +1 | 30 | 33.97 | 0.12 | +0.018 ± 0.004 |
| tracker | −1 | 24 | 34.38 | 0.16 | +0.035 ± 0.006 |

- **Back-to-back pairs (− minus +), band tau:** LES **+1.10 %** (sd 0.53, sem 0.11, 24 pairs); tracker **+1.18 %**
  (sd 0.42, sem 0.09). **− is higher in all 24 pairs** in both readouts (LES +0.10 to +2.08 %).
- **Tracker vs LES, same coast:** tracker/LES − 1 = −0.14 % (sd 0.16 %, range −0.50 to +0.21 %, 54 coasts). The two
  readouts agree coast by coast to well within the coast-to-coast scatter.
- **Time bases.** The front-end clock (`Y1:DAQ-DC0_GPS` read at each field-off, vs worker2's NTP host time, 60
  points over 13.6 h) runs **+0.123 % fast** (fit residual sd 0.42 s, from the 1 s caget resolution). The tracker's
  frame clock matches host time to ~1e-5 (2,785,195 frames in 55,703.9 s). If the LES samples run on the same
  front-end clock (assumed), LES tau is 0.12 % long in real seconds, which accounts for the −0.14 % tracker/LES
  difference. LES tau corrected by 1/1.00123: +1 33.99, −1 34.37 min. Pair ratios are unaffected.
- **Band 0.44–0.49 Hz (the 11-12 band), tracker:** +1 36.51 (sd 0.12, n 30), −1 36.97 (sd 0.19, n 20) min; pairs
  +1.21 % (sem 0.10, 20/20 positive). 11-12 tracker, same band: 36.2 / 36.8 min, − minus + +1.47 ± 0.57 % (3 pairs,
  `analysis/coast_pairs_20261112/coast_pairs.json`; the interim version of this README misquoted it as −1.47). So the shorter tau in the 0.40–0.47 band is the band, not a change since 11-12.
- Whole coast (≈0.49 → 0.37 Hz): LES +1 33.61 (sd 0.36), −1 33.98 (sd 0.38); pairs +1.22 ± 0.27 %. Larger scatter
  than the band because the speed range covered varies with the start speed.
- Per-coast fit errors (LES jackknife ~0.5 min) are ~4× the coast-to-coast scatter, so the scatter is used as the
  measured repeatability.

## Per pair, and the asymmetry in signal units (`pair_plots.py`, `les_phase.py`, 2026-11-16)

Labels: M measured, D derived (from measurements through a stated method or model), A assumed. Interpretations are not
approved. Tracker per-turn rates, band 0.40–0.47 Hz (~5.5 min of each coast), 24 back-to-back pairs (+ then −; pairs
with a swing or a low-start coast left out). Table `pair_table.csv`, summary `pair_summary.json`, plots
`plots/pair_example.png` (one pair, slide style), `plots/pair_grid.png` (all 24), `plots/pair_vs_time.png`,
`plots/les_phase_compare.png`.

- Per coast (D, log-linear exponential fit): tau 33.97 (+) / 34.38 (−) min; coast-to-coast sd 0.12 / 0.16 min.
  Error bars in the table and plots are formal errors from the scatter about a pure exponential (0.07 min); see the
  residual bullet below for why they are not a noise estimate.
- Pair difference tau(−)/tau(+) − 1 (D): **+1.18 % (sd 0.42, sem 0.09), 24/24 positive.**
- **Equivalent constant torque** (D, under an assumed model: per pair, d|f|/dt = −|f|/tau ± b with a common tau and a
  constant b; a direction-dependent drag would also show up in b): **b = −1.24e-6 Hz/s (sd per pair 0.44e-6, sem
  0.09e-6)**; b·tau = −2.6 mHz at tau 34 min. Negative = along −. Which of ± is CW is not established.
- **Signal scale** (A: torque 1.1e-18 N m from Molly's slide; I = 1.1e-11 kg m², DECISIONS ±10 %):
  b_signal = N/(2πI) = 1.6e-8 Hz/s, independent of the damping. The slide's 78 µHz equals b_signal × 79 min, the tau in
  `noise_budget_20261009.ipynb` (D); at 34 min it would be ~33 µHz (D).
  - In those units (D): mean asymmetry ~78× b_signal; per-pair sd ~28×; linear trend over the night −0.58e-6 Hz/s
    (~36×; 1.8σ, so not established).
  - Pairs for 1σ on b_signal at this sd: ~760 (D, ASSUMING pair-to-pair scatter is independent and stationary, and
    no systematic; neither is tested).
- **gamma at fixed speed** (D; `pair_plots.gamma_mid`: gamma = −d ln f/dt where f = 0.435 Hz, from a quadratic in
  log f over the band, so the common curvature is modelled; ± formal from the per-turn noise): gamma(+) 0.4916 mHz,
  gamma(−) 0.4857 mHz (sd between coasts 1.7 / 2.3 µHz; per-coast error ~0.15 µHz). Δgamma = gamma(−) − gamma(+) =
  −5.77 µHz (sd 2.12, sem 0.43; per-pair error ~0.22 µHz). The expected recoil changes Δgamma by 2·b_signal/f =
  0.073 µHz (A: N, I as below). Pair values differ by ~10× their errors (M/D); cause of the variation not identified.
- **Residuals about a pure exponential** (M/D): 0.51 mHz rms per turn; they do not average down over 10–80 s bins
  (lag-1 autocorrelation 0.98). Averaged over the coasts they form one curve (0.57 mHz rms); the coast-to-coast
  remainder is 0.06 mHz rms; with a curvature term per coast the per-turn rms is 0.08 mHz. So the per-turn rates are
  not exponential in the band, the same way in each coast (M); + and − coasts cover the same band, so this shape is
  shared within a pair (M); how much of it cancels in b depends on the fit model (not checked).
  - Readout noise in b: scaling the formal per-pair error (0.32e-6) by 0.08/0.51 gives ~0.05e-6 (D, rough; assumes the
    0.08 mHz remainder is white), i.e. well below the 0.44e-6 pair-to-pair sd. **What makes up the rest of the
    pair-to-pair scatter is not identified.** (An earlier version of this README said the scatter was mostly timing
    noise, and estimated a ~7× gain from a longer band; both withdrawn.)
- **LES phase readout vs tracker** (`les_phase.py`; D, with these two methods only): LES 2 f-line phase timed per turn:
  2.3 mHz per-turn scatter (tracker 0.51 with the common curvature); LES tau 1.2 % above the tracker and the FFT LES
  (a systematic of this method, not found). Combining the two weighted by their formal errors gives b sd 0.437e-6
  (tracker alone 0.439e-6). In-band 20 s residuals correlate 0.85 between the two readouts. A different LES estimator
  (full waveform, both channels) has not been tried.

## Local decay time vs speed (`local_tau.py`, 2026-11-16)

Tracker per turn; tau from a log-linear fit inside each 0.02 Hz slice, per coast (coasts starting ≥ 0.485 Hz); mean
and sd over coasts (D). − vs + error: from the sd/√n of each direction (D).

| slice (Hz) | tau + (min) | tau − (min) | − vs + |
|---|---|---|---|
| 0.37–0.39 | 27.83 (sd 0.27, n 30) | 28.29 (sd 0.24, n 22) | +1.68 ± 0.25 % |
| 0.39–0.41 | 30.27 (0.17) | 30.74 (0.23) | +1.54 ± 0.19 % |
| 0.41–0.43 | 32.58 (0.20) | 32.98 (0.23) | +1.23 ± 0.19 % |
| 0.43–0.45 | 34.52 (0.17) | 34.93 (0.21) | +1.20 ± 0.16 % |
| 0.45–0.47 | 36.18 (0.15) | 36.64 (0.21) | +1.29 ± 0.15 % |
| 0.47–0.49 | 37.59 (0.16) | 38.08 (0.20) | +1.31 ± 0.14 % |

- The local tau rises ~35 % from 0.38 to 0.48 Hz, so the decay is not a single exponential over this range (D). This
  is the common curvature in the per-pair residuals, and why tau depends on the band (34.0 at 0.40–0.47, 36.5 at
  0.44–0.49). Seen in both readouts (in-band residual correlation 0.85). Cause not identified.
- The − vs + difference is present in every slice (+1.2 to +1.7 %). Whether it changes with speed is not resolved at
  this precision; no conclusion drawn.
- The equivalent-torque fit above assumes one tau within the band; refitting with the measured speed dependence has
  not been done, so b may change.

## Room environment and chamber gas (`ambient_compare.py`, 2026-11-16)

- **Room sensor** (GHS, InfluxDB bucket `xsphere`, 1-min means, pulled 2026-11-16; data Dropbox
  `spinup/2026-11-14/overnight/ambient/`). Where the sensor sits relative to the apparatus is not recorded. Plot
  `plots/ambient_vs_gamma.png`.
  - Temperature (M): only ever reads 23.0 or 23.4 °C, switching back and forth all night: ~0.4 °C resolution, no
    trend visible at that resolution. Humidity ~19 %, also coarse.
  - Pressure (M): rose steadily 1009.3 → ~1017 hPa (+0.8 %; weather).
  - Against gamma at 0.435 Hz (D, 24 pairs): correlation with room pressure −0.79 (gamma−), −0.59 (gamma+), −0.34
    (Δgamma). Room pressure is almost linear in time (correlation with hour 0.99), so one night cannot separate
    "follows pressure" from "drifts with time". Temperature and humidity show no clear relation, at their resolution.
- **Chamber pressure 1.7e-7 mbar** (Molly, 2026-11-16; when it was read relative to the run, and whether it changed
  overnight, not recorded; the gauge is not logged, STATUS).
- **Gas damping estimate** (D, order of magnitude): free-molecular, drag coefficients of order 1 (A), sail upright in
  the plane of the spin axis (A), SAL-001 dimensions (`logs/2026-q3.md` 2026-09-30: wing r 0.88–1.88 × 1.40 mm, bar
  0–0.88 × 0.70 mm per half, ~4.0 mm² per face), disk Ø3.5 mm (thickness to be measured, STATUS), I = 1.1e-11 kg m².
  Sail ~1–2e-7 /s, disk (shear) ~0.6e-7 /s: **gamma_gas ~0.15–0.3 µHz** (factor ~2), i.e. ~0.05 % of gamma
  (~490 µHz) and ~25× smaller than gamma's overnight change (~5 µHz).
  - So the measured damping and its drift are not chamber gas, and room pressure cannot act through the gas (0.8 % of
    gamma_gas ~ 0.002 µHz). Indirect paths (mechanical) are not excluded and not evidenced.
  - gamma_gas is larger than the recoil's change in Δgamma (0.073 µHz). It should be the same for both spin
    directions and cancel in Δgamma (A, not tested); logging the chamber gauge during runs would test it.

## Observations, not interpreted

- tau depends on speed: ~34.0 min at 0.40–0.47 Hz, ~36.5 min at 0.44–0.49 Hz (+1), so damping is not purely
  viscous (exponential) over this range. Cause unknown.
- − damps less than + (longer tau) by ~1.1–1.2 %, every pair, both readouts, same sign as 11-12. Cause unknown.
  Which of ± is CW is not established.
- tau drifts up through the night, faster in − (+0.035–0.039 min/h) than + (+0.016–0.018 min/h), so the pair
  difference grows (~+0.5 % early, ~+1.5–2 % around 08:00–09:00). Cause unknown; temperature and pressure are not
  logged.
- −1 spin-ups failed 10/30 vs +1 1/30 tonight. Unexplained.

## Next

1. Molly: which readout and band to quote (both readouts agree; band choice changes tau by ~7 %).
2. A temperature/pressure log alongside the next long run, to test the drift.
