# Spin-up through the electrode offsets: proposed gates (DRAFT for Molly to edit, 2026-11-11)

Status: **proposal, nothing built.** Directive and pass marks: `measurement_objective.md` (stage 1 carry 0.01–0.05 Hz for
5 min; stage 2 ramp to 0.2 Hz and hold 5 min; stage 3 1 Hz; 8 of 10 in each direction). Rule for feedback runs:
`docs/DECISIONS.md` 2026-11-10 (measured trap + push map over the range used, simulator check, live safety).

## What we have (2026-11-10/11)

- **Brake** (gate B4, `analysis/brake_b4_20261111/`): live feedback through the offsets at 8 updates/s, one phase at
  800 counts; ±20° → ±2 in ~6 s, repeated once. Valid in 190–236° only.
- **Push map** (B2): one 45°-periodic shape (m = 8 + 16) shared by A/B/C, shifted 15° per phase; ~0.75 rad/s² peak at
  800 counts. Measured over 187–238° only (one 45° period plus a bit).
- **Trap** (B1, B2): measured over 150–290° (free ±72° swing), Q ≈ 4300; fine structure near rest not settled; barrier
  not reached (it lies outside 145–295°).
- **Timing**: field follows the 8 Hz intake (0–125 ms wait) plus a small constant (4 ± 12 ms from S1's first step).

## Constraints that shape the plan (derived)

- **8 updates/s limits the speed feedback can commutate.** The push pattern repeats every 45° (m = 8) and 22.5° (m = 16).
  Pushing usefully needs a few updates per period:
  - 0.05 Hz = 18°/s: ~10 updates per 22.5°. Fine (stage 1).
  - 0.2 Hz = 72°/s: 2.5 updates per 22.5°, 5 per 45°. Marginal (stage 2): may have to rely on the m = 8 part only.
  - 1 Hz = 360°/s: 1 update per 45°. **Not reachable on this route.** Stage 3 needs the front-end oscillator route or the
    paused front-end model change (PI: try without, then talk to Alma). Worth raising early.
- **Holding against the trap.** Carrying the rotor over the top at constant slow speed needs the field's push to beat the
  trap's restoring acceleration all the way round. Measured trap reaches ~2.5 rad/s² within 150–290° (more near the top,
  unmeasured); the push is ~0.75 rad/s² at 800 counts. If the push is linear in V (detent runs suggested ~linear; B2 assumed
  V²), ~3000–5000 counts are needed; if V², ~1600–2000. Unknown until G1 measures the scaling.
- **The brake is the safety net only where the map is measured.** Before the rotor goes over the top, braking must work
  over the whole swing.

## Agreed order (Molly, 2026-11-11)

G1 → G2 → stage 1 carry (sim, then live at ~0.02 Hz, both directions, brake as backup) → stage 2 if the 8 Hz limit allows.
G3 and G4 are folded into the carry attempt (a slow carry goes over the top under control; the brake catches a failure).
G1 run: kick A 2400, pump to ±35° (`brake_offsets.py --pump-to 35 --safe 150,280`, branch voltage-steps), then the pulse plan
`analysis/spinup_g1_20261111/g1_plan.csv` (25 pulses at 800 and 25 at 1600 counts, 0.25 s).

## Gates as first proposed (each: plan → mock/sim test → Molly's go → results README)

- **G1. Push map over the full swing, and its scaling with voltage.** Kick (A, 2400) and pump within the mapped range to
  ±40–60°, then B2-style random pulses across 150–290°, at 800 and at 1600 counts. Pass: the 45°-periodic shape holds
  across the range (or is remapped), and the 800 → 1600 ratio is measured (×2 linear, ×4 V²). This also answers STATUS's
  "which harmonic the drive couples to" and bears on rotor charge (a linear term needs net charge, derived 10-14).
- **G2. Brake from large swings.** Extend the brake to the G1 map and range; sim check; then brake a ±60° swing.
  Pass: below ±10° within 2 min, never growing, in 3 of 3 runs.
- **G3. Find the barrier.** Pump energy slowly (push along the motion, where the rotor is slow), braking if the energy
  overshoots a set limit; track the turning points as they approach the top. Pass: the trap's top region measured (energy
  to go over), without going over.
- **G4. First turn and stop.** Pump just over the top, allow 1–2 turns at slow speed (pushing only where slow), brake back
  to a swing. Sim first, including whether the 8 Hz brake can catch a slow rotation. Pass: over and back, 3 of 3, each
  direction.
- **G5. Carry (directive stage 1).** Feedback commutation at a set 0.01–0.05 Hz, holding position against the trap with
  the push map; no slips for 5 min. Pass: the objective's 8 of 10 per direction.
- **G6. Ramp to 0.2 Hz (stage 2)**, if the 8 Hz limit allows; otherwise this is where the route changes.

## Questions for Molly

1. Is this the right order, or go for carry (G5) sooner with the oscillator route instead of feedback?
2. Voltage ceiling for G1–G5 (the electrodes saw ~110 V peak in the detent runs; board rated 200 V, hipot 250 V)?
3. Raise the stage-3 route question (oscillator vs model change, Alma) now or after G5?
