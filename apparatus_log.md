# Apparatus log

Dated record of what changed and what was run. **New entries go at the top of
`## Changes`**, newest first. Dates are UTC unless noted.

Each entry is short: what was done or run (command, front-end GPS start–stop), what was
seen, and a link to any analysis. Label claims as measured, derived or assumed.
Open items live in `docs/STATUS.md`, current values in `docs/DECISIONS.md`, and which
constants applied to which datasets in `analysis/calibration_history.md`.

Entries before October 2026 are archived in `logs/2026-q3.md`.

---

## Changes

### 2026-11-12 (afternoon) — Coast pairs C1-C3; camera moved; tracker re-centred

- Coast pairs (`--spin-to 0.5 --stop-on-target 3 --stop-tol 0.01`, dad1a29; 600 s coasts, no writes): C1 (+1), C2 (-1) complete; C3 (+1) coast valid 0-336 s. First CW/CCW comparison: `analysis/coast_pairs_20261112/README.md`.
- Molly moved the camera during C3's coast (14:19:33 local, host 1794511172.9) and again ~14:55; series stopped (no writes after 14:13:56). Final view vs 11-11: +10, +16 px, -1.2 deg, scale -1.1 %. New tracker centre (131.03, 178.79), confirmed by Molly on a still; tracker locks (ncc 0.945). STATUS updated. Files Dropbox `camera_check/2026-11-12/` and `/2026-11-12b/`.

### 2026-11-12 (afternoon) — Reversal series U9-U20 at 0.5 Hz (live, worker2, Molly's go)

- `brake_offsets.py` c5a2afe (reversal: brake first if rotating against --dir), cap fix c1a86f5 from U19; `--level 800 --w-push-max 120 --spin-to 0.5 --duration 480 --ncc-min 0.70`. FE GPS 1478552676 (U9) to 1478560425 (final spin-down).
- 8 pass, 3 fail (+1 settling dips), 1 incomplete (U18: spurious speed-cap trip after a 150 ms tracker stall; fixed). All reversals turned along D (first turn 52-142 s). Combined with the morning series: - 9/10, + 6/10 (interpolated timing). Table: `lab_utils/SPINUP_HANDOFF.md`. Data Dropbox `spinup/2026-11-12/reversal/`.

### 2026-11-12 — worker2 disk: local video copies removed (Molly's OK)

- 11 tracker .avi files (32.7 GB) deleted on worker2 from `~/spinup/2026-11-11/{g2,spin}` and `~/spinup/2026-11-12/series` after a fresh `rclone check` showed each on Dropbox unchanged; CSVs, logs and consoles kept locally. Free space 24 -> 54 GB. Copies: Dropbox `spinup/...` (same paths).

### 2026-11-12 — Spin-up attempt series at 0.5 Hz, 4 per direction (live, worker2, one go from Molly)

- `brake_offsets.py` (voltage-steps e5c6495): U = `--map g1 --level 800 --w-push-max 120 --spin-to 0.5 --dir D --duration 540 --ncc-min 0.70`; D = spin-down `--level 1600 --w-push-max 120 --spin-to 0.001 --duration 300`. FE GPS 1478540331 (U1) to 1478549582 (D8).
- **6/8 passed at frame-resolution timing, 7/8 with interpolated crossings** (pass: first turn along D; within ±5 % of 0.5 Hz within 300 s; all turns of the next 300 s within ±5 %). U6 fails only at frame resolution (one turn at 0.527); U7 fails both ways (two turns at 0.471/0.474). Means 0.501-0.511 Hz (both directions run 1-2 % high). Spin-downs stopped rotation in 10-33 s (D1 failed with push limit 90, since fixed). No safety stops except D2's tracker stall during a concurrent upload. Table and files: `lab_utils/SPINUP_HANDOFF.md` (SERIES), Dropbox `spinup/2026-11-12/series/`.

### 2026-11-11 (night) — Spin-up by pumping over the top (live, worker2, Molly's go; DECISIONS 2026-11-11 amended rule)

