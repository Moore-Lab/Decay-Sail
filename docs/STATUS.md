# Status

What is open now. Overwrite freely: when an item closes, delete it here and record
the outcome in `apparatus_log.md` (and `docs/DECISIONS.md` if it sets a value).
The goal these serve is in `measurement_objective.md`.

## Open

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
- **Trap / libration frequency:** treat as not known. Re-examine
  `Y1_RDS-LES_YAW_IN1_DQ_1472933400_1472935200.h5` in the time domain.
- **PD check** across the 09-11 laser-only segment (from GPS 1473204806) for drift or
  mode hops.
- **`VOLTS_PER_COUNT`:** measure (`stator_epics_drive.py calibrate` + meter on the amp
  output).
- **Capture bracket:** detent runs at 4000 / 4800 / 5600 counts, recording the
  pre-drive rms each time.
- **Measure `I` directly** from the high-frequency asymptote of χ(f).
- **Tilt stage:** install the replacement, align, re-measure τ with a free spindown.
- **PD / pickoff:** measure the pickoff ratio; find why the PD lost ~28% response when
  the PBS went in; replace the PBS251 with a wedged window or characterise its drift.
- **Torque-per-mW drop (4.5×):** separate beam geometry from sail alignment once the
  tilt stage is in.
- Tilt the ND filter to break the etalon. Commanded laser counts before/after the 08-03
  step. Get the pressure gauge logging.
- **Basler:** lossless recording + per-frame timestamps in `grab_basler.py`; more
  magnification (16 mm lens is at ~0.09×).
- **Log housekeeping:** accuracy audit (label claims measured / derived / assumed);
  restructure `apparatus_log.md` into short entries, archive pre-October.
