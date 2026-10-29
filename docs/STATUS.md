# Status

What is open now. Overwrite freely: when an item closes, delete it here and record
the outcome in `apparatus_log.md` (and `docs/DECISIONS.md` if it sets a value).
The goal these serve is in `measurement_objective.md`.

## Spin-up (the current directive)

Stage 1 (carry) is **not yet passed**. 2026-10-14, two runs of `stator_osc_drive.py hold
--felec 0.08 --amp 6400`: LES rms 15.6 → 304.9 counts, with a line within one FFT bin
of the f_elec/8 prediction (reproduced), but the rotor is **not carried round**: video
phase coherence 0.670 during drive (four full turns would give ~0.04). Observed by eye:
sometimes forward with sudden backward slips, sometimes back-and-forth.
`--amp 6400` is the software ceiling (see DECISIONS).

## Open

- **Angle tracking (white dot):** good detections 83% on the 2026-10-28 recording but
  31% live, unexplained (`apparatus_log.md` 2026-10-28). Scope it as a multi-agent
  project (ground truth + scoring, detector, angle → frequency, capture on worker2,
  live loop) once the docs are clean.

- **Drag law:** `damping_law_comparison.ipynb` (τ₀ + γω, γ = 3.53e-15) vs
  `noise_budget_20260911_clean` (pure linear, γ = 2.30e-15). Decide which the programme
  uses. Settle with one long free spindown over a wide ω range, fitted both ways.
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
- **Rotor dimensions:** disk thickness (the models assume 0.5 mm, the V1.3 design
  note says 0.75 mm; both look too thick for the weighed 5.8 mg) and OD (3.4–3.5 mm).
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
  step. Get the pressure gauge logging.
- **Rotor frequency from the white dot:** not done yet (so far the dot has only been
  tested for angle detection). Once it works, compare against LES in one recording to
  settle the divisor for libration and rotation.
- **Basler:** lossless recording + per-frame timestamps in `grab_basler.py`; more
  magnification (16 mm lens is at ~0.09×).
- **Log housekeeping:** accuracy audit (label claims measured / derived / assumed);
  the October entries in `apparatus_log.md` are still long-form (pre-October is archived
  in `logs/2026-q3.md`).
- **Calibration history:** `analysis/calibration_history.md` (which constants applied
  to which datasets).
