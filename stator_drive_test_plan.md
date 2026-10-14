# Stator drive tests on worker2: plan and prompts, 2026-10-14

**Run this on worker2.** It needs live EPICS and NDS2 access to cymac1. The personal
Mac has neither.

This file is written for a Claude session on worker2. Paste §0 first, then hand over
one test at a time. Each test gives what to do, why, what to report, and where to
stop and wait for Molly.

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
  is worth ~3×). Tilt or bulge also gives a once-per-rev torque variation. A tilt
  stage and smaller screws/shims are planned. Separately, CLAUDE.md ("Known hardware
  issues") flags the tall live standoffs as a rotating in-plane field acting on any
  rotor charge. Swapping them for 4-40 screws addresses that too.
- **PI:** those changes are mostly cosmetic and probably not the cause.

The tests below are meant to settle this with numbers, **before and after** the
hardware change. Run A–C before touching the hardware, then repeat them afterwards.

---

## §0. Context prompt (paste first)

```
Context for this session. I'm working on the decay sail experiment: a levitated
"Snowflake V1.3" rotor (I = 1.1e-11 kg m^2 ±10%, sail lever arm 1.38 mm) over a
24-sector, 3-phase flex-PCB stator (rev G) meant to drive it as a
variable-capacitance synchronous motor at m = 8 (rotor speed = f_elec/8).

Read these before proposing anything: stator_drive_test_plan.md (this plan),
CLAUDE.md, lab_utils/stator_osc_drive.py (current drive: front-end oscillator +
DRVMTRX), lab_utils/measure_stator_stiffness.py, hv_amp_dc_investigation.md, and
stator_flex/flex_spec.md. Where these documents disagree (e.g. which script is
"THE drive"), say so and go by what the code actually does. Don't guess channel
names or script options. Read them.

Hardware facts:
- HV amp is bipolar about 0 V. The commanded pedestal (= amp) only keeps the amp
  input positive (0–2 V) and never reaches the electrode. Max --amp 6400 counts,
  i.e. ~±85 V at the electrode (~170 V peak-to-peak). 200 V p-p is not reachable.
- Design expectation (stator doc): tau_max ≈ 1.2e-12 N·m at "100 V" and 5.0e-12 at
  "200 V" with a 0.37 mm gap (no shim), tau ∝ V^2. Whether "V" there means amplitude
  or peak-to-peak is ambiguous, so at ±85 V expect roughly 0.9e-12 to 3.6e-12 N·m
  (×~3 with the 0.1 mm shim). Treat these as expectations to test, not facts.

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
  causes. If something is unexplained, say it's unexplained. Earlier notes in the
  repo contain interpretations. Treat them as hypotheses, not results.
- Log what you ran (command, GPS start/stop) in apparatus_log.md at the end of
  each test, and tell me what you added.
```

---

## Test A: intrinsic angular trap, drive off (baseline)

Earlier notes (`measure_stator_stiffness.py` docstring, 2026-08-28) report that with
**all electrodes grounded** the rotor still librates at ~0.25–0.33 Hz, drifting over
hours. Something other than the stator traps the rotor angularly. If that trap is
stiffer than the stator's, the stator can't break the rotor free, however well
the drive itself works.

Rotor offset and tilt over a non-uniform magnet/board are candidate sources of
such a trap. So **the frequency of this libration is the cleanest before/after metric
for the hardware change.** It needs no drive at all.

```
Test A. With the drive off (run `stator_osc_drive.py status` first and confirm
DRVON 0, all offsets 0, outputs off), record LES for ~30–60 min. Measure the
libration frequency f_off and its amplitude vs time (e.g. 5-min windows), using the
libration_freq() approach in measure_stator_stiffness.py or something better if
you can justify it. Also check whether f_off depends on amplitude (anharmonic well).

Report: f_off (mean, drift, scatter), amplitude, the implied intrinsic stiffness
k_int = I·(2π f_off)^2, and whether the rotor is librating or slowly rotating.
Note any harmonics of the libration line.
```

## Test B: stator stiffness, drive on/off pairs

The stator adds stiffness on top of the intrinsic trap, so with the drive on the
libration line shifts upward:

    k_stator / k_int = (f_on² − f_off²) / f_off²     (independent of I)
    tau_max = k_stator / m   (m = 8 if it couples via m = 8; see "Open question")

A single earlier pair (amp 6400) gave f_off 0.2704, f_on 0.2923 Hz, i.e.
k_int/k_stator ≈ 6. That's one measurement against a drifting baseline. The check the
script was written for is **V² scaling**: halving amp should quarter
(f_on² − f_off²). As far as I know that hasn't been done.

**Note:** `stator_epics_drive.py` has a `detent` subcommand (DC on one electrode via
`_OFFSET`). Since the amp maps any input DC to 0 V out, check whether it can do
anything at all. The 2026-08-21 DC-on-V2 result (libration rms 22.5 → 8.6) is then
unexplained.

**Caveat:** `measure_stator_stiffness.py` imports `stator_awg_drive` (the old AWG
path). `stator_osc_drive.py` says it replaces the AWG route entirely. So the
stiffness script may need porting to the oscillator drive before it can run.

```
Test B. Read measure_stator_stiffness.py and check whether it can run against the
current oscillator drive (stator_osc_drive.py). If not, propose the smallest port
that keeps its ON/OFF alternation and pairing (each ON vs its neighbouring OFFs,
to cancel drift) and reuses stator_osc_drive's bring-up / ramp_down instead of new
EPICS code. Show me the diff and a dry run before anything is live.

What should "ON" be? A slow 3-phase rotating field (rotor ~0.03 Hz, i.e. f_elec
~0.25 Hz) or a static one. Look at what the script did before and what the
oscillator allows, and propose one with your reasoning.

Run at --amp 6400 and 3200, at least 3 cycles each.

Report: f_on, f_off per pair, (f_on² − f_off²) per pair with scatter, the
6400/3200 ratio of that quantity (expect 4 if tau ∝ V²), k_stator/k_int, and
tau_max under m = 8 and m = 16 assumptions, compared against the design range above.
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

Only after A–C. With design torque, the fastest ramp the rotor can follow is
alpha_max = tau_max/I. At tau_max ~1e-12 that's ~0.014 Hz/s rotor (~0.11 Hz/s
electrical). Drag at 1 Hz (~1.3e-14 N·m) is negligible.

`sweep` steps the frequency and then glides over `--drvtramp`. The acceleration the
rotor must follow is ≈ step/drvtramp, not step/dwell. For a clean ramp-rate test,
set `--drvtramp` equal to `--dwell`.

```
Test D. Propose sweeps from a slow start (f_elec ~0.25–0.4 Hz) up to f_elec = 8 Hz
(rotor 1 Hz), with --drvtramp = --dwell, at 3–4 effective rates (step/dwell)
bracketing the alpha_max implied by Test B's tau_max, starting well below it.
Repeat each ~3–5 times, then repeat the best rate with --reverse. Dry-run first.
Wait for my OK.

For each trial, track the rotor frequency from LES. Check the divisor convention
in analysis/spindown_20261011.ipynb, where the LES line has been 2× rotation. Log
the outcome: followed to 1 Hz / slipped (at what speed) / never locked / locked
at an unexpected speed or direction (see Open question). After teardown, log
~10 min of coast.

Report: success rate vs rate and amplitude, pull-out rate → tau_max (cross-check
vs Test B), spread in final speed, any CW/CCW difference, and whether slips
cluster at a speed or rotor angle (that would be a once-per-rev torque).
```

---

## Open question: which rotor harmonic does a bipolar drive couple to?

*(Raised 2026-10-14 in conversation on the Mac. A derivation to check, not
established.)*

CLAUDE.md, "The DC pedestal is not cosmetic", already splits the torque into
ch1 (rotor m = 8, ∝ V_dc·V_ac) and ch2 (rotor m = 16, ∝ V_ac²), and notes that the
amp delivers no DC at the electrode. So for a neutral rotor ch1 is off. That part
is not new. The addition is an aliasing term that table doesn't list.

With bipolar V_j = V·cos(ωt − 120°·j) on 24 sectors at a 15° pitch:

    V_j² = V²/2 · [1 + cos(2ωt − 16·θ_j)]

Sampled on 24 sectors, the spatial pattern 16θ aliases with −8θ. So:

- the rotor's **m = 16** harmonic couples to a wave going **forward at f_elec/8**
  (ch2, the intended speed and direction)
- the rotor's **m = 8** harmonic *also* couples to the V² term, through the alias,
  to a wave going **backward at f_elec/4**
- forward m = 8 coupling at f_elec/8 (ch1) needs a term linear in V. With no DC at
  the electrode, that can only come from a **net rotor charge**

If this is right, the design's m = 8 torque numbers don't describe a neutral rotor
under this amp. The intended-direction torque is ch2 plus a charge-dependent ch1,
and there's a competing backward lock. Any of those could make the drive
"sometimes work". Things to check on worker2:

1. Does the rotor ever lock **backward at f_elec/4**? Look for it in Test D and in
   old sweep data.
2. Does the stator stiffness from Test B depend on rotor charge (before vs after a
   UV/charge change)?
3. How do `stator_flex/planar_drive_estimates.py` / `spinup_estimates.py` model the
   time dependence of V². Do they assume a DC level?

---

## After the hardware change (tilt stage, smaller screws/shims)

Repeat A, B, C with the same settings. The comparison that settles the question:

| metric | before | after |
|---|---|---|
| f_off (intrinsic trap) | | |
| k_stator/k_int at amp 6400 | | |
| tau_max (Test B) | | |
| centering offset δ | | |
| spin-up success to 1 Hz (Test D) | | |
