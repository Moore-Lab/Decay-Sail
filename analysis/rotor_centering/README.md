# Rotor centring on the rev G stator

## Result (photos 2026-10-21/22)

**The rotor sits 0.02–0.05 mm from the board centre.** The goal is ≤ 0.05 mm, so
this meets it. Torque scales as J0(8δ/r) with r ≈ 1 mm, giving 0.994 at 20 µm
and 0.96 at 50 µm. That is a loss of at most a few percent. No re-centring needed.

| Photo | Lighting | Rotor R (mm) | Edge pts | dx (µm) | dy (µm) | \|δ\| (µm) |
|---|---|---|---|---|---|---|
| 213036 | cool, side-lit | 1.70 | 315 | −15 | −10 | 19 |
| 213055 | cool, side-lit | 1.68 | 200 | +10 | −20 | 22 |
| 213113 | warm, bright | 1.69 | 452 | +24 | −42 | 48 |
| 213123 | warm, bright | 1.68 | 444 | +22 | −41 | 46 |

+x = image right and +y = image down; neither axis has been mapped to chamber
directions. The 20 vs 50 µm spread between lighting setups is the method's
systematic error, so treat the offset as **20–50 µm, probably toward image up**.
A check by eye on 213113 (`rotor_213113_nominal_circle.jpg`, red = R 1.75 mm
around the board centre) agrees. The rim is closer to the circle at the top and
right than at the bottom and left.

The rotor used is the slotted graphite disk that will fly. The diagonal line
across it is the sail seen edge-on (it stands perpendicular to the disk, on the
top side). The white patch is a marker Molly painted on for the video.

## Photos and setup

- Photos are in iCloud `RDS pics/2020_0108_2130{36,55}_025.JPG`,
  `2020_0108_2131{13,23}_025.JPG` (with rotor), and `2020_0108_213139_025.JPG`
  (board only, the reference). The camera clock is wrong (it reads 2020-01-08).
  The photos were taken around 2026-10-21/22.
- They were taken after straightening the microscope. An earlier pair (`2020_0108_211629_024`
  with an old rotor, `211650_024` board only) taken with the microscope tilted gave
  0.09–0.12 mm. Part of that was probably parallax, so don't compare it directly.
- Phase correlation shows the camera moved < 0.3 px between all five shots, so
  one board-only centre applies to all of them.

## Method (`rotor_centering.py`)

```
python rotor_centering.py BOARD_ONLY.jpg ROTOR1.jpg [...] --out .
```

1. **Board centre** (board-only photo): circle fit to the dark stitching vias at
   r = 3.15 mm, which also sets the scale (433.6 px/mm). This is averaged with a
   radial step-edge fit of the CTR disk. The two agree to 9 µm.
2. **Rotor centre**: 1440 rays from the current centre. On each ray, take the
   outermost pixel with V < 70 that is followed by bright board (mean V > 110
   over the next 5–25 px). Then do a robust circle fit (2σ clipping) and repeat
   three times from the new centre.
3. Output `rotor_centering_fits.jpg`: pink = rotor fit, red dots = edge points,
   orange cross = board centre.

**Pitfalls found:**

- The ray search must stop at about 2.07 mm. Beyond that, dark gaps between the
  electrode fingers count as "rotor". The fit then jumps to R ≈ 1.8–1.9 mm with
  fake 0.2 mm offsets.
- Area masks (dark threshold, or the difference from the board-only shot) pick
  up traces and shadows. In cool side lighting they gave R ≈ 1.96 mm. Don't use
  them.
- The fitted R (1.68–1.70 mm) is a little under the nominal 1.75 mm, probably
  because the threshold sits inside a soft rim. A common bias in R doesn't move
  the centre.

**For next time:** use warm, even lighting (it gave the most edge points). Keep
the microscope square to the board, and take a board-only shot from the same
position before placing the rotor.

## Basler video check after the tilt-stage adjustment (2026-11-06)

**Context (Molly):** after the chamber went onto the tilt stage and the table (10-26), the
rotor did not look centred on the video. On 2026-11-06 she adjusted the tilt stage and
changed the camera angle, then recorded `output_basler_gps1478037739.avi` (120 s,
FFV1, rotor swinging 67–86° (measured from the mark track); no drive was requested, not
verified). Videos: Dropbox `Microspheres/TFINER/videos/`.

