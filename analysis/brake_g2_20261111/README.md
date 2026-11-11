# Gate G2: brake from a large swing, G1 map, DC-coupled amp. Simulation (2026-11-11, Mac only)

Plan: `lab_utils/SPINUP_PLAN.md` (G2). Rule for feedback runs: DECISIONS 2026-11-10 (measured trap and push map, sim
check, live safety). Amp now DC-coupled: DECISIONS 2026-11-11.

**Status:** the sim passes at 800 counts. Nothing has run live. Interpretations are **not approved**.

## Code (branch `voltage-steps`, uncommitted)

- `brake_offsets.py --map g1` uses the G1+B2 joint push shape and shifts and the G1 `joint_run` trap over 172–262°.
- With that map the safe range defaults to 176–258°. `--map b2` (the default) is unchanged.
- The selftest passes.

## Sim (`g2_sim.py`, which calls the live `choose()`; derived)

- Start: ±40° about 216.4°, the G1 post-run swing centre.
- Scan:
  - trap table `joint_run` or `free_post_run`, ×0.9, 1.0, 1.1;
  - push ×0.75, 1.0, 1.25 (covers the DC path's unmeasured V/count);
  - f, the V² share of the push: 0, 0.1, 0.2;
  - landing delay C: 0, 30, 60 ms;
  - 2 seeds;
  - 800 and 1600 counts.
- DC electrode model: the level equals the command, with no decay (assumed).
- Pass: below ±10° within 120 s, never above 1.2× the start, never outside 176–258°.

| level | cells passed | median time to < 10° | worst final |
|---|---|---|---|
| 800 | 324/324 | 8 s | 0.8° |
| 1600 | 323/324 | 5–6 s | 12.2° (trap ×0.9, push ×1.25, f 0.2, C 60 ms) |

Full table: `g2_summary.md`. Traces: `plots/g2_traces.png`. Cells: `g2_cells.json`.

## Range note (derived)

The trusted map spans 172–262°. About the 216° swing centre, that allows at most about ±44°. G2 therefore targets about
±36–40° (pump to 36 leaves margin), not the ±60° first written in the plan. Larger swings need the trap measured further
out (G3).
