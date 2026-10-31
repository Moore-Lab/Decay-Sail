# Angle tracking: handoff

## 0. Current state (2026-10-30, end of gate-2 session)

**Read first:** `../TRACKING_NOTES.md` (what the rotor looks like, the gate plan, lessons)
and `../../CLAUDE.md`.

**Test video:** `output_basler_gps1477419607.avi` (2026-10-30, FFV1 lossless Mono8,
256×292 px, 1957 frames, ~50 fps, 39 s). Now synced on the Mac at
`~/Library/CloudStorage/Dropbox/Microspheres/TFINER/videos/`. Shared link (add `dl=1`):
https://www.dropbox.com/scl/fi/1yk4vf2gaw7q17hzmmqtb/output_basler_gps1477419607.avi?rlkey=994e51v4fl73dtscbfr3tgjwp&st=9wqscqv4&dl=0
OpenCV on the Mac cannot decode FFV1; decode with ffmpeg
(`ffmpeg -i v.avi -f rawvideo -pix_fmt gray -`).

**Gate 1, centre: PASSED.** (116.2, 180.2) px, the sail-line crossing, confirmed by
Molly by eye. `centre_gps1477419607.json`; `centre_estimate.py VIDEO 256 292` reproduces it.

**Gate 2, blob: PASSED (Molly, 2026-10-30):** "it is always on the blob, maybe not on the
same place on the blob, but always the edge of the blob." She also confirmed the motion
(swings plus a few full turns) matches what was happening.

**Second test video, new lighting:** `output_basler_gps1477428272.avi` (2026-10-30, same
format, 13071 frames, 261 s, same Dropbox folder). The image moved +16.6 px in x vs the
first video, so it has its own centre: **(132.3, 180.6)**, `centre_gps1477428272.json`,
**gate 1 PASSED** (Molly, 2026-10-30: cross on the rotation centre, red circle on the blob in all 12 frames) on `plots/gate1_2_frames_gps1477428272.png`
(yellow cross = centre, green = orbit, red = tracked blob point). The centre comes from the
blob orbit, not the sail crossing, because the sail is dim in this lighting. Measured:
- iteration converged (0.13 px move); 26-s chunks with >500° of motion agree within ~0.3 px
  over the 4.4 min; radial scatter 0.28 px.
- `blob_track.py ... centre_gps1477428272.json 0 257 ...` (template frame 0 at 257°): no
  jumps over 13071 frames (max step 7.2°), loop closure sharp
  (`plots/gate2_loopclosure_gps1477428272.png`). Net −19.8 rev.
- **New lighting tracks much better:** NCC median 0.96 vs 0.77; margin over the next-best
  angle at the 1st percentile 0.26 vs 0.05; sail blanking needed in 16% vs 66% of frames.
  The blob is bright white at every angle.
- Angle zero here is the frame-0 template
  point, not the same rotor point as the first video (see open items).

**Blob−sail angle (resolved, measured):** the 34.2° from gate 2 is between the sail and the
template point, which sits on the blob's edge. The blob's brightness-weighted centre in the
de-rotated mean of the first video is at ~97° and the sail at 49°, so **~48°**
(`plots/blob_sail_angle_gps1477419607.png`); a rough read of the microscope photo gives
~55°. TRACKING_NOTES' "about 60°" was approximate.

**Gate 2 record (first video):** detector built and checked as below.

Detector: `blob_track.py` (polar unwrap about the centre + normalised cross-correlation
with a blob template cut from frame 1100 at 82°; searches all 360° and ±8 px in r;
takes the better of a raw and a sail-blanked unwrap per frame). Run (9 s):

    cd camera_utils/tracking
    python blob_track.py ~/Library/CloudStorage/Dropbox/Microspheres/TFINER/videos/output_basler_gps1477419607.avi \
        256 292 centre_gps1477419607.json 1100 82 blob_gps1477419607.csv

Measured on the test video (all 1957 frames detected; none skipped):
- **Continuity:** largest frame-to-frame step 6.9° (the fastest motion in the video,
  ~5–7°/frame for ~20 frames). No jumps. (Before this, a brightness detector had
  ~25–35% of frames on the sail ends or arm tips, and an earlier template version had
  ~190 jumps >30°.)
- **Loop closure (passes):** de-rotating each frame by its tracked angle and averaging
  gives a sharp rotor: arms, sail and the blob's shape. The dim half of the orbit alone
  (1355 frames) is as sharp as the bright half (602). A control with shuffled angles
  blurs to rings. High-pass rms in the rotor: raw mean 5.4, de-rotated 12.7 (dim half
  14.1, bright half 15.8), shuffled 2.6. `plots/gate2_loopclosure_gps1477419607.png`.
- **Distance from (116.2, 180.2):** median 22.9 px, std 0.57 px, varying 22–24 px with
  angle. A circle fit to the orbit is centred at (115.70, 180.69), **0.70 px** from the
  chosen centre, radial scatter 0.30 px. The 4.6 px offset suspected in the last handoff
  is **not reproduced**; it came from the rough detector. Whether the remaining 0.7 px
  is tilt or centre error is open (not needed for the angle).
