#!/usr/bin/env python3
"""
Sail angle detection via ring-interruption method.
The mylar sail crosses the bright magnet ring, creating two dark gaps.
Optionally normalizes the ring brightness by a background profile to
cancel fixed structural shadows, leaving only the sail gaps.

Usage:
    python3 sail_angle_diagnostic.py <image_or_frame> [background.npy]
"""

import numpy as np
import sys
from PIL import Image
from skimage.color import rgb2gray
from scipy.ndimage import uniform_filter1d

# ── CONFIG ──────────────────────────────────────────────────────────────────
IMAGE_PATH = sys.argv[1] if len(sys.argv) > 1 else 'frame.png'

DISK_CENTER_FRAC = (0.49, 0.45)   # (row, col) as fraction of image size
RING_RADIUS_FRAC = 0.133          # radius of the bright magnet ring
RING_WIDTH_FRAC  = 0.03           # thickness of ring band to sample
N_ANGLES         = 720            # angular resolution (0.5 deg steps)
SMOOTH_WIDTH     = 20             # smoothing window in angular samples
GAP_THRESHOLD    = 0.88           # fraction of mean — below this = gap
# ────────────────────────────────────────────────────────────────────────────


def sample_ring(gray, cy, cx, r, width, n_angles):
    angles = np.linspace(0, 2 * np.pi, n_angles, endpoint=False)
    brightness = np.zeros(n_angles)
    h, w = gray.shape
    for i, a in enumerate(angles):
        vals = []
        for dr in np.linspace(-width, width, 7):
            row = int(cy + (r + dr) * np.sin(a))
            col = int(cx + (r + dr) * np.cos(a))
            if 0 <= row < h and 0 <= col < w:
                vals.append(gray[row, col])
        brightness[i] = np.mean(vals) if vals else 0.0
    return angles, brightness


def find_sail_gaps(brightness, n_angles, bg_brightness=None):
    """
    Find the two gap centres closest to 180° apart.
    If bg_brightness is provided, normalise the ring profile by the background
    to cancel fixed structural shadows before thresholding.
    The smoothed curve is returned only for plotting.
    """
    if bg_brightness is not None:
        bg_safe = np.where(bg_brightness > 1e-6, bg_brightness, np.mean(bg_brightness))
        profile = brightness / bg_safe
    else:
        profile = brightness

    smooth = uniform_filter1d(profile, size=SMOOTH_WIDTH, mode='wrap')
    thresh = np.mean(profile) * GAP_THRESHOLD
    is_gap = profile < thresh

    gap_centres = []
    in_gap = False
    gap_start = 0
    for i in range(n_angles):
        if is_gap[i] and not in_gap:
            in_gap = True
            gap_start = i
        elif not is_gap[i] and in_gap:
            in_gap = False
            gap_centres.append((gap_start + i) / 2.0)

    if len(gap_centres) < 2:
        return None, None, smooth

    gap_degs = [g / n_angles * 360.0 for g in gap_centres]
    best_pair = None
    best_err = np.inf
    for i in range(len(gap_centres)):
        for j in range(i + 1, len(gap_centres)):
            diff = abs(gap_degs[i] - gap_degs[j])
            diff = min(diff, 360.0 - diff)
            err = abs(diff - 180.0)
            if err < best_err:
                best_err = err
                best_pair = (int(gap_centres[i]), int(gap_centres[j]))

    if best_pair is None:
        return None, None, smooth
    return best_pair[0], best_pair[1], smooth


def detect_from_array(img_rgb, background=None):
    """Detect sail angle from a numpy RGB array. Returns angle in degrees or None."""
    gray = rgb2gray(img_rgb)
    h, w = gray.shape
    cy = int(DISK_CENTER_FRAC[0] * h)
    cx = int(DISK_CENTER_FRAC[1] * w)
    r  = int(RING_RADIUS_FRAC * w)
    rw = int(RING_WIDTH_FRAC * w)
    angles, brightness = sample_ring(gray, cy, cx, r, rw, N_ANGLES)

    bg_brightness = None
    if background is not None:
        _, bg_brightness = sample_ring(background, cy, cx, r, rw, N_ANGLES)

    g1, g2, _ = find_sail_gaps(brightness, N_ANGLES, bg_brightness)
    if g1 is None:
        return None
    return float(np.degrees(angles[g1]))


