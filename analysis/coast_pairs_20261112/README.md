# CW/CCW coast pairs (2026-11-12): damping symmetry

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


## All three pairs (C1/C2, C3b/C4, C5/C6; tracker centre (131.03, 178.79) from C3b on; derived)

| quantity | + coasts (C1, C3b, C5) | − coasts (C2, C4, C6) | − vs + per pair (%) | weighted mean (%) |
|---|---|---|---|---|
| τ, 0.44–0.49 Hz (min) | 36.22, 36.32, 36.14 | 36.77, 36.78, 36.71 | +1.51, +1.27, +1.58 (±0.9–1.1 each) | **+1.47 ± 0.57** |
| c, 0.44–0.49 Hz (1e−4 /s) | 3.672, 3.730, 3.724 | 3.634, 3.668, 3.682 | −1.04, −1.65, −1.14 | **−1.24 ± 0.62** |
| τ, 0.38–0.49 Hz (min) | 33.52, 33.60, 33.48 | 33.91, 33.92, 34.00 | +1.17, +0.97, +1.57 | +1.24 ± 1.89 |
| c, 0.38–0.49 Hz (1e−4 /s) | 3.708, 3.749, 3.754 | 3.687, 3.713, 3.706 | −0.59, −0.95, −1.29 | −0.98 ± 0.46 |

**Observations:**
- **Every pair shows the same sign:** the − direction damps 1.0–1.5 % less than the + direction (τ longer, c lower).
- **The scatter is smaller than the errors.** Repeats within a direction agree to ~0.1–0.3 % (τ: + 36.14–36.32, −
  36.71–36.78), and χ² ≈ 0 for 2 degrees of freedom. So the jackknife errors look conservative.
  - On the repeat scatter, the τ difference is about 1.5 ± 0.15 %, i.e. not consistent with zero.
  - On the jackknife errors it is 2.6σ.
- **Comparison with September** (Molly's slide, one coast each way): 0.4 ± 0.5 % at 0.50–0.75 Hz and ≈ 3 % at 0.3–0.5 Hz.
  These coasts are at 0.37–0.50 Hz.
- **Cause: unknown.** Candidates, not approved:
  - A small constant torque (direction-independent) would slow one direction and speed the other. It would give an
    asymmetry growing as 1/ω, matching September's larger lower-band difference. But here the wider band (lower speeds
    included) shows a smaller c asymmetry, not a larger one, so this data does not support that scaling.
  - A direction-dependent dissipation.
  - Something from the stator: the electrode floors at 0 counts are small and static, which by itself gives no net
    torque per turn.
- **Next tests (proposed):**
  - pairs at 0.75 Hz, which needs the 16 Hz update; there September matched to 0.4 %;
  - more pairs here, to fix the band dependence of the asymmetry;
  - a pair with the camera illumination changed, to check light-induced torque.
