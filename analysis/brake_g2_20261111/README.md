# Gate G2: brake from a large swing, G1 map, DC-coupled amp. Simulation (2026-11-11, Mac only)

Plan: `lab_utils/SPINUP_PLAN.md` (G2). Rule for feedback runs: DECISIONS 2026-11-10 (measured trap and push map, sim
check, live safety). Amp now DC-coupled: DECISIONS 2026-11-11.

**Status:** the sim passes at 800 counts, and the live runs (2026-11-11 evening) met the proposed criteria in 3 of 3. The gate pass is
Molly's call. Interpretations are **not approved**.

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

## Live (2026-11-11 evening, worker2, Molly's go; measured)

Each repeat: kick A 2400 → `--pump-to`, then `brake_offsets.py run --map g1 --level 800 --duration 120 --enable-outputs --live`.
Data in Dropbox `spinup/2026-11-11/g2/` (brake CSVs, consoles, GPS pairs, `tracker_1/`, `tracker_2/`, `tracker_2b/`).

| repeat | pump target | swing at brake start | first peak < 10° | final | safe range | stop |
|---|---|---|---|---|---|---|
| 1 | 36 | ±40.1 (peaks 256.9 / 176.6) | 3.3 s | ±0.6° | 176–258 | duration |
| 2 | 32 | ±40.4 (about 216.8) | 9.1 s | ±1.2° | **173–261** | duration |
| 3 | 26 | ±35.4 (about 215.9) | 6.2 s | ±0.2° | 176–258 | duration |

The swing never exceeded its start in any of the three brakes. Molly watched repeat 2 live and noted that it braked well.

**Figures:**
- `plots/g2_live_brakes.png` (`g2_live_plot.py`): angle against time for the three brakes, with the commanded electrode.
- Clips (`g2_clip.py`, Dropbox `spinup/2026-11-11/g2/clips/`): `brake_1794446406_clip.mp4` (repeat 2) and `brake_1794446727_clip.mp4` (repeat 3), each −5 to +25 s about the brake start, real time, with the angle and active electrode drawn on.

**Observations (not explained):**
- **Repeat 2's first brake** started at ±42.4 (peaks 259.3 / 174.5). It tripped the safe range (175.7) after 0.14 s. The rerun
  used `--safe 173,261` (Molly's go), after the free swing had shrunk to ±40.4.
- **The pump overshoots its target** by +4 to +10°, because its stop test reads a trailing window.
- **The kick is not a push measure.** The same 2400-count kick pulled the rotor to the same angle (~195°) in every repeat.
  The free swing after release was 18.8 / 5.5 / ~0°, following where the rotor was in its oscillation about the pulled
  position at release. That is consistent with the measurements but not proven.
- **Pump rate as the push check:** dA/dt 6.3 and 5.7 °/s in repeats 1 and 2. Repeat 3 took 4.6 s from ±1.2.
- **Repeat 2's brake was slower,** with ~4 s of +14..+21° peaks before the swing collapsed.
- **Large swings centre at ~216°,** not at the 208.4° rest.
