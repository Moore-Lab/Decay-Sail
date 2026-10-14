# Stator drive tests on worker2: plan and prompts, 2026-10-14

**Run this on worker2.** It needs live EPICS and NDS2 access to cymac1. The personal
Mac has neither.

This file is written for a Claude session on worker2. Paste §0 first, then hand over
one test at a time. Each test gives what to do, why, what to report, and where to
stop and wait for Molly.

**These are fresh measurements.** The hardware and the front-end model have
changed, so no earlier measured result in the repo (stiffness, libration
frequencies, detent results, spin-up outcomes) is a baseline or an expectation for
these tests. Use the repo for how the hardware and scripts work, not for what the
numbers should come out to.

---

## Why these tests

The goal is reliable **minute-scale** spin-up to ~1 Hz, stop, and reverse with the
rev G under-rotor stator. That enables a differential CW/CCW spindown measurement in
which the two directions have to be taken minutes apart, not days apart. Right now
the drive is unreliable.

There are two views of why:

- **Hardware alignment matters.** The rotor is visibly off-center over the flex PCB,
  and the PCB is held down by large standoffs, so it may not be flat. A lateral
  offset δ cuts m = 8 torque roughly as J0(8·δ/r) with r ≈ 1 mm (0.1 mm → −15%,
  0.2 mm → −55%, 0.3 mm → ~all). The torque also depends steeply on gap (0.1 mm of gap
  is worth ~3× per the design). Tilt or bulge also gives a once-per-rev torque
  variation, and offset or tilt could create an angular well that holds the rotor
  even with the drive off. The tall standoffs are live conductors near the rotor. A
  tilt stage and smaller screws/shims are planned.
- **PI:** those changes are mostly cosmetic and probably not the cause.

The tests below are meant to settle this with numbers, **before and after** the
hardware change. Run A–C before touching the hardware, then repeat them afterwards
with identical settings.

---

## §0. Context prompt (paste first)

```
Context for this session. I'm working on the decay sail experiment: a levitated
"Snowflake V1.3" rotor (I = 1.1e-11 kg m^2 ±10%, sail lever arm 1.38 mm) over a
24-sector, 3-phase flex-PCB stator (rev G) meant to drive it as a
variable-capacitance synchronous motor at m = 8 (rotor speed = f_elec/8).

Read these for how the hardware and scripts work: stator_drive_test_plan.md (this
plan), CLAUDE.md, lab_utils/stator_osc_drive.py (current drive: front-end
oscillator + DRVMTRX), lab_utils/measure_stator_stiffness.py, and
stator_flex/flex_spec.md. Where documents disagree (e.g. which script is "THE
drive"), say so and go by what the code actually does. Don't guess channel names
or script options. Read them.

IMPORTANT: these are fresh tests. I've changed the hardware and the front-end
model since earlier work, so do NOT use any previously recorded measurement in
the repo (docstrings, CLAUDE.md, apparatus_log.md, notebooks) as a baseline,
expectation, or sanity check for what you measure now. Use the repo for methods,
channel names, safety rules and hardware facts only. If you notice yourself
comparing to an old number, flag it and drop it.

Hardware facts:
- HV amp is bipolar about 0 V. The commanded pedestal (= amp) only keeps the amp
  input positive (0–2 V) and doesn't reach the electrode. Max --amp 6400 counts,
  i.e. ~±85 V at the electrode (~170 V peak-to-peak). Verify the counts-to-volts
  conversion from the script/docs and say how sure you are of it.
- Design expectation (stator doc, a calculation, not a measurement): tau_max ≈
  1.2e-12 N·m at "100 V" and 5.0e-12 at "200 V" with a 0.37 mm gap (no shim),
  tau ∝ V^2. Whether "V" there means amplitude or peak-to-peak is ambiguous, so at
  ±85 V the design implies roughly 0.9e-12 to 3.6e-12 N·m.

Goal: reliable minute-scale spin-up to ~1 Hz, stop, and reverse. The drive is
currently unreliable. I want measurements that tell whether rotor centering /
board tilt / mounting are costing torque (or adding an angular trap), versus
something else.

Ground rules:
- Scripts are dry by default. Show me the dry-run output of every command first.
  Never add --live or --enable-outputs without my explicit OK for that exact command.
- If anything looks wrong mid-run, use `stator_osc_drive.py stop --live`. Never zero
  offsets or gains by hand. The pedestal must outlive the AC, and the script
  enforces that order.
- Never use --leave-running unless I ask.
- Never restart the GNOME shell/compositor or display manager on this machine.
- Front-end (cymac) GPS runs ahead of true GPS. Check how the repo handles it
  before converting timestamps.
- Report what you observe and how big it is, with uncertainties. Don't jump to
  causes. If something is unexplained, say it's unexplained.
- Log what you ran (command, GPS start/stop) in apparatus_log.md at the end of
  each test, and tell me what you added.
```

