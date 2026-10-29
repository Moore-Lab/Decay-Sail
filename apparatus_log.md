# Apparatus log

Dated record of what changed and what was run. **New entries go at the top of
`## Changes`**, newest first. Dates are UTC unless noted.

Each entry is short: what was done or run (command, front-end GPS start–stop), what was
seen, and a link to any analysis. Label claims as measured, derived or assumed.
Open items live in `docs/STATUS.md`, current values in `docs/DECISIONS.md`, and which
constants applied to which datasets in `analysis/calibration_history.md`.

Entries before October 2026 are archived in `logs/2026-q3.md`.

---

## Changes

### 2026-10-28 — ACTUATOR IS FAST: matrix → DAC in under one 1024 Hz sample

> **Provenance.** MEASURED: everything below. The one INFERENCE is flagged in place.

**`DRVMTRX` reaches the DAC within a single 1024 Hz sample.** EPICS is not a
bottleneck and neither is the matrix.

Method: drive at `--felec 1.0 --amp 200` (torque 0.1% of amp 6400, negligible),
`DRVMTRX_TRAMP = 0`, step `SETTING_2_2` between +1 and −1 four times ~8 s apart,
then read `V2_OUT_DQ` at 1024 Hz from NDS.

| | |
|---|---|
| largest single-sample change at the step | **−283.8 counts** |
| median sample-to-sample change elsewhere | 0.63 counts |
| ratio | **453×**, inside one 1 ms sample |
| `caput` round-trip | 0.38–0.44 ms |

**Internal check:** the final transition, where `TRAMP` had been restored to 2.0,
took **1.48 s** — i.e. TRAMP does exactly what it says, while TRAMP = 0 steps
complete within one sample. The ramp machinery is not the slow thing; nothing is.

#### ⚠ CORRECTION — an earlier attempt the same day reported a "250 ms floor". It was wrong.

That attempt polled the **EPICS readback** `DRVMTRX_{r}_{c}` after `LOAD_MATRIX`
and saw ~250 ms regardless of TRAMP. **That is the readback scan rate, not the
actuator.** Measured on this front end from monitor callbacks: `LES_YAW_INMON`,
a continuously-changing channel, updates at **8.0 Hz (125 ms median interval)**.
The 250 ms "floor" is two of those.

> **EPICS readbacks cannot be used to measure front-end latency here.** Use a DAQ
> channel (`_OUT_DQ`, 1024 Hz) and a signal that is actually flowing.

Also note monitors fire on *change*: `DRVMTRX_2_2`, `V2_OUTMON` and `DRV_FREQ`
produced 0–1 callbacks in 12 s simply because they were static, which is not a
statement about their update rate.

#### Consequence for a feedback loop

| element | time |
|---|---|
| camera frame interval at 50 fps | **20 ms** |
| angle from a raw array | 0.14 ms (0.78 ms in `rotor_angle_loop.py`, larger box) |
| `caput` | 0.44 ms |
| matrix → DAC | < 1 ms |

The camera is the slowest element by ~20×. *(INFERRED, not tested: this supports
letting the front end synthesise the waveform at 16 kHz while Python writes
setpoints at camera rate. No loop has been closed.)*

#### New tool and a camera fact

`camera_utils/rotor_angle_loop.py` — in-process angle at frame rate, pypylon →
numpy → angle, no files and no JPEG. Measures only; commands nothing. Sustained
**50.0 fps, 0.78 ms/frame** live.

⚠ **The Basler is held EXCLUSIVELY.** One process at a time: `grab_basler.py` and
`rotor_angle_loop.py` cannot both run, and whichever opens first wins. The loop
writes `/dev/shm/rotor_angle_latest.jpg`, a *different* path from
`basler_latest.jpg`, so a viewer pointed at the usual file shows a frozen frame
rather than failing visibly.

#### Open, unexplained

- Live detection ran **31% good** where the same code on the 17:03 recording gives
  **83%**. Not the search box — two different boxes give identical results on the
  recording (centre 106.0,175.9, radius 29.8 px, 83%). Unexplained.
- An earlier claim in-session that the camera had moved further back was **wrong**;
  it came from reading an ill-conditioned circle fit as a measurement.
- A 3× harmonic carrying 25% of the orbit's radial variance. No candidate cause.

### 2026-10-21/22 — rotor centred on the board to 0.02–0.05 mm; board GND wired

- **Centring** (flight rotor on the rev G flex, top-down microscope, microscope
  straightened first). The rotor-edge circle fit, measured against the board centre
  (via ring + CTR disk, agreeing to 9 µm), gives |δ| = 19, 22, 48, 46 µm in four
  photos with different lighting. The spread between lighting setups is the
  systematic error. Torque factor J0(8δ/1 mm) ≥ 0.96, so no re-centring is needed.
  An earlier 0.09–0.12 mm reading with the microscope tilted was probably partly
  parallax. Details, script and the fit-window pitfall are in
  `analysis/rotor_centering/README.md`.
