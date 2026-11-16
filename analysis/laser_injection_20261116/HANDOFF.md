# Laser injection test with the CW/CCW coast-series protocol: HANDOFF (2026-11-16, for a fresh session)

**Status: idea and design questions only. Nothing built, nothing run.** Read CLAUDE.md, `docs/STATUS.md`,
`docs/DECISIONS.md` first. Discuss the physics and the design with Molly before building anything (CLAUDE.md:
gates first; ask about intent). Labels: M measured, D derived, A assumed, "Molly" = Molly said (2026-11-16).

## Goal (Molly)

Make the same plots as the overnight coast series (gamma per coast, Δgamma = gamma(−) − gamma(+) per pair, pair-to-pair
variation; `analysis/overnight_20261114/plots/pair_vs_time.png`) while a laser applies an asymmetric optical force,
to mimic the Pb-212 recoil signal: an injection / end-to-end calibration test.

## Molly's answers so far (2026-11-16)

1. Laser on during both spin-ups and coasts ("the real force from decay won't stop").
2. Beam focused, landing on one side of the sail, to mimic the signal.
3. Powers: to be chosen; an ND4 filter is available.
4. Power monitored on the PD; PD alignment to be checked first.
5. Schedule (how many pairs per power, on/off ordering) to be worked out; low powers may not need a full night.

## The protocol (the "flip" protocol: spin +, coast, spin −, coast)

| what | where |
|---|---|
| series script, stop rules, files written | `lab_utils/coast_series.py` docstring, branch **voltage-steps** (Mac worktree `~/Desktop/VSCode/decay_sail_wt_vs`; worker2 `~/wt_vs`) |
| spin-up tool it calls | `lab_utils/brake_offsets.py` (same branch); `lab_utils/SPINUP_HANDOFF.md` (main) |
| the overnight run 11-14/15 | `apparatus_log.md` "2026-11-14 (night)" |
| analysis and numbers | `analysis/overnight_20261114/README.md`; `pair_plots.py` (gamma at 0.435 Hz, pairs), `local_tau.py`, `tracker_coasts.py` |
| before the next live run | re-centre the tracker (3 px off overnight; `analysis/drive_fit_20261114/README.md`); worker2 conventions in CLAUDE.md (Molly types every live go in the worker2 session) |

Note: coast_series and brake_offsets do not touch the laser. Any laser control or logging added is hardware code:
a branch, tested on worker2, Molly's go.

## Numbers from the overnight series to design with (D, `analysis/overnight_20261114/`)

- gamma at 0.435 Hz: 0.4916 mHz (+), 0.4857 mHz (−) (1 mHz here = 1e-3 /s); per-coast formal error ~0.15 µHz.
- Δgamma per pair: −5.77 µHz, **sd 2.12 µHz between pairs** (per-pair formal error ~0.22 µHz). The pair-to-pair
  variation, not the readout, sets the noise; its cause is not identified, and whether it is independent between pairs
  and stationary is not tested.
- A constant torque N (fixed rotational sense, same for both spin directions; A) changes Δgamma by 2·N/(2πI)/f
  (I = 1.1e-11 kg m², DECISIONS, ±10 %). At f = 0.435 Hz: 0.073 µHz per 1.1e-18 N m (the expected recoil torque).
  Its signature: scales as 1/f across speed slices (`local_tau.py` style) and with laser power.
- Rough size for detection (D; assumes independent, stationary pair scatter): laser-on vs laser-off with N pairs each,
  5σ needs ~5 × 2.12 × √(2/N) µHz, e.g. ~4.7 µHz at N = 10, i.e. a torque ~65× the recoil (~7e-17 N m).
- Timing: one step (spin-up ~2.5–3.5 min + 10 min coast) ~13–16 min; a pair ~25–30 min.
- tau depends on speed (27.8 → 37.6 min from 0.38 → 0.48 Hz): compare coasts over the same frequency band.

## Old laser torque numbers (history only: old setup, Aug 2026; do not plan with them, re-measure)

- `analysis/calibration_history.md` lines ~69–81: 2.66e-15 N m/mW (08-03) vs 1.19e-14 N m/mW (July), 4.5× drop; STATUS
  "Torque-per-mW drop (4.5×)" is open. `analysis/laser_stepdown_sensitivity_notes.md`: PD counts/mW and N m/PD count.
- Molly's memory note: don't use Aug-2026 old-setup results in current reasoning; argue from current measurements.

## Open design questions (to discuss with Molly)

1. Torque per mW on the current rotor and beam geometry: measure first (e.g. a short coast pair at one power)?
   Which powers then (with ND4 and without)?
2. Laser on during spin-ups: the governor will fight or help the optical torque; check spin-up still reaches target
   in both directions.
3. Does the torque depend on rotor angle within a turn, and on spin direction (one side of the sail lit only part of
   each turn)? What is measured is the turn average.
4. Heating / gas effects could change gamma in both directions (mean gamma) rather than Δgamma; keep both.
5. Ordering: interleave laser-off and laser-on pairs (off/on/off/on) against drift; how many pairs per power.
6. PD: alignment check, logging alongside each coast (channel, rate), and the PD-to-mW calibration.
7. Temperature/pressure logging (sensors in hand, not set up) would help with the pair-to-pair variation.
