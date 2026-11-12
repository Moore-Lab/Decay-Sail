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