def detect_sail_angle(image_path, background=None):
    """
    Returns (sail_angle_deg, img, cx, cy, r, angles, brightness, smooth, gap1_angle, gap2_angle)
    or None if not detected.
    """
    img = np.array(Image.open(image_path).convert('RGB'))
    gray = rgb2gray(img)
    h, w = gray.shape
    cy = int(DISK_CENTER_FRAC[0] * h)
    cx = int(DISK_CENTER_FRAC[1] * w)
    r  = int(RING_RADIUS_FRAC * w)
    rw = int(RING_WIDTH_FRAC * w)

    angles, brightness = sample_ring(gray, cy, cx, r, rw, N_ANGLES)

    bg_brightness = None
    if background is not None:
        _, bg_brightness = sample_ring(background, cy, cx, r, rw, N_ANGLES)

    g1, g2, smooth = find_sail_gaps(brightness, N_ANGLES, bg_brightness)
    if g1 is None:
        return None

    gap1_angle = angles[g1]
    gap2_angle = angles[g2]
    return np.degrees(gap1_angle), img, cx, cy, r, angles, brightness, smooth, gap1_angle, gap2_angle


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    background = None
    if len(sys.argv) > 2:
        background = np.load(sys.argv[2]).astype(np.float32)
        print(f"Loaded background from {sys.argv[2]}")

    print(f"Loading: {IMAGE_PATH}")
    result = detect_sail_angle(IMAGE_PATH, background)

    if result is None:
        print("Sail not detected — try adjusting RING_RADIUS_FRAC or GAP_THRESHOLD")
        return

    sail_angle, img, cx, cy, r, angles, brightness, smooth, gap1_angle, gap2_angle = result
    print(f"Disk center: ({cx}, {cy}), ring radius: {r}px")
    print(f"Gap 1: {np.degrees(gap1_angle):.1f}°, Gap 2: {np.degrees(gap2_angle):.1f}°")
    print(f"Sail angle: {sail_angle:.1f}°")

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    axes[0].imshow(img)
    axes[0].plot(cx, cy, 'c+', markersize=15, markeredgewidth=2)
    axes[0].add_patch(plt.Circle((cx, cy), r, color='cyan', fill=False, lw=1.5))
    axes[0].set_title('Original + ring')

    axes[1].plot(np.degrees(angles), brightness, 'w', lw=0.8, alpha=0.5, label='raw')
    axes[1].plot(np.degrees(angles), smooth, 'yellow', lw=1.5, label='smoothed/normalized')
    for ga in [gap1_angle, gap2_angle]:
        axes[1].axvline(np.degrees(ga), color='lime', ls='--', lw=1.5)
    axes[1].set_xlabel('Angle (deg)')
    axes[1].set_ylabel('Brightness' + (' (normalized)' if background is not None else ''))
    axes[1].set_title('Ring brightness profile' + (' — background normalized' if background is not None else ''))
    axes[1].legend()
    axes[1].set_facecolor('black')

    axes[2].imshow(img)
    axes[2].plot(cx, cy, 'c+', markersize=15, markeredgewidth=2)
    axes[2].add_patch(plt.Circle((cx, cy), r, color='cyan', fill=False, lw=1.5))
    length = r * 1.3
    x1 = cx + length * np.cos(gap1_angle)
    y1 = cy + length * np.sin(gap1_angle)
    x2 = cx + length * np.cos(gap2_angle)
    y2 = cy + length * np.sin(gap2_angle)
    axes[2].plot([x1, x2], [y1, y2], 'lime', lw=2)
    axes[2].plot([x1, x2], [y1, y2], 'go', markersize=8)
    axes[2].set_title(f'Detected sail angle: {sail_angle:.1f}°')

    plt.tight_layout()
    plt.savefig('/tmp/sail_detection_result.png', dpi=150)
    print("Result saved to /tmp/sail_detection_result.png")


if __name__ == '__main__':
    main()