- S1 `brake_offsets.py run --map g1 --level 1600 --spin-to 0.5 --dir 1 --duration 480 --enable-outputs --live` (voltage-steps 70ca56b), FE 1478503576-1478503921: **first full turn along +1 at 40 s after the field went on; ~130 turns at 0.43-0.47 Hz (mean ~0.45) over ~5 min**; 0.5 Hz not reached (the governor kept pushing; ceiling with pushes only below 90 deg/s). Peak 291 deg/s; tracker ncc min 0.82. Stopped at 338 s on the speed cap, which was spurious (two frames with the same host time; fixed in 18e3e0a). The rotor coasted with the field off: 0.42 Hz just after, 0.41 Hz ~2 min later. Data worker2 `~/spinup/2026-11-11/spin/`, Dropbox `spinup/2026-11-11/spin/` (tracker_S1 verified).
- Free coast after S1: 0.43 -> 0.27 Hz in 11 min, last full turn at +681 s, then a swing (±100 deg by ~40 min). Video timing of S1: 0.459 Hz. Full-circle trap and damping from the coast: `analysis/spinup_spin_20261111/README.md` (barrier at 60 deg, 6.5 rad^2/s^2; c = 3.8e-4 /s).
- 2026-11-12 S3, spin-up --dir -1 (18e3e0a). First try (FE 1478536186) stopped at 26 s on ncc < 0.8: the tracker match dips to ~0.78 at 320-330 deg (S1 0.82 at 342). Rerun with `--ncc-min 0.70` (Molly's go; no frame went below 0.78), FE 1478536726-217: **first full turn along -1 at 25.8 s from the ±98 deg swing; 212 turns; 0.45-0.49 Hz, hold 200-480 s mean 0.470 Hz (0.447-0.491)**; 0.5 Hz not reached. Peak 274 deg/s.
- S4, spin-down --dir -1 --spin-to 0.001 (FE 1478537267-572): rotation ended at 37 s; then braked the swing to ~±42 about 213.5 by 300 s. End states clean. Files Dropbox `spinup/2026-11-11/spin/`. S3 video timing (independent of the tracker): 10 turns in 1066 frames = 0.469 Hz. tracker_S3 copy verified (135001 frames, 0 dropped).

### 2026-11-11 (evening) — Spin-up G2: brake from a large swing, DC-coupled (live, worker2, Molly's go)

- `brake_offsets.py run --map g1` (voltage-steps 7f62942). Each repeat: kick A 2400 + `--pump-to`, then brake at 800 counts. Data Dropbox `spinup/2026-11-11/g2/`.
- Repeat 1 (FE 1478496197-): kick ±18.8 deg (G1 AC: ±18.2), pump to 36 in 2.7 s, brake from ±40.1 (peaks 256.9/176.6): < 10 deg in 3.3 s, final ±0.6. Pass.
- Repeat 2 (FE 1478497433-): kick only ±5.5 deg (same pull to 194.6 as repeat 1; released at a different point of the hold oscillation, not proven); pump to 32 overshot to ±42.4 about 216.9; first brake tripped the safe range (175.7 < 176) after 0.14 s. Brake rerun with `--safe 173,261` (Molly's go): **braked well (Molly); video kept** (FE 1478497989, 125 s; `--safe 173,261` this run only): ±40.4 about 216.8 -> first peak < 10 deg at +9.1 s (a 4-8 s plateau of +14..+21 deg peaks first), < 2 deg at +10.0 s, final ±1.2. Pass. Video tracker_2b/output_basler_gps1478481358.avi.
- Repeat 3 (FE 1478498249-; brake FE 1478498309, default safe 176-258): kick ~0 (released near the top of the hold oscillation), pump to 26 in 4.6 s, brake from ±35.4 about 215.9: first peak < 10 deg at +6.2 s, final ±0.2. Pass. Video in tracker_2b.
- All three brakes met the proposed G2 criteria (results `analysis/brake_g2_20261111/README.md`); the gate pass is Molly's call. Dropbox copy verified (rclone check, 0 differences; tracker_2b 1800 s, 90001 frames, 0 dropped, holds repeat 2's free swing and rerun and all of repeat 3). worker2 idle, front end at rest.

### 2026-11-11 — HV amp switched to DC coupling; carry simulation (Mac); G1 run recorded

- Molly moved the HV amp J1/J5 jumpers from the capacitor (AC) path to the direct path: outputs now DC-coupled (DECISIONS 2026-11-11). Cables were being reconnected afterwards. Nothing measured on the new path yet.
- Camera check after a Basler USB replug (worker2, camera only, no EPICS writes): USB3 5000M; settings as G1 (256x292, 15 ms, 50 fps, 0 dropped). View unchanged to <= 0.55 px and 0.02 deg (phase correlation and ECC against G1's first 300 frames). The rotor was at rest at 207.7 deg (±0.14), against 208.6 before G1: observed, not explained (the view shift is far too small to account for it). Files Dropbox `camera_check/2026-11-11/`.
- HV amp direct (DC) path, outputs off, offsets 0, scope DC-coupled with offsets reset: all three electrodes read ~0 V (Molly; V2 looked slightly high, centred on 0 when zoomed). So no output floor at 0 counts.
- DC check step 1 (worker2, Molly's go, outputs on): V2 0 -> 400 -> 0 counts, 3 s hold (`voltage_steps.py run --plan dc_step1.csv --live --enable-outputs`). First try: the scope triggered early (FE 1478489995-1478490005; OUT_DQ confirms the 400-count step). Repeat (FE 1478490325-334): CH2 +4.70 V above a +0.75 V baseline (0.01175 V/count), flat over 3 s (-0.9 mV/s), edge overshoot to 7.1 V; V3/V4 unchanged (baselines +0.245/+0.050 V at 0 counts). Rotor moved -0.4 to -0.5 deg during the hold and returned; the G1 map and trap slope predict about -2.4 to -3 deg (derived): observed, not explained. Data worker2 `~/dc_check/2026-11-11/`, Dropbox `dc_check/2026-11-11/`.
- DC check step 2 (worker2, Molly's go, outputs on; FE 1478490564-607): V2, V4, V3 each 400/800/1200/0 counts, 3 s per level (`voltage_steps.py run --plan dc_steps.csv --live --enable-outputs`). Baseline-subtracted fits: V2 0.01237, V4 0.01279, V3 0.01259 V/count (per-level V/count rises 0.0117-0.0121 at 400 to 0.0122-0.0126 at 1200; common intercept -0.28 V); sag <= 0.2 % per 3 s plateau; crosstalk <= 12 mV. Scope zero depends on V/div (0-count baselines V2 +1.89/+0.75 V at 5/2 V/div; S1's offsets were these). Rotor during the V2 holds: -0.3 / -1.4 / -3.0 deg at 400/800/1200 (from 208.28; grows faster than the level, observed, not explained); the release from 1200 left a +-5 deg swing that blurs the V4/V3 plateaus. Data worker2 `~/dc_check/2026-11-11/vsteps_1794438991`, scope `scope_1794439054_step2.npz`.
- Scope: S1's constant trace offsets (CH2 +1.9, CH3 +0.5, CH4 +0.1 V) were the scope's own channel offsets (Molly, GND coupling).
- Spin-up G1 (live on worker2, earlier 11-11, Molly's go): kick A 2400, pump to ±35° (`brake_offsets.py --pump-to 35`), then 50 pulses (`voltage_steps.py --plan analysis/spinup_g1_20261111/g1_plan.csv`), on the AC path. Data Dropbox `spinup/2026-11-11/g1/` (tracker file gps1478438744). Results `analysis/spinup_g1_20261111/README.md`.
- Stage-1 carry simulation (Mac, AC path, before the jumper change): `analysis/carry_sim_20261111/README.md`. Derived, not approved.

### 2026-11-10/11 — Brake gates B2 and B4 on worker2 (live)

- B2 push-map pulses (11-10, outputs on): `voltage_steps.py run --plan b2_plan.csv --live --enable-outputs` (45 pulses, 800 counts),
  FE start 1478415207 (host 1794363700–1794363917); results `analysis/brake_b2_20261110/`.
- B4 (`brake_offsets.py` on `voltage-steps`, live tracker from `feedback-drive`): stage 1 outputs off (11-10, FE 1478419559–629);
  stage 2 outputs on but the rotor was at rest (11-11, FE 1478448785–915); stage 2b kick then brake, outputs on (11-11, FE
  1478449691–831): ±19.5° braked to ±2.6° in 4–8 s. End states clean. Data Dropbox `brake/2026-11-10/`, `brake/2026-11-11/`.
  Results `analysis/brake_b4_20261111/README.md`.

### 2026-11-10 (evening) — Detent runs on worker2, outputs ON, video (live)

- Ran (worker2, `~/wt_detent`, branch `detent-test` at 1b10ddc, Molly's go, remote): `python3 stator_detent.py run --counts 3200
  --cycles 1 --on 8 --release 30 --gap 10 --enable-outputs --live`, then the same at 6400; Basler `--record --show`, 15 ms.
  FE GPS 1478408039–1478408390. End state: outputs off, offsets 0, TRAMP 1 (caget; the script's own end line read stale values).
- Data: Dropbox `Microspheres/TFINER/data/detent/2026-11-10/`.
- Saw: no snap into a detent; each switch-on kicked the rotor, and the swing grew to ±74° and stays (Q ≈ 4300). Results:
  `analysis/detent_20261110/README.md`; trap over the swing `analysis/brake_b1_20261110/`; model checks
  `analysis/f3_step2_20261110/README.md`.

### 2026-11-10 (afternoon) — Voltage steps S1 on worker2, outputs ON, scope + video (live)

- Ran (worker2, `~/wt_vs`, branch `voltage-steps` at 70cf217, Molly's go, Molly not at the bench):
  `python3 voltage_steps.py run --preset s1 --level 1200 --field-level 1200 --live --enable-outputs`, with the RTB2004
  armed by hand (SING) and read after; Basler `grab_basler.py --record --duration 420 --exposure 15`. FE GPS
  1478396766–1478396867. Offsets 0, outputs off and TRAMP 1.0 at the end.
- Scope set remotely before the run: 20 s/div, CH2–4 5 V/div (20 V/div refused with 1x BNC), offsets 0. Plain STOP/read
  at these timebases returned stale records (marker test); single acquisition worked.
- Data: Dropbox `Microspheres/TFINER/data/voltage_steps/2026-11-10/vsteps_1794345310/` (scope, OUT_DQ, video).
- Saw: every update reached the amplifier outputs, 8/s included, all three electrodes together; ~0.0124 V/count; τ ~5.6 s;
  rising edges overshoot ~35 % for ~1 ms. Results: `analysis/voltage_steps_20261110_s1/README.md`.

### 2026-11-10 — Clean 8/s field test on worker2, outputs off (live)

- Ran (worker2, `~/wt_vs`, branch `voltage-steps` at 96519e1, Molly's go): `python3 voltage_steps.py run --preset field8
  --live --outdir ~/voltage_steps_runs`, then `fetch`. FE GPS 1478386135–1478386519. Outputs never on. Offsets 0 and
  TRAMP 1.0 at the end.
- Data: Dropbox `Microspheres/TFINER/data/voltage_steps/2026-11-10/vsteps_1794334700/`.
- Saw: 1915/1920 random-direction updates at 8/s landed on all three electrodes; the 5 failures were all within ~1 ms of
  an intake. Results: `analysis/voltage_steps_20261110/README.md`.

### 2026-11-09 (late) — Voltage steps S0 on worker2, outputs off (live)

- Ran (worker2, `~/wt_vs`, branch `voltage-steps` at e5bf8d2, Molly's go): `python3 voltage_steps.py run --live --shape stair
  --outdir ~/voltage_steps_runs`, then `fetch`. FE GPS 1478304227–1478304642. Outputs never on. Offsets 0 and TRAMP 1.0 at
  the end.
- Data: Dropbox `Microspheres/TFINER/data/voltage_steps/2026-11-09/vsteps_1794252897/`.
- Saw: OFFSET writes applied at 8 Hz; OUT_DQ edges ring (assumed to be the recording filter). Results:
  `analysis/voltage_steps_20261109/README.md`.

### 2026-11-09 (evening) — Voltage-steps scripts built and mock-tested (Mac, no hardware)

- Branch `voltage-steps` (900a654): `lab_utils/voltage_steps.py` (plan / run / fetch) and `voltage_steps_score.py`.
- Tested against a mock front end only (16 Hz ticks; every tick, every 2nd tick, V3 a tick late). The scorer recovered
  each injected behaviour; details and what is untested are in `lab_utils/VOLTAGE_STEPS_HANDOFF.md` (Built).
- Next: worker2 dry run, then S0 with outputs off on Molly's go.

### 2026-11-09 — Drive briefing for the PI; voltage-steps plan; offset-path V/count from existing scope data (Mac, no hardware)

- Briefing for the PI (drives tried, why a faster field update is needed): https://claude.ai/artifact/G1gMdFrWZ5W9PVX1MRt7xD
- PI's plan (Molly): fast DC voltage steps on the electrodes through the offsets, no model change; then talk to Alma.
  Plan, stages and plots: `lab_utils/VOLTAGE_STEPS_HANDOFF.md` (not started).
- Ran `analysis/voltage_steps/offset_gain_refit.py` on the 11-03 W2 scope records.
  - Offset-path gain ≈ 0.0118–0.0122 V/count (derived).
  - That's 4–5 % below the AWG burst gain in the same records; unexplained, and S1 checks it.

### 2026-11-04 — Setup history 09-09 → 10-30 recorded (Molly, recalled; no runs)

- 09-09: chamber on the optical table, no tilt stage (the old stage broke ~August).
- 10-15: new tilt stage put on the table; chamber taken off the table. Rebuild: shims, screw stands removed, PCB and magnet centred, board grounded.
  The 10-21/22 centring was done in this period, off the table.
- 10-26: chamber put on the tilt stage, back on the optical table.
- f₀ measured: 0.310 Hz on 09-09 (stopwatch) and 0.311 Hz on 10-30 (video), so the same across the rebuild.
- `docs/STATUS.md` now gives both dates (stage on the table 10-15, chamber on it 10-26).

### 2026-11-06 — Rotor centring checked on video after the tilt-stage adjustment (Mac, analysis only)

- Between the pre-chirp video gps1478031606 (20:19Z) and this check, Molly moved the camera and adjusted the tilt stage (order not recorded). She then recorded `output_basler_gps1478037739.avi` on worker2 (`grab_basler.py --record`, 120 s, no drive).
- Ran `analysis/rotor_centering/basler_centre.py` on it and on gps1477678308 (11-02) and gps1477428272 (10-30): rotor rim vs spoke convergence in the same frames.
- Saw: the rim is centred to within ~1 px (~2 px uncertainty) today; the method does not show 11-02 further off. Numbers and caveats: `analysis/rotor_centering/README.md` (2026-11-06 section).
- Molly's click checks in `centre_overlay.py` on worker2 (frame 3000 of each video) agree within the ≈ 2 px uncertainty. Before → after: (+0.25, −0.58) → (+0.51, −2.04) px, so it was already centred to ≲ 2 px before. Same README.
- The F3 tracker centre (122.8, 179.6) is stale for the new camera framing.
- Molly then walked the tilt stage back towards its earlier setting, without moving the camera, and recorded `output_basler_gps1478039512.avi` (22:31:34Z, 120 s). Clicked and automatic rotor − board both changed by ≤ 1.2 px (≈ the click repeatability). Same README.
- One more stage adjustment, camera not moved; Molly stopped adjusting there. Clip `output_basler_gps1478040383.avi` (22:46:05Z, 120 s). Rotor − board: clicked (−0.23, −1.17) px, automatic (+2.1, +0.9) px. Through all four states the rotor stays within ≈ 2–2.5 px (≈ 50–100 µm) of the board centre, with no change resolved. Tracker centre for the new framing ≈ (117.5, 165.1) clicked; confirm by replay before use. Same README.

### 2026-11-06 — Rotor-centring overlay for the tilt stage (Mac, no hardware)

- New `camera_utils/centre_overlay.py`: click circles on a board feature and on the rotor (or its white dot's orbit) to read rotor-minus-board dx, dy. Reads snapshots/files only and never opens the camera.
- Tested headless on the Mac only, with a frame from gps1477678308 and a synthetic fit. Not yet run on worker2.

### 2026-11-06 — Oscillator chirp through f₀ from rest (worker2 agent, Molly's go): large swing, no over-the-top

- Branch `osc-chirp` (2ba3ad4), runbook `lab_utils/OSC_CHIRP_RUNBOOK.md`; worker2 worktree `~/wt_chirp`.
- G0, outputs off: `sweep --felec 0.40 --to-felec 0.15 --step 0.01 --dwell 4 --drvtramp 3.5 --amp 6400 --pedestal-ramp 10 --live`,
  FE 1478047513–658. `osc_chirp_check.py`: G0 PASS (phase continuous, glide 0.40 → 0.15 Hz).
- R1, the same with `--enable-outputs`, from rest (rest angle 229.6), FE 1478047773–918.
  - The swing grew to 137° (0.74 of the barrier) by ~45 s, then held 0.45–0.75 of the barrier to the end.
  - Left swinging −104/+130°.
- R2 skipped (Molly). Free swing, drive off, 10 min, FE 1478048134–734: 108° → 91°.
- Analysis (Mac): `analysis/osc_chirp/README.md`.
  - No lock: the swing stayed at ~0.25–0.30 Hz while the drive went down.
  - The linear part of the drive scales with amplitude to 6400; the 2× part is undetermined.
  - The trap is unchanged since 11-04 (0.15 rad²/s² rms).
  - Damping time τ ≈ 32–35 min (derived).
- Data: Dropbox `data/osc_chirp/2026-11-06/`.

### 2026-11-04 (late) — F3 simulator checked against brake 1 (Mac, analysis only, no hardware)

- Ran `analysis/f3_20261104/outdq_replay.py` and `f3_check.py repro` (branch `feedback-drive`, uncommitted).
- Measured from the saved data:
  - OUT_DQ and LES timestamps disagree by 3.3 s (brake 1) and 4.2 s (live 2);
  - about every second matrix write lands;
  - a per-hold coupling fit holds out on brake 1 (R² 0.38).
- The measured-field replay reproduces brake 1's pumping. Over the top negative at 5.4–6.0 s in 2–3 of 9 cells per coupling.
- The push angles are within 6% of optimal, so they are not the fault.
- The closed-loop sim reproduces the failure to brake, but not the tip-over time.
- Analysis: `analysis/f3_20261104/README.md` (simulator check).

### 2026-11-04 (evening) — F3 brake-only 1 (worker2 agent, Molly's go): brake failed again

- The rotor had fallen back to a large swing by 20:59:48Z (Molly). `run --f3 --brake-only --brake 120` (dea18f0), loop FE 1477876900–1477877024.
- It went over the top within ~5 s and was left turning −0.6 rev/s, drive off.
- Push angles measured from today's data: −54 / +170 at 0.10 s effective delay (R² 0.63); the angles in use have the right signs.
- Analysis: `analysis/f3_20261104/README.md`. Data: `data/feedback/f3/brake1/`.

### 2026-11-04 (evening) — F3 live 2 (worker2 agent, Molly's go): rotation at ~0.53 rev/s; brake failed

- Settings: tracker exposure 15 ms, second light adjusted, `--ncc-min 0.7`, rest 229.8. Loop FE 1477875691–1477875870.
- Over the top 4.6 s in. 33 turns at 0.52–0.55 rev/s in the "hold", **with the field off**, i.e. coasting.
- The brake reversed the rotor. It was left turning **−0.55 rev/s** with the drive off.
- The trap was measured over the full circle from the coasting.
- Analysis: `analysis/f3_20261104/README.md`. Brake fix on `feedback-drive`. Data: Dropbox `data/feedback/f3/live2/`.

### 2026-11-04 (afternoon) — F3 live 1 (worker2 agent, Molly's go): watchdog stop after 4 s

Branch `feedback-drive` fe5c17f.
- **Tracker setup:** new light (the old flashlight had dimmed: ncc 0.80), exposure 8 ms, centre (122.8, 179.6).
- **Run:** `feedback_drive.py run --f3 --amp 4000 --pedestal 6400 --mtramp 0.0625 --rest-deg 229.9 --enable-outputs --live`, loop FE 1477874241–1477874250.
- **Saw:**
  - From rest, the swing grew to ~±90° within ~4 s (the simulation needed ~40 s to go over the top).
  - Tracker ncc fell with angle away from rest, to 0.75 at 320–340°, which tripped the ncc < 0.8 watchdog. Clean ramp-down.
  - The rotor was left swinging ~±90° (period ~3.6 s).
- **Centre check (replay of this video):**
  - The derived centre (122.8, 179.6) gives a constant spot radius of 23.5–24.4 px over ±90° and ncc 0.951.
  - A circle fit to the spot's brightest pixels gave (125.0, 180.9) and is worse: ncc 0.892, radius 22.5–26.4 px. That fit is biased by the one-sided light.
  - Relative to the board (spoke convergence), the rotation centre is where it was in F2 to ~1 px. The camera moved, not the rotor.
- 60 s swing video for later fits: FE 1477874636–696.
- Data: Dropbox `data/feedback/f3/live1/`, `.../centre_fit/`. Runbook: `lab_utils/FEEDBACK_HANDOFF.md` (branch).

### 2026-11-04 — ND 0.5 back in the LES beam; light-push test (worker2 agent, read-only)

- **Camera moved slightly** (Molly, 2026-11-03), so the tracker's registration fails. Recalibrate before F3.
- **Shared table:** the rotor trembles when the lab mate's system on the table changes pressure. One change was
  reported at 16:37:06Z.
- **Run:** video `grab_basler.py --exposure 15 --record --duration 630`, FE 1477860791–1477861422, with the ND
  out/in/out/in. The ND stays in afterwards (Molly).
- **Saw:** ND 0.5 transmits 37%. No rest-position shift with the ND (step 0.05 ± 0.3 px). LES noise is electronic,
  so SNR drops ~2.5× with the ND. The "still" rotor moves ±2° at 0.735 Hz.
- Analysis: `analysis/nd_test_20261104/README.md`. Data: Dropbox `data/nd_test_2026-11-04/`.
- Lab mate's system pressure changed again at 18:19:15Z (Molly). No run in progress.
- F3 pre-flight (outputs OFF, fake rotor; Molly's go): `feedback_drive.py run --f3 --amp 4000 --pedestal 6400 --mtramp 0.0625 --rest-deg 227 --live`,
  FE 1477867154–1477867352. The matrix ramp smooths the steps, with outputs inside 2400–10400. At 10 writes/s the field held ~40% of the time;
  fixed to 20/s, plus field off when braked to rest (a77c6a3). Results: `lab_utils/FEEDBACK_HANDOFF.md` (branch `feedback-drive`).

### 2026-11-03 (evening) — Feedback drive, model-change prep (Mac only, no runs)

Branch `feedback-drive` (main merged in).
- `fake_rotor.py`: sends a known rotor angle (spin, swing, replay, profile) in the tracker's UDP format, so FE1 can run with no camera and no rotor.
- `fe1_check.py`: scores the front end's field angle, smoothness and size against that truth; selftest passes.
- **`commutate.c` change (Molly OK):** a new input `COMM_TFRAME` (the frame's timestamp, 13 inputs now), so the block predicts from the frame's true age, not the 16 Hz arrival time.
  - Simulation, with an assumed constant 3 ms transport: spinning-rotor field-angle error p95 ~69° → ~23°.
  - FE1 measures the real value. Clock steps recover (tested); worker2 pre-rolls 2 s before enabling.
- Build steps: `lab_utils/rcg/SIMULINK_EDITS.md`; spec `y1rds_model_change_commutation.md`.

### 2026-11-03 — Problem 1 (arbitrary waveforms): scope on USB; W0 AWG stream test, outputs off (worker2 agent; Molly approved)

Branch `waveform-test`. Split agreed with the PI (Molly): first show arbitrary signals on V2–V4 up to ~10 Hz,
verified on the scope; the model change is paused until then.
- Scope RTB2004 on worker2 USB-TMC `/dev/usbtmc1` (udev rule by Molly); `*IDN?` answered twice, but later queries
  wedged it twice (cause not found). CH1 LES YAW, CH2–4 = V2–V4. LAN: "no cable", unresolved.
- W0 `awg_waveform_drive.py --wave pulse --amp 5000 --pedestal 6400 --live` (outputs off), start FE 1477788806.
  Saw: front-end clock − worker2 clock = +15496.6 s; only the first 3.0 s of the waveform played; the stop hung
  ("awgsendwaveform RPC error = 5") and was killed, leaving the pedestal up (outputs off).
  Cleanup (Molly OK): `awg_reclaim.py` freed 4 slots, EXCMON 0, offsets ramped to 0, TRAMP 1; all resting.
- W1 (outputs off, AWG built-ins, FE clock): `awg_waveform_drive.py --wave bburst --amp 5000 --pedestal 6400 --live`,
  start FE 1477790462; `--wave bchirp` (0.1→12 Hz, 60 s), start FE 1477790695; `--wave bsine`, start FE 1477791083. All three PASS by the proposed mark; clean stops.
- W2 (outputs ON, electrodes connected, scope CH2–4 by BNC 1×): `--wave bburst --amp 500 --pedestal 1000 --outputs-on --scope --live`,
  start FE 1477793256 (two earlier attempts: scope stopped, then read too late). Bursts at the electrodes in order, aligned
  within 0.07 ms; ~0.0125 V/count; AC-coupling τ ≈ 5.6 s on V2/V4. Two unexplained 14 ms ±25 V spikes on all scope
  channels (21:42:49Z, 21:48:32Z), not in OUT_DQ.
- **Wiring change (Molly, ~22:05Z):** the ground after the DAQ output was floated on **V4**. All the other channels already
  had it floated; V4 was the only one that hadn't. Runs before this (including W2 `bburst_1793742522` and `bsine_1793742986`) had V4 grounded.
- W2 `bchirp` (V4 floated), start FE 1477794662: V2/V3 at the electrodes flat 0.3–10 Hz (±0.15% / ±0.4%), V3–V2 timing
  < 0.13 ms at 1–10 Hz; **V4 showed no signal at the scope** (OUT_DQ exact). Molly then **restored V4 to its previous
  grounding** (by ~22:20Z); a retry with a different BNC cable is planned for 2026-11-04.
- **Wiring change (Molly, by ~22:36Z, on her PI's advice):** V2 and V3 changed to **grounded** after the DAQ output, so all three
  electrodes are now grounded (the ground only needs floating for a direct DAQ-to-scope connection; here the DAQ feeds the HV amp).
- W2 grounded (all three): `bburst` start FE 1477796873 and `bchirp` start FE 1477797395 (`--scope`, triggered on the pedestal
  step). All three electrodes flat 0.3–10 Hz (V2 0.0124, V3 0.0127, V4 0.0127 V/count), within 0.33 ms of each other at 1–10 Hz;
  τ 5.4–5.7 s with clean fits; no spikes. PASS by the proposed mark.
- **Wiring change (Molly, by ~23:08Z):** V1 (centre electrode) also grounded after the DAQ output, so V1–V4 all match. No runs since.
- Results: `lab_utils/WAVEFORM_HANDOFF.md` (branch `waveform-test`). Data: Dropbox `data/feedback/waveform/`.

### 2026-11-03 — F2: first outputs-on feedback run; the rotor made full turns (worker2 agent, Molly watching)

Branch `feedback-drive` (4bb45fc). Live tracker gps1477756297 (0 dropped).
- Prep hold `stator_osc_drive.py hold --felec 0.1 --amp 6400 --duration 30 --enable-outputs --live`,
  FE 1477771975–2007, from rest → ±25.5°.
- Scan 1 `feedback_drive.py run --scan default --dwell 10 --amp 5000 --pedestal 6400 --rate 10 --live --enable-outputs`,
  loop FE 1477772541–625.
- Saw: from the −90 step on, full turns, up to 1.17 rev/s; −2.7 turns net over the scan. Molly: CCW turns, then a
  slip and the other way (11:04–11:05 local); the outputs looked boxy (16 Hz staircase).
- **Recorded outputs left 0–12800** (to −389 / 13198, 13–20 samples per channel). Unresolved whether real or the DQ filter.
- Scan 2 not run (swing ±155°, Molly); free swing recorded ~13 min afterwards.
- Analysis: `analysis/f2_20261103/README.md`. Data: Dropbox `data/feedback/f2/`.

### 2026-11-02 — Feedback drive F1 and F1b, outputs off (worker2 agent; Molly approved the --live runs)

Branch `feedback-drive`; replay tracker (video gps1477428272) publishing angles; nothing reached the chamber.
- Clean-start hold `stator_osc_drive.py hold --felec 0.1 --amp 6400 --duration 20 --live`, FE 1477701639–662:
  0.1000 Hz from the first second, AC 10→90% in 3.0 s. The 1.1 s fix was then merged to `main` (Molly OK).
- F1 `feedback_drive.py run --lead 45 --duration 60 --live` (every frame, unpaced): loop FE 1477701705–767.
- F1b same with `--rate 10` (paced, writes waited): loop FE 1477702657–720.
- Saw: the field follows the commanded steps, and every output step lands on a 1/16 s grid. The pedestals
  now ramp together. The outputs ring after each step. The latency is not measured.
  Analysis and verdict: `lab_utils/FEEDBACK_HANDOFF.md` (branch `feedback-drive`).
- Data: Dropbox `Microspheres/TFINER/data/feedback/` (F1) and `.../feedback/f1b/`, with the agent's raw reports.

### 2026-11-02 — Feedback drive F0 and clean-start fix (Mac, no hardware)

Did: `feedback-drive` branch: `lab_utils/feedback_drive.py` (it freezes the oscillator at FREQ 0
and points the field each camera frame through DRVMTRX column 2; no model change), the F1 scorer
`feedback_f1_check.py`, and `live_blob_track.py --publish`. Self-test (simulated rotor) and
stub-EPICS runs pass. Also `drive-gps-second`: the clean start now holds DRV_TRAMP 0 for 1.1 s
(RCG cdsOsc applies FREQ at the next GPS second; LIGO-T080135 §7.6.3); merged into
`feedback-drive`. Not run on worker2. Plan and F1 steps: `lab_utils/FEEDBACK_HANDOFF.md`
(on the branch); F1 approved by Molly for the next lab session.
Later (evening, Mac only):
- y1rds commutation model change approved (Molly builds; `docs/DECISIONS.md`).
- `lab_utils/rcg/commutate.c` (RCG cdsFunctionCall) with `test_commutate.py`, which passes.
- Simulink steps: `rcg/SIMULINK_EDITS.md`.
- `feedback_drive.py frontend` mode; `--pedestal` now separate from `--amp`; F2 scorer `feedback_f2_check.py`.
- Runbooks for F2 and for FE1 (after the model change), all on branch `feedback-drive`.
- Not built or run on hardware.

### 2026-11-02 — Free-swing recording after C2 (no drive; Molly, worker2 agent)

`live_blob_track.py` (camera only), video `output_basler_gps1477678308` (true GPS), 39.0 min,
0 dropped, NCC median 0.836. LES PIT/YAW fetched FE 1477685294–1477696028. FE − true GPS 15380.9 s, read
live; this morning's read was 15368.7 s, so the offset drifts ~3.9 s/h.
Saw: the swing went ±27° → ±24° and its frequency 0.354 → 0.319 Hz over the 39 min. Analysis: `analysis/ringdown_20261102/README.md`.

### 2026-11-02 — C2 drive holds: seven holds, no lock on the quick look (worker2 agent, Molly in lab)

Branch `drive-clean-start` (e466653), runbook in `lab_utils/DRIVE_LOCK_HANDOFF.md`. Both
lights on; rotor still at the start (tracker: 0.3° span over 40 s).
- Step 0, outputs off: `hold --felec 0.1 --amp 6400 --duration 20 --live`, FE 1477683385–407.
  Writes in order DRV_TRAMP←0, DRV_FREQ←0.1 (from 4), DRV_TRAMP←5, then gains: PASS.
  D1 matrix as recorded. L3 replay: p99 4.72 ms, 0 dropped: PASS.
- Live tracker: video `output_basler_gps1477668186` (true GPS), 88173 frames over 1763.5 s,
  0 BlockID gaps, p99 8.41 ms; centre (132.06, 180.33); NCC median 0.967 at the start.
  Run in the `ueye` conda env, which has pypylon.
- Holds, all `--amp 6400 --duration 150 --enable-outputs --live`, exit 0, outputs confirmed off
  after each; drive-off ≥ 65 s + ~12 s ramp-down between holds. FE start–end:
  1 0.1 fwd 1477683665–817 · 2 0.2 fwd 1477683911–4061 · 3 0.4 fwd 1477684155–305 ·
  4 0.1 rev 1477684399–549 · 5 0.2 rev 1477684643–793 · 6 0.4 rev 1477684887–5037 ·
  7 0.155 fwd 1477685131–282.
- Saw (live angles, quick look only, not `drive_coupling.py`): no speed near f/8 or f/4 in any
  hold. Angle range during each hold: 96°, 151°, 206°, 133°, 202°, 310°, 241°. Hold 1 started
  from rest. The rotor settled before hold 4 but was still swinging ±90° at the start of holds 5–7.
- FE − true GPS = 15368.7 s (read live 0.5 h after the video start).
- Data: `dropbox:Microspheres/TFINER/videos/{output_basler,blob_live}_gps1477668186.*`;
  `data/LES_video/` and `data/Electrodes/` `*_1477683254_1477685619.h5` (LES PIT/YAW,
  OUTS V1–V4).
- Analysis (Mac): `analysis/c2_20261102/README.md` (gate 7 PASS; no lock in any hold).

### 2026-11-01 — Drive clean start written; lab_utils stale-script list (Mac, no hardware)

`stator_osc_drive.py` on branch `drive-clean-start`: DRV_FREQ jumped at zero gain (no
start-up glide), refuses if gains are nonzero, optional `--pedestal-ramp`. Checked only
against a stub `epics` (38/38 ordering and Ctrl-C checks); not run on hardware; outputs-off test added
as runbook step 0 in `lab_utils/DRIVE_LOCK_HANDOFF.md`. Worker audit:
`lab_utils/STALE_SCRIPT_CANDIDATES.md` (flags only; nothing deleted).
Later: gate 7 scorer `camera_utils/tracking/gate7_check.py` (branch `live-blob-tracker`;
PASS on a replay of gps1477428272, fails four broken inputs; found and fixed the live CSV
rounding its centre to 0.01 px, which alone failed the gate). Drive direction vs camera
MEASURED from the board's via-radius pattern in the gps1477428272 median frame: + image
angle = C→B→A, so `−f8` = with the field sequence (reviewer AGREE; assumes the 08-24
channel map). `lab_utils/DRIVE_LOCK_HANDOFF.md` items 2–3.
Later: `lab_utils/stator_detent.py` written (branch `detent-test`; torque per phase from
the tracked angle; ~1° expected, derived from trap f₀ and design torque); old
`stator_epics_drive.py` deleted (Molly). Not run on hardware.
Later: stale-doc cleanup from a worker audit of all 33 `.md` files (Molly decided): deleted
`stator_flex/spinup_note.md` + `spinup_estimates.py` (side-post era) and
`lab_utils/detection_notes.md` (old-rotor sail detection); root `README.md` now points to
the current docs; trimmed the muxmatrix proposal body, the AWG section of
`lab_utils/README.md`, uEye/old-rotor lines in `camera_utils/`, and stator_flex's
pre-order open items (now in STATUS). Kept: `bill_of_goods.md`, laser-stepdown notes,
the 09-11 dataset note, `laser-cutting/`, `momentum-simulation/`.

### 2026-11-01 — Docs audit: DECISIONS and STATUS (no hardware)

Audited `docs/DECISIONS.md` row by row with Molly. Removed stale rows (09-14 comb/2, 2026-09
GPS, 10-09 laser calibration, 10-09 use-PIT); qualified the LES direction rule (sign must be
set against video; MEASURED re-count on gps1477428272: 25 s positive / 59 s negative above
0.3 rev/s); calibration constants now point to `analysis/calibration_history.md` with "ask
before use". DECISIONS header changed from append-only to replace-and-remove (Molly).
STATUS: LES channel choice, laser/PD re-calibration, `_OFFSET` volts-per-count reworded/added.
Remaining STATUS rows await Molly. Later: STATUS tracking/drive-lock updates and trap
f₀ ~ 0.31 Hz (DECISIONS row) from the tracking/drive session; CLAUDE.md worktree rule;
Alma (she/her) in `docs/reference/` and CLAUDE.md.

### 2026-10-30 — Gate 6: video angle vs LES (analysis only)

`camera_utils/tracking/les_compare.py` on gps1477428272. MEASURED: video and LES align at
front-end − true GPS = 15073.56 ± 0.05 s (R² 0.87 for both PIT and YAW, 0.08 elsewhere).
LES is mostly a 2× function of the rotor angle (R² 0.77 vs 0.09 for 1×), so ÷2 when
rotating; LES circulation gives the direction (97% of frames above 0.3 rev/s). Swinging ±105° at 0.275 Hz: LES peaks at 3.0× with a comb at
2–5×, reproduced by the angle model; no fixed divisor while swinging. Details:
`camera_utils/tracking/HANDOFF.md`.

### 2026-10-30 — LES PIT/YAW fetched for video gps1477428272 (read-only, worker2 agent)

Ran `lab_utils/fetch_les_for_video.py 1477428272` (cds conda env). MEASURED: front end
ahead of true GPS by **15096.4 s** (read live at true GPS 1477450592.6, 6.2 h after the
video). Fetched front-end GPS 1477443068–1477443939 (video true GPS 1477428272–1477428542
+ 300 s each side): `Y1:RDS-LES_PIT_IN1_DQ`, `LES_YAW_IN1_DQ`, 1024 Hz, full coverage, no
NaNs. Dropbox `Microspheres/TFINER/data/LES_video/`; frame timestamps
`videos/output_basler_gps1477428272.csv` (from worker2 `/home/controls/stator_detent/`).

### 2026-10-30 — Angle tracking gate 2: blob detector (analysis only, no hardware)

Ran `camera_utils/tracking/blob_track.py` on `output_basler_gps1477419607.avi` (polar
template match, 9 s). MEASURED: all 1957 frames tracked with no jumps (max step 6.9°);
loop-closure de-rotation is sharp on the dim half too; orbit centred 0.70 px from the
gate-1 centre (the earlier 4.6 px offset was a detector artefact); blob−sail 34.2° ± 1.8°.
Gate 2 passed (Molly, by eye). New-lighting video `output_basler_gps1477428272.avi`
(261 s): image moved +16.6 px in x; centre (132.3, 180.6) pending her check; tracks with
no jumps, NCC median 0.96 (was 0.77). Gate 3: Molly hand-labelled 200 frames
(`label_frames.py`), 20 repeated 5 h later: rms 1.12°, max 2.75° (passes). Labels vs tracker
0.96° rms, max 3.0°. Gate 4: `score_angles.py` passes its self-test (fails a 180° copy);
blob_track scores 100% within 5°, 0% wrong-feature, rms 1.01°. Details: `camera_utils/tracking/HANDOFF.md`.

### 2026-10-29 — stator drive: pump chirp, then forward sweep; rotor went round with slips

*Recovered 2026-11-01 from worker2's agent memory; not logged at the time.*
Ran `lab_utils/stator_osc_drive.py`, amp 6400, with the white-dot tracker
(`rotor_angle_loop.py`) alongside. Times are worker2 (true) GPS; front-end GPS not logged.

1. `sweep --felec 0.40 --to-felec 0.14`. Tracker 1477307610 + 300 s: 0% good frames,
   no usable angle (`cam_chirp.log`, session scratchpad; not kept).
2. `sweep --felec 0.20 --to-felec 2.4 --step 0.04 --dwell 4`. Tracker 1477311410–1477311826
   (420 s, 46% good). Molly saw the rotor go round with slips, then swing back
   (observed by eye; no tracked angle survives in the repo).

### 2026-10-28 — ACTUATOR IS FAST: matrix → DAC in under one 1024 Hz sample

> **Provenance.** MEASURED: everything below. The one INFERENCE is flagged in place.

**`DRVMTRX` reaches the DAC within a single 1024 Hz sample.** EPICS is not a
bottleneck and neither is the matrix.

Method: drive at `--felec 1.0 --amp 200` (torque 0.1% of amp 6400, negligible),
`DRVMTRX_TRAMP = 0`, step `SETTING_2_2` between +1 and −1 four times ~8 s apart,
then read `V2_OUT_DQ` at 1024 Hz from NDS.

| | |
|---|---|
| largest single-sample change at the step | **−283.8 counts** |
| median sample-to-sample change elsewhere | 0.63 counts |
| ratio | **453×**, inside one 1 ms sample |
| `caput` round-trip | 0.38–0.44 ms |

**Internal check:** the final transition, where `TRAMP` had been restored to 2.0,
took **1.48 s** — i.e. TRAMP does exactly what it says, while TRAMP = 0 steps
complete within one sample. The ramp machinery is not the slow thing; nothing is.

#### ⚠ CORRECTION — an earlier attempt the same day reported a "250 ms floor". It was wrong.

That attempt polled the **EPICS readback** `DRVMTRX_{r}_{c}` after `LOAD_MATRIX`
and saw ~250 ms regardless of TRAMP. **That is the readback scan rate, not the
actuator.** Measured on this front end from monitor callbacks: `LES_YAW_INMON`,
a continuously-changing channel, updates at **8.0 Hz (125 ms median interval)**.
The 250 ms "floor" is two of those.

> **EPICS readbacks cannot be used to measure front-end latency here.** Use a DAQ
> channel (`_OUT_DQ`, 1024 Hz) and a signal that is actually flowing.

Also note monitors fire on *change*: `DRVMTRX_2_2`, `V2_OUTMON` and `DRV_FREQ`
produced 0–1 callbacks in 12 s simply because they were static, which is not a
statement about their update rate.

#### Consequence for a feedback loop

| element | time |
|---|---|
| camera frame interval at 50 fps | **20 ms** |
| angle from a raw array | 0.14 ms (0.78 ms in `rotor_angle_loop.py`, larger box) |
| `caput` | 0.44 ms |
| matrix → DAC | < 1 ms |

The camera is the slowest element by ~20×. *(INFERRED, not tested: this supports
letting the front end synthesise the waveform at 16 kHz while Python writes
setpoints at camera rate. No loop has been closed.)*

#### New tool and a camera fact

`camera_utils/rotor_angle_loop.py` — in-process angle at frame rate, pypylon →
numpy → angle, no files and no JPEG. Measures only; commands nothing. Sustained
**50.0 fps, 0.78 ms/frame** live.

⚠ **The Basler is held EXCLUSIVELY.** One process at a time: `grab_basler.py` and
`rotor_angle_loop.py` cannot both run, and whichever opens first wins. The loop
writes `/dev/shm/rotor_angle_latest.jpg`, a *different* path from
`basler_latest.jpg`, so a viewer pointed at the usual file shows a frozen frame
rather than failing visibly.

#### Open, unexplained

- Live detection ran **31% good** where the same code on the 17:03 recording gives
  **83%**. Not the search box — two different boxes give identical results on the
  recording (centre 106.0,175.9, radius 29.8 px, 83%). Unexplained.
- An earlier claim in-session that the camera had moved further back was **wrong**;
  it came from reading an ill-conditioned circle fit as a measurement.
- A 3× harmonic carrying 25% of the orbit's radial variance. No candidate cause.

### 2026-10-21/22 — rotor centred on the board to 0.02–0.05 mm; board GND wired

- **Centring** (flight rotor on the rev G flex, top-down microscope, microscope
  straightened first). The rotor-edge circle fit, measured against the board centre
  (via ring + CTR disk, agreeing to 9 µm), gives |δ| = 19, 22, 48, 46 µm in four
  photos with different lighting. The spread between lighting setups is the
  systematic error. Torque factor J0(8δ/1 mm) ≥ 0.96, so no re-centring is needed.
  An earlier 0.09–0.12 mm reading with the microscope tilted was probably partly
  parallax. Details, script and the fit-window pitfall are in
  `analysis/rotor_centering/README.md`.
- **Board ground:** the 1/4" magnet only overlaps the bottom GND contact ring
  (r 2.95–3.40) by ~0.23 mm, so the ring never made contact. Fix: 22–24 AWG
  insulated wire soldered to a top GND pad (r 10.8 mm, az 60°/240°), crimped into an
  MB-R6 ring lug under a base screw. The magnet and base were already grounded.
- PEEK height is now set with the stainless shims **under the PEEK plate**, not
  under the pads (a metal shim under a pad shorts that phase to the bare GND around it).

### 2026-10-14 — stator drive: the rotor is DRIVEN at f_elec/8 but NOT carried round

> **Provenance.** MEASURED: all LES amplitudes/rms, the video coherence and centroid
> figures, the 6 h quiet baseline, both drive runs. DERIVED (Claude's arithmetic,
> unchecked by Molly): the 0.030 Hz mechanical frequency and `k_off`. Molly's direct
> visual observation is noted as such.

**Headline: the rotor is driven at f_elec/8 but is not carried around by the wave —
synchronised in frequency, not locked in the motor sense.**

Two runs of `stator_osc_drive.py hold --felec 0.08 --amp 6400 --duration 400 --live
--enable-outputs` (rotor 0.0100 Hz commanded), front-end GPS **1476056543–1476056950**
(from rest) and **1476057672–1476058080** (from leftover motion).

| | LES rms (cts) | line at 0.0200 Hz (f_e/8) | at 0.0400 Hz (f_e/4) |
|---|---|---|---|
| run 1 before | 15.6 | 2.6 | 1.6 |
| **run 1 during** | **304.9** | **150.6 (SNR 24)** | 56.4 |
| run 2 before | 287.8 | 22.6 | 18.4 |
| **run 2 during** | **325.2** | **65.7 (SNR 8.4)** | 39.7 |

- **Rotor was genuinely at rest first** — 6 h with no drive and no laser (V2 rms = 0 in
  all 72 five-min bins, PD = −1) showed **no libration line at all** in 0.03–2 Hz. Video
  coherence 1.000, centroid stable to 0.10 px. This is the Test A answer: *neither
  librating nor rotating*, which is why Test B's premise (a line to shift) did not hold.
- **Drive on ⇒ 19× rms jump**, line within one bin of the f_e/8 prediction, twice.
- **It did not go round.** Video `|⟨e^{2iθ}⟩|` = 0.670 / 0.658 during drive; four turns
  would give ≈0.04. Noise only reduces coherence, so this is a bound.
- **Starting from motion barely changed the driven state** (coherence 0.670 vs 0.658,
  centroid rms 3.21 vs 3.16 px) but halved the drive line — pre-existing motion competes
  with capture rather than helping it.
- **Molly observed directly:** sometimes forward motion with sudden backward slips,
  sometimes back-and-forth — consistent with a drive at its capture threshold.
- **Free oscillation at 0.0600 Hz** (117 cts, SNR 25.6) seen in run 2's pre-drive window,
  excited by run 1. This is the f_off that Test A could not measure on an unexcited rotor.
  The drive suppressed it, 117 → 27.5 cts.
- **Preliminary answer to the plan's open question:** the response sits at f_elec/8, not
  the backward f_elec/4 — the 0.0400 Hz line was smaller in both runs. One frequency, two
  runs; not conclusive.

⚠ **`--amp 6400` is the ceiling** (amp + pedestal = 12800 = `V{n}_LIMIT`, keeping the HV
amp input inside 0–2.1 V). No more drive torque is available in software, so the deficit
has to be closed by geometry — which is what the hardware change below is for.

#### ⚠ V² test ATTEMPTED and INCONCLUSIVE — do not read a scaling out of it

A third run at **`--amp 3200`** (FE GPS **1476062143–1476062550**) was taken to test
τ ∝ V². **It does not measure the scaling and must not be quoted as if it does.**

| run | amp | start state | 0.0200 Hz line during |
|---|---|---|---|
| 1 | 6400 | at rest | 150.6 cts |
| 2 | 6400 | in motion | 65.7 cts |
| 3 | 3200 | in motion | 95.1 cts |

Halving the amplitude *raised* the line (ratio 0.69 against the 4.00 that V² predicts),
but **the initial condition alone moves the answer by 2.3× at fixed amplitude** — runs 1
and 2, both at 6400. The systematic is bigger than the effect. The three runs also began
from genuinely different states: the 0.0200 Hz line *before* the drive was 2.6, 22.6 and
1.6 cts respectively.

**Why it failed, for whoever retries it:** the test needs both amplitudes started from the
*same* condition, and the only clean one is rest — which took hours to reach after a drive.
It cannot be done back-to-back in an evening. Either allow the rotor to settle fully
between points, or find a reproducible way to prepare the initial state.

Two observations that do stand, independent of the scaling question:
- **The drive still couples strongly at half amplitude** — 95.1 cts, SNR 16.4 at
  `--amp 3200`. It did not switch off.
- **The driven rms is the same in all three runs** — 304.9 / 325.2 / 320.0 cts —
  independent of both amplitude and starting state. **Unexplained.** For a mechanism that
  should go as V² this is worth noticing rather than explaining away.

**Still open:** how far from the capture threshold the drive is. That remains unmeasured. Also unresolved: rocking vs slipping, rotation direction, and
whether 0.0600 Hz is really the trap frequency.

**Camera note:** `grab_basler.py` default `--exposure 2.0` saturates ~19% of the frame and
destroys the sail-angle measurement; **0.5 ms** works. The `/dev/shm` snapshot is throttled
to 2 Hz by `--snapshot-every 0.5`, fine below ~0.5 Hz rotor but aliased at the 1 Hz target
— use `--record` for anything faster.

### 2026-10-09 — new pickoff + beam realignment: PD is good again, and the LES signal axis FLIPPED

> **Provenance of this entry — written by Claude, not yet reviewed by Molly.**
>
> **MEASURED** (raw readings, Molly's or read live off the front end):
> the Ophir power / PD table; the LES PIT-vs-YAW amplitudes, SNRs and kurtoses;
> the 150 s → 600 s window comparison; the x–y phase and correlation; the GPS
> offset; the harmonic amplitudes behind the divisor check.
>
> **DERIVED** (arithmetic on the above — each is an inference, not a reading):
> "PD linear to ±4%" and the 411 counts/mW scale; "11.10 µW/count above 764"
> (a fit to five points); the 814× ND ratio; "DIVISOR = 2" (an interpretation of
> the harmonic pattern, though it agrees with the independent 09-14 timing);
> the `T ≈ sqrt(1/|df/dt|) ≈ 100 s` coherence limit; the per-block PD standard
> error.
>
> **Nothing here has been cross-checked by a second method except the divisor.**
> Treat the derived items as working numbers to be re-established, not as facts.

**Front-end GPS offset re-measured: +12833 s** (9876 on 09-11, 10155 on 09-14). It wanders
and it is accelerating. Re-measure every session.

#### The pushing beam, the ND30, and the pickoff

The pushing beam was cleaned up and the pickoff replaced, and **an ND30 now sits upstream
of both the pickoff and the chamber**. Measured with the Ophir at the chamber:

| counts | mW | PD | | counts | mW | PD |
|---|---|---|---|---|---|---|
| 1300 | 5.94 | 2440 | | 1150 | 4.29 | 1750 |
| 1250 | 5.40 | 2225 | | 1100 | 3.72 | 1545 |
| 1200 | 4.87 | 1980 | | 1300 + ND30 | **0.0073** | **2.35** |
| | | | | 0 | — | −0.80 (−0.85 with PD blocked) |

- ✅ **The PD is LINEAR to ±4% across an 814× range** — 411 counts/mW at 5.94 mW, 408 from
  the high-power slope, **432 at 7.3 µW**. This **supersedes the 2026-09-15 warning** that
  the PD was misaligned and must not be used as the power axis. It is a good power axis
  again. Supersedes the 283 (07-28) and 203 (08-03) scales.
- **Commanded→power is now 11.10 µW/count above a 764-count threshold** (was 11.87 above
  735 — 6% apart, consistent).
- **The ND30 measures 814×, i.e. OD 2.91**, not the nominal OD 3. Measure a stack, never
  assume it.
- ⚠ **`LASER_OFFSET = 0` is a TRUE optical off**: PD reads −0.80 unblocked and −0.85
  blocked, a 0.05-count difference, so essentially no light. July's 15.9 µW sub-threshold
  leakage is killed by the ND (→ ~20 nW at the sail). Software chopping with
  `laser_on.py` / `laser_off.py` is therefore clean and needs no shutter.
- ⚠ **A PD reading of ~0 at `LASER_OFFSET = 1300` is EXPECTED with the ND in**, because the
  pickoff now sits downstream of it (7.3 µW → ~3 counts). Do **not** read it as the
  2026-10-06 loose-MOD-cable failure. The 3.15-count step above dark is still a usable
  monitor: at 1024 Hz over a 600 s block its standard error is ~0.02 counts, 0.6% of the
  step. Check the dark level at the start *and* end of a session — drift there is the only
  thing that breaks it.
- The ND being in the science path promotes the existing open item **"tilt the ND filter to
  break the air-gap etalon"**: an untilted ND's transmission drifts with temperature, which
  would masquerade as a slowly changing force. The pickoff sitting *downstream* of the ND
  means the PD sees that drift — that is the compensation for losing absolute power
  monitoring.

#### ⚠ The LES signal axis has FLIPPED — track `LES_PIT`, not `LES_YAW`

Measured live on a rotating rotor, 150 s window, electrodes off:

| axis | DC | line amp | SNR | rms | kurtosis |
|---|---|---|---|---|---|
| **PIT** | +1362 | **397 cts** | **511** | 341 | −0.77 |
| YAW | −7357 | 148 cts | 212 | 167 | −0.81 |

Reference, `noise_budget_20260911_clean` **on LES_YAW**: line amplitude 331–539 counts,
median SNR 622. So PIT is now within ~20% of that reference and YAW is 3× worse.
Frequency precision goes as 1/SNR, and σ_f *is* the measurement in every force estimate —
so **the beam does not need moving, but the channel does.** `settled_check.py`,
`monitor_libration.py`, `track_spindown.py` and both noise-budget notebooks all still
default to `LES_YAW`. `LES_SUM = 80` is low versus 240 on 09-11 but irrelevant: SNR, not
light level, is the limit.

**x–y is usable again.** Both axes now see the motion (amplitude ratio 2.75:1, against the
old 1000:1). At the dominant line the relative phase is +2.4° with corr(x, y) = +0.81 — a
**line, not an ellipse**, so no whirl and no handedness to read. Rotation direction still
needs the camera.

#### DIVISOR = 2 confirmed independently, from the comb rather than by timing

A genuine line sits at 0.3550 Hz (44 counts) under a dominant 0.7100 Hz (137 counts), with
4f at 28 counts and the odd harmonics suppressed (3f = 8, 5f = 7) — exactly a 2-fold sail.
So the dominant line is 2f and rotation = dominant/2. This is a **third** independent route
to the same answer as the 09-14 stopwatch re-timing, and it needs no video.

#### ⚠ Coherent FFT window limit ≈ 100 s on a coasting rotor

Widening the analysis window from 150 s to 600 s made the measurement **worse**: PIT SNR
511 → 114 and amplitude 397 → 137. A coasting rotor chirps, and at the measured −1.0e-4
Hz/s the line smears across ~37 bins in 600 s. The limit is `T ≈ sqrt(1/|df/dt|) ≈ 100 s`.
**Use 100–150 s windows, or demodulate** — which is why `noise_budget_20260911_clean` made
demodulation its primary estimator. Do not widen a window expecting finer resolution.

#### New tool

`lab_utils/track_drive.py` — live rotor-frequency tracker for the electrode run. Reports
f_elec, f_rot and the **slip ratio** once per poll, plus SNR and the rotating/librating
kurtosis. Reads NDS2 rather than `cdsutils.getdata` (which streams in real time and so
blocks for the full window). **Derives the fundamental from the comb, with no divisor
constant anywhere in the file.** Validated against the 09-11 record: returns 0.7489 /
0.7487 / 0.7492 Hz at +1 h / +2 h / +10 h, matching the notebook's 0.748876 Hz.

```
python3 lab_utils/track_drive.py --h5 scan_fwd.h5          # headless, for an overnight run
python3 lab_utils/track_drive.py --gui --h5 scan_fwd.h5    # + live plot (needs DISPLAY)
```

`--h5` appends and **flushes one row at a time**, so a kill, a dropped ssh session or a dead
X server costs at most the poll in flight; re-running against an existing file appends
rather than truncating. `--gui` plots f_rot against the commanded f_elec/8 (the gap is the
slip), SNR and kurtosis, and the accumulating **f_elec → rotor curve**, which is the
deliverable of the scan and is expected to be non-monotonic. Acquisition runs in a daemon
thread so a fetch never freezes the window, and both paths call the same `poll_once()`, so
the plot cannot drift from the validated CLI.

**The GUI works over `ssh -X`/`-Y`**, and is built not to abuse it: it repaints only when a
new estimate actually arrives, rather than on a fixed animation tick. `FuncAnimation` would
have redrawn the whole canvas every interval regardless — at 1 Hz against a 60 s data
cadence that is ~60× more repaints than there is new data, which is barely noticeable
locally and is exactly what makes a forwarded plot feel sluggish. `--gui-interval` (default
2 s) only sets how often it checks.

#### ⚠ Two drag laws are in the repo and they disagree — unresolved

> **Resolved 2026-10-30:** most of the gap was I (the comparison notebook used 1.88e-11).
> Re-run with I = 1.1e-11: γ = 2.07e-15 vs 2.30e-15. Linear model adopted; see DECISIONS.

| source | law | γ | τ₀ |
|---|---|---|---|
| `damping_law_comparison.ipynb`, this log | τ_drag = τ₀ + γω | 3.53e-15 N·m·s/rad | 8.06e-16 N·m |
| `noise_budget_20260911_clean` | linear, γ = I/τ_mech | **2.2974e-15** | none |

γ differs by 1.5× and the constant term vanishes entirely. Both are in active use. Which is
right changes every sensitivity estimate in the programme. **Do not silently adopt one** —
see `docs/STATUS.md`.

