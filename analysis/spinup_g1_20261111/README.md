# Gate G1 (spin-up): push map over 167–267°, and how the push scales with voltage, 2026-11-11

Analysis only, Mac. `python3 g1_pushmap.py` (~8 min) rewrites `pushmap_g1.json`, `g1_summary.txt` (every number below,
plus the per-pulse table) and `plots/` (gitignored: `git check-ignore` → `.gitignore:22:plots/`). Interpretations are Claude's
and are marked "(interpretation, not approved)". `make_g1_plan.py` and `g1_plan.csv` are the plan and were not changed.
Methods follow `../brake_b2_20261110/README.md`; its helpers are imported from `b2_pushmap.py`.

**Data.** Dropbox `Microspheres/TFINER/data/spinup/2026-11-11/g1/`:
- `brake_1794403551.csv`: step 1, i.e. the kick (A 2400 counts, 2 s) and the pump (31 writes);
- `vsteps_1794403575/`: step 2, i.e. 50 pulses of 0.25 s, 25 at 800 and 25 at 1600 counts (A/B/C at 800: 9/8/8; at 1600: 9/8/8). `out_dq.npz` covers both steps;
- `tracker/blob_live_gps1478438744.csv` and `tracker/output_basler_gps1478438744.csv`.

## What was done

- **Angles: live tracker used directly.** It runs the same `blob_core.Tracker` as B2, with the same centre (117.5, 165.1)
  and template.
  - Check (measured): I re-tracked frames 0–3999 from the AVI, which includes the fast pump motion. Max |live − re-track| is
    0.005°. The live CSV rounds to 0.01°, so re-tracking the whole video was not needed.
  - The time base is the camera clock mapped to host by the median offset, as in B2's `host_time_cam`. The host stamp has one
    1.5 s stall (frame ~14000), and the camera clock avoids it.
  - ncc: median 0.967, min 0.944. 919 blanked-source frames are kept, as in B1/B2.
- **Pulse timing (measured, with a refit).** `voltage_steps_score` found every landing. Its host→FE lower-envelope fit,
  however, put 3 early pulses 21–27 ms before their write.
  - I refitted the drift. It is now b = 1.001237 (score: 1.000916), chosen to minimise the spread of write→landing delays
    over the step-2 writes plus the kick.
  - The spread is now 124.7 ms, i.e. one 8 Hz tick, which is consistent.
  - **One pulse (21, A 800) lasted 0.375 s at OUT_DQ (3 ticks).** It is fitted with its measured length. All the others
    lasted 0.250 s.
  - Common field start: +15 ms after `landing_host` (B2: −1 ms). Per-pulse median: +20 ms. This offset is absorbed by the
    fit and is not a latency (same caveats as B2).
- **AC tails (derived; V² assumed for the correction).** The electrode voltage is the high-pass (τ = 5.57 s) of the landed
  levels. Pulses start on a residual tail of −57..0 counts.
  - The correction factor κ = ((V+δ)/V)² ranges from 0.86 to 1.00, and `a` is divided by it.
  - Effect on the ratio: 2.043 corrected, 2.060 with linear κ, 2.076 uncorrected.
- **Per pulse:** the B2 trajectory fit (RK4, ±1.5 s, joint-fit trap) gives θ and ω at mid-pulse and a = the mean field
  acceleration over the pulse.
  - The B2 joint second-difference estimate is also computed.
  - The rotor sweeps up to 20° per pulse here (B2: ~13°). So the model is always averaged over each pulse's sweep.
- **Uncertainty (derived):**
  - Null test (54 fake pulses in the post-run swing): rms **0.039 rad/s²**, mean +0.030 (B2: 0.020). This is a floor only.
    The post-run swing reaches ±36°, so the extremes 167–180° and 253–267° are not covered by any null.
  - In practice the per-pulse error is dominated by shape misfit. The fits use σ² = σ_null² + (S·σ_shape)², with σ_shape
    = 0.148 rad/s² per unit S (G1) and 0.128 (G1+B2), chosen so that χ²/ndof = 1.
  - Ranges come from a bootstrap over pulses (400 resamples).
  - Trajectory vs joint estimate: rms 0.19 rad/s², corr 0.93.

## Results

### 1. Voltage scaling (measured ratio; `plots/g1_scaling.png`)

| fit | S(1600)/S(800) | 68 % | 95 % |
|---|---|---|---|
| **G1, shared F (m 8+16), shifts free** | **2.04** | 1.65–2.64 | 1.44–3.96 |
| **G1 + B2 jointly (B2 = 800)** | **2.19** | 1.93–2.45 | 1.68–2.75 |
| G1, F and shifts fixed to B2 | 2.29 | 2.02–2.56 | – |
| G1, between-pulse trap / joint 2nd-difference a | 2.05 / 1.94 | – | – |

