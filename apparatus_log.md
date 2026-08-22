# Apparatus change log

Dated record of physical changes to the rotor / optics / vacuum system, and what each
one invalidates. Analysis notebooks assume constants (γ, counts/mW, the thermal floor)
that are only valid for a particular apparatus state — this file is the record of which
state each dataset was taken in.

**Add an entry whenever anything in the beam path, the chamber, or the readout chain
changes**, even if it seems minor at the time. A change that is obvious in the lab is
invisible in an HDF5 file six months later.

Entries are newest-last. Dates are UTC unless noted.

---

## Changes

### 2026-07-27 — PD realigned, low-noise amplifier removed

The photodiode was poorly aligned through the step-down run, and a low-noise amplifier
in the PD chain was contributing significant noise. Both fixed on this day, before the
3 mW noise run started at 20:51 UTC.

- **Invalidates:** all PD-derived quantities from the 07-05 → 07-09 step-down run. A
  misaligned diode converts beam-pointing drift into apparent power drift, and the amp
  added noise that never reached the sail.
- **Consequence for correlation work:** PD noise not common with the rotor inflates
  `S_PP` and biases coherence `γ²(f)` **downward** (errors-in-variables), so any
  PD↔rotor coherence from the step-down run understates how much of the rotor's wander
  the laser explains. Use post-07-27 data for that analysis.
- The YAW channel is unaffected — rotor-frequency stability comparisons across this
  boundary remain valid.
- PD gain changed with the amp removal: ~16.2 counts/mW before, ~281–285 after.
  **Never reuse a κ quoted in N·m per PD count across this boundary**; convert to
  physical power first and use torque per mW, which is gain-independent.
- Measured PD linearity after the change: 280.6 vs 284.6 counts/mW over 3.03 → 10.40 mW,
  i.e. **+1.4%** — the chain is linear across the operating range.

### 2026-07-27, later the same day — tilt stage removed from the chamber

The chamber no longer has the tilt stage. The damping constant is **worse** as a result.

- **Invalidates:** τ_free = 67.65 min (measured 2026-07-02, tilt stage present) for
  everything after this point.
- **Propagates to:** the thermal torque floor `S_N = √(4k_BTγI)` scales as √γ, so the
  power-noise requirement `δP_req = S_N/(∂N/∂P)` moves with it — **0.735 µW/√Hz at
  τ = 67.65 min becomes ~1.86 µW/√Hz at the measured τ = 10.5 min**. The rotor response
  corner γ/2π moves 0.039 → 0.25 mHz.
- **Measured post-change value: τ = 10.5 ± 0.1 min** (`spindown_20260803.ipynb`). The
  electrodes drove the rotor at 3.9000 Hz phase-locked and switched off at t = 31.94 min;
  the laser stayed on, so the decay is fitted as a driven relaxation
  `f_ss + (f₀−f_ss)e^(−γt)`. The free-decay formula `γ = −(df/dt)/f` reads `γ − A/f` when
  a drive is present and returns ~11.1 min. Curve fit and model-independent regression
  agree to 0.1% (10.54 / 10.55 min). **Damping is 6.4× worse than with the tilt stage**,
  giving a thermal floor 2.53× higher and a requirement of ~1.86 µW/√Hz in that
  configuration.
- **Harmonic caution for all YAW work.** The dominant YAW line is the sail's **second**
  harmonic — two wings pass the sensor per revolution — so the Hilbert locks to 2× the
  rotation rate. Confirmed against the known electrode drive: the 3.898 Hz line equals
  the 3.9000 Hz drive to 0.05%, and 7.797 Hz is 2×. γ is immune (all harmonics decay at
  the same rate) but every *rate* must be divided by 2. Getting this wrong pushed the two
  γ methods 3% apart and doubled the fit residual; fixing it brought them to 0.1%.
- Still worth a deliberate **laser-off** spindown once the new stage is in, so the simple
  free-decay model applies and no drive term has to be fitted alongside γ.
- Note on timing: this happened the same day the 3 mW DARK record began (20:51 UTC), so
  that record may straddle it. It does not matter for the dataset itself — that run
  measures *laser* noise, with no rotor involved. It matters only for which γ the
  requirement is computed against.
- **A replacement tilt stage is on order**, to be installed and aligned to best tilt.
  The no-tilt period is therefore a temporary excursion, not the end state. τ after
  realignment will need re-measuring — it will not necessarily return to exactly
  67.65 min, since that value belongs to the *old* stage at its own alignment.

