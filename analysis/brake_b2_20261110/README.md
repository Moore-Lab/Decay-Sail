# Gate B2 (braking plan): push map from the pulse run, 2026-11-10

Analysis only, Mac. `python3 b2_pushmap.py` (~5 min) rewrites `pushmap_b2.json`, `b2_summary.txt` (every number below) and
`plots/` (gitignored). `python3 b2_pushmap.py --track` re-tracks the video first. Interpretations are Claude's and are marked
"(interpretation, not approved)". `make_b2_plan.py` and `b2_plan.csv` are the plan and were not changed.

**Data.** Dropbox `Microspheres/TFINER/data/brake/2026-11-10/b2/`: `vsteps_1794363701/` (45 pulses, 15 each on V2 = A,
V4 = B, V3 = C; offset 0 → 800 counts for 0.25 s) and `video/output_basler_gps1478398905.avi` (50 fps, 16503 frames, 0 dropped).

## What was done

- **Tracking.** `../detent_20261110/track_detent.py` was run unchanged → `rotor_angle_b2.csv`, using the `host_time_cam` column.
  Frames were decoded to the scratchpad. ncc median 0.966, min 0.953. 668 frames (4 %) come from the `blanked` source and are
  kept, as in B1. The board registration gives centre (119.4, 164.4) against the (117.5, 165.1) used. Angle range
  187.0–238.8°.
- **Pulse timing (measured).** `voltage_steps_score.load/score` reports that all 90 writes landed. Every pulse lasted 0.250 s at
  OUT_DQ (two 8 Hz ticks). The write → landing delay is 0–140 ms relative to the earliest pulse, set by the 8 Hz intake grid. Each
  landing is put on the host clock as `landing_host` = write + relative delay.
- **Field model (assumed).** Torque ∝ V², as in CLAUDE.md. Each pulse is a rectangle with the AC droop exp(−2t/5.57 s), starting
  at `landing_host` + d.
- **Trap.** Two traps were fitted with the B1 MAIN method (position second differences, 2° nodes, 184–242°, lags 3–20
  frames):
  1. jointly with 45 free pulse accelerations on the run data;
  2. on the post-run free swing alone (t ≥ last write + 20 s, field off).
- **Per pulse.** A trajectory fit (RK4) with the joint trap, free (θ, ω) at mid-pulse, field acceleration a, and optionally the
  delay d. The window is ±1.5 s, trimmed to stay clear of neighbouring pulses. a = the mean field acceleration over the
  pulse, and Δω = 0.25 s · a.
- **Uncertainty (derived).** Two estimates:
  - Null test: the same estimator at 39 fake pulse times in the post-run free swing, with the trap fitted on the run only.
    rms **0.020 rad/s²**.
  - Method spread: trajectory-fit a vs joint-fit a, rms difference **0.051 rad/s²**, correlation 0.990.
  The per-pulse error is between the two. The 0.051 is used for χ².

## Results

### Trap (derived; `plots/b2_delay_and_trap.png`)

Replay of the post-run free swing (period 2.929 s measured, 191.8–237.0°), starting from the first turning point:

| trap | period error | rms, first 10 s |
|---|---|---|
| B2 joint (run) | −0.07 % | 0.42° |
| B2 free swing | −0.18 % | 0.31° |
| B1 MAIN | +7.5 % | 10.9° |
| B1 smooth | −1.4 % | 5.3° |
| S1 canonical (valid only 198–234°) | +3.0 % | 6.1° |

The B1 and S1 traps do not reproduce this swing. The trap had to be refitted from this video. **For the braking plan:** the
B1 trap is not usable at this amplitude and date (+7.5 % period, 11° rms after 10 s). The joint trap and the free trap
differ by 0.29 rad/s² rms over 192–236°.

### Push per pulse (measured; table in `pushmap_b2.json` → `pulses`, also in `b2_summary.txt`)

