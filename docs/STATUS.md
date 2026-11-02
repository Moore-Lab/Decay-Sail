# Status

What is open now. Overwrite freely: when an item closes, delete it here and record
the outcome in `apparatus_log.md` (and `docs/DECISIONS.md` if it sets a value).
The goal these serve is in `measurement_objective.md`.

## Open

- **Angle tracking (white blob):** gates 1–6 passed on recorded video
  (2026-10-30, `blob_track.py`, new lighting): 100% of 200 hand labels within 5°, rms 1.0°.
  LES vs video: ÷2 when rotating; while swinging LES shows a comb, no fixed divisor.
  Live tracker `live_blob_track.py` built (branch `live-blob-tracker`; replay = offline
  exactly, board-registration centre within 0.9 px). Open: L3 speed + gate 7 on worker2
  via the runbook in `lab_utils/DRIVE_LOCK_HANDOFF.md`. The old `rotor_angle_loop.py` 83% recorded / 31% live gap is unexplained but
  belongs to the old detector. State: `camera_utils/tracking/HANDOFF.md`.

- **LES channel choice:** look at both `LES_PIT` and `LES_YAW` and use the better one
  (Molly, 2026-11-01). `track_spindown.py:30` and both `noise_budget_20260911*` notebooks
  still hardcode YAW (`monitor_libration.py` already reads both).
- **Re-measure the laser and PD calibration** (power per count, PD counts/mW): the setup
  changed after the 2026-10-09 values (Molly, 2026-11-01). Values: `analysis/calibration_history.md`.
- **Re-run §2 of `noise_budget_20260911_clean.ipynb`** with F0 = 0.81 fN.
- **`I = 1.88e-11` still in** `analysis/laser_dark_vs_on.py:117` (and Dave's
  `thermal_noise_spindown.py:37`, left alone on purpose).
- **HV amp output coupling (lab check, Molly):** read the code on R1 (0805 chip resistor
  near the output headers) and which pins the jumpers on J1/J5 connect. From the
  schematic/board netlist (not confirmed on the board), each output looks
  jumper-selectable: direct from `HVOUT`, or through 5 × 1 µF in series with R to GND,
  a high-pass with τ = R × 5 µF. The 2026-08 DC step "returned to 0 over roughly 20 s"
  (≈ 3–4 τ, so τ ≈ 5–7 s, R ≈ 1–1.5 MΩ: an estimate). Ceramic caps lose capacitance
  at high DC bias, so R × 5 µF is an upper bound; timing a DC step to 37% on the scope
  measures τ directly. If DC coupling is available, it bears on the two items below.
- **Detent test:** one phase on → rotor should snap to one of 8 detents; step
  A→B→C → 15° mech per step. The amp output is AC-coupled (DC fades over ~20 s), so a
  static detent fades unless read within seconds or the J1/J5 coupling allows DC. Confirms m = 8 (now only derived) and calibrates τ_max
  vs V². The blob tracker can measure the steps.
- **Drive lock:** at amplitude 6400, a 0.4 → 4 Hz electrical sweep (gps1477428272) did not
  lock the rotor at ±f/8 or ±f/4; it kept swinging (~0.3 Hz) with bursts of net rotation
  one way. C2 holds (2026-11-02): no lock either; results and open questions in
  `analysis/c2_20261102/README.md`. Next (C4): Molly picks one variable (DC coupling
  via J1/J5, slow pedestal ramp, rotor charge, CTR bias). `lab_utils/DRIVE_LOCK_HANDOFF.md`.
- **Drive start/stop transients:** `bring_up()` glides DRV_FREQ from the previous run's
  value while the gains ramp in, and the pedestal step reaches the electrodes as a DC
  kick (decays ~20 s; Molly sees it). Proposed: set the frequency with the gains at 0
  (TRAMP 0, guard gains = 0), and ramp the pedestal over ~60 s. Branch + outputs-off test.
