# Gate B1 (braking plan): field-off trap over 145–293°, 2026-11-10

Analysis only, Mac. `python3 b1_trap.py` (~25 s) rewrites `b1_summary.txt` (every number below), `trap_b1.json` and
`plots/` (gitignored). Interpretations are Claude's and are marked "(interpretation, not approved)".

**Data.** Detent free swing: `../detent_20261110/rotor_angle_detent.csv`, `host_time_cam` 1794356925.0–1794357029.8
(104.8 s, 5240 frames, 50 fps). This starts ~20 s after the phase-C ramp end, when the AC-coupled residue is < 3 % (derived,
from the brief). Angle 145.3–293.3°, angle noise 0.035° rms (measured). 57 `blanked` frames (1.1 %) lie at 223–292°.
S1 free swing: `../voltage_steps_20261110_s1/rotor/rotor_angle_s1.csv`, host ≥ 1794345430. S1 trap: `../f3_step2_20261110/refit/refit_coeffs.json`.

**Method.**
- MAIN table: position second differences, θ(t+τ) − 2θ(t) + θ(t−τ) = ∫ acc(θ(s)) (τ − |s−t|) ds, with τ = 3, 5 and 8 frames.
  acc is piecewise linear on 2° nodes (142–298) with a 2nd-difference penalty. No velocity estimate is needed.
- Smooth table: the refit's velocity-integral method (Δω over 0.16 s segments, ω from a ±0.07 s local quadratic) on the same
  data.
- Synthetic test (derived): at full swing speed (~130°/s) the ω estimate smears features finer than ~10°. Simulated ±74° swings
  with frame noise added give these refit errors:

  | truth | MAIN refit error | velocity-integral refit error |
  |---|---|---|
  | MAIN table | 0.26–0.30 rad/s² | 1.0–1.2 rad/s² |
  | MAIN with the S1 trap spliced into 198–234 | 0.13 rad/s², recovers S1's zeros | – |

  **The MAIN node uncertainty is ~0.3 rad/s².** The jackknife gives 0.04, which is an underestimate because it misses the penalty bias.
- Damping: from the energy at the turning points, E_k = U(θ_turn), not from the acceleration fit.

## B1 result: PASS (derived)

The test is an open-loop replay of the trap alone, starting from the first measured turning point with ω = 0. The integrator is
f3_check's 1 ms semi-implicit Euler, run for 104 s (25 cycles), with the measured γ (`plots/b1_validation.png`).

| replay | period meas / sim | mean turning max, min (meas / sim) | last max, min (meas / sim) | drift at end |
|---|---|---|---|---|
| **MAIN + γ** | 4.1670 / 4.1701 s (+0.07 %) | 292.30/292.39, 146.31/146.23° | 291.29/291.19, 147.18/147.02° | +72 ms (+6° of phase) |
| MAIN, no damping | +0.95 % | p2p +1.5 % | 293.5 vs 291.3 | +0.95 s |
| smooth + γ | +0.74 % | p2p +0.14 % | within 0.2° | +0.73 s |
| hold-out: fit 1st half, replay 2nd | +0.41 % | p2p +0.03 % | within 0.25° | +0.20 s |
| hold-out: fit 2nd half, replay 1st | −0.09 % | p2p +0.22 % | within 0.5° | −0.04 s |

The replay stays inside the data range (145.3–293.5°). Damping is needed for the phase (MAIN without it drifts 82° of swing
phase), but not for the "within a few percent" criterion.

## ⚠ Main caveat: the fine structure is not validated, and small swings contradict it

- **Measured, same day, field off.** The pre-run swing (±1.76° about 208.6°, ~6 min before the first kick) has a period of
  **1.480 s**. Replayed through each trap (derived):

  | trap | period |
  |---|---|
  | B1 MAIN | 0.97 s |
  | B1 smooth | 2.72 s |
  | S1 canonical | 1.49 s |

  Both B1 tables reproduce the ±74° swing. **Neither reproduces small-amplitude motion near rest.**
