# Spin-up by pumping over the top, holding a set mean rate. Simulation (2026-11-11, Mac only)

Rule amended for this run (DECISIONS 2026-11-11): the run may go past the measured trap. Safety is a time limit, a speed cap and
the tracker checks. Target: a set mean rate per spin-up, 0.5 Hz (0.75 Hz if reachable). Interpretations are **not approved**.

## Code (branch `voltage-steps`, uncommitted)

`brake_offsets.py run --map g1 --spin-to HZ --dir ±1` uses `choose_spin()`. Every 125 ms it fits the last 8 frames
(quadratic) and uses the fit's own acceleration to predict to the middle of the hold. It needs no trap model. It then acts
only where the rotor is slower than `--w-push-max` (90°/s), because 8 updates/s cannot commutate faster:

- **mean rate below target:** push along `--dir`, only while moving that way. That pumps the swing over the top in the
  chosen direction, then adds energy near the top of each turn.
- **mean rate above target × 1.05:** brake.

The mean rate is taken over the last full turn. The angle is now unwrapped, so the code works across 360°; it is a no-op
for swings. Safety: `--duration`; field off for good above `--w-cap` (500°/s); stale or low-ncc frames. There is no safe
angle range. The selftest passes.

## Sim (`spin_sim.py`, which calls the live `choose_spin()`; derived)

- **Plant:** the carry-sim plant made conservative. The stitched trap table is shifted by its mean over a turn, since a
  first version gained energy with the field off.
- **Scan:**
  - trap measured inside, assumed sinusoid outside ×1, ×1.5, ×2 (plus inside ×1.12);
  - f 0, 0.1, 0.2; push ×0.75, 1, 1.25;
  - C 15 or 60 ms;
  - both directions, 5 seeds;
  - DC electrodes;
  - 600 s from rest.

| case | first turn along dir | reaches target | turns within ±5 % (last 300 s) |
|---|---|---|---|
| 0.5 Hz, 1600 counts, trap ×1 / ×1.12 | 72/72 | 72/72 | 95–97 % (20/36, 25/36 cells all within) |
| 0.5 Hz, 1600 counts, trap ×1.5 / ×2 | 69/72 | yes, but overshoots to ~0.54 Hz | ~35 % |
| 0.5 Hz, 800 counts, nominal | 4/4 | 4/4 (~200 s) | 100 % |
| 0.5 Hz, 3200 counts, nominal | 4/4 | 4/4 (~35 s) | 94 % |
| 0.75 Hz, any level, push limit 60–240°/s | – | **0/152** (tops out at 0.50–0.70 Hz) | – |

- **Timing (1600 counts):** first turn after ~90–170 s (median), or ~310 s with the trap ×2. Peak speed 270–360°/s,
  under the 500°/s cap. No aborts.
- **Spin-down:** a target of ~0 after 300 s at 0.5 Hz stops the rotation in all 4 cases tried, leaving a ±80–120° swing
  about ~217°. That is outside the brake's map, and it decays slowly.
- **0.75 Hz and 1 Hz ±1 %** need faster updates (USB DAC or oscillator route), as derived beforehand.

Files: `spin_summary.md`, `spin_cells.json`, `plots/spin_traces.png`.

## Live S1 and the free coast (2026-11-11 night; measured unless marked)

- **S1** (`--level 1600 --spin-to 0.5 --dir 1`, FE 1478503576–921):
  - first full turn along +1 at 40 s;
  - ~130 turns at 0.43–0.47 Hz (video timing: 10 turns in 1090 frames = 0.459 Hz);
  - 0.5 Hz not reached, a ceiling with pushes only below 90°/s;
  - stopped at 338 s by a spurious speed-cap trip (host-timestamp jitter; fixed in 18e3e0a).
- **Free coast, field off:** the mean rate per minute fell 0.427 → 0.267 Hz over 11 min, faster towards the end. The last
  full turn (0.20 Hz) came at +681 s, then the rotor fell back into a swing (±130 → ±100° over the next ~30 min).
