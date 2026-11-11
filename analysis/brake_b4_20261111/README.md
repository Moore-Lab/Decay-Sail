# Brake gate B4, 2026-11-10/11: live brake through the electrode offsets

Interpretations are Claude's and marked "(interpretation, not approved)".

- **Plan:** braking gates B1–B4 (B1 trap `analysis/brake_b1_20261110`, B2 push map `analysis/brake_b2_20261110`, B3 simulation
  `analysis/brake_b3_20261110`); rule in `docs/DECISIONS.md` 2026-11-10 (measured trap + push map, simulator check, live safety).
- **Code:** `lab_utils/brake_offsets.py` on branch `voltage-steps` (df9d6df stage 1; ee337c0 stage 2; b6c2ef9 stage 2b). Live tracker
  `camera_utils/tracking/live_blob_track.py --publish` from branch `feedback-drive` (centre 117.5, 165.1).
- **Data:** Dropbox `Microspheres/TFINER/data/brake/2026-11-10/b4/` (stages 1, 2) and `.../2026-11-11/b4/` (stage 2b): brake logs,
  tracker angle CSVs, videos. Check script: `b4_check.py` (plot `plots/b4_kick_brake.png`, gitignored).

## Runs (worker2, Molly's typed go each)

| stage | outputs | what | result |
|---|---|---|---|
| 1 (11-10, FE 1478419559–629) | off | loop test, 60 s, on a ±13.6° swing | 441 writes (7.4/s), choices A 156 / B 113 / C 155 / off 17; angles 9 ms median after the frame; clean. Fixed after: queued angles at start, write cadence |
| 2 (11-11, FE 1478448785–915) | on | 120 s, 800 counts | rotor already at rest (±0.12°, ~8 h of decay); no rest zone, so V3 was held on all 1004 writes; nudged ±1°. Not a brake test. Fixed after: rest zone, starting kick |
| 2b (11-11, FE 1478449691–831) | on | kick A 2400 counts 2 s, settle 10 s, observe 5 s, brake 120 s at 800 counts | **swing ±19.5° → ±2.6° by 4–8 s, ±1.1° by 12–16 s**; then the rest zone kept the field off (918 of 1006 updates off) and the rotor sat at ±1.05° about 208.5° for 105 s. No safety stop |

## Measured (stage 2b, `b4_check.py`)

- Swing (half peak-to-peak) after braking starts: 15.7° (0–4 s), 2.6° (4–8 s), 1.5° (8–12 s), 1.1° (12–16 s), 1.05–1.08° (16–120 s).
- Pushes: A 23, B 12, C 53 (88 in all, nearly all in the first ~10 s); off 918.
- The kick took the angle to 195.6–235.1°, 0.9° inside the 236° safety limit.
- Pass mark (B4, Molly 2026-11-10: below ±10° within 2 min, never growing, never over the top): **met.**

## Derived

- Without the brake, a ±19.5° swing would decay with Q ≈ 4300 (B1): amplitude e-folding ~1.6 h. The brake did it in ~6 s.
- The simulator (B3) predicted 4–5 s to below ±10° at 800 counts; measured 4–8 s.

## Interpretation (not approved)

- (interpretation, not approved) Braking works on this route because the controller uses the push map measured on this rotor
  in this range, not push angles carried over from 11-04 (F3's brake added energy).

## Open

- One successful run; reproducibility (repeat, other kick phases) not shown.
- The ±1° left is below the 1.5° rest threshold, by design; not tested lower.
- The push map covers 187–238°; larger swings need it measured further out (and a wider safety range).
