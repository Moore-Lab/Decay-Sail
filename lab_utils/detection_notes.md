# Sail angle detection — approaches tried

## Setup

Camera views disk (graphite, ~1.45 mm radius) from above in vacuum (~10^-8 mbar).
Bright magnet ring surrounds disk. Mylar sail crosses disk diameter.
Lighting is off-axis (LED, not coaxial), so only ~90 deg of the ring arc is evenly lit.
Mass constraints rule out added markers.

---

## Method 1: Ring-interruption (raw brightness)

**Idea:** Sample brightness around the bright magnet ring. The sail crossing
the ring creates two dark gaps ~180 deg apart. Find the gap pair and report
the sail direction.

**Implementation:** `sail_angle_diagnostic.py`

**Result:** Works on frames where the ring is uniformly lit. Fails when
fixed structural shadows (standoffs, electrode mounts) create false gaps
that compete with the sail gaps.

---

## Method 2: Ring-interruption with background normalisation

**Idea:** Build a median background from many spinning frames (sail averages
out; fixed shadows remain). Divide each frame's ring profile by the background
ring profile. Fixed shadows cancel; only the sail gap remains.

**Implementation:** `build_background.py` + `sail_angle_diagnostic.py` (with background .npy)

**Result:** Improves gap detection significantly. Fails when lighting
illuminates only ~90 deg of the ring arc — the algorithm picks the edges of
the bright arc instead of the sail gap in the dark region.

**Key observation:** The sail gap on the ring is always visible on the LEFT
side of the ring. The right arc is bright but does not show the sail gap
on-ring (though the sail line is visible extending past the ring).

---

## Method 3: Radon transform on disk interior

**Idea:** The sail casts a dark stripe across the graphite disk interior.
The Radon transform finds the angle of the darkest stripe.

**Implementation:** `sail_radon_diagnostic.py`

**Result:** Abandoned. Graphite disk has low contrast and a brightness
gradient from off-axis lighting that dominates the Radon response.

---

## Method 4: Log-polar cross-correlation with median subtraction (WORKING)

**Idea:**
  1. Warp each frame to polar coordinates (r, theta) centred on the disk.
     In polar space, a rotation of the disk = translation in theta.
  2. Build a median polar frame across the video window. Fixed features
     (lighting arc, ring) dominate the median; the rotating sail averages out.
  3. Subtract the median from each frame's polar image (residual).
     This removes the fixed lighting and leaves only the rotating sail signal.
  4. Cross-correlate consecutive residuals to find delta-theta per step.
  5. Integrate to get cumulative angle vs time.

**Why the median subtraction is essential:** Without it, the fixed bright
lighting arc (upper-right, ~90 deg of the ring) dominates the correlation and
returns near-zero shift even when the disk rotates. Subtracting the median
removes this fixed pattern entirely.

**Implementation:** `sail_logpolar_analysis.py`

**Key result on reversed-drive video (2026-05-11):**
- Total duration: 14.6 minutes
- Detected rotation: -293.7 deg (~0.82 full counterclockwise rotations)
- Average spin rate: 0.056 RPM
- Disk quasi-static for first ~100s, then spins up, oscillates, drifts net CW

**Usage:**
```bash
# Full video, stride=90 (~3s per step)
python3 sail_logpolar_analysis.py video.avi

# Specific window with finer resolution
python3 sail_logpolar_analysis.py video.avi --start 105 --end 160 --stride 30

# Polar diagnostic for one frame (check centering)
python3 sail_logpolar_analysis.py video.avi --diag_frame 3077

# Output in /tmp/logpolar/:
#   angle_vs_time.png   -- cumulative angle + spin rate
#   angle_data.npz      -- times, angles, per-step deltas
#   polar_median.png    -- median background polar
#   polar_frame_NNNN.png (if --diag_frame used)
```

**Limitations:**
- Gives cumulative (relative) angle, not absolute angle
- Errors accumulate with integration over time
- Requires the disk to have visited many different angles during the analysis
  window so the sail averages out of the median
- Step-to-step noise is high at coarse stride; use stride=10-30 for spin rate

---

## Method 5: Hough line detection

**Idea:** Apply Canny edge detection to the disk interior (ring excluded by a
circular mask). The Hough transform finds all straight lines in the edge image.
Lines not passing within 25 px of the disk centre are rejected, since the sail
always crosses through the centre.

**Implementation:** `sail_angle_diagnostic.py` (experimental branch, not kept)

**Result:** Failed. The bright magnet ring boundary creates strong edges that
dominate the Hough output even with masking — most frames returned 0° or 90°.

**Key observation that led to Method 6:** Inspecting the Canny edge images
revealed that the sail and its shadow appear as a *dark* (edge-free) stripe
through the disk interior. The graphite disk has dense texture edges everywhere
except where the smooth sail/shadow region suppresses them. The correct angle
is the direction of *minimum* edge density, not maximum.

---

## Method 6: Minimum-edge stripe (CURRENT BEST)

**Idea:** The sail and its shadow create a smooth, texture-free stripe across
the disk interior. Canny edge detection produces dense edges in the graphite
but a dark (edge-free) band along the sail direction. Scanning all 180
orientations and summing edge density along each gives the sail angle as the
orientation with fewest edges.

**Steps:**
  1. High-pass filter the disk interior (subtract Gaussian blur) to flatten
     the brightness gradient from off-axis lighting.
  2. Apply Canny edge detection within the disk interior mask (80% of ring
     radius, to exclude ring boundary bleed).
  3. For each angle 0-179°, sum Canny edge values along a narrow band
     (width ~6% of ring radius) centred on the disk centre.
  4. Smooth the resulting 180-point profile with a 20° running average to
     suppress narrow spikes from ring boundary bleed.
  5. The angle with minimum smoothed edge sum = sail direction.

**Key advantage over all prior methods:** Gives *absolute* angle per frame
with no integration — errors do not accumulate over time. Works for both the
thin sail stripe (small shadow) and the large shadow boundary (sail perpendicular
to light), since both create a smooth region in the edge image.

**Implementation:** `sail_minedge_analysis.py` (in progress)

**Result on reversed-drive video (2026-05-11), 12 test frames:**
- 9/12 frames correct by visual inspection
- Failures at t=160s, 170s, 200s — frames where a competing narrow minimum
  from ring boundary bleed is not fully suppressed by the 20° smoothing

**Usage:**
```bash
python3 sail_minedge_analysis.py video.avi
python3 sail_minedge_analysis.py video.avi --start 100 --end 300 --stride 10
```

---

## Key parameters (shared across methods)

| Parameter | Value | Meaning |
|---|---|---|
| `DISK_CENTER_FRAC` | (0.49, 0.45) | disk centre as (row_frac, col_frac) |
| `RING_RADIUS_FRAC` | 0.133 | magnet ring radius / image width |
| `DISK_RADIUS_FRAC` | 0.165 | polar crop radius / image width (ring + margin) |
| `THETA_BINS` | 720 | angular bins in polar image (0.5 deg / bin) |
| `UPSAMPLE` | 20 | sub-pixel upsampling for phase correlation (0.025 deg resolution) |
| `interior_frac` | 0.80 | disk interior mask radius / ring radius (Method 6) |
| `band_half` | 6% of ring radius | half-width of edge-sum scan band (Method 6) |
| `profile_smooth` | 20 deg | running average window on angle profile (Method 6) |