- **Trap over the full circle and damping from the coast** (`coast_trap.py`, `coast_trap.json`, `plots/coast_trap.png`;
  derived):
  - **Method:** fit ½ω² = E(t) − U(θ) to 31 238 frames of the rotating coast, with U as a Fourier series to m = 24 and E
    as a quartic in time.
  - **Fit residual:** 0.04 rad²/s².
  - **Potential:** minimum at 219.5°, barrier at **60°**, height **6.5 rad²/s²** (per unit I). The carry sim had assumed
    8.5 at 37° (k-sinusoid).
  - **Consistency check:** the coast energy fell from 8.0 to 6.52 by the end of the fit window, matching the barrier
    (6.50) just as the rotor stopped clearing it.
  - **Trap a = −dU/dθ:** shows the m = 8/16 ripple all the way round (±2–4 rad/s²). Inside 180–254° it follows G1's table
    in shape; rms difference 1.6 rad/s², with both carrying ripple. High orders may be partly overfit.
  - **Damping:** dE/dt = −c ω² gives **c = 3.8e−4 /s**, within ~10 % of B1's 3.5e−4 (B1's γ is this viscous coefficient,
    derived from its 0.11 %-per-cycle figure).
- **Against September (observation, cause not identified):** the September spindown gave τ_mech = 79.8 min (DECISIONS
  drag row), i.e. c = 1/τ = 2.1e−4 /s. Tonight's coast gives τ = 1/c = 44 min, and B1 gave 48 min: damping is now ~1.8×
  September's.
  - What changed since September (Molly, 2026-11-11): the board was already installed then, but not grounded.
  - Since then: the beam change; the tilt-stage rebuild (10-15 to 10-26: shims, screw stands removed, PCB and magnet
    centred); board grounding (10-27).
  - The speeds also differ: September ran faster, tonight 0.3–0.45 Hz with the trap in the fit.
  - A spindown on this setup at September's speed would separate speed dependence from setup changes.
- **S3** (2026-11-12, `--dir -1 --ncc-min 0.70`): first full turn along −1 at 25.8 s, starting from a ±98° swing; 212 turns;
  0.45–0.49 Hz, with a 200–480 s hold mean of 0.470 Hz (0.447–0.491). The first attempt stopped on the tracker floor (0.8),
  at a match-quality dip at 320–330°.
- **S4 spin-down:** the rotation stopped 37 s after braking began, and the swing was then braked to ±42° by 300 s.
- **Proposed directive bookkeeping (Molly's call):** both directions spun up from a swing or from rest within ~30–40 s to
  the first turn and ~1.5 min to a ~0.45–0.47 Hz plateau, and both stopped on command. 0.5 Hz was not reached by the
  per-turn measure, and the hold within ±5 % of 0.5 Hz was 0 % (S1) and 35 % (S3).

## Sim with the measured trap (2026-11-12; `spin_sim_coast.py`, `spin_coast_summary.md`; derived)

- **Speed dependence of the trap** (`coast_speed_check.py`): the coast's fast half (0.40 Hz) and slow half (0.31 Hz) give
  the same barrier (6.52 vs 6.51 at 60°) and the same minimum (220°). The trap shape differs by 0.19 rad/s² rms, against a
  turn-to-turn noise of 0.04, i.e. ~5 % of the peak; it may partly come from the fit. The swinging regime (≲0.1 Hz) is not
  covered by the coast.
- **Validation:** with the coast trap, the sim at a 90°/s push limit and 1600 counts gives the first turn at 45 s and a
  plateau of 0.44 Hz (0.41–0.47). Live: 40 s / 26 s, and 0.43–0.47 Hz.
- **Governor deadband:** now centred on the target (voltage-steps, after 18e3e0a). The old band (target to +5 %) sat the
  mean above target.
- **Scan:** trap ×0.9/1/1.1; push (f, scale) = (0.1, 1), (0, 0.75), (0.2, 1.25); C 15/60 ms; both directions.

| target | level | push limit | cells passed | median t to first turn / to target | turns within ±5 % |
|---|---|---|---|---|---|
| 0.5 Hz | 800 | 90°/s | 0/36 | 120 s / – (plateau 0.435) | 0 % |
| 0.5 Hz | 800 | **120°/s** | **28/36** | 91 s / 133 s | **94 %** |
| 0.5 Hz | 1600 | **120°/s** | 21/36 | 42 s / 59 s | 87 % |
| 0.5 Hz | 800–1600 | 150–240°/s | 0–17/36 | faster | overshoots (mean 0.53–0.63) |
| 0.75 Hz | any | 90–240°/s | ≤1/36 | – | – |

- **Pushing faster than ~120°/s** overshoots: at 8 updates/s the extra pushes add energy that the governor cannot take
  back out.
- **0.75 Hz** is not reachable on this route (needs faster updates).
- **Within ±1 %** of 0.5 Hz: about 20–50 % of turns at the best settings.
