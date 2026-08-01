# Rotor angle tracking — notes & status

Working notes for camera-based rotor angle tracking, toward closed-loop phase-locked
drive. Companion to `README.md` (camera setup/scripts). Written so it can be picked up
from anywhere (e.g. a laptop) via the repo.

## Goal
Measure rotor **angle / phase, frequency, direction, and libration-vs-rotation** live,
so a controller can phase-lock the electrode/laser drive and spin the rotor reliably
past 1 Hz (target ~4 Hz), starting from libration. See `../lab_utils/` for drive scripts.

## The base tracker we studied (spinner_learned / runbrakereverse family)
`runbrakereverse.py`, `spinner_learned.py`, `spinner_learned_episodic_memory.py`, and
`spinner_control_ueye_adaptive.py` all share the same `measure()` tracker:

1. `HoughCircles` auto-detects rotor centre + radius (once).
2. Polar unwrap of an annular band via `cv2.remap`.
3. **Median across the radial band** → one intensity per angle (rejects glare/dust).
4. **Fold φ and φ+π** → assumes a *diametric* feature, angle **mod π (180°)**.
5. **Subtract a broad circular smooth** → removes illumination gradients, leaves narrow
   dark spokes.
6. `argmin` = darkest spoke, **quadratic sub-sample** refine.
7. **MAD-based darkness confidence.**

Good design: it's an **absolute per-frame** measurement (no integration → no libration
rectification). `measure()` is **stateless**; the calling loop is expected to add
unwrapping / continuity / confidence gating.

## What we found testing it on `output_roi_gps1468161639.avi` (libration → spin-up)
This rotor has a thin **dark diametric line through the centre** (distinct from a bright
central bar, which turned out to be a **fixed glint** that does NOT rotate — don't track
it). Two changes made the tracker work:

1. **Inner radial band (~0.12–0.45 R), not the stock 0.48–0.84 R.** The outer band sits
   on the ~12-fold **teeth**, which alias a single-minimum tracker (it just jitters).
   The dark line lives at small radius.
2. **Continuity gating.** Raw per-frame `argmin` over-counts (−9.4 rev, jumpy,
   monotone-frac 0.12). Picking the dark minimum **nearest the predicted angle** gives a
   clean **−4.4 rev, ~0.12 Hz, monotone-frac 0.8–0.9**, and captures the libration as a
   bounded ~20–25° wobble.

**Cross-validation:** that −4.4 rev **agrees with an independent teeth m=12 harmonic
method (~4.1 rev)** — so it's real, not an artifact.

**Caveat:** the built-in *darkness* confidence read ~0.2 even when tracking was correct.
Don't trust it alone — validate with **loop-closure** (de-rotate frames by the tracked
angle; structure should sharpen) and **cross-method agreement**.

## Reusable implementation: `darkline_tracker.py`
Distilled, tested version of the above (inner band + continuity gating + velocity
prediction). Reproduces the video result: libration span 20°, spin-up −4.32 rev @ 91%
monotone.

```bash
# angle time-series + plot from a video:
python darkline_tracker.py output_roi_gps1468161639.avi --cx 150 --cy 166 --radius 76 \
       --csv out.csv --plot out.png
# or let it auto-detect the circle (omit --cx/--cy/--radius)
```
As a library:
```python
from darkline_tracker import DarkLineTracker
trk = DarkLineTracker(center=(cx, cy), radius=r, r_in=0.12, r_out=0.45)
angle_deg, angle_mod180, confidence = trk.update(frame)   # frame: BGR/gray/mono
```

## Cameras & capture (see README.md)
- **Basler acA1440-220um** on worker2 (global shutter, 220 fps, Mono8) — preferred for
  the loop. `grab_basler.py` = headless capture: `/dev/shm` snapshot, MJPEG stream
  (`--mjpeg` → browser at `http://worker2:8080/`), GPS `.avi` (`--record`), and a
  live window (`--show`, needs a display). `pypylon` is in the `ueye` conda env
  (import `cv2` before `pypylon`).
- uEye/Thorlabs DCC1545M via `record_ueye_video.py` (legacy, rolling shutter).

## TODO / next steps
1. Raise `usbfs_memory_mb` 16→1000 for >60 fps.
2. Mount/focus Basler on the **current** rotor + illumination; suppress the fixed glint
   (reposition light / cross-polarization).
3. Grab a clean frame; find where the current rotor's **dark line** sits radially → set
   `r_in/r_out`; auto-detect or fix the centre.
4. Run `darkline_tracker` live; validate with loop-closure + cross-method.
5. Wire angle/frequency/direction (+ confidence) into `grab_basler.py` overlay and/or an
   EPICS channel for the controller.
6. Close the loop: phase-locked electrode/laser drive; test at low rate first.
7. Fiducial only if needed, and **balanced** (balance is critical); white/vacuum-rated,
   not colour (mono cameras).
