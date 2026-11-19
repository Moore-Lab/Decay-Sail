# Laser injection test: HANDOFF (updated 2026-11-19)

**State: ND4, ND3 and ND2 interleaved nights done. ND2 (11-18/19) shows the laser: all pairs +7.4 ± 2.6 µHz (median-based +5.7 ± 1.8) vs +5.3 expected; ND4 and ND3 do not resolve it.** Labels: M measured,
D derived, A assumed; "Molly" = Molly said. Numbers from the CW/CCW coast-pair protocol (`coast_series.py`).

## Goal (Molly)

Repeat the overnight coast-pair plots (γ per coast, Δγ = γ(−) − γ(+) per pair) while a 660 nm laser pushes on one side
of the sail, mimicking the Pb-212 recoil (a constant torque of fixed sense): an end-to-end injection test. PI's plan:
high power first (the CW/CCW difference should be obvious), then lower power over longer runs, towards the signal.

## Results so far (2026-11-16)

| run | laser | Δγ (µHz, `gamma_mid` at 0.435 Hz, ± formal) | note |
|---|---|---|---|
| off1 (1 pair) | blocked before chamber | +0.90 ± 0.27 | 11-14/15 night: −5.77, sd 2.12 (24 pairs) |
| on (1 pair) | ND1, 0.30 mW at window | +53.11 ± 0.21 | γ(+) −27.0, γ(−) +25.2, mean γ −0.9 |

- **S1 = +52.2 ± ~5 µHz** (M) at 0.30 mW (error D, corrected 2026-11-19: one pair per state, so it is the pair-to-pair
  scatter, 2.1–5 µHz per pair on the nights, × √2 ≈ 3–7 µHz; the ±0.2 in the table is the fit error only): ~25× the pair scatter. Equal and opposite shifts, mean γ unchanged (no heating
  seen to ~2 µHz). Laser helps the + direction.
- **Torque ~7.9e-16 N m; ~2.6e-15 N m/mW at the window, each ±~10 % from S1 and ±10 % from I** (D: Δγ·π·I·f, I = 1.1e-11 ±10 %).
  Every expected value scaled from S1 carries the same ~10 % (ND2 +5.3 ± 0.5, ND3 +0.63 ± 0.06, ND4 +0.05). Window AR-coated (coating to
  be confirmed, Molly); power measured before it.
- **Recoil equivalent (D): 1.1e-18 / 2.6e-15 ≈ 0.42 µW** at the window.
- **Baseline moved (M, unexplained):** off1 is +6.7 µHz (3.1 sd) from the 11-14/15 mean, both γ moved in opposite
  senses (looks like a torque). So non-interleaved comparisons across days are not trustworthy below ~10 µHz.
- Plots: `plots/laser_pair_panels.png` (blocked vs ND1 coasts), `plots/laser_pairs.png` (gitignored; rerun scripts).

## Calibration (`analysis/calibration_history.md`, 2026-11-16)

- PD (`Y1:RDS-PD_INMON`, after the ND, before the chamber): 685.5 counts = 3.08 mW (Ophir before window) → 222 counts/mW.
- ND1 transmission 0.098 (PD ratio). ND4 (and ND3) transmission at 660 nm: **not measured — Ophir at full power, same
  holder untouched (to do).**
- PD dark: −0.93 (PD covered, blocks room light too). Laser-off (`LASER_OFFSET` 0) level: +0.19 (ND1, 11-16), ~0.5
  (ND3, ND2): it does not fall with the filter, so it is room light; laser leakage at offset 0 is consistent with 0
  (D, rough bound ≲0.5 % of full power; 2026-11-18). Clean test: block the beam vs offset 0, room light unchanged.
- Laser switching (check A): back within 1 % in ~10 s after 0→1000 (overshoot +4–6 % for ~4 s), within 0.3 % after.

## Interleaving (branch `laser-interleave`, 60a4d3b; Mac worktree `~/Desktop/VSCode/decay_sail_wt_li`, worker2 `~/wt_li`)

`coast_series.py --laser-pattern off,on,on,off [--laser-on 1000 --laser-off 0 --laser-settle 30]`: before each pair's
+ spin-up it writes `Y1:RDS-OUTS_LASER_OFFSET`, waits, then runs the pair; never changes mid-pair; restores the start
value on every exit; `laser.csv` logs setpoint, readback, PD per switch and coast. ABBA cancels linear drift.
Analysis: laser effect = mean Δγ(on pairs) − mean Δγ(off pairs). Checks A and B passed on worker2 (rotor at rest; B with
`lab_utils/coast_series_stub_brake.py`, whose fake final brake makes the test exit 2 — harmless). Not yet merged.

