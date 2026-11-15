# Overnight coast series 2026-11-14/15: damping per coast (LES, interim)

**Status: interim, first 38 coasts (to 07:56 EST). Series still running at the time of writing. Interpretations are
not approved.** Run log: `apparatus_log.md` 2026-11-14 (night). Code: `les_coasts.py` (method in its docstring);
output `les_coasts.json`, `les_coasts.csv`, `les_coasts_stdout.txt`, `plots/les_tau_vs_time.png` (gitignored).

Data: Dropbox `spinup/2026-11-14/overnight/les/` (LES PIT and YAW `_OUT_DQ`, 1024 Hz, FE GPS 1478767437–1478799321,
no gaps) and `.../series/` (`series.csv`, `coast_On.txt`). Each coast: 600 s, field off, nothing written;
spin-up to 0.5 Hz before it (`lab_utils/coast_series.py`, voltage-steps 6e861aa).

## Measured (derived from the LES line at 2 f_rot; rate per 40 s window)

- The 2 f_rot line is strong in both channels (median SNR ~1600–2000); PIT and YAW give the same tau to ≤0.05 min.
- 36 of 38 coasts were rotating. O04 and O20 were swings (the − spin-up never went over the top), skipped. O08 (start
  0.41 Hz) and O10 (0.46 Hz) started low and are out of the band and whole-coast summaries.
- **tau in the common band 0.40–0.47 Hz:**

  | dir | coasts | mean tau (min) | scatter (sd) | trend (min/h) |
  |---|---|---|---|---|
  | +1 | 19 | 33.99 | 0.11 | +0.019 ± 0.009 |
  | −1 | 15 | 34.32 | 0.14 | +0.042 ± 0.009 |

- **Back-to-back pairs (− minus +), band tau: +0.94 % (sd 0.36 %, sem 0.09 %, 15 pairs), every pair positive**
  (+0.36 to +1.50 %). Whole coast (start ≥ 0.48 Hz, 14 pairs): +1.0 ± 0.26 %.
- Whole-coast tau (≈0.49 → 0.37 Hz): +1 33.46 (sd 0.26), −1 33.80 (sd 0.30) min; shorter than the band value
  because it reaches lower speeds.
- The per-coast jackknife errors (~0.5 min) are ~5× the coast-to-coast scatter, so they are not used; the scatter is
  the measured repeatability.

## Observations, not interpreted

- − damps less than + (longer tau) by ~1 %, the same sign as the 11-12 tracker coast pairs (−1.47 ± 0.57 %, band
  0.44–0.49 Hz, `analysis/coast_pairs_20261112/`). Cause unknown. Which of ± is CW is not established.
- tau drifts up over the night, more in − (+0.36 min over 8.5 h, ~1 %) than in + (+0.16 min), so the pair difference
  grows from ~0.5 % to ~1.3 %. Cause unknown; temperature and pressure are not logged.
- LES tau here (34.0 / 34.3 min, 0.40–0.47 Hz) is shorter than the 11-12 tracker values (36.2 / 36.8 min,
  0.44–0.49 Hz). Different band and different readout: not comparable until the tracker analysis of this night
  (planned) is done on the same band.

## Next

1. Remaining coasts after the series ends (last LES chunk; worker2).
2. Tracker per-turn tau for the same coasts and band (`coast_pairs.py` method), against LES coast by coast.
3. Molly: which readout and band to quote.
