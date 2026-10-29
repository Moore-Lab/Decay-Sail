# Calibration history

Which constants were valid for which apparatus state, and which datasets were taken
in which state. Current values are in `docs/DECISIONS.md`; this file is for
re-analysing older data. Moved here from `apparatus_log.md` on 2026-10-29.

## Vacuum (July–August 2026)

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
| commanded→power | 11.87 µW/count above 735 | ≤ 2026-10-08 | **superseded: 11.10 µW/count above a 764-count threshold, measured 2026-10-09** (−6%, consistent) |
| PD counts/mW | 283 | 07-28 → 07-31 only | 203 on 08-03 (−28%). **Both superseded: the pickoff was replaced and reads ~411 counts/mW, measured 2026-10-09** — see the 2026-10-09 entry |
| lever arm | r_c = 2.625 mm | ≤ 2026-10-08 | **superseded: `R_EFF = 1.38 mm`** (wing centroid), with `R_TIP = 1.88 mm` for geometry comparison — `noise_budget_20260911_clean.ipynb` |
| `TAU_FREE_S` | 67.65 min | ≤ 07-27 only | tilt stage present |
| `REQ_UW` | 0.735 µW/√Hz | ≤ 07-27 only | derived from the above; **1.86 µW/√Hz** post-tilt |
| `I_KGM2` | ~~1.88e-11~~ → **1.1e-11** | **superseded 2026-09-30** | 1.88e-11 was a calc with an older 2×2 mm sail and a heavier disk model; SolidWorks 1.7e-11 is also too heavy (11.05 mg CAD). Now from the **weighed 7 mg** assembly + model shape, ±10%. See the 2026-09-30 log entry and `docs/DECISIONS.md`. Dated notebooks still using 1.88e-11 have torques/forces ×0.585 too high. |
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
