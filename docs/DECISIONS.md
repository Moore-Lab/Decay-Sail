# Decisions and current values

The one home for "what is true now". The goal and expected force F0 are in `measurement_objective.md`. Append-only: to change something, add a new
entry that supersedes the old one, and mark the old one ~~struck~~ with a pointer.
Each entry says who decided and what it rests on (measured / derived / assumed).

| Date | Decision or current value | Who / basis | Details |
|---|---|---|---|
| 2026-10-27 | Board height set with shims **under the PEEK plate**. Flex lies flat. No metal under the pads (bare GND around each live pad → phase-to-GND short). | Molly; meter checks passed | Shim stack: _to fill in_ |
| 2026-10-28 | `DRVMTRX` changes reach the DAC within one 1024 Hz sample (with `DRVMTRX_TRAMP = 0`); `caput` ~0.4 ms. The camera (20 ms/frame at 50 fps) is the slowest element in a feedback loop. | Measured | `apparatus_log.md` 2026-10-28 |
| 2026-10-27 | Board GND is a wire from a top GND pad (r 10.8 mm, az 60/240°) to a base screw. The bottom GND ring barely overlaps the 1/4" magnet and does not make contact. | Molly; continuity measured | `apparatus_log.md` 2026-10-21/22 |
| 2026-10-21 | Rotor centred on the board to 0.02–0.05 mm. | Measured (microscope photos) | `analysis/rotor_centering/README.md` |
| 2026-10-19 | **No centre shim**, and none planned. Gap h ≈ 0.37 mm. | Molly. h is the design value; levitation height not yet measured | Earlier "0.1 mm shim / 0.27 mm gap" text was a Claude assumption |
| 2026-10-14 | Drive amplitude ceiling `--amp 6400` (amp + pedestal = 12800 = `V{n}_LIMIT`). | Hardware limit | `measurement_objective.md` |
| 2026-10-09 | Laser calibration 11.10 µW/count above 764 counts. PD pickoff ~411 counts/mW. Lever arm `R_EFF` = 1.38 mm. | Measured | `apparatus_log.md` 2026-10-09 |
| 2026-10-09 | Use `LES_PIT`, not `LES_YAW`, after the beam move (SNR 511 vs 212). | Measured | `apparatus_log.md` 2026-10-09 |
| 2026-09-30 | Moment of inertia **I = 1.1e-11 kg·m² (±10%)**. Supersedes 1.88e-11 and 1.7e-11. | Derived: weighed 7 mg assembly + model shape | `logs/2026-q3.md` 2026-09-30 |
| 2026-09-08 | **`lab_utils/stator_osc_drive.py` is the drive** (front-end oscillator + `DRVMTRX`), after the model change. | Verified −120.00° phases, 5-sig-fig amplitudes | `y1rds_model_change_muxmatrix.md` |
| design | **Drive harmonic m = 8** (rotor speed = f_elec/8). | **Derived** from the rotor drawing; the flown rotor's 8-fold holes agree (photo, 2026-10-29). Detent test pending | `stator_flex/flex_spec.md` |
| 2026-09-14 | LES divisor, working rule: **rotation = comb/2**. | Molly timed 10 turns with a stopwatch, 2026-09-14 (before the 2026-10-09 beam move) | `logs/2026-q3.md` 2026-09-14 |
| 2026-09 | Front-end (cymac1) GPS is read live from `Y1:DAQ-DC0_GPS`; no stored offset. worker2 file names (Basler, uEye) are true GPS. | Offset measured 3072–9876 s and wandering | `lab_utils/stator_awg_drive.py`, `spindown_gui.py` |
| 2026-08-24 | V1 is the centre electrode; phases (A, B, C) = (V2, V4, V3), `PHASE_ELECTRODES = (2, 4, 3)`. The old (2,3,4) swaps B and C. | Continuity check | `logs/2026-q3.md` 2026-08-24 |
