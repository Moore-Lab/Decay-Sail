# Detent runs 2026-11-10: rotor angle through the six single-phase steps

Analysis only, Mac. Data: `Dropbox/Microspheres/TFINER/data/detent/2026-11-10/` (event CSVs = authority for times).
Interpretations are Claude's, marked "(interpretation, not approved)".

    ffmpeg -nostdin -v error -i video/output_basler_gps1478391767.avi -f rawvideo -pix_fmt gray FRAMES.u8
    python3 track_detent.py FRAMES.u8 video/output_basler_gps1478391767.csv   # -> rotor_angle_detent.csv (~2 min)
    python3 analyse_detent.py DATA_DIR    # -> steps_detent.csv, swings_detent.csv, plots/detent_overview|zoom_*|period_vs_amp
    python3 kick_detent.py DATA_DIR       # -> kick_detent.csv, plots/detent_kick_residual.png

Tracking: same as S1 (unmodified `blob_core.Tracker`, centre (117.5, 165.1), template `template_gps1477428272.npz`, full
360° search), every frame. ncc median 0.965, min 0.912 (at the 145°/294° turning points of the final swing), best other
match ≤ 0.72, max step 2.9°/frame, r_px 23.0–24.6 (stable per angle). Frames at 145° and 294° checked by eye: blob found.
Time axis `host_time_cam` = camera clock mapped to host by the median offset (host-stamp jitter 2.6 ms rms). Onset of A1
(from rest) is visible within ~0.1–0.15 s of the event time, so no ~1 s offset.

## Measured

- **The rotor never settles into a new equilibrium.** Each switch-on changes the swing amplitude and the rotor then swings
  freely, with no visible damping (final swing 74 → 72° amplitude over 123 s). Amplitude ratchets
  1.75 → 21 → 30 → 31 → 38 → 56 → 74°. No snap (no fast move to a new rest) in any step.
- Swing centre (max+min)/2, hold vs gap of the same step: A1 214.5/215.5, B1 210.6/213.5, C1 214.6/213.3,
  A2 210.0/217.0 (amplitude grew during this hold), B2 217.2/217.5, C2 219.0/219.5. Shifts ≤ 3° except A2, none near 15°.
- Period grows with amplitude: 1.48 s at ±1.75° (pre-run) to 4.18 s at ±74° (`plots/detent_period_vs_amp.png`).
- Free swing after run 2 (field off) gives the trap acc over 145–294°; for this large swing its single zero is at 214.5°,
  not 208.6° (`plots/detent_kick_residual.png`, right). Not explained.

## Derived

- Field acceleration in the first 0.6 s (acc − free trap; two trap models, binned big-swing and canonical refit):
  A1 −1.2/−1.3 rad/s² (192–209°), A2 −2.7/−2.4 (186–209°), B1 +1.25/+1.07, B2 +1.9 (238–271°), C1 −0.07/−0.4,
  C2 −1.2 (216–270°). Field-off residual rms 0.05–0.55 rad/s². A at 6400 vs 3200 over overlapping angles: ×1.9–2.2, not ×4.
- AC coupling (τ 5.57 s): the hold field decays to 20 % by release; the 30 s linear ramp-down gives a steady reversed field
  of ≈ −τ/30 ≈ −19 % of the step; it decays only in the 10 s gap. Only after teardown is the field truly off.

## Interpretation (not approved)

- With the rotor swinging ±20–75° and the hold field decaying, the protocol cannot resolve 15°-spaced detents; the step
  acts as a kick. Sign at switch-on: A pushes to lower angle (twice), B to higher (twice), C mixed.
- The A-phase kick scales closer to linear than V² at 192–209°, but the trap-model systematic is ~±0.5 rad/s².