- Exponent n = log₂(ratio): **1.03 (G1; 68 % 0.73–1.40)** and 1.13 (G1+B2; 68 % 0.95–1.29).
- **The push is close to linear in V. V² (ratio 4) is excluded**: it lies outside the G1+B2 95 % range and at the edge of G1's.
- Per phase (68 %):

  | phase | ratio | 68 % range |
  |---|---|---|
  | A | 2.63 | 1.60–4.10 |
  | B | 1.65 | 1.15–2.60 |
  | C | 1.72 | 1.47–1.96 |

  All three are consistent with 2.
- **Independent check, the kick** (derived; `g1_summary.txt` §6):
  - I simulated the 2 s kick at 2400 counts (trap + S(2400)·F_A + AC droop) and compared the angle over −0.5..+2.0 s.
  - The best fit is **S(2400) ≈ 3.5–4** (rms 1.1–2.0°), for both F choices and both V² and signed-linear drive. That is
    n ≈ 1.14–1.26.
  - S = 9 (V²) misses by ≥ 12° rms.
  - This constrains the product S·F_A over 196–225°. A weaker local F would be needed to rescue V², and the pump below shows
    F(800) is not weaker over this swing.
  - The post-kick amplitude alone is threshold-like in S (3° at S = 3, 16–20° at S ≥ 4), so it is not used as a test.

### 2. Shape and 45° periodicity over 167–267° (derived; `plots/g1_pushmap.png`)

- **The shared shape and the shifts carry over.**
  - The G1+B2 joint fit gives P8 0.248, P16 0.537, span −0.75..+0.69 rad/s². B2's own F had P8 0.287, P16 0.529.
  - F_joint − F_B2 is 0.038 rad/s² rms over a period.
  - Shifts: s_B −15.4° (68 % −15.8..−14.9) and s_C +13.8° (+13.3..+14.4), against B2's −16.0 and +14.5. G1 alone gives
    −14.7 and +12.6.
- **Periodicity:**
  - Adding non-45°-periodic harmonics (m = 4, 12, 20) does not improve the fit (F-test p = 0.14).
  - Separate shapes for θ < 217° and θ ≥ 217° do not either (p = 0.14).
  - m = 24 helps a little (p = 0.03), as in B2.
- **Amplitude (observation, not robust).**
  - A linear amplitude gradient is significant on G1+B2 (κ = −0.36 per 50°, p < 0.001) and on G1 trajectory a (p = 0.006).
  - It is not significant with the joint 2nd-difference a (p = 0.16) or with the 800-count pulses only (p = 0.17).
  - B2's amplitude relative to G1 at 800: 1.13 when left free.
  - A possible ~10–30 % fall-off toward high θ is therefore not established.
- G1 pulses against B2's F: rms residual 0.10 rad/s² inside 187–238° and 0.27 outside (1600 pulses unscaled).
- Fast pulses (sweep ≥ 8°) regress on B2 F with slopes 0.53±0.24 (800) and 2.39±0.16 (1600). Slow pulses give 0.98±0.33 and
  2.25±0.44. The fast-800 slope is low; this is unexplained and is an observation only.
- **Pump check (measured vs derived; `plots/g1_pump_check.png`):**
  - 31 writes produced 41 commanded level changes. 39 landed. 2 B writes were superseded within one tick.
  - The swing went from ±18.3° to ±45.1°.
  - E = ω²/2 + U(θ) rose **0.318 → 1.339 rad²/s² (+1.02)**.
  - The work predicted along the measured path, with the map, is **+0.78 to +0.81**, i.e. 76–79 %. The energy rises in the
    same steps as the writes.
  - A forward simulation gives ±33–36° against the 45° measured.
  - So the map under-predicts the pump by ~25 %, which is about the size of σ_shape. Observation, cause not identified. The
    result does not depend on n, because the pump ran at 800 counts only.

### 3. Trap (derived; `plots/g1_trap.png`, table in JSON `trap`)

- Three G1 traps were fitted: joint (run with pulse columns), between-pulse (run, pulses masked) and free (post-run, 180–253°).
- Over 192–236° they agree to 0.03 and 0.13 rad/s² rms.
- Post-run swing replay (period 3.367 s, ±36.4° about 216.4°):

  | trap | period error | rms, first 10 s |
  |---|---|---|
  | joint | −0.06 % | 0.37° |
  | between-pulse | −0.17 % | 0.61° |
  | free | +0.16 % | 0.31° |

- 167–180° and 253–267° are visited only during the pulse run. There the joint and between-pulse traps differ by ≤ 0.32
  rad/s². Re-fitting the outer pulses with the other trap moves a by 0.011 rms.
