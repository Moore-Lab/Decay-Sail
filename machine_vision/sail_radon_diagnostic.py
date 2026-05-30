#!/usr/bin/env python3
"""
Sail angle detection via Radon transform on the disk interior.
The sail creates a dark stripe across the graphite disk; the Radon
transform finds the angle where the projection is darkest.

Usage:
    python3 sail_radon_diagnostic.py <video_path> [frame_number] [background.npy]
"""

import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cv2
from skimage.color import rgb2gray
from skimage.transform import radon
from skimage.draw import disk as sk_disk
from scipy.ndimage import gaussian_filter

# ── CONFIG ──────────────────────────────────────────────────────────────────
DISK_CENTER_FRAC  = (0.38, 0.45)   # (row, col) as fraction of image size
RING_RADIUS_FRAC  = 0.135          # radius of bright magnet ring
DISK_RADIUS_FRAC  = 0.10           # radius of graphite disk interior (inside ring)
N_ANGLES          = 180            # angular resolution for Radon (1 deg steps)
OUT_PATH          = '/tmp/sail_radon_result.png'
# ────────────────────────────────────────────────────────────────────────────


def extract_disk_patch(gray, cy, cx, r_disk, background=None):
    """
    Return a square patch centred on the disk with pixels outside
    the disk circle set to zero. If a background is provided, subtract
    it first to isolate the sail stripe.
    """
    h, w = gray.shape
    r = int(r_disk)
    y1, y2 = max(0, cy - r), min(h, cy + r)
    x1, x2 = max(0, cx - r), min(w, cx + r)

    if background is not None:
        diff = gray - background
        patch = diff[y1:y2, x1:x2].copy()
    else:
        patch = gray[y1:y2, x1:x2].copy()

    # build circular mask in patch coordinates
    ph, pw = patch.shape
    pcy, pcx = cy - y1, cx - x1
    mask = np.zeros((ph, pw), dtype=bool)
    rr, cc = sk_disk((pcy, pcx), r, shape=(ph, pw))
    mask[rr, cc] = True

    patch[~mask] = 0.0
    return patch, mask


def detect_sail_radon(gray, cy, cx, r_disk, background=None):
    """
    Returns (sail_angle_deg, sinogram, theta).
    sail_angle_deg is in [0, 180).
    """
    patch, _ = extract_disk_patch(gray, cy, cx, r_disk, background)
    theta = np.linspace(0.0, 180.0, N_ANGLES, endpoint=False)
    sinogram = radon(patch, theta=theta)

    # angle where the mean projection is lowest = perpendicular to darkest stripe
    # add 90° to convert from projection direction to stripe direction
    mean_per_angle = sinogram.mean(axis=0)
    idx = np.argmin(mean_per_angle)
    sail_angle = (theta[idx] + 90.0) % 180.0
    return sail_angle, sinogram, theta


def load_frame(video_path, frame_number):
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError(f"Could not read frame {frame_number} from {video_path}")
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def run_diagnostic(img_rgb, label='', background=None):
    gray = rgb2gray(img_rgb)
    h, w = gray.shape
    cy = int(DISK_CENTER_FRAC[0] * h)
    cx = int(DISK_CENTER_FRAC[1] * w)
    r_ring = int(RING_RADIUS_FRAC * w)
    r_disk = int(DISK_RADIUS_FRAC * w)

    sail_angle, sinogram, theta = detect_sail_radon(gray, cy, cx, r_disk, background)
    patch, mask = extract_disk_patch(gray, cy, cx, r_disk, background)

    print(f"Detected sail angle: {sail_angle:.1f} deg")

    fig, axes = plt.subplots(1, 4, figsize=(18, 5))
    if label:
        fig.suptitle(label, fontsize=11)

    # original + overlays
    axes[0].imshow(img_rgb)
    axes[0].plot(cx, cy, 'c+', markersize=15, markeredgewidth=2)
    axes[0].add_patch(plt.Circle((cx, cy), r_ring, color='cyan', fill=False, lw=1.5))
    axes[0].add_patch(plt.Circle((cx, cy), r_disk, color='yellow', fill=False, lw=1.0, ls='--'))
    a_rad = np.deg2rad(sail_angle)
    length = r_ring * 1.2
    for sign in [1, -1]:
        x_ = cx + sign * length * np.cos(a_rad)
        y_ = cy + sign * length * np.sin(a_rad)
        axes[0].plot([cx, x_], [cy, y_], 'lime', lw=2)
    axes[0].set_title('Original + detected angle')

    # disk interior patch
    axes[1].imshow(patch, cmap='gray')
    patch_title = 'Disk interior — background subtracted' if background is not None else 'Disk interior (input to Radon)'
    axes[1].set_title(patch_title)

    # sinogram
    axes[2].imshow(sinogram, aspect='auto', cmap='gray',
                   extent=[0, 180, sinogram.shape[0], 0])
    axes[2].axvline(sail_angle, color='lime', lw=1.5, ls='--')
    axes[2].set_xlabel('Angle (deg)')
    axes[2].set_ylabel('Projection position')
    axes[2].set_title('Radon sinogram')

    # mean projection vs angle
    mean_per_angle = sinogram.mean(axis=0)
    axes[3].plot(theta, mean_per_angle, color='steelblue')
    axes[3].axvline(sail_angle, color='lime', lw=1.5, ls='--', label=f'{sail_angle:.1f}°')
    axes[3].set_xlabel('Angle (deg)')
    axes[3].set_ylabel('Mean projection brightness')
    axes[3].set_title('Mean projection vs angle')
    axes[3].legend()
    axes[3].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUT_PATH, dpi=150)
    print(f"Diagnostic saved to {OUT_PATH}")
    return sail_angle


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 sail_radon_diagnostic.py <video_or_image> [frame_number]")
        sys.exit(1)

    path = sys.argv[1]
    frame_number = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    bg_path = sys.argv[3] if len(sys.argv) > 3 else None

    background = None
    if bg_path:
        background = np.load(bg_path).astype(np.float32)
        print(f"Loaded background from {bg_path}")

    if path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
        from PIL import Image
        img_rgb = np.array(Image.open(path).convert('RGB'))
        label = path
    else:
        img_rgb = load_frame(path, frame_number)
        label = f"{path}  frame {frame_number}"

    run_diagnostic(img_rgb, label=label, background=background)


if __name__ == '__main__':
    main()
