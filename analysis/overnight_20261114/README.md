# Overnight coast series 2026-11-14/15: damping per coast (LES and tracker)

**Status: complete, all 60 steps (30 pairs, 23:06 to 12:54 EST). Interpretations are not approved.** Run log:
`apparatus_log.md` 2026-11-14 (night). Code: `les_coasts.py`, `tracker_coasts.py` (methods in their docstrings);
output `les_coasts.{json,csv}`, `les_coasts_stdout.txt`, `tracker_coasts.{json,csv}`, `tracker_coasts_stdout.txt`;
plots `plots/les_tau_vs_time.png`, `plots/tracker_vs_les.png` (gitignored).

Data: Dropbox `spinup/2026-11-14/overnight/`: `les/` (LES PIT and YAW `_OUT_DQ`, 1024 Hz, FE GPS
1478767437–1478817856, 15 files, no gaps), `series/` (`series.csv`, `coast_On.txt`, consoles), `tracker/`
(`blob_live_gps1478746563.csv`, 50 fps all night, 0 dropped frames, ncc min 0.725). Each coast: 600 s, field off,
nothing written; spin-up to 0.5 Hz before it (`lab_utils/coast_series.py`, voltage-steps 6e861aa).

## Run (measured)

- Spin-ups on target 49/60: +1 29/30 (O05 held 0.489), −1 20/30. Of the −1 misses, O04, O20, O56, O60 never went
  over the top (swing, no coast data); O08 made one turn at 0.41 Hz; O10, O22, O26, O38, O48 held 2–8 % low. No
  ncc, stale-tracker, speed-cap or error stops. Final brake ran 300 s; front end at rest after (OFFSET 0, SW2R 768,
  OUTMON 0).
- 56 coasts rotating. Band summaries use the 54 that started at ≥ 0.47 Hz (all but O08, O10); whole-coast summaries
  the 52 that started at ≥ 0.48 Hz.

## Damping (derived)

tau from a fit of f = f0 exp(−t/tau). LES: the 2 f_rot line, rate per 40 s window. Tracker: per-turn rates, as
`analysis/coast_pairs_20261112/coast_pairs.py`. Same coast windows (field off + 5 s to coast end − 2 s).

**Band 0.40–0.47 Hz** (min):

| readout | dir | coasts | mean tau | sd between coasts | trend (min/h) |
|---|---|---|---|---|---|
| LES | +1 | 30 | 34.03 | 0.13 | +0.016 ± 0.005 |
| LES | −1 | 24 | 34.41 | 0.17 | +0.039 ± 0.006 |
| tracker | +1 | 30 | 33.97 | 0.12 | +0.018 ± 0.004 |
| tracker | −1 | 24 | 34.38 | 0.16 | +0.035 ± 0.006 |

- **Back-to-back pairs (− minus +), band tau:** LES **+1.10 %** (sd 0.53, sem 0.11, 24 pairs); tracker **+1.18 %**
  (sd 0.42, sem 0.09). **− is higher in all 24 pairs** in both readouts (LES +0.10 to +2.08 %).
- **Tracker vs LES, same coast:** tracker/LES − 1 = −0.14 % (sd 0.16 %, range −0.50 to +0.21 %, 54 coasts). The two
  readouts agree coast by coast to well within the coast-to-coast scatter.
- **Band 0.44–0.49 Hz (the 11-12 band), tracker:** +1 36.51 (sd 0.12, n 30), −1 36.97 (sd 0.19, n 20) min; pairs
  +1.21 % (sem 0.10, 20/20 positive). 11-12 tracker, same band: 36.2 / 36.8 min, − minus + +1.47 ± 0.57 % (3 pairs,
  `analysis/coast_pairs_20261112/coast_pairs.json`; the interim version of this README misquoted it as −1.47). So the shorter tau in the 0.40–0.47 band is the band, not a change since 11-12.
- Whole coast (≈0.49 → 0.37 Hz): LES +1 33.61 (sd 0.36), −1 33.98 (sd 0.38); pairs +1.22 ± 0.27 %. Larger scatter
  than the band because the speed range covered varies with the start speed.
- Per-coast fit errors (LES jackknife ~0.5 min) are ~4× the coast-to-coast scatter, so the scatter is used as the
  measured repeatability.

## Observations, not interpreted

- tau depends on speed: ~34.0 min at 0.40–0.47 Hz, ~36.5 min at 0.44–0.49 Hz (+1), so damping is not purely
  viscous (exponential) over this range. Cause unknown.
- − damps less than + (longer tau) by ~1.1–1.2 %, every pair, both readouts, same sign as 11-12. Cause unknown.
  Which of ± is CW is not established.
- tau drifts up through the night, faster in − (+0.035–0.039 min/h) than + (+0.016–0.018 min/h), so the pair
  difference grows (~+0.5 % early, ~+1.5–2 % around 08:00–09:00). Cause unknown; temperature and pressure are not
  logged.
- −1 spin-ups failed 10/30 vs +1 1/30 tonight. Unexplained.

## Next

1. Molly: which readout and band to quote (both readouts agree; band choice changes tau by ~7 %).
2. A temperature/pressure log alongside the next long run, to test the drift.