- **Comparison with B1/B2 over 186–240°:**

  | trap | straight-line zero | slope k (rad/s² per rad) | ripple rms (rad/s²) |
  |---|---|---|---|
  | G1 | 212.5° | 4.37 | 0.91 |
  | B2 joint | 212.8° | 4.40 | 0.79 |
  | B2 free | 212.4° | 4.51 | 0.79 |
  | B1 MAIN | 212.2° | 4.90 | 1.06 |
  | B1 smooth | 212.4° | 4.84 | 0.40 |

  - rms vs the G1 joint trap (192–236°): B2 joint 0.56, B2 free 0.44, B1 MAIN 0.80, B1 smooth 0.78 rad/s².
- The trap is a weak restoring slope plus a ~±1–2 rad/s² ripple. The ripple differs between days at the 0.4–0.8 rad/s²
  level, as B2 found for B1.
- |trap| reaches 3.9 rad/s² at 176° and 256°.

### 4. Carry (derived; `plots/g1_carry.png`, JSON `carry`)

**Assumptions:**
- one electrode at a time, chosen as the best of A/B/C at each angle;
- slow quasi-static carry, so dynamics and damping are neglected;
- the G1+B2 F and shifts;
- a ≈ (V/800)ⁿ·F, extrapolated beyond 1600 counts;
- the 12800-count V_LIMIT.

**Results:**
- At 800 counts the best single phase pushes forward by only 0.05 rad/s² at two dips (210.5°, 255.5°), where the three
  shifted copies of F cross. Elsewhere it gives ~0.3–0.7.
- Strict criterion (beat the trap at every angle):

  | direction | S needed | worst angle | bootstrap 68 % |
  |---|---|---|---|
  | forward | 62 | 255.5° | 27–189 |
  | backward | 31 | 178.5° | 24–49 |

  - Forward, in counts: ~50 000 at n = 1, ~19 000 at n = 1.29, and 6300 only if n = 2. So with the measured scaling it is
    **not reachable at 12800 counts**.
- **Coverage at 12800 counts:**

  | n | S at 12800 | forward coverage of 167–267° | backward coverage |
  |---|---|---|---|
  | 0.95 | 14 | 97 % | 98 % |
  | 1.13 | 23 | 99 % | 99 % |
  | 1.29 | 36 | 100 % (fails only at 255.5°) | 100 % |

  At n ≈ 1, the forward push fails only in narrow windows at the envelope dips, inside 210–256°.
- (derived) Because the push is ~linear in V, two phases energised together should superpose and fill those dips. This is
  untested.
- **The amplifier is AC-coupled (τ 5.57 s).** A carry cannot hold a static offset: each phase step decays by e⁻¹ in 5.6 s.
  Carry steps must be ≪ 5.6 s apart, or be re-stepped.
- Counts → volts were not re-measured here.

### Swing through the run (measured; `plots/g1_angle_vs_time.png`)

| segment | half-amplitude | centre |
|---|---|---|
| pre-kick | 0.7° | 208.6° |
| after kick | 18.2° | 215.9° |
| step 2 | 34–50° | – |
| post-run | 36.4° | 216.4° |

- Tracked angle range: 167.4–267.1°.
- Summed ω·Δω over the 50 pulses: −0.24 rad²/s².

## Caveats

- The shape misfit (σ_shape ≈ 0.13–0.15 per unit S) is 3–4× the null floor. The model a = S·F(θ − s_q) with m = 8+16 does
  not capture everything (as in B2, χ² was ~2.5× ndof).
- **The ratio's width is set by this misfit, not by tracking noise.**
- The slow pulses at the extremes carry most of the weight. There the trap is constrained only by run data, but the trap
  systematic on a is small (0.011 rad/s²).
- n is measured over 800–1600 counts only, plus the kick constraint at 2400. Extrapolating to 12800 is assumed.
- The live CSV's 0.01° rounding is negligible next to these errors.

## Files

- `g1_pushmap.py`: the analysis.
- `pushmap_g1.json`: per-pulse table, scaling fits and bootstraps, shape fits and tests, trap tables, pump/kick checks, carry.
- `g1_summary.txt`
- Plots (in `plots/`): `g1_angle_vs_time.png`, `g1_pushmap.png`, `g1_scaling.png`, `g1_trap.png`, `g1_pump_check.png`,
  `g1_carry.png`, `g1_null_test.png`.
- Scratch, not needed to rerun: `/private/tmp/claude-501/-Users-mollywatts/fd37af79-d00b-4dd9-9b6f-ae64bcbeb22b/scratchpad/g1_frames_0_4000.u8`
  (re-track check frames) and `/private/tmp/claude-501/-Users-mollywatts/fd37af79-d00b-4dd9-9b6f-ae64bcbeb22b/scratchpad/g1/` (logs, check scripts).