**Assumptions (not checked; everything below depends on them):**
- A1. The board centre is the convergence of the radial spoke edges (and, for the clicks, the
  centre of the long-spoke end pads). Both are assumed concentric with the electrode pattern.
- A2. The automatic "rim" fit follows the rotor's outer edge. That identification was made by Claude, not checked;
  Molly's clicked rim has radius 37.0 px against 41.8 px from the fit (see below).
- A3. px → µm: 0.040–0.042 mm/px, from the microscope rotor radius 1.69 mm (above) divided by
  the automatic rim radius. If the clicked radius is the true rim, the scale is ≈ 0.046 mm/px
  and every µm value rises by ≈ 10 %.
- A4. The ≈ 2 px uncertainty is a choice: the largest of three checks, set by the gap between
  the rotor-body centre and a rotation centre on 10-30. It is not a fitted error bar.
- A5. Camera position and stage changes are as Molly stated. The pre-adjustment video's
  "rotor at rest at frame 3000" and its run-to-video mapping come from the decay-sail-9f
  session.

**Method (`basler_centre.py`, measured).** Both centres come from the same frames, so a
camera *shift* cancels. A change of camera *angle* does not cancel (parallax, below).
- Board centre: least-squares convergence of the radial spoke edges, on the median frame.
- Rotor centre: circle fit to the rotor's outer rim, on the max frame (the swinging
  rotor's bright face against the dark board).
- Swing centre: circle fit to the white mark's track.

```
python basler_centre.py output_basler_gps1478037739.avi --board-guess 118,158 --spot 115,127 \
    --plot ../../plots/rotor_centre_gps1478037739.png
python basler_centre.py output_basler_gps1477678308.avi --board-guess 132,182 --stride 100 --plot ...
python basler_centre.py output_basler_gps1477428272.avi --board-guess 132,182 --stride 100 --plot ...
```

Figures (gitignored, regenerate with the commands): `plots/rotor_centre_gps<GPS>.png`,
median | max frame, red × = board centre, yellow = rim fit, green = rim points.

### Result (+x image right, +y image down; µm via A3)

| video | state | rim − board (px) | \|d\| |
|---|---|---|---|
| gps1477428272 (10-30) | on the table, before adjustment | (−1.9, −2.7) | 3.3 px ≈ 140 µm |
| gps1477678308 (11-02) | on the table, before adjustment | (−0.5, −0.9) | 1.0 px ≈ 42 µm |
| **gps1478037739 (11-06)** | **after tilt + camera adjustment** | **(+0.8, −0.2)** | **0.8 px ≈ 33 µm** |

**Uncertainty, about 2 px (≈ 80 µm), from three checks (A4):**
- Board centre: the scatter over 3 start guesses × 3 fit annuli is 0.2–0.6 px (std).
- Rim fit on today's video: each of the four 30 s quarters gives rim − board between
  (+0.1…+0.8, −1.0…−1.9) px: no drift beyond ≈ 1 px during the recording.
- On gps1477428272, the rim centre and the rotation centre (circle fit to the mark's orbit
  over 13071 frames, `camera_utils/tracking/centre_gps1477428272.json`) are both measured against the same
  board centre (132.5, 182.0). They differ by (2.1, 1.2) px. This is the largest of the
  three and sets the 2 px.

**Swing centre: not used.** On today's 67–86° arc, the fitted centre of the white-mark
track depends on how the mark is located. Brightness percentiles of 90–99.5 % give
centres from (+3.0, −4.0) to (+8.4, +0.3) px from the board, each with 0.4–0.9 px rms.
Possible cause (interpretation, not tested): on a short arc, a mark whose centroid shifts
as it turns pulls the fitted centre. A rotation centre from full turns would avoid this.

### What it does and doesn't show

- Measured: after the adjustment, the rotor rim is centred on the spoke convergence to
  0.8 px (≈ 33 µm, A3), with ≈ 2 px (≈ 80 µm) uncertainty (A4). The microscope result of
  10-21/22 was 20–50 µm, with a finer method.
- Measured: this method does **not** show the rotor further off-centre on 11-02 than today.
  The 11-02 and 11-06 values differ by 1.4 px, within the 2 px uncertainty. The 10-30
  value is 3.3 px, at most marginally outside it. If the rotor looked off-centre on the
  video, this measurement doesn't capture it at the ≥ 2 px level. Unexplained; not
  investigated.
