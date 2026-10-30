# Angle tracking: handoff

## 0. Current state (2026-10-30)

**Read first:** `../TRACKING_NOTES.md` (what the rotor looks like, the gate plan, lessons)
and `../../CLAUDE.md`.

**Test video:** `output_basler_gps1477419607.avi` (2026-10-30, FFV1 lossless Mono8,
256×292 px, 1957 frames, ~50 fps, 39 s). Dropbox `Microspheres/TFINER/videos/`; the Mac
Dropbox app had not synced it, so it was fetched from this link (add `dl=1`):
https://www.dropbox.com/scl/fi/1yk4vf2gaw7q17hzmmqtb/output_basler_gps1477419607.avi?rlkey=994e51v4fl73dtscbfr3tgjwp&st=9wqscqv4&dl=0
OpenCV on the Mac cannot decode FFV1; decode with ffmpeg
(`ffmpeg -i v.avi -f rawvideo -pix_fmt gray -`). What the rotor was doing in it: _ask Molly_.

**Gate 1, centre: PASSED.** (116.2, 180.2) px, the sail-line crossing, confirmed by
Molly by eye. `centre_gps1477419607.json`; `centre_estimate.py VIDEO 256 292` reproduces it.

**Gate 2, blob: next.** Findings so far:
- The blob is clearly visible, but its brightness depends strongly on angle (side
  lighting): bright white at the bottom of the orbit (frames ~1100, 1956), dim grey at
  right and upper left (~500, 1400).
- A rough detector (largest compact spot above the median frame) caught only part of the
  blob in many frames: its orbit fit is centred 4.6 px from the chosen centre, with 4.6 px
  radial scatter. Suspected cause: partial detection on the dim side. If a better
  detector's orbit still misses (116.2, 180.2), the offset is real (tilt or sail off-axis)
  and needs discussing with Molly.
- Orbit radius ~24 px (≈1.05 mm at ~44 µm/px).

**Next commands / steps:**
1. Build a blob detector that segments the whole blob in bright and dim frames (e.g.
   difference from the median frame, region grown from the brightest compact spot,
   rejecting the elongated sail).
2. Plot blob distance from (116.2, 180.2) vs frame, and its angle vs frame.
3. Show Molly ~12 frames across the video with the detected blob circled; she confirms.
4. Then gate 3 (labelling tool) and gate 4 (scorer), before any detector iteration.

**Open questions for Molly:** what the rotor was doing in the test video; the pass mark
for gate 5; whether to add a synthetic video (rendered from the DXF) as an exact-truth test.
