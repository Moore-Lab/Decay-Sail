# Laser injection test: HANDOFF (updated 2026-11-16 evening)

**State: overnight interleaved ND4 run in progress (started 19:43 local, ends ~06:30–07:00).** Labels: M measured,
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

- **S1 = +52.2 µHz** (M) at 0.30 mW: ~25× the pair scatter. Equal and opposite shifts, mean γ unchanged (no heating
  seen to ~2 µHz). Laser helps the + direction.
- **Torque ~7.9e-16 N m; ~2.6e-15 N m/mW at the window** (D: Δγ·π·I·f, I = 1.1e-11 ±10 %). Window AR-coated (coating to
  be confirmed, Molly); power measured before it.
- **Recoil equivalent (D): 1.1e-18 / 2.6e-15 ≈ 0.42 µW** at the window.
- **Baseline moved (M, unexplained):** off1 is +6.7 µHz (3.1 sd) from the 11-14/15 mean, both γ moved in opposite
  senses (looks like a torque). So non-interleaved comparisons across days are not trustworthy below ~10 µHz.
- Plots: `plots/laser_pair_panels.png` (blocked vs ND1 coasts), `plots/laser_pairs.png` (gitignored; rerun scripts).

## Calibration (`analysis/calibration_history.md`, 2026-11-16)

- PD (`Y1:RDS-PD_INMON`, after the ND, before the chamber): 685.5 counts = 3.08 mW (Ophir before window) → 222 counts/mW.
- ND1 transmission 0.098 (PD ratio). ND4 (and ND3) transmission at 660 nm: **not measured — Ophir at full power, same
  holder untouched (to do).**
- PD dark: −0.93 (PD covered), −0.9 (ND4 in); +0.19 with ND1 and `LASER_OFFSET` 0 → the laser at offset 0 still emits
  ~1.7 % of full power (tentative, two dark methods). Off pairs therefore carry ~1.7 % of the on light.
- Laser switching (check A): back within 1 % in ~10 s after 0→1000 (overshoot +4–6 % for ~4 s), within 0.3 % after.

## Interleaving (branch `laser-interleave`, 60a4d3b; Mac worktree `~/Desktop/VSCode/decay_sail_wt_li`, worker2 `~/wt_li`)

`coast_series.py --laser-pattern off,on,on,off [--laser-on 1000 --laser-off 0 --laser-settle 30]`: before each pair's
+ spin-up it writes `Y1:RDS-OUTS_LASER_OFFSET`, waits, then runs the pair; never changes mid-pair; restores the start
value on every exit; `laser.csv` logs setpoint, readback, PD per switch and coast. ABBA cancels linear drift.
Analysis: laser effect = mean Δγ(on pairs) − mean Δγ(off pairs). Checks A and B passed on worker2 (rotor at rest; B with
`lab_utils/coast_series_stub_brake.py`, whose fake final brake makes the test exit 2 — harmless). Not yet merged.

## Overnight 2026-11-16/17 (running)

ND4 in (~0.31 µW, ~0.7× recoil, ND4 transmission unmeasured), beam open, `--pairs 24 --laser-pattern off,on,on,off
--ncc-min 0.62 --live`, pid 752075, worker2 `~/spinup/2026-11-16/laser/night_nd4_il`, tracker pid 691391 (centre
128.62,176.54). **Expected: no visible laser effect** (D: ~0.05 µHz vs ~0.9 µHz error for 12+12 pairs). Use: the first
interleaved baseline, drift within the night, start of the near-recoil record. An on−off difference ≫ 2–3 µHz would not
be the laser.

## Next (exact steps)

1. Morning: worker2 copies small files to Dropbox; then on the Mac:
   `cd analysis/laser_injection_20261116 && python3 coasts.py --no-cache && python3 pair_panels.py`
   (`coasts.py` labels pairs by the `laser on/off` line in each `coast_On.txt` and prints on − off per interleaved
   run; `pair_panels.py` covers only off1/on so far).
2. Ophir: ND4 transmission at full laser power, holder untouched; then set `--laser-on` for exactly 1× (0.42 µW).
3. Decide with Molly: more ND4 nights vs ND2 interleaved (D: ~6σ in one night) to demonstrate power scaling.
4. Pair-to-pair scatter (~2.1 µHz) sets how close to the recoil is reachable (D: 5σ at 1× needs ~4e4 pairs per arm):
   temperature/pressure logging (STATUS) and the baseline jump.
5. Merge `laser-interleave` after a clean night (Molly's call).

## Background numbers (pre-run design, D)

Pair scatter 2.12 µHz; Δγ = N/(π I f); radiation-pressure estimate k ≈ 2–9e-15 N m/mW (measured 2.6e-15). The PI's
"78 µHz" is the recoil's steady frequency shift N τ/(2πI) at τ = 80 min (now ~33 µHz at τ ≈ 34 min); not the Δγ the
coast pairs measure (0.073 µHz). Old (Aug) laser numbers: history only.