- **Board ground:** the 1/4" magnet only overlaps the bottom GND contact ring
  (r 2.95–3.40) by ~0.23 mm, so the ring never made contact. Fix: 22–24 AWG
  insulated wire soldered to a top GND pad (r 10.8 mm, az 60°/240°), crimped into an
  MB-R6 ring lug under a base screw. The magnet and base were already grounded.
- PEEK height is now set with the stainless shims **under the PEEK plate**, not
  under the pads (a metal shim under a pad shorts that phase to the bare GND around it).

### 2026-10-14 — stator drive: the rotor is DRIVEN at f_elec/8 but NOT carried round

> **Provenance.** MEASURED: all LES amplitudes/rms, the video coherence and centroid
> figures, the 6 h quiet baseline, both drive runs. DERIVED (Claude's arithmetic,
> unchecked by Molly): the 0.030 Hz mechanical frequency and `k_off`. Molly's direct
> visual observation is noted as such.

**Headline: the rotor is driven at f_elec/8 but is not carried around by the wave —
synchronised in frequency, not locked in the motor sense.**

Two runs of `stator_osc_drive.py hold --felec 0.08 --amp 6400 --duration 400 --live
--enable-outputs` (rotor 0.0100 Hz commanded), front-end GPS **1476056543–1476056950**
(from rest) and **1476057672–1476058080** (from leftover motion).

| | LES rms (cts) | line at 0.0200 Hz (f_e/8) | at 0.0400 Hz (f_e/4) |
|---|---|---|---|
| run 1 before | 15.6 | 2.6 | 1.6 |
| **run 1 during** | **304.9** | **150.6 (SNR 24)** | 56.4 |
| run 2 before | 287.8 | 22.6 | 18.4 |
| **run 2 during** | **325.2** | **65.7 (SNR 8.4)** | 39.7 |

- **Rotor was genuinely at rest first** — 6 h with no drive and no laser (V2 rms = 0 in
  all 72 five-min bins, PD = −1) showed **no libration line at all** in 0.03–2 Hz. Video
  coherence 1.000, centroid stable to 0.10 px. This is the Test A answer: *neither
  librating nor rotating*, which is why Test B's premise (a line to shift) did not hold.
- **Drive on ⇒ 19× rms jump**, line within one bin of the f_e/8 prediction, twice.
- **It did not go round.** Video `|⟨e^{2iθ}⟩|` = 0.670 / 0.658 during drive; four turns
  would give ≈0.04. Noise only reduces coherence, so this is a bound.
- **Starting from motion barely changed the driven state** (coherence 0.670 vs 0.658,
  centroid rms 3.21 vs 3.16 px) but halved the drive line — pre-existing motion competes
  with capture rather than helping it.
- **Molly observed directly:** sometimes forward motion with sudden backward slips,
  sometimes back-and-forth — consistent with a drive at its capture threshold.
- **Free oscillation at 0.0600 Hz** (117 cts, SNR 25.6) seen in run 2's pre-drive window,
  excited by run 1. This is the f_off that Test A could not measure on an unexcited rotor.
  The drive suppressed it, 117 → 27.5 cts.
- **Preliminary answer to the plan's open question:** the response sits at f_elec/8, not
  the backward f_elec/4 — the 0.0400 Hz line was smaller in both runs. One frequency, two
  runs; not conclusive.

⚠ **`--amp 6400` is the ceiling** (amp + pedestal = 12800 = `V{n}_LIMIT`, keeping the HV
amp input inside 0–2.1 V). No more drive torque is available in software, so the deficit
has to be closed by geometry — which is what the hardware change below is for.

#### ⚠ V² test ATTEMPTED and INCONCLUSIVE — do not read a scaling out of it

A third run at **`--amp 3200`** (FE GPS **1476062143–1476062550**) was taken to test
τ ∝ V². **It does not measure the scaling and must not be quoted as if it does.**

| run | amp | start state | 0.0200 Hz line during |
|---|---|---|---|
| 1 | 6400 | at rest | 150.6 cts |
| 2 | 6400 | in motion | 65.7 cts |
| 3 | 3200 | in motion | 95.1 cts |

Halving the amplitude *raised* the line (ratio 0.69 against the 4.00 that V² predicts),
but **the initial condition alone moves the answer by 2.3× at fixed amplitude** — runs 1
and 2, both at 6400. The systematic is bigger than the effect. The three runs also began
from genuinely different states: the 0.0200 Hz line *before* the drive was 2.6, 22.6 and
1.6 cts respectively.

**Why it failed, for whoever retries it:** the test needs both amplitudes started from the
*same* condition, and the only clean one is rest — which took hours to reach after a drive.
It cannot be done back-to-back in an evening. Either allow the rotor to settle fully
between points, or find a reproducible way to prepare the initial state.