---

## Test A: angular trap with the drive off (baseline)

If something other than the stator holds the rotor angularly (an offset or tilt
over a non-uniform magnet/board, patch charges, the standoffs), the rotor will
librate about a fixed angle with the drive off. If such a trap is stiffer than
the stator, the stator can't break the rotor free, however well the drive works.
The frequency of that libration, if present, is a clean before/after metric for
the hardware change, and it needs no drive at all.

```
Test A. With the drive off (run `stator_osc_drive.py status` first and confirm
DRVON 0, all offsets 0, outputs off), record LES for ~30–60 min. Determine whether
the rotor is librating, slowly rotating, or neither. If librating, measure the
libration frequency f_off and amplitude vs time (e.g. 5-min windows), and whether
f_off depends on amplitude (anharmonic well). Check CLAUDE.md for how libration
shows up on LES_YAW (there is a frequency-doubling convention) and justify which
convention applies to what you see.

Report: state of motion, f_off (mean, drift, scatter) and amplitude, the implied
stiffness k_off = I·(2π f_off)^2, and any harmonics of the line.
```

## Test B: stator stiffness, drive on/off pairs

The stator adds stiffness on top of whatever holds the rotor with the drive off,
so with the drive on, the libration line should shift upward:

    k_stator / k_off = (f_on² − f_off²) / f_off²     (independent of I)
    tau_max = k_stator / m   (m = 8 or 16; see "Open question")

The drive-off baseline may drift, so alternate ON and OFF segments and pair each
ON with its neighbouring OFFs. The key test of the mechanism is **V² scaling**:
halving amp should quarter (f_on² − f_off²).

`measure_stator_stiffness.py` implements this ON/OFF pairing but imports
`stator_awg_drive` (the old AWG path). `stator_osc_drive.py` says it replaces the
AWG route entirely. So it probably needs porting.

```
Test B. Read measure_stator_stiffness.py for its method only (ignore any results
recorded in it) and check whether it can run against the current oscillator drive
(stator_osc_drive.py). If not, propose the smallest port that keeps its ON/OFF
alternation and pairing and reuses stator_osc_drive's bring-up / ramp_down instead
of new EPICS code. Show me the diff and a dry run before anything is live.

What should "ON" be? A slow 3-phase rotating field (rotor ~0.03 Hz, i.e. f_elec
~0.25 Hz) or something else the oscillator allows. Propose one with your
reasoning, including what happens if the rotor isn't librating in Test A.

Run at --amp 6400 and 3200, at least 3 cycles each.

Report: f_on, f_off per pair, (f_on² − f_off²) per pair with scatter, the
6400/3200 ratio of that quantity (expect 4 if tau ∝ V²), k_stator/k_off, and
tau_max under m = 8 and m = 16 assumptions, compared against the design range in §0.
```

## Test C: rotor-vs-stator centering from the camera

