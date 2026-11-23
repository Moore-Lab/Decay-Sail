# Laser injection test: HANDOFF (updated 2026-11-21)

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
- **Recoil equivalent (D): 1.1e-18 / 2.6e-15 ≈ 0.42 µW** at the window; ~0.52 µW if the hill factor 1.23 holds
  (see Bursts vs steady below; ND2 30.5 µW is then ~59× the recoil, not 73×).
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
  the run the air cycles at ~23 min (FFT peaks 22.7–24.2 min); after the run the peaks were 85, 43 min. Correction 2026-11-21
  (reviewer): the cycle is not phase-locked to the pairs (ND3 26.2 vs 24.9 min, ND2 25.7 vs 24.3, p 0.32/0.42) and is
  present with no run active (1.26 K p-p 10:00–12:00 on 11-18); "at the pair period" and "gone after the run" do not hold.
  + coasts 0.105 ± 0.046 °C warmer than − coasts. Δγ vs (T− − T+) per pair r = −0.45, p = 0.03 (one of ~8 tests; temp_vs_noise.py and the reviewer get −0.26, p 0.22 at zero lag, 2026-11-21; −0.45 is stale or a different γ); γ per
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
  (D: PD step 6.77 counts = 30.5 µW from the 1-s trend over coast windows, ±1 % over the run; ~59× recoil with the hill factor 1.23, ~73× without; see Bursts vs steady)** (M,
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
- **Side camera (11-17, worker2 `side-camera` branch 3c12597, not pushed; results Dropbox `spinup/2026-11-17/side_camera/`,
  videos `videos/side_camera_2026-11-17/`), D:** beam b = 1.34 ± 0.05 mm from the axis (projected); two radial Al wings
  (r 0.88–1.88 mm, A); beam on a wing −47..+27° from face-on (geometric ±44.5°), twice per turn; spot ≈ 0.35–0.55 ×
  0.55–0.75 mm; no beam walk ND3→ND4.
- **Light budget (`light_budget.py`, 2026-11-19, D, rough):** on a radial plate the torque while lit is (1 + R) P b / c,
  independent of the wing angle (8.9e-15 N m/mW for a perfect mirror). Turn-averaged maximum with R 0.9: 4.2e-15
  (geometric window) / 3.5e-15 (measured 74° window) N m/mW; measured 2.6e-15 ± 14 % = 0.62–0.74 of it. Radiation
  pressure alone can account for the push (an earlier chat estimate that it exceeded the limit used a wrong window
  and an angle factor that cancels; retracted). R, I and the wing geometry are assumed.
- **Bursts vs steady, and the hill (`bursts_vs_steady.py`, simulation, 2026-11-19, D):** with the measured hill, a push
  in two 74° windows gives the same Δγ as a steady push of the same turn-averaged torque (ratio 0.979 at ND1 torque,
  0.999 at full power). Check with no hill: γ 490.01, Δγ 51.87 vs 51.89 expected. **But the hill amplifies both drag and
  torque in the fitted γ by ~1.3× at 0.435 Hz** (drag 490 → 646 µHz; torque Δγ 51.9 → 66.8). If that holds for the
  real rotor, N = Δγ π I f overstates the laser torque by ~1.3 (2.6e-15 → ~2.0e-15 N m/mW, light budget 47–57 % of
  maximum) and the real drag torque, and the recoil's Δγ would be ~0.094 µHz instead of 0.073. The laser/recoil power
  equivalence is NOT unchanged (corrected 2026-11-19): the recoil torque is a predicted absolute value, so its laser
  equivalent rises by the factor (0.42 → ~0.52 µW at 1.23) and its Δγ to ~0.090 µHz; consistent both ways. Factor depends on the hill and speed.
  Cross-check without the hill model (D, assumes the hill is conservative): from energy and lap time, torque factor =
  ⟨ω⁻³⟩/⟨ω⁻¹⟩³ and drag factor = ⟨ω⟩⟨ω⁻³⟩/⟨ω⁻¹⟩² (averages over rotor angle). With the MEASURED speed in 36 angle
  bins (ND2 laser off, turns averaging 0.435 Hz, `sawtooth_windows.measured_speed_vs_angle`): torque 1.23, drag 1.31
  (1.22 / 1.30 with 3-bin smoothing), vs simulation 1.29 / 1.32. Window width does not enter (steady and windowed agree).
  Not yet tested against an independent measurement (e.g. τ against speed).

- **Glare vs dot (`glare_dot_zoom.py`, 2026-11-20, M, averages):** in mean images per 10° (ND2 night) the glare sits
  beside the white dot, never on it (0 overlapping pixels; on - off inside the dot 3-9 counts of ~200-255).
- **Open, for Molly + PI (2026-11-20):**
  - Hill factor: put ÷1.23 into the PI notes / light budget? Molly will discuss with the PI first; PI notes unchanged.
  - The recoil cannot be switched off: the laser-off Δγ offset is ~-6 µHz (ND4 -5.6, ND3 -6.6; unexplained, moved
    6.7 µHz between days), ~70x the recoil (~0.09 µHz). Needs a modulation (Pb-212 decay, 10.6 h; source / no source).
  - What the PI's F0 = 0.81 fN assumes: activity and time, escape fraction, hemisphere, source position (1.38 mm assumed).
  - Alpha charging and heating could add torques the laser does not.
- **glare_raw run (2026-11-20, worker2, staged):** one + spin-up to 0.5 Hz, laser at ~ND2 (PD 7.0-8.9; filter not
  confirmed), then laser on 2-3 min / off 1 min while coasting; tracker 50 fps, AVI every 10th frame. Upload to Dropbox
  spinup/2026-11-20/laser/glare_raw/. Next: pull single frames at 230-280 deg and check glare vs dot.

- **Offset stability (`offset_stability.py`, 2026-11-20, M):** laser-off Δγ night means 11-14/15 −5.77 ± 0.43,
  ND4 −5.06 ± 0.76, ND3 −7.61 ± 1.13, ND2 −9.46 ± 2.40 (all pairs; median −7.37); chi2 5.8 for 3 dof (p ~0.12), so
  consistent with one constant ~−5.9 µHz at the ~1 µHz level. Within nights, means of 2/4/6 laser-off pairs scatter as
  pure pair noise (no wander seen; few blocks). 11-16 off1 (+0.9) is a single pair, not evidence of a day-scale jump.
  Recoil ~0.09 µHz: needs stability tested ~30x finer than these data can.

- **Idea (2026-11-20, not run): test the hill factor from data.** Track omega^2 at a fixed rotor angle (e.g. 205 deg)
  turn by turn per coast (50 fps tracker); at fixed angle the hill term is the same, so I*omega*domega/dt gives the
  torque by energy, no lap-rate fit. Compare laser on vs off (ND1 pair, ND2 night) with N = Delta gamma pi I f: ratio
  should be ~1.23 if the hill factor is right. Within-turn sawtooth at full power: not useful without a 660 nm camera
  filter (glare ~100x ND2 would fake mHz-level speed changes vs a ~0.2 mHz kick).

- **Pair scatter and offset against speed (`band_scatter.py`, 2026-11-20, M; interpretations not approved):** γ per
  coast in 0.37–0.41 / 0.41–0.45 / 0.45–0.49 Hz (`band_scatter_<run>.json`). Laser-off Δγ: ND4 −13.6 / −5.3 / −4.6,
  ND3 −16.4 / −8.5 / −6.7, ND2 −14.2 / −9.9 / −6.7 µHz (2.4–2.9 % of γ in the low band, 1.0–1.5 % in the high band):
  still falling at the top of the range. Pair sd minus fit error, torque-equivalent at 0.435 Hz (D): ND4 5.7 / 2.6 /
  3.1, ND3 7.1 / 4.0 / 4.8 µHz, so the scatter drops from the low to the middle band, then not further. Pair residuals
  correlate low–mid 0.37–0.55, mid–high −0.05 to 0.16, low–high ~0 (each ±~0.2); no timescale follows from this
  (corrected 2026-11-21; see G1).
- **G1, within-coast vs per-coast (`g1_within_coast.py` → `g1_<run>.json`, 2026-11-21, M; interpretation not
  approved):** 10-block jackknife of γ within each coast, rms 2.5–2.8 µHz, matches the coast-to-coast sd (1.9–2.5;
  ND2 + 8.0 with O39, MAD 3.25) on all three nights: the scatter is made within the coast. The formal fit error
  (0.13–0.17) assumes white per-turn noise and is ~20× too small. Fit residuals are red (power at periods > 1 min
  7–12× that at < 20 s). Rough torque spectrum, ND4 (D, scratch script, I 1.1e-11, r 1.38 mm): flat ~6–7e-13 N/√Hz
  at periods 30 s–5 min, ~100× thermal; readout dominates below 30 s. Pairs are independent:
  sd(Δγ) ≈ √(sd γ+² + sd γ−²) in every band. Gas drag at 1.6e-7 mbar is ~1e-10 /s (D), negligible.
- **glare_raw run 2026-11-20 (worker2; deviated from the plan, `run_log.txt` in Dropbox `.../2026-11-20/laser/glare_raw/`):**
  spun up with the laser on; ND out and offset 1500 from 13:50 (PD ~2450 counts ≈ 11 mW, D); no laser-off coast. Tracker
  (13:47–14:12) shows the laser accelerating the rotor 0.51 → 0.65 Hz in 21 min (M); fit f∞ 0.82 ± 0.01 Hz, τ 31.6 min,
  implied torque 3.0e-14 N m vs 2.9e-14 from the calibration (D). Laser stayed on to ~17:21, then off; the coast
  from ~0.8 Hz was not recorded (no tracker; LES off, imaging beam off).
- **Clock:** host − `Y1:DAQ-DC0_GPS` moved from 315947891.97 (11-16) to ~315947476 (11-20) (worker2 session, M).
  `pd_trend.py`, `pd_vs_dgamma.py`, `pd_lag.py` hard-code the 11-16 value: fine for the ND4 night (≲50 s), wrong by
  minutes for later nights. Read the offset per run before reusing them.
- **Sept/Oct vs November wobble, same LES readout and estimator (`les_wobble_sept_oct.py` → `les_wobble_sept_oct.json`,
  2026-11-21, M; interpretation not approved):** 0.40–0.47 Hz band, jackknife scaled to 10 min in band: CCW 09-13 4.7,
  CW 10-11 4.7 µHz (one coast each, γ ~225 µHz); ND4 night rms 2.4 µHz (48 coasts, range 1.6–4.3, γ ~490). The slow
  torque noise was not smaller when the damping was better.
- **damping_1300, 2026-11-21 (worker2; laser 1300 counts, ND out, + direction; Dropbox `spinup/2026-11-21/laser/damping_1300/`;
  `damping_1300.py` → `damping_1300.json`; M, one coast; interpretation not approved):** laser plateau 0.605–0.606 Hz;
  free coast 0.59 → 0.28 Hz. τ by band 0.50–0.59 / 0.47–0.50 / 0.40–0.47 / 0.33–0.40 Hz: 39.9 / 37.4 / 33.9 / 31.7 min
  (Sept 85.5 min at 0.50–0.75, so ~2.1× more damping at matched speed). Wobble scaled to 10 min: 2.2 µHz at
  0.50–0.59 vs 2.3 at 0.40–0.47 (no drop with speed, each ±~50 %); 0.33–0.40 Hz 9.3 µHz (residual lag-1 0.82).
  Force-equivalent noise during the laser-held plateau (16:05–16:21) 2–6e-12 N/√Hz, ~3–9× the free coast at similar
  speed; laser power noise (PD 1740–1786 counts) is a candidate, not checked against the PD log. **Caution (2026-11-22):**
  during the plateau the tracker angle jumps ~+90° at ~55° and back at ~140° on every turn (laser glare at 8 mW; 964
  jumps > 20°, 60 % of frames on the 'blanked' path), so the plateau noise figure may be a tracker artefact; not trusted.
- **Speed around a turn, laser on vs off (`ripple_figure.py` → `ripple_on_off.json`, plot `ripple_on_off.png`; 2026-11-22,
  M):** ND2, + coasts at 0.435 Hz, 10° bins: the hill makes the speed swing 0.28–0.63 Hz within each turn (laser off and
  on identical). Laser on − off per bin rms 384 µHz vs ~230 µHz bin error (χ²/dof 2.9); the expected laser kick is ~1.3 µHz
  per pass, far below this. The 8 mW plateau cannot be used for this (tracker glare, above).
- **Air temperature vs coast noise, ND3 + ND2 (`temp_vs_noise.py` → `temp_noise_<run>.json`, `temp_pairs_summary.json`,
  plots `temp_vs_noise.png`, `temp_pair_dgamma.png`; 2026-11-21, M; interpretation not approved; reviewer re-check
  pending):** within-coast noise (jackknife) does not follow T, |dT/dt| or T rms (|ρ| ≤ 0.17). Pair Δγ (laser-state
  mean removed) vs T(−) − T(+): ND2 (O39 and the 17.6 °C dip excluded, 37 pairs) r −0.76, −12.0 ± 1.7 µHz/K, scatter
  5.1 → 3.4 µHz with the T term; first 7 h (air ~1 K sawtooth, period 26 min vs pair period 24.5) r −0.88, 6.3 → 3.2;
  hours 7+ (air steady) r −0.41 (p 0.09). ND3 r −0.26, −4.4 ± 3.5 µHz/K, scatter unchanged 3.6. 12 tests. Probe is in
  air outside the chamber. Reviewer re-check 2026-11-21 (`.claude/review_temp_dgamma_20261121.md`): AGREE; reproduces from
  raw data; 0 of 401 circular shifts of T reach r −0.76; leave-one-out −0.73..−0.79; Theil–Sen −12.7 (−16.9..−9.4).
  Pearson needs the dip out (a probe artefact); with O39 in (no-outlier rule): r −0.37, −9.9 ± 4.1 µHz/K. The T cycle
  (~26 min) is not locked to the pairs and runs with no run active; source unknown. Per coast the effect is common-mode
  (γ minus neighbours vs T −11.9 ± 1.3 µHz/K, ≈ −2.4 %/K), reaching Δγ because the two coasts sit ~half a T cycle apart.
  Best match with T taken 2–5 min after the coast (ND2 +2 min r −0.81; ND3 +5 min r −0.63, post hoc). Not a causal
  temperature coefficient: probe outside the chamber; TSP logger clock assumed (not verified) to be worker2 host time.
  Laser on − off with the ΔT term +4.37 ± 1.11 µHz vs +5.14 without (37 pairs).
- **G3, hill height and angle per coast (`g3_hill.py` → `g3_hill_<run>.json`, 2026-11-22, M; interpretation not
  approved):** hill from energy, U(θ)/I = −½ω² + const, per turn in 10° bins (band 0.40–0.47 Hz). Depth 6.9e-11 J on ND2
  and ND3; + and − profiles correlate 1.000 (conservative, direction-independent). Height drifts smoothly −0.7 % (ND2,
  16 h) / −1.0 % (ND3, 10 h); coast-to-coast scatter about the trend 0.04–0.07 % (error 0.02–0.03 %); height changes
  account for ≲ 0.5 µHz of the ~2.5 µHz per-coast noise. Hill ANGLE (phase of the 1-per-turn part): scatter about the
  night trend 0.07–0.09° (error ~0.02°). Pair Δγ vs angle difference between its coasts: ND2 r 0.65 (p 1e-5),
  with ΔT: scatter 5.1 → 2.8 µHz; ND3 r 0.34 (p 0.11), 3.5 → 3.4. Angle difference correlates with ΔT (r −0.4, −0.6).
  ~15 tests; estimator drifts −1.1°/10 min within every coast (speed dependence, unexplained).
  Estimator check 2026-11-22 (`G3_DETREND=1`, `G3_PBAND`; `g3_hill_<run>_chk*.json`): removing the within-turn drag
  trend before taking the angle shrinks the angle scatter ~40 % (0.070 → 0.042°, 0.069 → 0.037°) and the correlation
  stays, same sign: ND2 r 0.53 (p 8e-4; circular-shift null 1/34), ND3 r 0.44 (p 0.03; null 0/21). Speed-matched turns
  only (0.43–0.44 Hz): ND2 0.41, ND3 0.23. Speed differences between coasts (sd 0.0002 Hz) do not carry it.
  **Frozen test for the 11-22 5-min run (set 2026-11-22 before the data arrived):** `G3_DETREND=1`, angle band and γ band
  both 0.44–0.49 Hz (the coasts run ~0.50 → 0.44), pairs (O1,O2), (O3,O4)…, pair Δγ = γ(−) − γ(+) with its mean removed,
  Δangle = angle(−) − angle(+). Pass: r > 0.3, positive sign, and fewer than 5 % of circular shifts of Δangle against Δγ
  reach |r|. Report the coefficient (ND2/ND3 30–44 µHz/deg at 0.435 Hz) and the scatter with/without the term.
  **Result, 11-22 5-min run (`fast_5min`, 40 pairs, laser 0; `g3_frozen_test.py` → `g3_frozen_test_fast_5min.json`,
  2026-11-22, M; interpretation not approved): PASS.** r +0.64 (p 9e-6), 0 of 39 circular shifts reach it; 46.7 ± 9.1
  µHz/deg; pair scatter 4.15 → 3.23 µHz. Not fixed by the spec: γ evaluated at the band centre 0.465 Hz (gamma_mid's 0.435
  is outside the band); at 0.44 (band edge) r +0.52, shifts 0/39, but scatter 10.3 µHz (edge extrapolation). Hill depth
  6.7e-11 J, ± templates corr 1.000. Same run, post hoc (not part of the test): air ΔT (TSP re-uploaded 11-22, logger
  ran throughout) r −0.63, scatter 4.15 → 3.26; Δangle and ΔT correlate r −0.85, so the two cannot be separated here
  (both together 3.20). No trend in time (r −0.10). γ(+) and γ(−) of a pair are uncorrelated (r −0.10): no
  cancellation from close spacing. Per-coast jackknife median 0.96 µHz vs per-coast sd 2.6–3.0: scatter is set per coast.
  Pair period 11.4 min; τ 36.4 min. Reversal to target median 34.2 s (24.5–73.2, n 79).
- **Does the scatter scale with the drag γ? (2026-11-22, from existing `band_scatter_*.json`, `g1_*.json`; M/D;
  interpretation not approved):** not testable with current data: γ spans only 450–567 µHz (×1.26) across speed bands and
  is the same every November night. Across bands, pair scatter (MAD sd) rises ~2× from 0.41–0.45 to 0.37–0.41 Hz
  (ND4 3.1 → 6.5, ND3 4.2 → 9.6, ND2 5.4 → 8.5 µHz) while γ rises 15 %: not proportional to γ; grows at low speed.
  Across nights at fixed γ (~495 µHz), scatter varies ~2× (2.1 → 5 µHz). The −2.4 %/K temperature figure is −12 µHz/K
  divided by γ, not a demonstrated proportionality. A real test needs pairs at a different drag.
- **Spin-up Phase A (simulation, `analysis/spinup_phaseA_20261121/README.md`, 2026-11-21, D):** see that README for
  the settings and results; Phase B (live, laser 0) approved by Molly for the night of 11-21, run by worker2 into
  Dropbox `spinup/2026-11-21/phaseB/`.

## Next (exact steps)

1. After each run: `cd analysis/laser_injection_20261116 && LASER_DIR=<day>/laser python3 coasts.py --no-cache &&
   RUN=<run folder> python3 night_plots.py` (`night_plots.py` defaults to RUN = 'night_nd4_il2' if RUN is not set;
   `coasts.py` reads every `tracker*/` folder).
2. Ophir: ND2 (and ND3) transmission at full power, holder untouched (ND4 now known from the PD).
3. ND2 interleaved: done 11-18/19 (above). The 405 nm beam was off for all of ND3 and ND2, and the offset stayed
   (ND3 section), so the planned off/on split is no longer needed. Still to do: box the optics, shield the PD from
   room light, log temperature (TSP01B) and pressure with every run.
4. Pair-to-pair scatter sets how close to the recoil is reachable. It has grown night by night (M): 2.1 (11-14/15),
   2.6 (ND4), 3.3–3.9 (ND3), 5.0 µHz (ND2; 5.0 also with O39 dropped); cause unknown. D: 5σ at 1× recoil (0.073 µHz)
   needs ~4e4 pairs per arm at 2.1 µHz, ~2.3e5 at 5.0 (~0.66× those if the hill factor holds, recoil 0.09 µHz).
   Leads: temperature/pressure logging (STATUS) and the baseline jump.
5. Merge `laser-interleave` after a clean night (Molly's call).

## Background numbers (pre-run design, D)

Pair scatter 2.12 µHz; Δγ = N/(π I f); radiation-pressure estimate k ≈ 2–9e-15 N m/mW (measured 2.6e-15). The PI's
"78 µHz" is the recoil's steady frequency shift N τ/(2πI) at τ = 80 min (now ~33 µHz at τ ≈ 34 min); not the Δγ the
coast pairs measure (0.073 µHz). Old (Aug) laser numbers: history only.