- |a| reaches up to 0.78 rad/s². Signs are mixed.
- Δω reaches up to 0.19 rad/s, i.e. 11°/s.
- Trajectory fit and joint fit agree to 0.05 rad/s² rms.

### Which harmonic (derived; `plots/b2_pushmap.png`)

Per-phase fits of a = Σ_m P_m cos(mθ − φ_m) + c, using the pulse-averaged basis. The rotor sweeps up to ~13° during a pulse,
so each basis function is averaged over the pulse.

| m | rms residual (rad/s²) | χ²/ndof at σ = 0.051 |
|---|---|---|
| 4 | 0.258 | 1152/36 |
| 8 | 0.268 | 1246/36 |
| 16 | 0.202 | 711/36 |
| 24 | 0.306 | 1630/36 |
| 4+8 | 0.130 | 294/30 |
| **8+16** | **0.065** | **74/30** |
| 8+16+24 | 0.052 | 46/24 |

- **No single harmonic fits.** m = 16 is the best single one, and it still leaves 0.20 rad/s² rms.
- **m = 8 and m = 16 together fit**, to 0.065 rad/s².
- Per phase, the fitted amplitudes are:

  | phase | P8 (rad/s²) | P16 (rad/s²) |
  |---|---|---|
  | A | 0.29 | 0.50 |
  | B | 0.26 | 0.53 |
  | C | 0.32 | 0.53 |

  The three phases are equally strong, within ~10 %. Adding m = 24 helps a little.
- (derived) A single phase's electrode set is 8-fold, so by symmetry it couples to every multiple of 8. Seeing m = 8 here is
  therefore expected from geometry alone. It is neither evidence for nor against the STATUS net-charge hypothesis, and the
  scaling with V was not tested (one level only).
- The angle coverage is 187–238° (≈ 1.1 periods of 45°), so the decomposition beyond m = 8 and 16 is not well constrained.

### Phase spacing and order (derived; `plots/b2_shared_shape.png`)

- **Shared-shape test.** One 45°-periodic shape F (c + m = 8 + m = 16) fits all three phases with a(θ) = F(θ − s_q) and s_A = 0.
  The best fit is **s_B = −16.0°, s_C = +14.5° mechanical** (68 % region: s_B −16.0 to −15.5, s_C +14.5 to +15.0).
  - The residual is 0.072 rad/s², against 0.065 for independent per-phase fits that have 8 more parameters.
  - Fixed at (−15, +15) the residual is 0.076. Fixed at (+15, −15) it is 0.342, and with no shift it is 0.334.
- Since s_C = +14.5° ≡ −30.5° (mod 45°), the pattern steps by **−15° mechanical per step A → B → C**. That is the 360/24 sector
  pitch.
- **In electrical degrees**, from the per-phase (8, 16) fit:

  | harmonic | φ_B − φ_A | φ_C − φ_B | φ_A − φ_C | per step |
  |---|---|---|---|---|
  | m = 16 | 117° | 121° | 122° | ≈ +120° |
  | m = 8 | 210° | 261° | 248° | expected 240° (= −120°) for a −15° step; rougher |

- **Shape amplitude.** F spans −0.74 to +0.74 rad/s² (rms 0.43). Its components are P8 0.29 and P16 0.53, with constant
  −0.006 (no net push).
- (interpretation, not approved) Each step A → B → C moves the push pattern 15° toward lower tracked angle. So the sequence
  A → B → C would drag the rotor toward decreasing θ, and A → C → B toward increasing θ. The sign convention of the tracked
  angle against the drive has not been checked here.

### Delay (measured: relative timing only; `plots/b2_delay_and_trap.png`)

- **The field follows the 8 Hz OUT_DQ landing, not the write** (measured):
  - The joint-fit χ² scan puts the common field start at −1 ms from `landing_host`.
  - Per-pulse free fits (40 pulses with |a| > 3σ) give a median of +1 ms (IQR −1 to +5, bootstrap error of the median 1.1 ms).
  - Timed from the write instead, the per-pulse spread is 39 ms rather than 10 ms, and χ² is 0.55 % worse.
  - The field start does not correlate with the relative landing delay (r = +0.01).