```
Test C. Using the Basler camera, measure the levitated rotor's center offset from
the stator pattern's center, in mm.

Take a frame as close to top-down as possible. Fit a circle (or ellipse, if the
view is oblique) to the ring of radial traces/pads, using the known geometry from
the stator Gerbers (stator_flex/) for the pixel scale and the stator center. Fit
the rotor outer edge (radius ≈ 1.75 mm). Report δ (mm and direction), the pixel
scale, an honest uncertainty, and how oblique the view is. Save the frame and an
annotated overlay.

For reference, m = 8 torque ≈ J0(8·δ/r) with r ≈ 1 mm.
If there is any side view, also estimate the rotor–board gap and any visible
board bulge or tilt.
```

## Test D: spin-up, pull-out rate, reverse

Only after A–C. The fastest ramp the rotor can follow is alpha_max = tau_max/I.
At tau_max ~1e-12 N·m that's ~0.014 Hz/s rotor (~0.11 Hz/s electrical). Drag at
1 Hz is negligible by comparison.

`sweep` steps the frequency and then glides over `--drvtramp`. The acceleration the
rotor must follow is ≈ step/drvtramp, not step/dwell. For a clean ramp-rate test,
set `--drvtramp` equal to `--dwell`.

```
Test D. Propose sweeps from a slow start (f_elec ~0.25–0.4 Hz) up to f_elec = 8 Hz
(rotor 1 Hz), with --drvtramp = --dwell, at 3–4 effective rates (step/dwell)
bracketing the alpha_max implied by Test B's tau_max, starting well below it.
Repeat each ~3–5 times, then repeat the best rate with --reverse. Dry-run first.
Wait for my OK.

For each trial, track the rotor frequency from LES. Work out the LES divisor
convention for rotation from the repo and justify it. Log the outcome: followed
to 1 Hz / slipped (at what speed) / never locked / locked at an unexpected speed
or direction (see Open question). After teardown, log ~10 min of coast.

Report: success rate vs rate and amplitude, pull-out rate → tau_max (cross-check
vs Test B), spread in final speed, any CW/CCW difference, and whether slips
cluster at a speed or rotor angle (that would be a once-per-rev torque).
```

---

## Open question: which rotor harmonic does a bipolar drive couple to?

*(Raised 2026-10-14 in conversation on the Mac. A derivation to check, not
established.)*

Torque goes as V² per sector. With no DC at the electrode (bipolar amp) and
V_j = V·cos(ωt − 120°·j) on 24 sectors at a 15° pitch:

    V_j² = V²/2 · [1 + cos(2ωt − 16·θ_j)]

Sampled on 24 sectors, the spatial pattern 16θ aliases with −8θ. So for a neutral
rotor:

- the rotor's **m = 16** harmonic couples to a wave going **forward at f_elec/8**
  (the intended speed and direction)
- the rotor's **m = 8** harmonic couples to a wave going **backward at f_elec/4**
- forward m = 8 coupling at f_elec/8 needs a term linear in V, which with no DC at
  the electrode can only come from a **net rotor charge**

If this is right, the intended-direction torque is the m = 16 term plus a
charge-dependent m = 8 term, and there's a competing backward lock. Things to
check on worker2:

1. Does the rotor ever lock **backward at f_elec/4** in Test D?
2. Does the stator stiffness from Test B change with rotor charge (before vs after
   a UV/charge change)?
3. How do `stator_flex/planar_drive_estimates.py` / `spinup_estimates.py` model the
   time dependence of V²? Do they assume a DC level?

---

## After the hardware change (tilt stage, smaller screws/shims)

Repeat A, B, C with the same settings. The comparison that settles the question:

| metric | before | after |
|---|---|---|
| drive-off state; f_off if librating | | |
| k_stator/k_off at amp 6400 | | |
| tau_max (Test B) | | |
| V² ratio (6400 vs 3200) | | |
| centering offset δ | | |
| spin-up success to 1 Hz (Test D) | | |