Two observations that do stand, independent of the scaling question:
- **The drive still couples strongly at half amplitude** — 95.1 cts, SNR 16.4 at
  `--amp 3200`. It did not switch off.
- **The driven rms is the same in all three runs** — 304.9 / 325.2 / 320.0 cts —
  independent of both amplitude and starting state. **Unexplained.** For a mechanism that
  should go as V² this is worth noticing rather than explaining away.

**Still open:** how far from the capture threshold the drive is. That remains unmeasured. Also unresolved: rocking vs slipping, rotation direction, and
whether 0.0600 Hz is really the trap frequency.

**Camera note:** `grab_basler.py` default `--exposure 2.0` saturates ~19% of the frame and
destroys the sail-angle measurement; **0.5 ms** works. The `/dev/shm` snapshot is throttled
to 2 Hz by `--snapshot-every 0.5`, fine below ~0.5 Hz rotor but aliased at the 1 Hz target
— use `--record` for anything faster.

### 2026-10-09 — new pickoff + beam realignment: PD is good again, and the LES signal axis FLIPPED

> **Provenance of this entry — written by Claude, not yet reviewed by Molly.**
>
> **MEASURED** (raw readings, Molly's or read live off the front end):
> the Ophir power / PD table; the LES PIT-vs-YAW amplitudes, SNRs and kurtoses;
> the 150 s → 600 s window comparison; the x–y phase and correlation; the GPS
> offset; the harmonic amplitudes behind the divisor check.
>
> **DERIVED** (arithmetic on the above — each is an inference, not a reading):
> "PD linear to ±4%" and the 411 counts/mW scale; "11.10 µW/count above 764"
> (a fit to five points); the 814× ND ratio; "DIVISOR = 2" (an interpretation of
> the harmonic pattern, though it agrees with the independent 09-14 timing);
> the `T ≈ sqrt(1/|df/dt|) ≈ 100 s` coherence limit; the per-block PD standard
> error.
>
> **Nothing here has been cross-checked by a second method except the divisor.**
> Treat the derived items as working numbers to be re-established, not as facts.

**Front-end GPS offset re-measured: +12833 s** (9876 on 09-11, 10155 on 09-14). It wanders
and it is accelerating. Re-measure every session.

#### The pushing beam, the ND30, and the pickoff

The pushing beam was cleaned up and the pickoff replaced, and **an ND30 now sits upstream
of both the pickoff and the chamber**. Measured with the Ophir at the chamber:

| counts | mW | PD | | counts | mW | PD |
|---|---|---|---|---|---|---|
| 1300 | 5.94 | 2440 | | 1150 | 4.29 | 1750 |
| 1250 | 5.40 | 2225 | | 1100 | 3.72 | 1545 |
| 1200 | 4.87 | 1980 | | 1300 + ND30 | **0.0073** | **2.35** |
| | | | | 0 | — | −0.80 (−0.85 with PD blocked) |

- ✅ **The PD is LINEAR to ±4% across an 814× range** — 411 counts/mW at 5.94 mW, 408 from
  the high-power slope, **432 at 7.3 µW**. This **supersedes the 2026-09-15 warning** that
  the PD was misaligned and must not be used as the power axis. It is a good power axis
  again. Supersedes the 283 (07-28) and 203 (08-03) scales.
- **Commanded→power is now 11.10 µW/count above a 764-count threshold** (was 11.87 above
  735 — 6% apart, consistent).
- **The ND30 measures 814×, i.e. OD 2.91**, not the nominal OD 3. Measure a stack, never
  assume it.
- ⚠ **`LASER_OFFSET = 0` is a TRUE optical off**: PD reads −0.80 unblocked and −0.85
  blocked, a 0.05-count difference, so essentially no light. July's 15.9 µW sub-threshold
  leakage is killed by the ND (→ ~20 nW at the sail). Software chopping with
  `laser_on.py` / `laser_off.py` is therefore clean and needs no shutter.
- ⚠ **A PD reading of ~0 at `LASER_OFFSET = 1300` is EXPECTED with the ND in**, because the
  pickoff now sits downstream of it (7.3 µW → ~3 counts). Do **not** read it as the
  2026-10-06 loose-MOD-cable failure. The 3.15-count step above dark is still a usable
  monitor: at 1024 Hz over a 600 s block its standard error is ~0.02 counts, 0.6% of the
  step. Check the dark level at the start *and* end of a session — drift there is the only
  thing that breaks it.
- The ND being in the science path promotes the existing open item **"tilt the ND filter to
  break the air-gap etalon"**: an untilted ND's transmission drifts with temperature, which
  would masquerade as a slowly changing force. The pickoff sitting *downstream* of the ND
  means the PD sees that drift — that is the compensation for losing absolute power
  monitoring.

#### ⚠ The LES signal axis has FLIPPED — track `LES_PIT`, not `LES_YAW`

Measured live on a rotating rotor, 150 s window, electrodes off:

| axis | DC | line amp | SNR | rms | kurtosis |
|---|---|---|---|---|---|
| **PIT** | +1362 | **397 cts** | **511** | 341 | −0.77 |
| YAW | −7357 | 148 cts | 212 | 167 | −0.81 |

Reference, `noise_budget_20260911_clean` **on LES_YAW**: line amplitude 331–539 counts,
median SNR 622. So PIT is now within ~20% of that reference and YAW is 3× worse.
Frequency precision goes as 1/SNR, and σ_f *is* the measurement in every force estimate —
so **the beam does not need moving, but the channel does.** `settled_check.py`,
`monitor_libration.py`, `track_spindown.py` and both noise-budget notebooks all still
default to `LES_YAW`. `LES_SUM = 80` is low versus 240 on 09-11 but irrelevant: SNR, not
light level, is the limit.

**x–y is usable again.** Both axes now see the motion (amplitude ratio 2.75:1, against the
old 1000:1). At the dominant line the relative phase is +2.4° with corr(x, y) = +0.81 — a
**line, not an ellipse**, so no whirl and no handedness to read. Rotation direction still
needs the camera.

#### DIVISOR = 2 confirmed independently, from the comb rather than by timing

A genuine line sits at 0.3550 Hz (44 counts) under a dominant 0.7100 Hz (137 counts), with
4f at 28 counts and the odd harmonics suppressed (3f = 8, 5f = 7) — exactly a 2-fold sail.
So the dominant line is 2f and rotation = dominant/2. This is a **third** independent route
to the same answer as the 09-14 stopwatch re-timing, and it needs no video.

#### ⚠ Coherent FFT window limit ≈ 100 s on a coasting rotor

Widening the analysis window from 150 s to 600 s made the measurement **worse**: PIT SNR
511 → 114 and amplitude 397 → 137. A coasting rotor chirps, and at the measured −1.0e-4
Hz/s the line smears across ~37 bins in 600 s. The limit is `T ≈ sqrt(1/|df/dt|) ≈ 100 s`.
**Use 100–150 s windows, or demodulate** — which is why `noise_budget_20260911_clean` made
demodulation its primary estimator. Do not widen a window expecting finer resolution.

#### New tool

`lab_utils/track_drive.py` — live rotor-frequency tracker for the electrode run. Reports
f_elec, f_rot and the **slip ratio** once per poll, plus SNR and the rotating/librating
kurtosis. Reads NDS2 rather than `cdsutils.getdata` (which streams in real time and so
blocks for the full window). **Derives the fundamental from the comb, with no divisor
constant anywhere in the file.** Validated against the 09-11 record: returns 0.7489 /
0.7487 / 0.7492 Hz at +1 h / +2 h / +10 h, matching the notebook's 0.748876 Hz.

```
python3 lab_utils/track_drive.py --h5 scan_fwd.h5          # headless, for an overnight run
python3 lab_utils/track_drive.py --gui --h5 scan_fwd.h5    # + live plot (needs DISPLAY)
```

`--h5` appends and **flushes one row at a time**, so a kill, a dropped ssh session or a dead
X server costs at most the poll in flight; re-running against an existing file appends
rather than truncating. `--gui` plots f_rot against the commanded f_elec/8 (the gap is the
slip), SNR and kurtosis, and the accumulating **f_elec → rotor curve**, which is the
deliverable of the scan and is expected to be non-monotonic. Acquisition runs in a daemon
thread so a fetch never freezes the window, and both paths call the same `poll_once()`, so
the plot cannot drift from the validated CLI.

**The GUI works over `ssh -X`/`-Y`**, and is built not to abuse it: it repaints only when a
new estimate actually arrives, rather than on a fixed animation tick. `FuncAnimation` would
have redrawn the whole canvas every interval regardless — at 1 Hz against a 60 s data
cadence that is ~60× more repaints than there is new data, which is barely noticeable
locally and is exactly what makes a forwarded plot feel sluggish. `--gui-interval` (default
2 s) only sets how often it checks.

#### ⚠ Two drag laws are in the repo and they disagree — unresolved

| source | law | γ | τ₀ |
|---|---|---|---|
| `damping_law_comparison.ipynb`, this log | τ_drag = τ₀ + γω | 3.53e-15 N·m·s/rad | 8.06e-16 N·m |
| `noise_budget_20260911_clean` | linear, γ = I/τ_mech | **2.2974e-15** | none |

γ differs by 1.5× and the constant term vanishes entirely. Both are in active use. Which is
right changes every sensitivity estimate in the programme. **Do not silently adopt one** —
see `docs/STATUS.md`.

