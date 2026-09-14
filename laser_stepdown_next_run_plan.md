# Laser step-down, next run: plan worked out 2026-09-14

**Do this on worker2, not the personal Mac.** This dev machine has NO live network
path to cymac1's NDS2 server (confirmed: `cymac1:8088` unreachable) -- anything that
needs to read recent/live data has to run where `laser_step_down.py` already runs.

`lab_utils/laser_step_down.py` has **not been edited yet** -- this file is the plan,
worked out in conversation, to implement once back on worker2.

---

## Context

Rotor re-spun-up 2026-09-14 with the same laser settings as the 09-11 run
(`LASER_OFFSET = 1300`, ~5.8 mW at chamber). Goal: step the laser power **down** from
1300, letting the rotor settle to a new terminal speed at each level, and see how low
it can go before it stops sustaining rotation. 1300 is a known-safe high point (not
being raised), so the question is only how far down and how finely to resolve it.

## What "last time" (2026-07-05 -> 07-09) actually showed

There's a full prior run + analysis: `lab_utils/laser_step_down.py`, 48 commanded
levels, and three notebooks (`analysis/laser_stepdown_settling.ipynb`,
`laser_stepdown_forward_model.ipynb`, `laser_stepdown_stability.ipynb`) plus
`laser_stepdown_steps.csv` and `laser_stepdown_sensitivity_notes.md`. Key facts that
should inform this run:

- **Fine steps were genuinely necessary near the low end.** After step 11 (1000
  counts) the operator switched to ~1-10 PD-count spacing, 15-30 min holds -- coarser
  spacing stopped resolving distinct steady states. Expect the same need somewhere
  below ~1000 counts this time; **start coarse near 1300** (not fine -- see below).
- **The on-drive relaxation time is NOT the free-decay time, and by a lot.** Free
  decay (laser off, no drive) measured τ = 67.65 min (`spindown_20260702.ipynb`,
  used as the reference in the July analysis). But the global forward-model fit to
  the whole 4-day *driven* record (scanning assumed τ, minimizing residual RMS)
  preferred **τ ≈ 160 min -- 2.4x slower.**
  - This session separately measured a fresh free-decay τ = 79.8 min
    (`analysis/spindown_20260913.ipynb`, laser-driven-then-coasted). Same kind of
    number as the 67.65 min one (drive fully off), not the on-drive one.
  - **Why this matters:** for a strictly linear drag law, free decay and driven
    step-response are required by basic linear-ODE behaviour to relax at the *same*
    rate -- a step in forcing always decays at the system's own characteristic rate
    regardless of the new target. Getting 2.4x apart means the real system, under
    illumination, isn't well captured by that simple picture. Cause not established
    (considered and rejected: local heating -> more outgassing -> *faster* damping,
    wrong direction for what's observed). Most likely candidate: the same kind of
    narrow-range model misspecification this session found independently comparing
    the 09-09 and 09-13 spindowns (`analysis/damping_law_comparison.ipynb`) -- but
    that's not confirmed here, just the best current guess.
  - **Practical consequence: don't trust either 67.65/79.8 min or 160 min as a fixed
    dwell time.** Use the programmatic settled-check below instead of a fixed timer.

## Decisions made

1. **Step schedule: coarse -> fine, starting coarse.** ~100-150 count steps near
   1300 (this region is already well inside last time's well-behaved range, between
   old steps 7 and 8 -- no reason to spend fine-resolution time there). Shrink step
   size approaching ~1000 counts, where fine resolution turned out to matter last
   time. Exact fine-schedule numbers not yet fixed -- pick when you're actually
   there and can see the per-step response size.

2. **Replace the fixed `DWELL_TIME` with a programmatic settled-check, not a fixed
   number.** Schedule: initial wait **~60-80 min** (~1τ, checking before that is
   guaranteed to fail), then **re-check every ~20-30 min** (not big jumps -- avoids
   a 2x overshoot risk) up to a **hard ceiling ~320-360 min (~4x the conservative
   τ)**. Past the ceiling, **stop waiting and flag it rather than loop forever** --
   given the on/off discrepancy above, an unattended script that just keeps waiting
   indefinitely is a real risk on an overnight run.

3. **The settled-check itself: `lab_utils/settled_check.py` (NEW, written and
   validated this session).** `check_settled(les, fs, f_guess)` pulls the most
   recent 20 min of LES_YAW, gets ~12 frequency estimates with the band-following
   tracker, and requires BOTH: (a) linear-fit slope across the window consistent
   with zero, (b) first-half-window mean vs second-half-window mean consistent.
   20 min, not 10: the July stability notebook found a persistent ~10-min
   quasi-periodic oscillation on the high-power plateau that a 10-min window could
   be fooled by (catch it on a rising/falling phase and misread the slope).
   **Validated against 4 known-ground-truth historical cases from the 09-11 run,
   all correct** -- see the module docstring for the numbers. Not yet tested against
   truly live/real-time data. **Before trusting the check cadence in an unattended
   loop, verify on worker2 how much latency NDS2 has for "just happened" data** --
   this wasn't testable from the dev Mac.

4. **Keep logging through any libration transition -- don't stop when rotation
   stops.** If the rotor falls out of sustained rotation at some low power, that
   transition is itself the measurement (the threshold where laser torque drops to
   wherever the drag law's constant term / trap barrier takes over). Worth holding
   a couple of extra steps below that point to see the libration behaviour itself.
   Reuse `lab_utils/watch_capture.py` / `monitor_libration.py` rather than building
   anything new for this.

5. **Log every commanded step to a file, not just stdout.** July's settling notebook
   had to re-detect step boundaries from the raw PD trace because *"no setpoint
   channel was exported"* -- avoidable rework. This time: write timestamp, GPS,
   commanded offset, and readback to a file for every step, and log every
   settled-check call (not just the final pass/fail) -- slope, half1/half2 means,
   pass/fail per test. Then a future analysis notebook doesn't need to reconstruct
   the step history from PD alone.

6. **Pressure logging is still an open gap.** No live DAQ record of chamber
   pressure exists right now (separate from this run -- it's the same open
   `apparatus_log.md` TODO, "get the pressure gauge logging"). Not solved here.
   Cheapest partial mitigation: **manual spot-reading of the gauge at the start of
   each dwell**, logged alongside the step file above. Worth it even un-automated --
   this is the clean discriminator for the τ0-vs-γ / gas-drag-vs-eddy-current
   question from earlier in this session (see `analysis/damping_law_comparison.ipynb`
   conclusions), and a per-step run like this is a good chance to get real pressure
   coverage across a range of laser powers essentially for free.

## Not yet done

- `lab_utils/laser_step_down.py` itself has not been touched. Once on worker2, fold
  in: the coarse->fine `OFFSET_VALUES` schedule, `settled_check.check_settled()`
  replacing the fixed `DWELL_TIME` sleep with the wait/recheck/ceiling loop above,
  the step + settled-check logging to a file, and the libration-transition handling
  (don't stop the loop / data collection when rotation stops; consider running
  `monitor_libration.py` alongside).
- NDS2 real-time latency on worker2, unverified.
- Fine-step spacing/hold-time numbers for the low end, not yet fixed -- decide live.