### Before 2026-08-03 — power meter moved onto a pickoff (Thorlabs PBS251)

The Ophir head no longer samples the full beam. It sits on the **rejected port of a
PBS251 polarizing beamsplitter cube** ("not in the main direction"), reading roughly
5–10% of the beam (~540 µW against a PD implying ~5–7 mW at the chamber). Ratio
inferred, **not measured**.

- ⚠️ **This pickoff amplifies polarization noise.** The sampled fraction is sin²θ, so
  its fractional sensitivity to a polarization drift is `sin(2θ)/sin²θ` ≈ 6 per radian
  at θ ≈ 18°, versus `sin(2θ)/cos²θ` ≈ 0.67 per radian for the transmitted beam the
  rotor sees — roughly **9× amplified**. A 1 mrad polarization wobble reads as 0.6% on
  the meter but only 0.07% on the beam. Any polarization drift (thermal, fiber stress)
  therefore appears on this channel as power noise that the rotor never experiences.
- **Consequence:** for `260803-12_*.txt` the meter is **not** a clean independent power
  witness. Its excess over the PD should be assumed to be polarization until shown
  otherwise. This defeats the PD↔meter cross-check that worked on the earlier logs.
- **Invalidates:** absolute mW from those logs, until the pickoff ratio is measured.
- **Recommended fix:** replace with a non-polarizing pickoff — an uncoated **wedged**
  window (~4% Fresnel), largely polarization-blind near normal incidence, and wedged so
  the two surface reflections cannot form an etalon.
- Earlier logs (`260728_laser_power.txt`, `260731_laser_power_10mW.txt`) predate this and
  do read chamber power directly, head-on.

### Not done — ND filter tilt

Recommended 2026-07-20 to break the air-gap etalon around the reflective ND in the PD
filter stack (notch → reflective ND → PD), which produces a ±12 count wiggle and makes
the PD non-monotonic vs true power in the 1500–1800 commanded-count range.

**Never done.** The etalon is still present in all data to date. Note that the PD and
the head-on meter nonetheless agreed to 0.2% at 0.3–1 mHz on the 07-28 run, so the
etalon is not dominating at those frequencies — but it remains a candidate for
anomalies at the count levels above.

### 2026-08-21 — first stator drive that measurably moved the rotor

First runs of `lab_utils/stator_epics_drive.py` (EPICS-only, offsets on the electrode
filter modules). Two DC detent runs, `--cycles 1 --dwell 180`, laser OFF, no shim
(gap 0.37 mm), rotor already librating from earlier activity. Video via
`grab_basler.py --record --fps 10`, analysed with `camera_utils/analyze_detent_video.py`.

| electrode | 6400 counts | 3200 counts |
|---|---|---|
| pre-drive | rms 22.5 | rms 19.9 |
| **A (V2)** | **rms 8.6 — captured, 2.6x quieter** | rms 19.8 — no effect |
| B (V3) | rms 24.0 | rms 21.2 |
| C (V4) | rms 23.0 | rms 23.7 |
| post-drive | rms 21.1 | rms 23.8 |

**The result: at 6400 counts, energising V2 collapsed the rotor's motion 2.6x and held
it quiet for the full 180 s. That is a detent capturing a moving rotor — a static
torque the four side posts could not produce at any drive level.** At 3200 counts the
same electrode did nothing.

**Only V2 is demonstrated; V3 and V4 are untested, not shown broken.** The rms returning
to ~24 when the detent moved to V3 is *not* evidence V3 did anything — switching from V2
to V3 releases V2's detent and applies V3 in the same instant, and a return to the
pre-drive amplitude (22.5) is fully explained by release alone. More generally an
A→B→C walk cannot compare electrodes: capture depends on where the rotor is and how fast
it is moving when the field switches on, so the first electrode meets a settled rotor and
the rest meet one the earlier steps just stirred up. Use `detent --phase` (added
2026-08-21) to give each electrode the same test.

**So the capture threshold for the rotor's libration energy that day lies between 3200
and 6400 counts.** Since tau ~ V^2 that is a factual bracket on the drive torque, and
the first quantitative statement this apparatus has made about the stator. It does not
yet give tau in N*m, because `VOLTS_PER_COUNT` is still unmeasured.

