# ND 0.5 in the LES beam, 2026-11-04: does the LES light push on the rotor?

Interpretations are Claude's and marked "(interpretation, not approved)". Everything else is measured or derived as
labelled.
- **Why:** Molly wants less light on the rotor (less optical force), so ND 0.5 goes back in the LES beam. A still
  rotor is a sensitive test: a steady light torque would move its rest angle when the light changes.
- **Run:** worker2 agent, read-only (video + LES only, nothing driven). `grab_basler.py --exposure 15 --record
  --duration 630`, host 16:33:12–16:43:43Z, FE GPS 1477860791–1477861422.
- **ND times:** out until the 16:35:52Z cue, then in at 16:36:27Z, out at 16:40:02Z, in at 16:42:09Z (Molly's
  confirmations; each move took 8–15 s). Lab mate's system changed pressure at 16:37:06Z (Molly).
- **Data:** Dropbox `Microspheres/TFINER/data/nd_test_2026-11-04/` (video, frame CSV, LES YAW/PIT/SUM 1024 Hz,
  notes.txt).
- **Method:** the camera was moved slightly on 2026-11-03, so the tracker's stored centre and template no longer
  apply. `spot.py` uses no tracker:
  - it takes the white spot's intensity-weighted centroid every 5th frame (10 fps);
  - it subtracts the board's own image shift (phase correlation on a static board patch), which stayed below 0.3 px;
  - then it fits position = slow drift (quadratic) + a step whenever the ND is in, excluding the handling windows.

## Results

**Transmission (measured):** LES_SUM fell from 72.5 / 74.3 to 26.7 / 27.3 counts, so ND 0.5 passes **37%** (nominal 32%).
The ND was out/in/out/in, as cued.

**Rotor rest position vs ND (measured):**

| | Spot x, px | Spot y, px |
|---|---|---|
| Out (first) | 96.86 | 157.75 |
| In (first) | 96.69 | 157.94 |
| Out (second) | 96.42 | 158.35 |
| In (second) | 96.21 | 158.60 |

- **The position does not alternate with the ND.** It drifts steadily, by about 1.4 px over 10 min.
- **Fitted ND step:** x +0.05 ± 0.28 px, y −0.08 ± 0.34 px. The ± is rough: residuals averaged in 10 s blocks.
- **No light-driven shift is detected.**
- (Derived, rough.) The spot is ~25–30 px from the rotation centre (not measured since the camera moved), so 1 px ≈ 2°.
  The 2σ bound of ~0.6 px is a rest-angle change below ~1.3°. With I = 1.1e-11 kg m² and the 1× trap of
  4.94 rad/s² (F2), the change in light torque between full and 37% light is below ~1.3e-12 N·m. That bounds
  the full-beam torque at ≲ 2e-12 N·m, a few percent of the trap.

**The "still" rotor is not still (measured):**
- The spot moves with 0.85 px rms, about ±2°.
- That motion is dominated by **0.735 Hz**: about twice the 0.35 Hz swing frequency. Not explained.
- The motion fell over the 10 min: x std 1.0 → 0.63 px.
- The 16:37:06Z pressure change shows no clear step: −0.18 / +0.20 px, inside the scatter.

**LES with the ND (measured):**

| | Fast noise above ~10 Hz, counts rms | Slow motion signal, peak-to-peak |
|---|---|---|
| Without ND | YAW 4.0–5.1, PIT 3.7–4.1, SUM 0.20–0.22 | YAW 154–245, PIT 91–127 |
| With ND | YAW 3.8, PIT 3.7, SUM 0.17 | YAW 71–161, PIT 51–64 |

- The fast noise barely changes, so it is **electronic** (it doesn't scale with light).
- The signal drops with the light, so LES signal-to-noise falls by **~2.5×** with the ND in.
- The PIT mean moves from ~110 to ~700–750 counts when the light drops, so PIT carries a light-independent offset.
  Not interpreted.

## Open

- The 0.735 Hz motion of the "still" rotor.
- The slow drift: 1.4 px in 10 min.
- The rotor rest angle moved ~20° since F2 (worker2's pinned-centre reading 207° vs 227°).
- The tracker needs recalibrating after the camera move before F3.