- **Max ramp rate vs V** (expect ∝ V²): confirms the capacitance-motor mechanism.
- **Which rotor harmonic the drive couples to** (derivation to check, 2026-10-14). With
  no DC at the electrode, torque ∝ V², and on 24 sectors V² couples the rotor's
  **m = 16** pattern forward at f_elec/8 (intended) and its **m = 8** pattern
  *backward* at f_elec/4. Forward m = 8 coupling needs a term linear in V, which only a
  net rotor charge would give. Watch for a backward lock at f_elec/4 in spin-up
  attempts; check whether stiffness changes with rotor charge. Checked on the 2026-10-30
  sweep: no lock at either (see Drive lock).
- **Levitation height** over the installed board, to confirm h ≈ 0.37 mm.
- Confirm the magnet sits flush in the plate's Ø7 hole; cross-check the
  exp(−m·h/r) coupling model against 3-D BEM/COMSOL.
- **Rotor dimensions:** the drawing (`stator_flex/inputs/Snowflake_disk_V1.3_drawing.png`)
  gives Ø3.50 mm × 0.75 mm, CAD mass 9.89 mg for the disk alone, but the whole rotor
  (disk + sail) weighed 7 mg. Some models assume 0.5 mm thick. Measure the actual disk
  thickness and OD.
- **Trap / libration frequency:** small-amplitude f₀ ~ 0.31 Hz (stopwatch 09-09 0.310 Hz and
  video 10-30 0.311 Hz agree); how it depends on amplitude and time is open (`analysis/ringdown_20261102/README.md`). Current value:
  `docs/DECISIONS.md`. The older LES-based 0.12–0.16 Hz values predate the comb rule and
  are unexplained. Re-examine `Y1_RDS-LES_YAW_IN1_DQ_1472933400_1472935200.h5` in the
  time domain (cusp spacing, not a peak finder).
- **Rotation direction:** which way A→B→C turns the rotor has not been observed. No lock
  yet; on the sweep the camera-to-board sign mapping is not established.
- **PD check** across the 09-11 laser-only segment (from GPS 1473204806) for drift or
  mode hops.
- **`VOLTS_PER_COUNT` on `_OFFSET`:** ~0.0134 V/count is measured on the `_EXC` path only;
  `stator_osc_drive.py` sets the pedestal with `_OFFSET`, which is unverified. Measure
  with a meter on the amp output.
- **Capture bracket:** detent runs at 4000 / 4800 / 5600 counts, recording the
  pre-drive rms each time.
- **Measure `I` directly** from the high-frequency asymptote of χ(f).
- **Free spindown (laser off) with the tilt stage in:** the replacement stage is installed
  on 2026-10-15 (Molly, 2026-11-01; alignment not recorded here). Re-measure τ to get
  the current γ (drag row in `docs/DECISIONS.md`).
- **PD / pickoff:** measure the pickoff ratio; find why the PD lost ~28% response when
  the PBS went in; replace the PBS251 with a wedged window or characterise its drift.
- **Torque-per-mW drop (4.5×):** separate beam geometry from sail alignment (the tilt
  stage is now in).
- Tilt the ND filter to break the etalon. Commanded laser counts before/after the 08-03
  step.
- **Slow-controls logging:** get **temperature** and the **pressure gauge** logging
  continuously. Existing pieces: `lab_utils/log_pressure.py` (written, gauge not
  recording); `analysis/ambient_temp_pull.py` pulls the GHS room sensor from InfluxDB
  after the fact. Gauge notes: `docs/reference/wrg_gauge.md`.
- **Basler:** more magnification (16 mm lens is at ~0.09×; options in
  `camera_utils/README.md`). Lossless FFV1 + per-frame timestamps are done (2026-10-28).
- **Log housekeeping:** accuracy audit (label claims measured / derived / assumed);
  the October entries in `apparatus_log.md` are still long-form (pre-October is archived
  in `logs/2026-q3.md`).

## Process (later)

- **Hooks:** `PreToolUse` guards that block `--live`/`--leave-running`, `ssh cymac1` and
  GNOME Shell restarts without approval (about 15 lines each, in `.claude/settings.json`).
- **Process improvements:** go through what has gone wrong with agents and fix the
  owning doc or rule.