**What did NOT work.** Extracting a libration frequency to get tau from
`tau = (2 pi f)^2 I / m`. PC1 explains only ~30% of the masked variance and the peak
frequencies scatter (0.25, 0.38, 0.77, 1.2, 1.3 Hz) with no consistent scaling between
the two drive levels — the motion is multi-mode, not one clean oscillator. Treat the
capture bracket as the result and the frequencies as not yet interpretable.

**Two analysis traps, both hit for real before being caught** (guards now built into
`analyze_detent_video.py`, which prints both on every run):

1. Selecting the highest-variance pixels finds steep spoke edges, where the ~0.14%
   lamp ripple looks like large motion. This produced a confident and entirely wrong
   "the rotor oscillates at 0.78 Hz" from a clip in which nothing moved.
2. Coherence with frame brightness does **not** prove artefact: the rotor is a few
   percent of the frame, so real motion modulates the frame mean too. The correct
   discriminator is **localisation** — on-rotor vs off-rotor change ratio, 9.4x and
   19.0x on these two runs. Illumination lights the static mounts as well; motion does
   not.

Rotor motion persisted well after the drive was grounded, as expected with no laser
and hence no optical damping. `V{n}_TRAMP` was found at 1.0 s on all four electrodes,
which silently distorts any software-generated sinusoid; the drive script now zeroes it
for the duration of a run and restores it after.

### 2026-08-21, 16:12 — five-electrode `--phase` sweep (RESULTS PENDING)

Follow-up designed to fix the flaw in the morning runs: an A→B→C walk cannot compare
electrodes, because capture depends on where the rotor is and how fast it is moving when
the field switches on, so the first electrode meets a settled rotor and the rest meet one
the earlier steps stirred up. `detent --phase` gives each electrode the same test.

Sequence, 6400 counts, 3 attempts of 60 s with 30 s grounded between, 4:00 per electrode:

| electrode | start | role |
|---|---|---|
| V2 | 16:12:01 | control — the one that captured in the morning |
| V3 | 16:16:02 | first fair trial |
| V4 | 16:20:02 | first fair trial |
| V1 | 16:24 | **centre-disk test** — symmetric, so must show NO capture from any rotor state |
| V2 | 16:28 | control again — brackets the session against drift in rotor energy |

Laser off, no shim, gap 0.37 mm. Camera recording started 16:10:37 (so video t=0 is
16:10:37; the drive begins at t≈84 s), one continuous clip at 10 fps.

Artifacts, both on Dropbox at `Microspheres/TFINER/videos/`:
`output_basler_gps*.avi` (the sweep) and `phase_sweep.log` (the exact electrode start
times, which is what the analyser reads so no window boundary is guessed).

To score it:

```
python camera_utils/analyze_detent_video.py <video> \
       --sweep-log phase_sweep.log --dwell 60 --release 30 --attempts 3
```

Reports rms(ON)/rms(OFF) per electrode. Below 0.6 = capture, above 0.85 = nothing.
**Read the two V2 control blocks first:** if they disagree with each other, the rotor's
energy drifted across the 20 minutes and the electrodes in between are not comparable.

`V{n}_TRAMP` was again found at 1.0 s on all four at the start of the sweep — it resets
between runs, so anything writing offsets to these channels must zero it first or it is
fighting a 1-second ramp.

---

### 2026-08-22 — rotor librates ~20 h with drive AND laser off: floating/domed board suspected

Left the rotor after the 08-21 stator tests; it was still librating the next morning with,
as far as the records show, **no drive of any kind**:
- **Electrodes off.** Last real drive was the 16:33 08-21 sweep. `V{1-4}_OUT_DQ` is flat 0
  across the ~23:09 amp power-off window (±20 min) — no command or transient there. (The GUI
  power-off is an HV-amp state, not in `_OUT_DQ`.)
- **Laser off.** `RDS-PD_IN1_DQ` sat at the dark level (−1 ct, median=min=max) for the whole
  17 h overnight; commanded laser offset 0. So the optical libration spring is NOT involved.

LES is unaligned (to be fixed ~Mon 08-24), so the camera is the only readout. Two clips
scored with `analyze_detent_video.py` — both pass the localisation guard (ratio 30.6× and
16.3×; frame-flicker ~0.1%), so this is real motion, not the lamp-ripple trap:

| clip | time | motion rms | dominant f | PC1 |
|------|------|-----------:|-----------:|----:|
| `output_basler_gps1471403607` | 23:13 Fri | ~25.3 | 0.37 Hz | 38% |
| `output_basler_gps1471438107` | 08:48 Sat | ~25.9 | 0.61 Hz | 79% |

