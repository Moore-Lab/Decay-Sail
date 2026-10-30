# Status

What is open now. Overwrite freely: when an item closes, delete it here and record
the outcome in `apparatus_log.md` (and `docs/DECISIONS.md` if it sets a value).
The goal these serve is in `measurement_objective.md`.

## Open

- **Angle tracking (white dot):** good detections 83% on the 2026-10-28 recording but
  31% live, unexplained (`apparatus_log.md` 2026-10-28). Working doc:
  `camera_utils/TRACKING_NOTES.md` (gate plan); current state in
  `camera_utils/tracking/HANDOFF.md` (gate 1 passed 2026-10-30). Scope it as a multi-agent
  project (ground truth + scoring, detector, angle → frequency, capture on worker2,
  live loop) once the docs are clean.

- **`LES_YAW` → `LES_PIT`:** `settled_check.py`, `monitor_libration.py`,
  `track_spindown.py` and both `noise_budget_20260911*` notebooks still hardcode YAW.
- **Re-run §2 of `noise_budget_20260911_clean.ipynb`** with F0 = 0.81 fN.
- **`I = 1.88e-11` still in** `analysis/laser_dark_vs_on.py:117` (and Dave's
  `thermal_noise_spindown.py:37`, left alone on purpose).
- **Drive-off baseline** now that the board is flat and grounded: does the rotor still
  move with drive and laser off (cf. 2026-08-22)?
- **DC detent test:** one phase on → rotor should snap to one of 8 detents; step
  A→B→C → 15° mech per step. Confirms m = 8 (now only derived) and calibrates τ_max
  vs V². The white-dot camera tracking can measure the steps.
- **Max ramp rate vs V** (expect ∝ V²): confirms the capacitance-motor mechanism.
- **DC pedestal:** what the commanded `V_dc` does to the m = 8 torque channel is
  unresolved (`hv_amp_dc_investigation.md`).
- **Levitation height** over the installed board, to confirm h ≈ 0.37 mm.
- Confirm the magnet sits flush in the plate's Ø7 hole; cross-check the
  exp(−m·h/r) coupling model against 3-D BEM/COMSOL.
- **Bright deposit** near the centre of the rotor's underside: anything standing proud
  there costs torque (τ ∝ exp(−m·h/r)).
- **Rotor dimensions:** the drawing (`stator_flex/inputs/Snowflake_disk_V1.3_drawing.png`)
  gives Ø3.50 mm × 0.75 mm, CAD mass 9.89 mg for the disk alone, but the whole rotor
  (disk + sail) weighed 7 mg. Some models assume 0.5 mm thick. Measure the actual disk
  thickness and OD.
- **Trap / libration frequency:** treat as not known. Three values disagree: 0.310 Hz
  mech (09-09, small amplitude, timed), 0.12–0.16 Hz LES before the 09-08 drive
  (0.06–0.08 mech if halved), ~0.13 Hz at capture on 09-08 (band-limited tracker).
  Re-examine `Y1_RDS-LES_YAW_IN1_DQ_1472933400_1472935200.h5` in the time domain (cusp
  spacing, not a peak finder) and get f₀ at small amplitude.
- **Rotation direction:** which way A→B→C turns the rotor has not been observed.
- **PD check** across the 09-11 laser-only segment (from GPS 1473204806) for drift or
  mode hops.
- **`VOLTS_PER_COUNT`:** measure (`stator_epics_drive.py calibrate` + meter on the amp
  output).
- **Capture bracket:** detent runs at 4000 / 4800 / 5600 counts, recording the
  pre-drive rms each time.
- **Measure `I` directly** from the high-frequency asymptote of χ(f).
- **Tilt stage:** install the replacement, align, re-measure τ with a free spindown
  (laser off). That gives the post-tilt γ the 08-03/08-04 notebooks still need.
- **PD / pickoff:** measure the pickoff ratio; find why the PD lost ~28% response when
  the PBS went in; replace the PBS251 with a wedged window or characterise its drift.
- **Torque-per-mW drop (4.5×):** separate beam geometry from sail alignment once the
  tilt stage is in.
- Tilt the ND filter to break the etalon. Commanded laser counts before/after the 08-03
  step.
- **Slow-controls logging:** get **temperature** and the **pressure gauge** logging
  continuously. Existing pieces: `lab_utils/log_pressure.py` (written, gauge not
  recording); `analysis/ambient_temp_pull.py` pulls the GHS room sensor from InfluxDB
  after the fact.
- **Rotor frequency from the white dot:** not done yet (so far the dot has only been
  tested for angle detection). Once it works, compare against LES in one recording to
  settle the divisor for libration and rotation.
- **Basler:** more magnification (16 mm lens is at ~0.09×; options in
  `camera_utils/README.md`). Lossless FFV1 + per-frame timestamps are done (2026-10-28).
- **Log housekeeping:** accuracy audit (label claims measured / derived / assumed);
  the October entries in `apparatus_log.md` are still long-form (pre-October is archived
  in `logs/2026-q3.md`).
- **Calibration history:** `analysis/calibration_history.md` (which constants applied
  to which datasets).

## Process (later)

- **Hooks:** `PreToolUse` guards that block `--live`/`--leave-running`, `ssh cymac1` and
  GNOME Shell restarts without approval (about 15 lines each, in `.claude/settings.json`).
- **Process improvements:** go through what has gone wrong with agents and fix the
  owning doc or rule.
