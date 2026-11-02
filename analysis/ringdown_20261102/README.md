# Free-swing ring-down, 2026-11-02 (no drive)

This is a **libration ring-down**: the rotor swings in its trap and never turns fully round. It is NOT a spindown. The recorded damping (`docs/DECISIONS.md` 2026-10-30, τ_mech = 79.8 min) comes from true spindowns of a fully rotating rotor, measured until it stopped doing full turns. The two are compared below only under a stated assumption.

Interpretations in this file are Claude's and **not approved by Molly**.

The rotor's free swing after the C2 run, with nothing driving it.
- **Recording:** `videos/output_basler_gps1477678308.{avi,csv}` and `blob_live_gps1477678308.csv` (Dropbox `Microspheres/TFINER/`). Recorded by Molly with `live_blob_track.py`, 39.0 min, 116853 frames, 0 dropped.
- **Worker2 report:** `videos/ringdown_report_1477678308.md`.
- **LES:** `data/LES_video/Y1_RDS-LES_{PIT,YAW}_IN1_DQ_1477685294_1477696028.h5` covers the end of C2 through the end of this recording. Not analysed yet.
- **Tracking quality:** NCC median 0.836, lower than C2's 0.967, and flat across the recording, so the flashlight did not dim during it. The worker2 agent noted the lighting differs from C2. Gate 7 was not run on this recording.

Run: `python3 ringdown.py ~/Library/CloudStorage/Dropbox/Microspheres/TFINER/videos <C2 data dir>`. It fits A cos(2πft+p) plus a linear baseline in 60 s windows. One window, at 1590 s, failed to fit (A 0.5°) and is dropped. Plot: `plots/ringdown_20261102.png` (gitignored).

## Libration damping (measured)

- **Over this recording:** the amplitude fell 27.3° → 23.5° in 39 min, so τ_A ≈ 15000 s. The fit's ±150 s is optimistic because the windows overlap. Q = π f τ_A ≈ 16000.
- **Since the end of C2:** the swing went from ±105° (end of C2, true GPS ≈ 1477669949) to ±27° (start of this recording) over 8359 s, which averages τ_A ≈ 6200 s.
- **So the decay is faster at large amplitude, or it is not exponential.** Not resolved; the LES covers the gap.
- **Comparison with the recorded spindown (assumed: the same linear drag in libration and rotation).** τ_mech = τ_A/2 ≈ 3100–7500 s, against the recorded 4788 s (September, before the board and beam changes). Without that assumption, the libration data says nothing about rotational drag.
- **Drag vs drive torque (derived from the RECORDED spindown γ = 2.30e-15 N·m·s, not from this file):** at lock speeds of 0.0125–0.1 rev/s, the drag is γω ≈ 2 × 10⁻¹⁶ to 1.4 × 10⁻¹⁵ N·m. The design drive torque is ~10⁻¹² N·m. For drag to matter at these speeds, the spindown time would have to be ≲ 7 s. Interpretation, not approved: damping does not explain the missing lock.

## Swing frequency drifts with time (measured)

- **In this recording:** the frequency fell 0.354 → 0.319 Hz (10%) over 39 min while the amplitude changed only 27° → 24°.
- **Against the C2 drive-off gaps (all free swing):** f was 0.341 Hz at 47°, 0.335 at 53°, 0.326 at 57°, 0.285 at 96° and 0.275 at 100°.
- **The frequency is not set by amplitude alone.** At ~25° it was 0.354 Hz at the start of this recording and 0.32 Hz 39 min later. The direction is also wrong for amplitude softening: a softening well would raise the frequency as the swing shrinks, but here it fell.
- **So the C2 "frequency falls with amplitude" reading is confounded with time.** During C2 both the amplitude and the elapsed time increased. Cause of the drift: not investigated.
- The small-amplitude f₀ was not measured: the swing never got below ~24°.

## Open

- LES over the 2.3 h gap: the swing frequency vs time and amplitude between C2 and this recording.
- A small-swing recording, after quieting the rotor, for f₀.
- Whether the drift continues: record again later and compare at the same amplitude.