Over 9.6 h the amplitude did **not** decay — it slightly ROSE (25.14→25.41 within the first
clip; 25.3→25.9 between clips). Free decay can only shrink amplitude, so the growth argues
for a weak *sustaining drive*, not merely a high-Q ringdown. Either way a lower bound:
**libration τ ≳ 90 h** (≳100× the 67-min spin ringdown). The 0.37→0.61 Hz shift with PC1
38→79% is energy consolidating into one librational mode.

**Leading hypothesis (Molly, 2026-08-22): the board GND ring is not seated — doming.**
The board is 0.1 mm flex held only by the four r=9 mm screws, so the whole centre (GND ring
r=2.95–3.40 + CTR) is unsupported and can bow up, lifting the GND ring off the magnet. The
board's ground reference then floats and, beside the **charged** rotor, presents a stray
field that can pump the libration. This explains why *no amp state changed the behaviour —
the amp was never the variable*:
- **Board-on-metal does NOT ground the sector electrodes.** They are separate insulated nets
  (coverlay; no ground copper under the active area, by design). Only the bare GND ring
  grounds, and only by pressing on the magnet.
- **"Amp on, offsets 0" only grounds the sectors IF the amp output is low-Z at 0 V.** If it
  is high-Z at 0, both amp-on and amp-off leave the sectors floating, so a *true* ground
  (hard short A/B/C→GND) has never actually been tested. Confirmed librating in BOTH amp-on
  (pre-power-off) and amp-off (overnight).

Tests at the next chamber opening (some already on the first-article list):
- **GND-ring-to-magnet continuity/resistance** — open/high ⇒ doming confirmed. Top priority.
- Board flatness / does the centre sit proud when mounted.
- Does the HV amp hold 0 V low-Z, or go high-Z, when idle? (decides whether amp-on-0 counts
  as grounded).
- Interim mitigation *without* opening, if available: **neutralise the rotor charge**
  (protocol step 1) — the stray coupling needs rotor charge.
- Opening safety: amp OFF → verify 0 V → discharge electrodes/board to ground before
  handling (barrels live to ~80 V when driven); ground yourself for ESD on the de-energised
  board.

---

## Vacuum

Pressure ~**2.9e-7 mbar**, consistent across this period. No logger yet
(`lab_utils/log_pressure.py` written, gauge not recording).

Because pressure was steady, it is **not** the explanation for the elevated damping from
07-27 onward — that is the tilt-stage removal.

---

## Dataset → apparatus state

| dataset | window (UTC) | tilt stage | PD | meter |
|---|---|---|---|---|
| laser step-down | 07-05 → 07-09 | **yes** | misaligned + LN amp | none |
| 3 mW dark / ON | 07-27 → 07-29 | removed same day | good | at chamber, head-on |
| 10 mW noise run | 07-31 → 08-02 | no | good | at chamber, head-on |
| spindown (electrode drive-off) | 08-03 → 08-04 | no | good | PBS251 pickoff |
| stability run (1600 cts) | 08-04 → 08-05 | no | good | PBS251 pickoff |

τ_free = 67.65 min applies **only to the first row**.

---

## Known-stale constants

| constant | value | valid for | note |
|---|---|---|---|
| commanded→power | 11.87 µW/count above 735 | **still good** | verified to 3.6% by direct measurement 08-03 |
| PD counts/mW | 283 | 07-28 → 07-31 only | **203 on 08-03** (−28%); use measured chamber power |
| `TAU_FREE_S` | 67.65 min | ≤ 07-27 only | tilt stage present |
| `REQ_UW` | 0.735 µW/√Hz | ≤ 07-27 only | derived from the above; **1.86 µW/√Hz** post-tilt |
| `I_KGM2` | 1.88e-11 | assumed | from `momentum-simulation/thermal_noise_spindown.py`, never measured |
| `KAPPA_PD_OLD` | 7.35e-16 N·m/count | step-down gain only | do not reuse post-amp-removal |

### Decision: which γ goes in which notebook

The two uses of γ are different questions and take different values.

- **`laser_dark_vs_on.ipynb` keeps τ = 67.65 min** (tilt stage present). Its measurements
  are laser properties, unaffected by the chamber; the requirement line is a *design
  target* for the configuration the experiment is meant to run in. With a replacement
  tilt stage on order, that is the tilt-present state — so the 0.735 µW/√Hz line stands,
  and the 89× / 361× margins quoted against it are the honest ones. Re-drawing it ~2×
  looser to match a temporary no-tilt excursion would flatter the result.
