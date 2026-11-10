# Voltage steps S1, 2026-11-10: outputs on, scope on the amplifier outputs

Interpretations are Claude's and marked "(interpretation, not approved)". Everything else is measured or derived as labelled.

- **Plan and code:** `lab_utils/VOLTAGE_STEPS_HANDOFF.md` (S1, step 6); branch `voltage-steps` at 70cf217:
  `voltage_steps.py run --preset s1`, scored with `voltage_steps_s1.py` (which runs `voltage_steps_score.py` first).
- **Run:** worker2, outputs **on**, Molly's typed go, Molly not at the bench (scope set remotely). FE GPS 1478396766–1478396867
  (host 1794345310.15–1794345406.80). 293/293 writes read back correctly; at the end offsets 0, outputs off, TRAMP 1.0.
- **Changed from the runbook, because the scope could not be set at the bench:**
  - levels **1200 counts** for every block (planned 3200 / 1600). With 1x BNC the RTB2004 refused 20 V/div
    (−222 "Data out of range"), so the screen was 5 V/div, ±20 V (Molly chose the lower level);
  - scope **20 s/div**, offsets 0, **single acquisition** (SING) as in W2. The scope's trigger was not checked
    (Molly: possibly on the LES, low level). It completed, and the run sits at scope t −11 to +90 s. Plain STOP/read at
    these timebases returned a stale record (four reads and a marker test, 15:52–16:05; files in `scopetest/`).
- **Data:** Dropbox `Microspheres/TFINER/data/voltage_steps/2026-11-10/vsteps_1794345310/` (writes, OUT_DQ FE
  1478396741–1478396895, OUTMON with EPICS timestamps, `scope_1794345444_s1.npz/.json`, console logs, GPS pairs;
  `video/output_basler_gps1478380390.avi`, 15 ms exposure, 21000 frames in 420 s, 0 dropped, per-frame CSV).
- **Figures and tables:** `python3 lab_utils/voltage_steps_s1.py <data dir> --outdir analysis/voltage_steps_20261110_s1/plots`
  → `s1_summary.md`, `s1_block00_hold.png` (holds vs the AC-coupling model), `s1_edges.png` (electrode edge vs OUT_DQ),
  `s1_gain.png`, `s1_block0[1-3]_*.png`, plus the OUT_DQ plots (gitignored).

## Measured

- **Every front-end update reached the electrodes.** All 722 OUT_DQ landings in the scope record were seen at the
  amplifier outputs, including the 8/s block (241 steps, all landed in OUT_DQ). The scorer flags one 8/s V2 "miss": a
  20-count (0.24 V) change, below the ~0.05 V rms noise times the 50 % threshold, so it is not a lost update.
- **The three electrodes change together at the amplifier outputs:** within multi-electrode steps the 50 % crossings agree
  to median 0.00 ms, p95 0.05 ms, max 0.53 ms (601 channel edges).
- **Volts per count, offset path** (1200-count level):

  | electrode | first instant of a step (median per edge) | whole-record fit (slow part) | τ (s) | τ W2 11-03 (s) |
  |---|---|---|---|---|
  | V2 | 0.01236 | 0.01214 | 5.58 | 5.69 |
  | V4 | 0.01271 | 0.01242 | 5.57 | 5.43 |
  | V3 | 0.01264 | 0.01237 | 5.57 | 5.56 |

  The first-instant values sit in the AWG-path range measured 11-03 (0.0124–0.0128); the slow part is ~2 % lower,
  near the top of the refit offset-path value (0.0118–0.0122, derived). Handoff mark (within 10 % of the refit, τ
  within 10 % of W2): both met.
- **The AC-coupling model describes the holds:** scope = G × one-pole high-pass(applied counts, τ) + a constant fits
  every block with 0.15–0.17 V rms residual (`s1_block00_hold.png`): a 4 s hold loses ~51 %, and the step back to 0
  swings negative and recovers with the same τ.
- **The electrode edge is fast but overshoots on the way up.** Rise 10–90 % 0.29 ms (all three). Rising steps
  overshoot by ~35 % of the step in a spike lasting ~1 ms (1.4 V at ~300 counts, 2.9 V at ~700, 4.7 V at ~1100;
  that is why the peaks reached +20–22 V, not ~+16 V). Falling steps overshoot much less, least for the largest
  (median 0.2 V for −900 to −1300 counts, steps that end at or near 0). This is a different shape from OUT_DQ's ringing (~18 %, ~10 ms, sample to sample).
- **Constant offsets on the scope traces,** outputs off or on: CH2 (V2) +1.9 V, CH3 (V3) +0.5 V, CH4 (V4) +0.1 V. Not
  from the drive (present before the first write, and the fit's constant term). Cause not known.
- **Scope timing:** saved at 20.8 kS/s (block-averaged by `scope_rtb.py`); the scope's own `ACQ:SRAT?` read 496–992 S/s,
  which cannot be its sampling rate given the resolved 0.29 ms edges. Scope clock vs FE: 0.998773 (FE runs 1.23 ms/s
  fast; OUT_DQ host fit 1.2 ms/s in S0 and the 8/s test).
- **OUT_DQ side as before:** writes applied on the 8 Hz grid, 100 % landed in every block; write → OUTMON median 138–209 ms.

## Derived

- 8 updates/s works through to the amplifier outputs, not only in the front end: 241/241 updates at 8/s, all
  electrodes together within 0.5 ms.
- At 1200 counts a step is ~15 V at the electrode. 3200 counts would be ~40 V plus a ~35 % rising-edge spike
  (~54 V peak), which needs 10× probes on this scope.

## Interpretation (not approved)

- (interpretation, not approved) The small overshoot on steps down to 0 counts may be the amplifier input clamping at
  0 V (its input range is 0–2.1 V), so the spike below the new level is cut off.
- (interpretation, not approved) The ~1 ms rising-edge spike is in the amplifier (or its output network), not the DAC:
  the front end's own record shows no such spike, only its decimation ringing. It could also be the 1x BNC/scope input;
  a 10× probe would tell.

## Not done / open

- **Rotor:** the video is recorded but not tracked. The tracker centre must be re-derived from it first (handoff).
  At 1200 counts the push is ~1/7 of 3200's, so little motion is expected.
- Absolute write → field delay: not measured (the scope has no common clock; the OUTMON EPICS timestamps were logged
  but are not analysed).
- A bench S1 at 3200 counts with 10× probes and the trigger on CH2: not run.