- The **S1 free swing** (±17.5°) replayed with each trap (60 s) gives:

  | trap | period error | lower turning point (measured 198.3°) |
  |---|---|---|
  | B1 MAIN | +4.8 % | 195.8° |
  | B1 smooth | +3.7 % | 193.9° |
  | S1 canonical | +0.4 % | 198.1° |

  The B1 potential is not level between S1's measured turning points 198.3° and 233.4°, so the result depends on the start. From
  198.3° the B1 MAIN period is 2.50 s instead.
- **Over 198–234°, B1 MAIN − S1 canonical is 1.17 rad/s² rms** (max 2.5 at 226°), about 4× the MAIN node error. The synthetic test
  shows that the method would have recovered the S1 shape had it been there. So the difference is in the data, not in the fit.
  Stiffness at 208.6° (±3° fit): B1 MAIN 41, B1 smooth 10, S1 canonical 18.5 rad/s². The pre-run 1.48 s implies 18.0 (derived).
- Amplitude ladder (`steps_detent.csv`). The gaps between steps still carry the AC residue, so the field is not off there. The
  table gives the measured period at each amplitude, then the trap replays (derived):

  | amplitude | measured | B1 MAIN | B1 smooth |
  |---|---|---|---|
  | ±20° | 2.61 s | 2.77 s | 2.64 s |
  | ±30° | 3.20–3.33 s | 2.62–2.64 s (~20 % short) | 2.94–2.97 s (~10 % short) |
  | ±38° | 3.30 s | 3.03 s | 3.10 s |
  | ±56° | 3.86 s | 3.73 s | 3.79 s |
  | ±74° | 4.18 s | 4.21 s | 4.24 s |

  Observation only. The residue would have to account for a 10–20 % shift at ±30°.
- (interpretation, not approved) There are two readings:
  1. The trap changed during the six kicks (the runs are ~3.2 h after S1; the pre-run swing came before the kicks).
  2. A speed-dependent tracking error. Measured acc ≈ true acc + δ''(θ) ω². Turning S1 into B1 over 198–234 would need only
     **δ ≈ 0.12° peak-to-peak (0.033° rms, ~0.05 px at r 23.5 px)**, because ω² there is ~10× larger than in S1.

  A free swing cannot separate the two: at fixed energy, ω² is a fixed function of θ.

## Trap features (MAIN table; derived; `plots/b1_trap_acc.png`, `plots/b1_potential.png`)

- **Equilibria** (stiffness −da/dθ from a ±3° fit). Each hump is the barrier height above the higher of the two neighbouring
  minima. The U uncertainty is ~0.02 rad²/s².

  | angle | type | stiffness | hump |
  |---|---|---|---|
  | 208.5° | stable | 41 rad/s² | |
  | 215.4° | unstable | | 0.126 rad²/s² |
  | 222.1° | stable | 51 rad/s² | |
  | 247.6° | unstable | | 0.016 (noise level) |
  | 250.9° | stable | 21 rad/s² | |
  | 260.8° | unstable | | 0.024 (noise level) |
  | 263.9° | stable | 43 rad/s² | |

  The smooth table has only three zeros: 209.3° (stable, 5.4 rad/s²), 215.4° (unstable) and 220.6° (stable, 4.9 rad/s²).
  Given the caveat above, treat these stiffness values as specific to the big swing.
- **Potential** (per unit inertia; minimum 0 at 222°): U(150) = 2.40, U(290) = 2.54 rad²/s². The highest points in the valid
  range are its ends. The swing energy is E = 2.64 rad²/s² (U at the turning points, 145.3° and 293.3°).
- **Barrier.** acc is restoring and still growing in magnitude at both edges (+3.97 at 150°, −1.71 at 292° rad/s²). There is no
  flattening, so the barrier cannot be located or bounded from these data. For reference only: the 11-04 harmonic trap × 0.796
  has a 7.67 rad²/s² barrier (≈ 2.9 E) near 53° in the s1data alignment (assumed form, different alignment).
