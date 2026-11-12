# CW/CCW coast pairs (2026-11-12): damping symmetry, first look

Method: Molly's differential spindown. Spin up with the electrodes (`brake_offsets.py --spin-to 0.5 --stop-on-target 3
--stop-tol 0.01`, voltage-steps dad1a29), field off on target, coast 600 s with no writes, reverse, repeat.

- **Runs:** C1 (+1), C2 (−1), C3 (+1). C3's coast is valid only to 336 s: the camera was moved at host 1794511172.9.
  The series was stopped there.
- **Data:** Dropbox `spinup/2026-11-12/coast/`.
- **Code:** `coast_pairs.py` → `coast_pairs.json`, `plots/coast_pairs.png`.
- **Status:** derived; interpretations **not approved**.

## Fits

Two fits per coast:

1. **Per-turn rates**, with interpolated crossings and frame-index timing; fit f = f0·exp(−t/τ).
2. **Energy** E = ½ω² + U(θ), with U from S1's coast; fit dE/dt = −c⟨ω²⟩ turn by turn (viscous c; τ = 1/c).

C2's 7-frame dot loss is masked. Errors are 1σ from a delete-one-block jackknife over 10 blocks of turns.

| quantity | C1 (+) | C2 (−) | C3 (+, 0–336 s) | C2 vs C1 | C3 vs C1 (repeat) |
|---|---|---|---|---|---|
| τ, common band 0.44–0.49 Hz (min) | 36.22 ± 0.24 | 36.77 ± 0.22 | 36.10 ± 0.27 | +1.5 ± 0.9 % | −0.3 ± 1.0 % |
| c, common band (1e−4 /s) | 3.672 ± 0.024 | 3.634 ± 0.034 | 3.701 ± 0.026 | −1.0 ± 1.2 % | +0.8 ± 1.0 % |
| c, 0.38–0.49 Hz (C1, C2 only) | 3.708 ± 0.014 | 3.687 ± 0.030 | – | −0.6 ± 0.9 % | – |
| τ, whole coast (min) | 32.9 ± 1.0 | 34.1 ± 1.0 | 35.8 ± 0.4 | (different bands) | (different bands) |

## Observations

- **CW against CCW:** the − coast damps 0.6–1.5 % less than the + coasts. That is 1–1.7σ, so consistent with zero at this
  precision, from one pair.
- **Repeatability:** the two + coasts agree to within ~1 %.
- **Comparison with September** (Molly's slide): 0.4 ± 0.5 % at 0.50–0.75 Hz, and ≈ 3 % at 0.3–0.5 Hz. These coasts are
  in the lower band.
- **The whole-coast τ depends on the band,** from 32.9 to 35.8 min depending on where each coast starts and ends,
  because the trap makes the per-turn rate non-exponential at these speeds. Only common-band numbers compare.
- **The energy fit gives the same c** for all three coasts to ~1 % (3.63–3.70e−4 /s). That fits S1's coast value
  (3.8e−4, 0.27–0.43 Hz).
- **Precision needed:** the recoil is ~1e−4 of the drag (slide), so this is far from the level the measurement needs.
  It needs many pairs, and 0.75 Hz.
