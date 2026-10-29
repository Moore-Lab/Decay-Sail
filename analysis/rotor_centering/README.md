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