## Overnight 2026-11-16/17 (done; analysis 2026-11-17, interpretations not approved)

ND4, `--pairs 24 --laser-pattern off,on,on,off --ncc-min 0.62 --live`, worker2 `~/spinup/2026-11-16/laser/night_nd4_il2`
(first launch `night_nd4_il` stopped at 50 s: room lights off, tracker lost; relaunched with tracker2). 19:52–05:45,
48/48 coasts on target, no stops; tracker 10.1 h, 0 dropped frames, ncc ≥ 0.77.
- **Laser on − off Δγ = −1.13 ± 1.04 µHz (M, `coasts.py`; worker2's whole-band fit −1.6 ± 1.0).** Consistent with 0;
  expected +0.05. Off −5.06 ± 0.76, on −6.19 ± 0.71; ABBA blocks and a drift fit give the same.
- **CW/CCW asymmetry reproduced from 14–15 Nov** (M, `night_plots.py`): τ(−)/τ(+) − 1 = +1.14 % (sd 0.56), 24/24 pairs
  (+1.18 % then); Δγ all pairs −5.63 (sd 2.56); local τ vs speed table the same. off1's +0.9 looks like one outlier.
- **ND4 transmission from the night's PD (M):** on − off step 0.065 counts = 0.29 µW = 9.5e-5 of no filter → ~0.7× recoil.
  PD 1-s trend fetched by worker2 (Dropbox `.../laser/pd_trend/`); PD also sees room light (~4 µW-equiv. lights off).
  A 31 µW period 18:31–18:51 on 11-16 is not in the logs (ND2 trial? ask Molly).
- **No anomaly vs measured power** (`pd_vs_dgamma.py`, `pd_lag.py`): r(PD, Δγ) within state not significant; delay and
  thermal-lag scans (night PD only) max |r| 0.49, reached by chance in 21 % of shifted-PD trials.
- Plots for the PI: Claude doc "Laser injection, 16–17 Nov: notes for PI" (https://claude.ai/artifact/Qm2V7UF1anicjtWFgKsJUs).
- Beam spot (top camera, ND1/no filter frames): left/lower-left of the hub, ~25–30 px from the axis; side camera being
  set up (`camera_utils/SIDE_CAMERA_BRIEF.md`). Rotor nudged 11-17 11:37 to ±30° swing (worker2, Molly's go).

## ND3 night 2026-11-17/18 (done; analysis 2026-11-18, interpretations not approved)

`coast_series.py --pairs 24 --laser-pattern off,on,on,off --laser-on 1000 --laser-off 0 --laser-settle 30 --ncc-min 0.62
--live` (worker2 `~/wt_li` 60a4d3b), `~/spinup/2026-11-17/laser/nd3_night`, 18:16–04:34; 48/48 coasts (44 on target; O08,
O20, O26, O38 stopped on duration at 0.50–0.51 Hz, all − reversals, fit normally); tracker 12 h, 0 dropped frames.
TSP01B logged (`.../2026-11-17/env/`); pressure not (Edwards serial silent, see below); display 1.6e-7 mbar at launch.
- **On − off Δγ = +2.05 ± 1.47 µHz (M, `LASER_DIR=.../2026-11-17/laser python3 coasts.py`; worker2 +2.40 ± 1.32).
  Expected +0.63 (D: PD step 0.80 counts = 3.6 µW, ND3 transmission 1.2e-3, ~9× recoil).** Pair scatter sd 3.3–3.9 µHz
  (earlier nights 2.1–2.6).
- Asymmetry again: τ(−)/τ(+) − 1 = +1.34 % (sd 0.76), 22/24 (M, `RUN=nd3_night ... python3 night_plots.py`).
- **405 nm imaging beam off for this night (Molly, 2026-11-18).** vs ND4 night (beam on): Δγ all pairs −6.58 ± 0.75 vs
  −5.63 ± 0.52 (diff −0.95 ± 0.91), asymmetry +1.34 ± 0.15 vs +1.14 ± 0.11 % (diff +0.20 ± 0.19); local-τ bands also
  +0.8–2.0 % on both nights (M). The imaging beam is not needed for the offset; turning it off did not reduce it.
- Low off pairs 8, 9 (21:16–22:05; −14.5, −13.4) and 12 (23:02; −12.2). PD, tracker ncc and temperature flat at 21:15–22:05.
- **Air temperature (M, TSP01B `ext_T0_C`; one probe hanging in air near the table, away from lights, Molly; `ext_T1_C`
  is an identical copy):** 23.6–24.8 °C, sd 0.22. The internal sensor (27.4–28.0) reads ~3.6 °C high (self-heating?). During
  the run the air cycles at ~23 min, the pair period (FFT peaks 22.7–24.2 min); after the run that period is gone (85, 43 min).
  + coasts 0.105 ± 0.046 °C warmer than − coasts. Δγ vs (T− − T+) per pair r = −0.45, p = 0.03 (one of ~8 tests); γ per
  coast vs T, RH: none (p > 0.1). Cause of the cycle unknown (drive electronics, laser, computers near the table?).
- **Light step 22:42 (M, cause unknown):** PD +0.37 counts in both laser states for the rest of the night, ncc min
  0.79 → 0.83 at the same time; on − off PD step unchanged (0.80). Δγ mean unchanged across it. A lab mate may have been
  in (Molly); not confirmed.
- coast_series stop-on-target misses when per-turn rates jitter ±2 % (4/48): loosen (e.g. 3 of 5 within 1.5 %) on the
  branch before another night.
- Edwards gauge: `/dev/ttyUSB0` (Prolific PL2303) gives no reply to `?GA1`/`?V913` at 9600/19200/38400; `log_pressure.py`
  also fails to open this adapter (DTR ioctl EIO; open with `dsrdtr=True, rtscts=True`). Next: DB9 pin 2–3 loopback.
- Rotor left swinging ±46° about 216° after the final brake (below the 176° safe edge): `nudge.py --calm --live` first.

## ND2 run 2026-11-18/19 (done; analysis 2026-11-19, interpretations not approved)

`coast_series.py --pairs 40 --laser-pattern off,on,on,off --laser-on 1000 --laser-off 0 --laser-settle 30 --ncc-min 0.62
--live` (worker2 `~/wt_li` 60a4d3b), `~/spinup/2026-11-18/laser/nd2_run`, 11:51–04:16; 80/80 coasts on target; tracker
18 h, 0 dropped frames, ncc ≥ 0.824; imaging beam off. PI notes: https://claude.ai/artifact/GjDhtekFq9DRv4JHaZfYJJ.
- **On − off Δγ, all 40 pairs: +7.44 ± 2.65 µHz (mean), +5.72 ± 1.82 (Hodges–Lehmann, bootstrap error); expected +5.3
  (D: PD step 6.77 counts = 30.5 µW from the 1-s trend over coast windows, ±1 % over the run; ~70× recoil)** (M,
  `coasts.py`, `nd2_checks.py` → `nd2_checks.json`). Without the O39 pair, for reference: +5.31 ± 1.62 (linear drift
  +5.31 ± 1.53, quadratic +5.20 ± 1.47, ABBA +5.19 ± 1.02). worker2's exponential-τ fit: +7.6 ± 2.6 / +5.6 ± 1.6.
- **No outlier rule (Molly, 2026-11-19): all pairs stay in the headline.** O39 (+, laser off, 19:34–19:44, not 20:34
  as first relayed): ~9 % extra drag from ~19:38, tracker normal, cause unknown. γ(0.44–0.49) − γ(0.38–0.43 Hz) per
  coast vs the night's median: O39 −37.7 µHz; no other of 176 coasts on ND4/ND3/ND2 beyond 11.4 (`nd2_checks.py`).
- Pair scatter sd 5.0 µHz per state (ND4 2.6, ND3 3.3–3.9). Asymmetry +1.19 % (sd 1.85, 31/40). Mean γ on − off +0.5 ± 0.5.
- Air (ext_T0_C) 23.0–24.5 °C; + minus − coasts −0.05 ± 0.05 °C (ND3's +0.1 not repeated); dip to 17.6 °C
  23:50–00:15 (pairs 30–31) with internal T and RH flat: local to the probe? Δγ in those pairs normal. Pair-period
  cycle not checked yet.
- Rotor left swinging ±51° (final brake stopped on duration): `nudge.py --calm --live` first (Molly's go).
- **Torque against rotor angle (`angle_profile.py`, 2026-11-19, observations):** θ̈ from the 50 fps tracker angles,
  averaged by angle in the 0.40–0.47 Hz band. Hill θ̈ 7.9 rad/s² peak to peak, the same for + and − (lab-fixed,
  speed-independent). Laser-off halves A − B: 45° bump height noise 2.7–4.6 mrad/s² with ~1450 turns per half. Laser
  on − off shows a ±20–40 mrad/s² pattern, the same in both directions and scaling as f² (0.78–0.81× at 0.39 Hz,
  1.07–1.12× at 0.47 Hz, vs 0.82 / 1.17 for f²): kinematic, i.e. a laser-on tracker angle error of ~0.002° depending
  on angle (glare?), not a torque. Expected real laser bump (D, 45° window): 5.8e-5 (ND2), 5.8e-3 rad/s² (full power).
  Δγ is not affected (a fixed angle error cancels over whole turns). Angle-resolved push needs 660 nm kept out of the
  top camera first.
- **Glare check (`glare_frames.py` on worker2, Molly's go 13:20; output Dropbox `spinup/2026-11-18/laser/glare/`):** the
  top camera sees the ND2 laser (M). Laser on − off mean images per 10° of rotor angle: rms 1.87 counts per bin vs
  0.16 for off A − off B (11×), max 159 counts; strong in rotor angles 40–130° and 210–310°, weak at 140–200° and
  320–30°, streaks along the spokes rotating with the rotor; all-angle mean: a streak on the hub just lower-left of the
  axis (x 85–110, y 150–200 px, on or near the white dot's r ≈ 23 px path) and a fixed glint at (115, 83). Consistent
  with the f² angle-profile pattern being glare biasing the dot match (not shown directly).
- **LES vs tracker, ND4 night (`les_vs_tracker.py`, LES fetched by worker2 2026-11-19 to Dropbox
  `spinup/2026-11-16/laser/les/`):** LES 2f line SNR ~840–1080 in every coast. γ per coast LES − tracker −1.25 µHz
  (sd 0.96, 48 coasts; laser off −1.49 ± 0.19, on −1.02 ± 0.19). Laser on − off of Δγ: LES −0.95 ± 1.37, tracker
  −1.13 ± 1.04 (M). The two readouts agree; no sign the laser biases the tracker's γ. LES_SUM_IN1 averaged only
  ~3.1 counts that night although the LES lines were strong, so SUM_IN1 is not a reliable on/off indicator for the
  405 nm beam (the "beam off" for ND3 rests on Molly's word and the weak ND3 lines, not on SUM).
- **LES vs tracker, ND1 pairs 11-16 (`RUNS=off1,on LESDIR=les_nd1 python3 les_vs_tracker.py`; LES in Dropbox
  `.../2026-11-16/laser/les_nd1/`):** laser on − off of Δγ LES +52.4 ± 5.5 vs tracker +52.2 µHz (single pairs; M; ± ~5 from pair scatter, ± 0.3 formal).
  Per coast LES − tracker −0.5 to −2.5 µHz, as on the ND4 night. At 10× the ND2 glare the camera-free readout gives the
  same laser effect.

## Next (exact steps)

1. After each run: `cd analysis/laser_injection_20261116 && python3 coasts.py --no-cache && python3 night_plots.py`
   (`night_plots.py` has RUN = 'night_nd4_il2' hard-coded; `coasts.py` reads every `tracker*/` folder).
2. Ophir: ND2 (and ND3) transmission at full power, holder untouched (ND4 now known from the PD).
3. Plan discussed 11-17 (Molly to confirm): ND2 interleaved (D: ~+5 µHz, ~5σ in one night) with the 405 nm imaging
   beam off for the first ~8 pairs, then on (tests whether the 405 beam makes the −5 µHz offset). Then box the optics,
   shield the PD from room light, log temperature (TSP01B) and pressure with every run.
4. Pair-to-pair scatter (~2.1 µHz) sets how close to the recoil is reachable (D: 5σ at 1× needs ~4e4 pairs per arm):
   temperature/pressure logging (STATUS) and the baseline jump.
5. Merge `laser-interleave` after a clean night (Molly's call).

## Background numbers (pre-run design, D)

Pair scatter 2.12 µHz; Δγ = N/(π I f); radiation-pressure estimate k ≈ 2–9e-15 N m/mW (measured 2.6e-15). The PI's
"78 µHz" is the recoil's steady frequency shift N τ/(2πI) at τ = 80 min (now ~33 µHz at τ ≈ 34 min); not the Δγ the
coast pairs measure (0.073 µHz). Old (Aug) laser numbers: history only.
