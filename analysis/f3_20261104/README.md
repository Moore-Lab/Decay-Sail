# F3, 2026-11-04: feedback spin-up, hold and brake through EPICS (live runs 1 and 2)

Interpretations are Claude's and marked "(interpretation, not approved)". Everything else is measured or derived as labelled.
- **Runbook and code:** branch `feedback-drive`, `lab_utils/FEEDBACK_HANDOFF.md` (F3). The controller is `feedback_drive.py run --f3`.
- **Data:** Dropbox `Microspheres/TFINER/data/feedback/f3/` (`preflight*`, `live1`, `live2`, `centre_fit`, `exposure_test`, `tracker_checks`).
- **Figures:** `python3 f3_plots.py` writes four figures to `plots/` (gitignored): `f3_live2_overview.png`, `f3_live2_hold_detail.png`,
  `f3_live2_trap_from_rotation.png`, `f3_live2_tracking.png`.
- **Target (Molly):** go over the top from rest; for 60 s every full turn at 0.4–0.6 rev/s with no reversal; then brake to a swing under 30°.

## Live 1 (20:16Z)

The watchdog stopped the run 4 s in. The swing grew from rest to ~±90° in ~4 s. Tracker ncc then fell to 0.75 at
320–340° from rest, below the 0.8 limit. Fixes, all checked read-only:
- exposure 15 ms;
- the second light adjusted;
- ncc limit 0.7.

The derived tracker centre (122.8, 179.6) holds: the spot radius stays 23.5–24.4 px over ±90°. The camera moved; the rotor didn't
(log 2026-11-04).

## Live 2 (20:41Z): `--f3 --amp 4000 --pedestal 6400 --mtramp 0.0625 --rest-deg 229.8 --ncc-min 0.7`

Loop FE 1477875691–1477875870. Measured from the tracker CSV (10276 frames, 0 dropped) and the drive log:
- **Spin-up:** started from a ~±70° swing; over the top 4.6 s after loop start. The field pushed for ~5 s.
- **"Hold" 60 s:** 33 full turns, each at 0.521–0.550 rev/s; no reversal. **The scorer's hold criterion passes.**
  **But the field was OFF throughout the hold:** the speed never fell below the 0.3 rev/s push limit (minimum ~0.33 near
  the top). So the rotor coasted on the spin-up's energy. **This shows the spin-up landed in the band, not that the
  controller held it.**
- **Coasting decay:** the per-turn rate fell from 0.556 to 0.521 rev/s over ~130 s with the field off.
- **Brake 90 s: failed.**
  - The field was off for the first ~20 s (the same speed limit).
  - A few brake pushes at 105–135 s brought the energy below the barrier at ~136 s.
  - Then, during the swings, pushes alternated in both directions and the energy rose back.
  - The rotor went over the top in the negative direction. At the end of the run it was turning at −0.55 rev/s, and it carried on with the drive off.
- **Tracking:** ncc 0.79–0.98 at all angles over the full circle, never below 0.7. Spot radius 21.5–25.2 px.
- **Outputs:** within 2400–10400 apart from ~670 samples per channel below 2400 while on; max |step| 171 counts per sample.

**The trap over the full circle (derived from the coasting hold, field off: energy conserved within each turn):**
- U(φ) − U(bottom) = ½ω_bottom² − ½ω(φ)²; see `f3_live2_trap_from_rotation.png`.
- The barrier is 9.4 rad²/s² per unit I, at about −165° from rest, not ±180°.
- The 1× model from F2 gives 9.88 at ±180°.
- The shape is asymmetric, consistent with F2's 2×–4× terms.

(Interpretation, not approved) Why the brake failed:
- The 0.3 rev/s push limit kept the field off while rotating.
- In the swing regime, brake pushes near the turning points used a lagging motion direction, so they pumped.

## After live 2

Changes on `feedback-drive`:
- `--push-max 0.4`;
- no brake pushes below `--brake-wmin 40` deg/s;
- `--brake-only` mode.

Simulation, with the trap barrier 9.36 vs the controller's 9.88 and loads every 2nd tick:
- the old settings never brake from 0.55 rev/s, as seen live;
- the new settings stop the rotation in ~3 s, to a ±12° swing;
- the full F3 passes.

## Brake-only 1 (21:01Z): `--f3 --brake-only --brake 120` (push_max 0.4, brake_wmin 40)

Loop FE 1477876900–1477877024. Measured:
- **The rotor had already fallen back into a large swing** before the run: 263° span, near the top of the trap. It had been coasting since live 2.
- **Pushes:** the field was on for only 44 log rows, all in the first ~3 s, at −88 and 167.
- **By 5 s it was rotating at −0.54 rev/s.** It reached −0.61 to −0.65 rev/s, then coasted with the field off: |speed| above 0.4 rev/s everywhere.
- **Still turning at the end:** −0.58 rev/s (LES 1.16 Hz). The brake failed again.

## Push angles measured from today's data (`push_angles.py`, live 2 + brake 1)

Method:
- Residual angular acceleration = tracker acceleration minus the trap's. The trap's comes from the live-2 coasting, with harmonics 1–4.
- That residual is fitted against the field–rotor angle Δ = ψ_commanded + 8θ, with 1× and 2× terms, scanning the command-to-field delay.
- 1097 field-on frames. With the field off, the residual is 0.00 ± 0.55 rad/s², which validates the trap model.

| Delay, s | R² | Best + push | Best − push | At −88 | At +167 |
|---|---|---|---|---|---|
| 0.07 | 0.60 | −50° (+2.9 rad/s²) | +154° (−3.2) | +1.8 | −3.1 |
| **0.10** | **0.63** | **−54° (+2.8)** | **+170° (−3.4)** | **+1.9** | **−3.4** |
| 0.15 | 0.40 | −33° | +176° | +0.3 | −2.8 |

- **The push angles in use (−88 / +167) have the right signs:** −88 accelerates + motion, 167 accelerates − motion.
  The measured best values are −54 / +170, at an effective delay of ~0.10 s.
- (Interpretation, not approved) So the brake did not fail because of wrong angles. Two more likely causes:
  - **near a swing's turning point,** a brake push acts ~0.1 s later, after the rotor has reversed, so it pumps;
  - **while rotating faster than 0.4 rev/s,** the field is off, so the brake never acts.
