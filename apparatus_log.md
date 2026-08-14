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
  τ = 67.65 min becomes ~1.6 µW/√Hz at τ = 14.5 min**. The rotor response corner γ/2π
  moves ~0.039 → ~0.18 mHz.
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
| spindown (accidental) | 08-03 → 08-04 | no | good | PBS251 pickoff |
| stability run | 08-04 → 08-05 | no | good | PBS251 pickoff |

τ_free = 67.65 min applies **only to the first row**.

---

## Known-stale constants

| constant | value | valid for | note |
|---|---|---|---|
| commanded→power | 11.87 µW/count above 735 | ≤ 07-20 | **~44% high on 08-03** — see below |
| `TAU_FREE_S` | 67.65 min | ≤ 07-27 only | tilt stage present |
| `REQ_UW` | 0.735 µW/√Hz | ≤ 07-27 only | derived from the above; ~1.6 µW/√Hz post-tilt |
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

## Throughput discrepancy — commanded counts vs delivered power

On the 2026-08-03 run the laser was commanded to **1400 counts**. The 2026-07-20
calibration (11.87 µW/count above a 735-count threshold) predicts **7.89 mW**; the PD
read 1550 counts, which at the 283 counts/mW measured against the Ophir on 07-28 / 07-31
is **5.48 mW** — the commanded figure is **~44% high**.

The commanded calibration is self-consistent for July: it reproduces the step table's
1600 cts = 10.34 mW (as 10.27) and 1400 cts = 8.0 mW exactly. So it was right *then*.
The PD figure is the better anchored one now — 5.5 mW sits between the two meter
calibration points and the chain measured 1.4% linear across them.

So throughput to the chamber appears to have dropped ~30% between 07-20 and 08-03.
Candidates: the 07-27 realignment, the PBS pickoff diverting its share, or drift in the
laser itself. **Unresolved** — re-running `lab_utils/laser_power_calibration.py` would
settle it, and until then commanded counts should not be converted to power for any
post-07-27 dataset.

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
- [ ] Re-run `lab_utils/laser_power_calibration.py` — the commanded-count→power
      calibration is ~44% high against the PD on 08-03 (see above). Until it is redone,
      commanded counts cannot be converted to power for post-07-27 data.
- [ ] Measure `I` directly rather than inheriting it — the electrode drive gives it from
      the high-frequency asymptote of χ(f).
