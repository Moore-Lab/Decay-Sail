# Voltage steps S0, 2026-11-09: fast DC offset steps, outputs off

Interpretations are Claude's and marked "(interpretation, not approved)". Everything else is measured or derived as labelled.

- **Plan and code:** `lab_utils/VOLTAGE_STEPS_HANDOFF.md`; branch `voltage-steps` (`voltage_steps.py`, `voltage_steps_score.py`, scored at 275d152).
- **Run:** worker2, outputs **off**, `--shape stair`, level 3200 counts. FE GPS 1478304227–1478304642 (host 1794252883.8–1794253294.7).
  All 3798 writes read back correctly, and every channel connected.
- **Data:** Dropbox `Microspheres/TFINER/data/voltage_steps/2026-11-09/vsteps_1794252897/` (writes, blocks, OUTMON, OUT_DQ FE
  1478304212–1478304671, console logs, GPS pairs).
- **Figures and full table:** `python3 lab_utils/voltage_steps_score.py <data dir> --outdir analysis/voltage_steps_20261109/plots`
  (on the branch). It writes `summary.md` (per-block table), `summary.png` and one `blockNN_*.png` per block (gitignored).
- OUT_DQ is upstream of the output switch. These numbers are when the front end **applies** a write, not what reaches the electrode.

## Measured

- **Offset writes are applied on a fixed 8 Hz grid.**
  - Every landing sits on the same parity of the 16 Hz tick for the whole 7 min: 1661 landing ticks odd, 8 even, and the 8 even
    ones are all in the end-of-run ramp below.
  - Spacing between landing ticks is 2, 4 or 6 ticks (1175 / 238 / 58), never 3 or 5.
  - The grid is locked to the FE GPS second. Edge onsets are at OUT_DQ samples 125 + 128 j of each second, within 3 samples (the
    filter's slow first sample).
- **Achieved rate levels off at 8 updates/s** (7.0–8.05 landings/s at 16 and 32 requested). At ≤ 4 steps/s every write landed
  (all 3 patterns). At 16/s about 50 % of writes landed, at 32/s about 25 %. Single electrode at 16/s and 32/s: 44 % and 3 %, because
  the stair cycle's last-wins value often equals the previous one.
- **8/s:** 100 % (single), 91 % (all3), 77 % (stepper) landed. The losses come from the measurement dither, which moves 8/s steps by
  0–62.5 ms and so sometimes puts two writes in one 125 ms window. Undithered writes, one per 125 ms window, would land every
  time (derived from the grid above).
- **Several channels land together.** 0 of 987 landed multi-channel steps split across ticks.
  - The chance of a split with an 8 Hz intake is ~0.25–0.4 % per step (write burst 0.3–0.5 ms). So ~2–4 splits were expected
    under random timing, and the run can't tell "one snapshot of all channels" from chance.
  - Also, the three writes probably reach the IOC in one packet (assumed).
  - So this is consistent with all three channels being applied together, not proof that they always are.
- **Write → OUTMON on the host: median 170–200 ms, p95 ~220–250 ms** at ≤ 8 steps/s.
  - This is an **upper bound on host-side latency**. It includes the EPICS monitor publish period and network delivery, so it is
    not write-to-DAC latency.
  - At 16–32/s the medians are shorter (45–155 ms), but only because a match is counted only before the next same-value write.
  - OUTMON does follow the offset with outputs off (2179 non-zero updates).
- **Write-to-landing spread (relative):** 0–~125 ms at ≤ 4/s. This fits a 125 ms intake grid. Absolute write → DAC latency is not
  measured: the fitted host → FE offset mixes the clock offset with the latency.
- **Clock drift:** FE time runs +1.21 ms/s against worker2 host time (fit to 1689 writes). F1 on 11-02 found ~1.1 ms/s.
- **TRAMP:** found at 1.0 at block 0, then 0.0 at blocks 1–17. So it did not reset within the run (blocks a few seconds apart);
  the "resets between runs" note may still hold across separate runs.
- **OUT_DQ edges ring:** ~18 % overshoot, alternating sample to sample, settled to < 0.1 % after ~35 samples. The cause is assumed to
  be the DQ decimation filter, i.e. a recording artefact. The S1 scope will show whether the electrode edge rings.
- **End of run:** the last 0-write to V3 and the TRAMP restore (1.0 s) landed in the same applied tick, so V3 ramped from 3200 to 0
  over 1 s instead of stepping. With outputs off this has no effect. The script now waits 0.5 s before restoring TRAMP (275d152).

## Derived

- **Three-phase stepper aliasing**, from the applied A/B/C states in OUT_DQ (consecutive transitions forward / reversed):

  | requested | forward | reversed |
  |---|---|---|
  | 4/s | 79 | 0 |
  | 8/s (dithered) | 86 | 36 |
  | 16/s | 3 | 155 |
  | 32/s | 154 | 2 |

  At 16/s the intake keeps every 2nd state, so the field steps **backwards**. At 32/s it keeps every 4th, which is one step forward.
  A commanded stepping rate above 8/s does not give a faster field: depending on the rate, the field steps backwards or at 8/s.
- **Ceiling for a stepper through the offsets:** 8 updates/s. At 15° per step that is 120°/s ≈ 0.33 rev/s at most, and only if the
  rotor follows every step. The handoff's 8–16 updates/s estimate becomes 8.

## Not explained

- ~190 ms host-side write → OUTMON, against F3's "~0.1 s effective delay" for matrix updates. These measure different things
  (monitor delivery vs the field), so they need not agree. The absolute latency is still open.

## Interpretation (not approved)

- (interpretation, not approved) The 16 Hz "tick" in DECISIONS 2026-11-02 (DRVMTRX) and the 8 Hz here (OFFSET) may be one mechanism:
  F3 saw matrix loads landing every 2nd tick too.
- (interpretation, not approved) The limit is the front end's EPICS intake, not the host. Host lateness was ≤ 0.4 ms in every block,
  and write bursts were < 1 ms.

## Open (next run, suggestions)

- **Absolute latency:** the OUTMON callback receives an EPICS `timestamp` that is dropped now. If the IOC stamps in FE time, host
  receive minus that timestamp gives the clock offset directly. Alternatively, poll `Y1:DAQ-DC0_GPS` for its rollover. Either fixes
  the offset well under 1 s, and the latency follows from the fitted mapping. Not built.
- **S1** (outputs on, scope, video) per the handoff: electrode volts per count, edge shape (clean or ringing), droop against τ.