- Not checked:
  - Parallax: the rotor floats above the board, so a camera tilt shifts it in the image
    against the board. The camera angle was changed on 11-06, so the before/after
    values are not strictly comparable at the 1–2 px level.
  - The pre-move videos (10-22/23): the R ≈ 43 px ring there may be a board feature,
    not the rotor.

### Independent click check (Molly, 2026-11-06 22:21Z, measured)

Molly ran `camera_utils/centre_overlay.py --video …gps1478037739.avi --frame 3000` on worker2
and clicked one frame. The run was relayed by the decay-sail-9f session; raw files are in
worker2 `~/click_check/` (`log.csv`, `board.json`, stdout).

| | clicked | automatic fit | clicked − automatic |
|---|---|---|---|
| board centre | (119.39, 158.63): 7 long-spoke end pads, R 125.75, rms 0.47 | (118.3, 158.2): spoke convergence | (+1.1, +0.4) |
| rotor centre | (119.89, 156.59): 6 rim points, R 36.99, rms 1.43 | (119.2, 158.0): rim, R 41.8 | (+0.7, −1.4) |
| **rotor − board** | **(+0.5, −2.0) px, \|d\| 2.1 px ≈ 85 µm** | (+0.8, −0.2) px, 0.8 px ≈ 33 µm | (−0.3, −1.8) |

- The two methods agree within the ≈ 2 px uncertainty. Both put the rotor within ≈ 2 px
  (≈ 85 µm) of the board centre after the adjustment.
- The clicked rim radius is 37.0 px, against 41.8 px from the fit. The clicks and the fit
  may be following different rim features (for example inner vs outer edge of a soft
  rim). Not resolved. A common radius bias doesn't move the centre.
- The click check is one frame and six rim points; the automatic fit is the max over
  120 s.

### Before vs after, like for like (measured)

Molly also clicked the pre-adjustment video `output_basler_gps1478031606.avi`, frame 3000. It
was recorded 20:19Z, before the oscillator-chirp run; the rotor was at rest at frame 3000
(per decay-sail-9f, A5). It is in
Dropbox `data/osc_chirp/2026-11-06/`. **Two changes** happened between the two recordings:
the camera was moved, and the tilt stage was adjusted. The board moved (+3.7, −21.4) px in
the image, from both changes together (the stage alone moved it 4–8 px in later steps). Their
order and times are not recorded here.