- **`spindown_20260803` / `rotor_stability_20260804` need the measured post-tilt γ**,
  because they describe how the rotor actually behaved, not what it should achieve.

Revisit both once the new stage is installed and τ re-measured.

---

## PD scale shift — the PD, not the commanded calibration

On the 2026-08-03 run the laser was commanded to **1400 counts** and the chamber power
was **measured at 7.62 mW**. The 2026-07-20 commanded-count calibration
(11.87 µW/count above a 735-count threshold) predicts 7.89 mW — **agreement to 3.6%**,
inside its own repeatability. **That calibration is sound.**

What moved is the PD. It read 1550 counts for that 7.62 mW, i.e. **203 counts/mW**,
against **280.6** (07-28) and **284.6** (07-31) measured head-on against the Ophir. The
PD has lost **~28% of its response relative to chamber power**, between 07-31 and 08-03
— which is when the PBS pickoff was installed.

- **Use measured chamber power** for post-08-03 datasets, not the 283 counts/mW scale.
- The PD remains fine as a *relative* monitor (its 1.4% linearity was measured across
  3–10 mW); it is the absolute scale that has shifted.
- Worth finding out *why* — a 28% change in the PD's share of the beam suggests its tap
  was disturbed when the PBS went in.

### Consequence: the laser torque has dropped too

The 08-03 fit gives a drive torque of 2.03e-14 N·m at 7.62 mW, i.e. **2.66e-15 N·m/mW**
against the July calibration of **1.19e-14 N·m/mW** — **4.5× lower** (4.5–5.4× across the
f_ss method spread).

Combined with damping 6.4× worse, the sustainable rotation rate
`f_ss = κP/(2πIγ)` is **~29× lower than in July**. That is why the laser could not hold
the rotor at a power that would have worked before the tilt stage came out, and it is a
torque-coupling change as well as a damping change — worth separating once the new stage
is in.

---

## Open items

- [ ] Clean post-tilt γ measurement — driven-relaxation fit to the 08-03 decay, or a
      deliberate spindown. Needed by the spindown and stability notebooks.
- [ ] Install the replacement tilt stage, align to best tilt, and **re-measure τ** with a
      deliberate free spindown (laser off, so the free-decay formula applies). This
      becomes the new design-target γ for the requirement.
- [ ] Measure the pickoff ratio (meter at chamber vs meter at pickoff, one reading).
- [ ] Replace the PBS251 pickoff with a wedged uncoated window, or characterise the
      polarization drift so the amplification can be corrected for.
- [ ] Tilt the ND filter to break the air-gap etalon.
- [ ] Commanded laser counts before and after the 08-03 step (PD went 2359 → 1545).
- [ ] Get the pressure gauge logging.
- [ ] Find out why the PD lost ~28% of its response relative to chamber power when the
      PBS pickoff was installed — was its tap disturbed? Re-anchor counts/mW against the
      Ophir head-on.
- [ ] Separate the 4.5× torque-per-mW drop into beam-geometry vs sail-alignment causes
      once the new tilt stage is in.
- [ ] Measure `I` directly rather than inheriting it — the electrode drive gives it from
      the high-frequency asymptote of χ(f).
- [ ] Measure `VOLTS_PER_COUNT` (`stator_epics_drive.py calibrate` + a meter on the
      amplifier output). Until then the 3200–6400 count capture bracket cannot be turned
      into a torque in N·m. The old placeholder 0.03125 is provably wrong — it implies
      200 V at 6400 counts on an amplifier that stops at ~80 V.
- [ ] Narrow the capture bracket: detent runs at 4000 / 4800 / 5600 counts against a
      comparable starting libration amplitude. Note the threshold depends on the rotor's
      energy at the time, so record the pre-drive rms for each.
- [ ] Settle which `V{n}` is the centre electrode by continuity check at the next chamber
      opening. V2 captured the rotor on 08-21, so V2 has real angular authority and is
      *not* the centre disk — but that does not by itself confirm V1 is.
- [ ] Swap the ½" electrode stands for 4-40 vented screws and fit a ≤Ø5.8 mm, 0.1 mm
      shim. The stands are a live confound (tall conductors at r ≈ 9 mm) and the shim is
      worth 3.2× torque, which at the ~80 V ceiling is no longer optional.
