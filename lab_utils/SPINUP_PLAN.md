# Spin-up through the electrodes: plan and status (updated 2026-11-12)

Directive and pass marks: `measurement_objective.md`. Decisions: `docs/DECISIONS.md` (2026-11-10 feedback rule;
2026-11-11 DC coupling; 2026-11-11 spin-up amendment). State, settings and conventions for a new session:
`lab_utils/SPINUP_HANDOFF.md`. Earlier versions of this plan: git history (gates G1–G6 as first proposed, 2026-11-11).

## What changed the plan (2026-11-11/12)

- **The amp is DC-coupled** (11-11), so a held level holds.
- **G1 and G2 done:**
  - G1: push map over 167–267°, push ~linear in V up to 1600 counts.
  - G2: brake from ±35–40°, 3/3.
- **The steady slow carry (stage 1 as written) was not built.**
  - The sim (AC path, assumed trap) showed narrow dips every 45° where all three phases push weakly.
  - Instead, Molly chose a set spin rate per spin-up as the target (11-11). Interim targets: 0.5 Hz, then 0.75 Hz.
- **Spin-up by "pump over the top, then govern the mean rate" works in both directions.**
  - Live 11-11/12: 0.45–0.47 Hz at a 90°/s push limit. U1 and U2 passed at 0.5 Hz ±5 % with a 120°/s limit.
  - Spin-down with the same tool stops 0.5 Hz in ~20 s.
- **The trap is now measured over the full circle** (S1's free coast): barrier at 60°, 6.5 rad²/s² per I.

## Stages as we now run them (proposed mapping to the directive; Molly to confirm)

| stage | directive | what we run | status |
|---|---|---|---|
| 1 | carry 0.01–0.05 Hz, no slips, 5 min | not run; superseded by a set-rate spin-up (Molly, 11-11)? | to confirm |
| 2 | from rest to 0.2 Hz, hold 5 min | covered by the 0.5 Hz runs if a lower target is set (not run at 0.2) | open |
| 3 | 1 Hz within 5 min, ±1 % for ≥ 5 min | interim: 0.5 Hz ±5 % (8 updates/s); then 0.75 Hz (Molly: consistent 0.75 Hz would be fine) | 0.5 Hz: series in progress |

Each stage needs 8 of 10 per direction.

## Next steps

1. **Finish the 0.5 Hz attempt series** (8 attempts, alternating direction) and score it per direction.
2. **Choose the faster-update route for 0.75 Hz.** The update-rate sim (`analysis/spinup_spin_20261111/spin_rate_summary.md`)
   shows what each rate reaches. Options:
   - (a) RCG EPICS helper back to 16 Hz: recompile the two models on cymac1 (Molly's and Alma's);
   - (b) a USB/Ethernet DAC into the amp input, with the loop on worker2 at up to 50 updates/s.

   Before (b):
   - its range must be held to 0–2.1 V by design, since the front end's clamp no longer applies;
   - grounding (DECISIONS 11-03);
   - a switch between the front end and the DAC;
   - logging of the commands;
   - USB timing jitter.

   Purchases need Molly's OK.
3. **What the update-rate sim says (derived):**
   - 16 updates/s reaches 0.75 Hz with the current governor (7/12 cells pass; 94 % of turns within ±5 %).
   - Faster rates need a proportional governor before they help.
   - 1 Hz and ±1 % need both a faster rate and that governor.
   - So route (a) covers the 0.75 Hz target with the code we have.
4. **Supporting items:**
   - a tracker template fix for the 320–330° match dip;
   - a damping spindown at September's speed;
   - the trap at swinging speeds against rotating speeds.
