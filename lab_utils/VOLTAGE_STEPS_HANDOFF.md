# Fast DC voltages on the electrodes: handoff

**Status: plan, not started (2026-11-09).** Nothing below is built or run. Every live run needs Molly's go.

## Goal (Molly's PI, as Molly relayed it, 2026-11-09)

- Show that we can put **chosen DC voltages** on the electrodes, **quickly**, stepping through a list of levels,
  within what the EPICS route gives us. These are voltages, not waveforms.
- **The rotor doesn't need to follow.** No feedback on position yet. The point is to measure **what limits** fast
  voltage steps.
- **No front-end model change.** The PI wants this tried first, and then a talk with Alma before any model change,
  because it may not be needed.
- Path chosen by Molly: the electrode **offsets** (`V{n}_OFFSET`), the `stator_detent.py` way. The drive matrix,
  oscillator and AWG are not used.

Background: why the drive needs fast, well-timed field updates. See the briefing
(https://claude.ai/artifact/G1gMdFrWZ5W9PVX1MRt7xD) and `analysis/osc_chirp/README.md`, `analysis/f3_20261104/README.md`.

## What is already known (with sources)

| Fact | Value | Basis |
|---|---|---|
| EPICS-written values take effect only on the front end's ticks | 16 Hz grid (852/852 output steps) | measured, F1/F1b 11-02; `docs/DECISIONS.md` 2026-11-02 |
| Drive-matrix updates (several writes + load) landed every 2nd tick | ~8 Hz, ~0.1 s effective delay | measured, F3 11-04 (`analysis/f3_20261104/README.md`) |
| Whether **offset** writes behave the same (rate, same-tick for 3 channels) | unknown | to measure in S0 |
| Amplifier output is AC-coupled | τ = 5.69 / 5.56 / 5.43 s (V2 / V3 / V4) | measured W2, 11-03 (`lab_utils/WAVEFORM_HANDOFF.md`, branch `waveform-test`) |
| Volts per count at the electrode, `_EXC` (AWG) path | 0.0124–0.0128 (11-03 scope); 0.0134 (August, 12800 counts p-p) | measured; the two differ by 5–8 %, not reconciled |
| Volts per count, `_OFFSET` path | **~0.0118–0.0122** (V2 0.0118–0.0119, V3 0.0121–0.0122, V4 0.0121–0.0122) | derived: two-gain refit of the W2 scope records, `analysis/voltage_steps/offset_gain_refit.py`. 4–5 % below the AWG burst gain in the same records; probably the one-pole model at < 0.1 Hz (the pedestal is a slow ramp), since both paths share one module gain (GAIN 1, no filters, 11-02). Not settled; S1 checks it |
| Amplifier input range | 0–2.1 V = 0–12800 counts (`V{n}_LIMIT`); offsets alone must stay in 0..12800 | CLAUDE.md "Hardware traps" |
| `V{n}_TRAMP` ramps every offset change | found at 1.0 s; resets between runs | CLAUDE.md; set to 0 for steps and restore after |
| Output switch | `SW2` bit 1024; **never write a whole SW2 word** (`sw2 & ~1024` to clear) | CLAUDE.md |
| Trap (once per turn), for rotor expectations | up to 5.0 rad/s² | measured 11-04, shape unchanged 11-06 |
| Push from a well-placed field | ~3 rad/s² at amp 4000 | measured 11-04 (per-hold fit) |

**What an offset step does at the electrode** (derived from the AC coupling): a step up by V appears as +V and decays
to 0 with τ ≈ 5.6 s, losing ~8 % in 0.5 s and ~16 % in 1 s. A step back down gives a −V transient. So "DC" here means
**held much shorter than τ**, and a sequence's running mean drifts towards 0 at the electrode.

**Existing script:** `lab_utils/stator_detent.py` on branch `detent-test` (written 2026-11-01, never run). It steps one
electrode group at a time to a level, holds, ramps down slowly, logs host time and FE GPS per event, and has safety
refusals. **Its "~1° shift" expectation is outdated:** it used the design torque. With the measured push (~3 rad/s²
against ~3.8 rad/s² per radian of trap stiffness near rest), a held step may move the rotor by **tens of degrees**
(derived, rough). Not needed for S0/S1, but don't trust that docstring.

## Plan (gates; Molly edits before anything is built)

### Build (Mac, branch `voltage-steps` from `main`)
- `lab_utils/voltage_steps.py`, adapted from `stator_detent.py`. It plays a list of (t, V2, V4, V3) counts through the offsets:
  - sets `V{n}_TRAMP` to 0 and restores it afterwards;
  - logs each write's host time and `caget -f0 Y1:DAQ-DC0_GPS` before and after;
  - polls `V{n}_OUTMON` to time when each write appears;
  - outputs **off** unless `--enable-outputs`;
  - refuses if the oscillator is on, an offset is non-zero at start, or a level is outside 0..12800;
  - ramps slowly to 0 at the end and on Ctrl-C; never writes a whole SW2 word.
- A list generator for the test patterns (below) and a scorer/plotter (S0, S1). Each gets a `selftest` against a
  mock front end (16 Hz tick model).

### S0: offsets with outputs OFF (OUT_DQ only; Molly's go)
- **Patterns:**
  1. one electrode, square steps 0 ↔ 3200 counts;
  2. all three changed together (A, B, C patterns);
  3. three-phase "stepper" order A → B → C → A.
- **Rates:** requested 1, 2, 4, 8, 16, 32 steps/s, ~20 s each.
- **Measures:**
  1. fraction of steps that land, and the highest rate that works;
  2. landing times against the 16 Hz grid;
  3. whether a 3-channel change lands on one tick or is split;
  4. delay from write to output (host side, from the OUTMON poll);
  5. the TRAMP reset.
- **Plots** (`analysis/voltage_steps_<date>/`):
  1. per channel, **the commanded list and the OUT_DQ output on one time axis**, with the residual;
  2. a histogram of landing times modulo 1/16 s;
  3. achieved versus requested rate;
  4. cross-channel landing differences.
- **Pass:** a complete dataset and the table of measured numbers. There is no threshold: the numbers are the result.

### S1: the same with outputs ON, scope on the amplifier outputs, video recorded (Molly's go per run)
- A subset of S0 (e.g. 1, 4 and 16 steps/s) at moderate level (≤ 3200 counts).
- RTB2004 on CH2–CH4 = V2, V3, V4 at the amplifier outputs, 10× probes. DC-couple the scope and check the zero line
  first (CLAUDE.md).
- Record a Basler video: `grab_basler.py --record` (camera free; no live tracking, since the tracker centre is stale,
  `docs/STATUS.md`).
- **Measures:**
  1. volts per count on the offset path: a **check** of the refit value, separately for the first instant of a step
     (expect ~0.0124–0.0128, the burst gain) and its slow part (expect ~0.012);
  2. step rise time and shape at the electrode;
  3. droop against τ;
  4. ringing and spikes;
  5. rotor motion (afterwards, from the video).
- **Plots:**
  1. per channel, **commanded list, OUT_DQ and scope volts** on one time axis;
  2. measured droop with the τ model overlaid;
  3. **rotor angle from the video on the same time axis as the applied voltages** (stacked panels). How best to show
     the rotor response is to be decided with Molly after S0.
- **Pass:** electrode steps equal counts × V/count (the refit value) within 10 % and the droop matches τ. Or, if not, a
  clear measurement of how they differ.

### Afterwards
- A one-page summary of the measured constraints (rate, same-tick, delay, V/count, droop) for the PI and Alma.
- **Questions for Alma:**
  - Can the 16 Hz EPICS intake be raised, or is there a faster input path without a model change?
  - Can several values be applied in the same tick?
  - Can the front-end clock offset (4.3 h, 0.12 % fast) be fixed? That would also unblock streamed AWG waveforms.

## Expected ceiling (derived; for the discussion, not a pass mark)

At ~8–16 updates/s, a 15°-per-step stepper reaches at most 120–240°/s = ~0.33–0.67 rev/s, and only if the rotor keeps
up with every step (which the trap may not allow at low speed). That's enough for the stage-1/2 targets in
`measurement_objective.md` (0.01–0.2 rev/s), not for 1 rev/s or fast reversals.

## Open items carried from 2026-11-06 (not part of this task)

- **Tracker centre stale:** see `docs/STATUS.md` (first Open item).
- **Damping τ ≈ 32–35 min** (derived, `analysis/osc_chirp/README.md`): Molly hasn't decided whether to record it in
  DECISIONS; 88 min is on record.
- **Front-end model change** (`rcg/commutate.c`, branch `feedback-drive`): paused. PI: try this first, then talk to Alma.
- The feedback handoff (`lab_utils/FEEDBACK_HANDOFF.md`, branch `feedback-drive`) still lists F3 step 2 (brake fixes).
  Superseded in priority by this task, not cancelled.

## Next (exact)

1. Molly reviews and edits this plan.
2. Mac session: `git worktree add ../decay_sail_wt_vs -b voltage-steps main`. Build the script, generator and
   scorer/plots with selftests; commit to the branch; push.
3. worker2 (repo `~/rds-code/Decay-Sail`; use a worktree, never stash): dry run, then S0 with outputs off, on
   Molly's typed go.
4. S1, on Molly's go per run.
