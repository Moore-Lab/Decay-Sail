# Measurement objective

## Goal

Measure the alpha-recoil force on the sail from a Pb-212 source.
Expected force **F0 = 0.81 fN** (PI's figure, 2026-10-09).

## Current directive

**Reliably spin up the rotor with the electrodes:** to a set frequency, on demand,
repeatably, in both directions.

## Success criteria

Each stage is passed when it succeeds in **8 of 10 consecutive attempts** in **each
direction** (final target: 10 of 10). Every stage is done before moving to the next.

| Stage | Pass when |
|---|---|
| 1. Carry | At a fixed low speed (0.01–0.05 Hz mech, below capture), the rotor follows the wave with **no slips for 5 min** |
| 2. Ramp | From rest, ramp to **0.2 Hz** and hold it for 5 min |
| 3. Target | From rest to **1 Hz within 5 min**, then held at **1 Hz ± 1% for ≥ 5 min** |

For each attempt, record which LES divisor was used and confirm the frequency once
by stopwatch or camera.

Progress: `docs/STATUS.md`. Tools: the drive-script table in `CLAUDE.md`.