- **Blob − sail angle:** 34.2° (MAD-std 1.8°, 700 frames where the sail finder is
  continuous and the blob is on the dim half). TRACKING_NOTES says "about 60°";
  not resolved. In bright frames the sail finder is pulled onto the blob, so the sail
  angle is only used as a check, never by the detector's output.
- **What the rotor did (observation):** back-and-forth swings of roughly ±70–100°, with
  full turns around frames 950–1130 and 1680–1957; net −1.5 rev in 39 s; peak speed
  ~7°/frame ≈ 0.95 rev/s (at 50 fps). `plots/gate2_series_gps1477419607.png`.

**Still open from gate 2:** for other videos, reuse one saved template (and its declared
offset) rather than cutting a new one per video, or the angle zero differs between recordings.
`blob_track.py` currently cuts it from REF_FRAME of the video it runs on.

**Gate 3, ground truth: PASSED by its criterion (2026-10-30).** Molly labelled all 200
frames (none skipped; no zoom, a spot on the blob at -102.4 deg, r 25.1 px in the reference),
then 20 again 5 h later. Pass 2 vs pass 1: mean -0.20 deg, **rms 1.12 deg, max 2.75 deg**
(radial 0.66 px rms), so one label scatters ~0.8 deg (derived, /sqrt2, n=20). Labels vs
blob_track (preview of gates 4-5, not the formal score): constant offset 0.25 deg, then
**rms 0.96 deg, max 3.0 deg, 100% within 5 deg**, similar in every selection category
(fast 0.84, reversal 0.93, low-margin 1.12). With ~0.8 deg of label scatter, the tracker's own
error is roughly 0.5 deg rms (derived, rough).

Tool notes (kept from the build):
Decided (Molly, 2026-10-30): gate 3 uses only gps1477428272 (the new lighting); the first
video stays an unlabelled stress test. `label_frames.py` (headless-tested with simulated
clicks: angles recorded exactly, resume/skip/back, repeat pass and compare all work).
200 frames picked (`labels/selection_gps1477428272.csv`): 119 evenly in angle, 40
fastest, 20 swing reversals, 20 lowest detector margin, 1 random; shown shuffled and
without any detector angle. Molly runs, on the Mac:

    cd ~/Desktop/VSCode/decay_sail/camera_utils/tracking
    python label_frames.py point 1477428272    # once: click the rotor point to use
    python label_frames.py label 1477428272    # pass 1, resumable (q quits, saves)
    python label_frames.py repeat 1477428272   # pass 2 on 20 frames, later
    python label_frames.py compare 1477428272  # gate 3 passes if within a few degrees

(`select` was run as `label_frames.py select VIDEO centre_gps1477428272.json
blob_gps1477428272.csv`; rerun only if the frames cache is lost.) The labels CSVs are
ground truth: commit them.

**Gate 4, scorer: PASSED (2026-10-30).** `score_angles.py ANGLES.csv GPS --offset DEG`;
`score_angles.py selftest GPS` checks it: 100% on the labels themselves; FAILS the labels
rotated 180 deg and 45 deg, 6% of frames flipped 180 (93.5% within 5 deg), and 6% missing;
passes labels + 1 deg rms noise. The offset is DECLARED per detector from geometry, not
fitted (a fitted offset would let a 180 deg copy pass). For blob_track with template frame 0
at 257 deg: offset = point ref_angle 257.56 - 257 = **+0.56 deg** (fitted would be +0.25).
Valid only with blob_track REF_FRAME = 0: the labelling reference image is frame 0's
orientation. Another REF_FRAME needs a different offset (or `select` changed to match).

**blob_track.py scored (gate-5 marks, provisional until Molly sets them):**

    python score_angles.py blob_gps1477428272.csv 1477428272 --offset 0.56

100% within 5 deg, 0% wrong-feature, 0% no answer, rms 1.01 deg, max 3.29 deg (fast 0.75,
reversal 1.09, low-margin 1.10 rms). 0 of 200 wrong-feature bounds the rate only below ~1.5%
(95%, rule of three), so "< 1%" rests also on the full video: 13071 frames with no step over
7.2 deg (a 45/180 deg flip would show as a jump) and a sharp loop closure. Its 180 deg-rotated copy FAILS. Most of the 1 deg is
label scatter (~0.8 deg per label, from gate 3). blob_track was built before the labels
existed, so it was not tuned on them.

**Next:** Molly sets the gate-5 pass mark (proposed: >= 95% within 5 deg, < 1% wrong-feature);
if blob_track passes it, gate 5 needs no detector iteration. Then gate 6 (angle -> frequency,
compare with LES on the same recording), which needs LES data for the video's GPS span
(video filenames are true GPS; the front end's clock is not, read Y1:DAQ-DC0_GPS live).

**Open questions for Molly:** the gate-5 pass mark; whether to add a synthetic video
(rendered from the DXF) as an exact-truth test.