- So the write → field delay **varies by the grid wait** (0–140 ms in this run).
- **The absolute write → field latency is not determined here.**
  - `landing_host` assumes the earliest pulse landed at its write time.
  - `host_time_cam` is built from frame-arrival stamps, so video events appear late by exposure + transfer (unmeasured;
    ≥ ~15 ms is plausible).
  - Taken at face value, these assumptions put the field start *before* the write for the earliest pulse, which is not
    physical. So the assumed chain is inconsistent by at least the camera latency, and the −1 ms is not a latency.
  - It is also assumed that the camera and vsteps host clocks are the same PC clock.
- The relative landing delays span 0–140 ms, more than the 125 ms grid period, and grow with time through the run. That points
  to a small drift misfit in the single-block host → FE mapping. It is harmless for the relative result above.

### AC tail (derived)

- **If the push were linear in V**, the −4.4 % reversed tail (τ 5.57 s) times the push map shifts each a by 0.033 rad/s² rms
  (max 0.095). It moves the (8, 16) fit coefficients by ≤ 0.02 rad/s² and ≤ 10°.
- **With V²** the tail is 0.2 % and negligible.
- The headline numbers above use V².

### Swing amplitude: B1's random-walk concern (measured; `plots/b2_angle_vs_time.png`, lower panel)

| segment | half-amplitude | centre |
|---|---|---|
| pre-run | 20.43° (±0.03) | 215.3° |
| run, first 30 s | 24.2° | – |
| run, last 30 s | 20.9° | – |
| post-run | 22.63° | 214.4° |

- The run walked the amplitude between **16.6° and 25.9°**, and the net change was +2.2°.
- 53 % of pulses added energy. The summed ω·Δω is +0.17 rad²/s², with 0.051 rms per pulse.
- The swing never left 187–239°.

## Caveats

- **The χ² of the best model is still ~2.5× ndof at σ = 0.051**, so there is unmodelled structure at ~0.05 rad/s².
  - Same-phase pairs at nearly the same mid-angle can differ a lot because a(θ) is steep (up to ~0.15 rad/s² per degree).
    Example: A pulses 24 and 43 (−0.24 vs +0.11) sweep 196.8–201.5° and 195.1–199.5°. Their (8, 16) model residuals are +0.03
    and +0.14.
  - Phase C residuals are +0.06 in the first half and −0.06 in the second. Whether that is a time dependence is an observation
    only.
- Example fits (`plots/b2_example_pulses.png`) leave residuals of 0.1–0.4° that are structured over ±1.5 s, which is trap
  mismatch. Per-pulse rms ranges from 0.04° to 0.42°.
- The fit covariance of the delay is unreliable (degenerate Jacobian). Per-pulse delays are quoted only as a distribution.
- **The push map is for 800 counts (~9.9 V) only.** The scaling with V is not tested here.
- Only 187–238° was sampled. The map outside that range is the fitted periodic extrapolation.

## Files

- `b2_pushmap.py`: the analysis.
- `rotor_angle_b2.csv`: per-frame angle.
- `pushmap_b2.json`: per-phase fits for m = 4/8/16, combinations, shared shape, global variant, tail test, trap tables and the
  per-pulse table.
- `b2_summary.txt`
- Plots:
  - `plots/b2_angle_vs_time.png`
  - `plots/b2_pushmap.png`
  - `plots/b2_shared_shape.png`
  - `plots/b2_example_pulses.png`
  - `plots/b2_delay_and_trap.png`
  - `plots/b2_null_test.png`
- Decoded frames: `/private/tmp/claude-501/-Users-mollywatts/fd37af79-d00b-4dd9-9b6f-ae64bcbeb22b/scratchpad/b2_frames.u8` (1.2 GB).