- **Direction.** Tables fitted separately for ω > 0 and ω < 0 rows differ by 0.09 rad/s² rms (max 0.29 at 260°), well below the
  0.3 node error. No direction dependence is seen (derived).

## Damping (derived)

- The turning points move inward by 1.2°/min at the top and 1.1°/min at the bottom (measured).
- The energy at the turning points falls linearly: dE/dt = −7.1e−4 rad²/s³. It is the same in the first and second halves
  (−6.9 and −6.5e−4), so there is no front-loading from residual field.
- **Viscous γ = 3.50e−4 ± 0.07e−4 s⁻¹** (statistical; the smooth U gives 3.49e−4). That is Q ≈ 4300, or 0.11 % of the energy per
  cycle.
- At peak speed the damping term is ~8e−4 rad/s², invisible in the acceleration fit. Its viscous form is assumed. Coulomb vs
  viscous was not tested.
- The upper turns lose energy at −6.3e−4 and the lower turns at −7.9e−4. The difference reflects the shape of U near the walls.

## Comparison with other traps (derived)

- **S1 canonical (198–234).** See the caveat above.
  - B1 MAIN − S1: rms 1.17 rad/s².
  - B1 smooth − S1: rms 0.55 rad/s².
  - Check: the MAIN method applied to the S1 free swing gives 0.54 rms against the canonical table, which is itself a joint
    field-on/off fit.
  - Potential relative to 208.6°, B1 / S1: U(198) 0.27/0.26, U(216) 0.13/0.08, U(234) 0.35/0.28 rad²/s².
- **11-04 trap × TRAP_S 0.796** (zero placed at 208.6°, the s1data convention; the 11-04 rest itself was 229.8°), over 150–290°:
  - rms difference 1.49 rad/s² to MAIN and 0.67 to smooth. The rms values themselves are MAIN 2.59, smooth 2.18 and old 2.36.
  - The best fit onto smooth is a +2.5° shift and ×0.87 (rms 0.60).
  - Its potential bowl tracks B1 closely: U(150) 2.65 vs 2.40, U(290) 2.56 vs 2.54.

## Use (recommendation; the choice is Molly's)

- **Replaying swings of ±56° to ±74°:** use B1 MAIN with γ = 3.5e−4 s⁻¹ (np.interp on the nodes).
- **Near rest and small swings (198–234):** use S1 canonical.
- **±20–40°:** no table is validated. This is where a brake passes on its way down.
- **Outside 150–290°:** not measured. np.interp holds the end node flat, which is not physical.

## Files

| file | what |
|---|---|
| `b1_trap.py` | the analysis |
| `b1_summary.txt` | full numeric output |
| `trap_b1.json` | `trap_nodes_deg`, `trap_acc_rad_s2` (MAIN), `trap_acc_smooth_rad_s2`, potentials, `valid_deg` [150, 290], `damping`, `equilibria`, `recommended_use`, validation, S1 replay, amplitude ladder, direction split, savgol 2° bin tables |
| `plots/b1_trap_acc.png` | acceleration vs angle with the fits, the savgol bins, S1 and the 11-04 trap; direction split |
| `plots/b1_potential.png` | potential |
| `plots/b1_validation.png` | replay vs measured and phase drift |
| `plots/b1_s1_and_synthetic.png` | S1 swing replays and the synthetic recovery test |

## Checks run / skipped

- **Run:**
  - synthetic recovery (two truths);
  - hold-out halves;
  - direction split;
  - damping split into first and second halves;
  - the S1 out-of-sample replay;
  - the amplitude ladder;
  - the implied tracking error.
- **Skipped:**
  - an independent tracker-linearity test (it needs a slow, known rotation through 198–234°);
  - a Coulomb-friction fit;
  - any field-residue correction for the first 20 s after the ramp. That window was excluded instead, and later start times
    were not scanned.