| | clicked rotor − board (frame 3000) | automatic rim − board |
|---|---|---|
| before (gps1478031606) | (+0.25, −0.58) px: board 5 pads (bottom ones off-frame), rms 0.18; rotor 6 pts, R 36.56, rms 0.59 | (−1.1, −3.3) px over 1324 s; 331 s quarters range (−0.1…−1.6, −0.5…−3.3) |
| after (gps1478037739) | (+0.51, −2.04) px | (+0.8, −0.2) px; quarters (+0.1…+0.8, −1.0…−1.9) |
| change | (+0.26, −1.46) px; ≈ ±0.9 px from the click residuals (decay-sail-9f's estimate) | (+1.9, +3.1) px |

- **The rotor was already centred to ≲ 2 px (≲ 85 µm) before the adjustment, and still is
  after. Neither method shows a change clearly larger than its uncertainty.** The two methods
  don't agree on the direction of the change.
- The automatic fit scatters more on the pre-adjustment video: its 331 s quarters spread by
  2.8 px. The video is 1324 s long and is filed with the chirp data, so it probably spans
  the driven chirp run (inferred, not checked against the run times).
- Rotor − board within one frame cancels a camera *translation*. It does not cancel
  parallax from a change in camera *angle* (the rotor floats above the board), so changes of
  1–2 px between the two framings are not fully like for like.

### Third state: tilt walked back, camera not moved (measured)

Molly moved the tilt stage back towards its earlier setting. She says the camera was not
moved after gps1478037739. Clip: `output_basler_gps1478039512.avi`, 22:31:34Z, 120 s,
8 ms exposure, in Dropbox `TFINER/videos/`. The board moved (+4.3, +1.8) px in the image
with the camera fixed (Molly's statement); the stage moving the chamber would do this
(interpretation).

| | clicked rotor − board (frame 3000) | automatic rim − board |
|---|---|---|
| after tilt change (gps1478037739) | (+0.51, −2.04) | (+0.8, −0.2); quarters (+0.1…+0.8, −1.0…−1.9) |
| after walk-back (gps1478039512) | (−0.65, −1.87): mean of two click sets, (−0.56, −1.33) and (−0.73, −2.40) | (+1.0, −0.6); quarters (−0.4…+0.7, −0.6…+0.1) |
| change | (−1.2, +0.2) | (+0.2, −0.4) |

- Repeating the clicks on the same frame scatters by 0.17 px in x and 1.07 px in y (two sets
  only).
- Both methods find no change larger than about 1 px (≈ 40 µm) between the two tilt
  settings. Both settings leave the rotor within ≈ 2 px of the board centre.
- With the camera fixed, the parallax caveat shrinks to the tilt change itself, which is
  small: a rotor height h above the board shifts by h·Δθ, so a 1 mm height and a 10 mrad
  tilt change give 10 µm ≈ 0.25 px. Neither h nor Δθ is measured here; those values are
  examples.
- Raw clicks are in worker2 `~/click_check/` (log.csv row 3, board_walkback.json,
  overlay_stdout_run5/6.txt). Figure: `plots/rotor_centre_gps1478039512.png`.

### Final state: one more stage adjustment, camera not moved (measured)

Molly adjusted the stage once more and stopped there; the camera was not moved (her
statement, 22:51Z). Clip: `output_basler_gps1478040383.avi`, 22:46:05Z, 120 s, 8 ms. The
board moved (−6.1, +5.0) px in the image from the walk-back clip.

| camera fixed | clicked rotor − board (frame 3000) | automatic rim − board |
|---|---|---|
| after tilt change (gps1478037739) | (+0.51, −2.04), 1 set | (+0.8, −0.2) |
| walk-back (gps1478039512) | (−0.65, −1.87), 2 sets | (+1.0, −0.6) |
| **final (gps1478040383)** | **(−0.23, −1.17)**: sets (+0.24, −0.76) and (−0.70, −1.58) | **(+2.1, +0.9)**; quarters (−0.0…+2.9, +0.5…+3.9) |

- Clicks: final vs walk-back is (+0.4, +0.7) px, inside the ≈ 1 px click scatter.
- Automatic: final vs walk-back is (+1.1, +1.5) px.
- On this clip the clicks and the automatic fit differ by (2.3, 2.1) px. That is the
  largest disagreement of the day, at the edge of the ≈ 2 px uncertainty. The automatic board
  fit scatters most on this clip (measured): 31–42 spoke segments, quarters spread 3.1 px in
  x, robustness std (0.6, 0.8) px. That it causes the disagreement is an interpretation. In the overlay the two sets of centres can't be told
  apart by eye.
- **Through all four of today's states, both methods put the rotor within ≈ 2–2.5 px
  (≈ 50–100 µm) of the board centre. Neither method resolves a change caused by the
  tilt adjustments.** Molly has stopped adjusting. Figure:
  `plots/rotor_centre_gps1478040383.png`.
- Tracker centre for the next tracked run, final framing (from decay-sail-9f): the clicked
  rotor-rim centre ≈ (117.5, 165.1), or (119.1, 167.7) from the automatic rim fit. Both
  are rotor-*body* centres. On 10-30 the body and rotation centres differed by (2.1, 1.2)
  px, so check by tracker replay (ncc), as in the F3 setup, before relying on it. The rest
  angle needs re-noting.

### Images of the click fits

`render_clicks.py` redraws all six of Molly's click fits on frame 3000 of each video, numbered
in click order: `plots/clickfit_<1-6>_run<k>_gps<GPS>.png` and `plots/clickfit_sheet.png`
(gitignored; rerun the script to regenerate). Inputs: Dropbox
`TFINER/data/rotor_centering/2026-11-06/click_check/`, a copy of worker2 `~/click_check/`.
Pad points are drawn where a board json still holds that fit (runs 3, 4, 6, 8). Rim points
were not saved except for run 5. From now on `centre_overlay.py` saves a PNG, the raw frame
and a JSON with all clicked points on every `s`.

The F3 tracker centre (122.8, 179.6) belongs to the framing before the camera move; the
final-framing values are under "Final state" above.
