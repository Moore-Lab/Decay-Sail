# F3 step 2 and model checks, 2026-11-10 (Mac, analysis only)

Interpretations are Claude's and marked "(interpretation, not approved)".

- **Step-2 scan** (`f3_step2.py` on branch `feedback-drive`; `step2_summary.md`, `step2_cells.json`): braking fixes in the 11-04
  measured-model simulator, offset route, trap rescaled to the 0.379 Hz post-S1 swing, scanned over extra delay 0–100 ms,
  tick phase, both couplings, trap and coupling strength ×0.75–1.25. Start A = brake 1's state, B = the ±17.5° post-S1 swing.
  - No fix passed every cell. Best for B: half amplitude, brake_wmin 10 deg/s, horizon fixed for 30 ms extra delay: 135/144,
    the misses 5.1–8.1° at 60–100 ms; never over the top. The live brake-1 settings put B over the top in 13/144 cells.
  - **Superseded as a basis for runs:** the simulator's trap and coupling do not describe the current setup (below). Molly
    amended the rule on 2026-11-10 (DECISIONS): feedback runs need a measured trap and push map, a simulator check with them,
    and live safety limits.
- **Delay from S1's first hold step** (`delay_fit.py`): motion onset 4 ± 12 ms after write + its measured intake wait
  (measured, one clean edge). The full replay fit failed (the 11-04 model swings at 0.38 Hz where the rotor swung at ~0.65 Hz).
- **Refit on S1** (`refit/`, README there): the trap near rest is much stiffer than the 11-04 fit (17.9 rad/s² near 208.6°,
  0.67 Hz small swing); the coupling refit is inconsistent between blocks; delay not determined (−48…+103 ms equally good).
- Trap over the full ±72° swing: `analysis/brake_b1_20261110/`.
