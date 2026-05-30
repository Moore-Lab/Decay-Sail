#!/usr/bin/env python3
"""
Run sail angle detection on every frame of a video and plot angle vs time.
"""

import cv2
import numpy as np
import sys
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, '/Users/mollywatts/Library/CloudStorage/OneDrive-Personal/VSCode/Decay-Sail/linux_code')
from sail_angle_diagnostic import detect_sail_angle, detect_from_array

VIDEO_PATH  = sys.argv[1] if len(sys.argv) > 1 else \
    '/Users/mollywatts/Library/CloudStorage/Dropbox/Microspheres/TFINER/videos/output_roi_2026-05-05_17-25-43.avi'
STRIDE      = 1    # process every Nth frame (set > 1 to speed up)
OUT_PLOT    = '/tmp/sail_angle_vs_time.png'
OUT_VIDEO   = '/tmp/sail_annotated.avi'
WRITE_VIDEO = True  # set False to skip writing annotated video
DIAG_STRIDE = 50   # save a 3-panel diagnostic image every Nth frame (0 = disabled)
DIAG_DIR    = '/tmp/sail_diag_frames'

def save_diagnostic_frame(img_rgb, frame_idx, t):
    """Save a 3-panel diagnostic image for this frame to DIAG_DIR."""
    os.makedirs(DIAG_DIR, exist_ok=True)
    result = detect_sail_angle.__wrapped__(img_rgb) if hasattr(detect_sail_angle, '__wrapped__') else None

    # run full detection to get all the plotting data
    from PIL import Image as PILImage
    from sail_angle_diagnostic import (sample_ring, find_sail_gaps,
                                       DISK_CENTER_FRAC, RING_RADIUS_FRAC,
                                       RING_WIDTH_FRAC, N_ANGLES)
    from skimage.color import rgb2gray
    import numpy as np

    gray = rgb2gray(img_rgb)
    h, w = gray.shape
    cy = int(DISK_CENTER_FRAC[0] * h)
    cx = int(DISK_CENTER_FRAC[1] * w)
    r  = int(RING_RADIUS_FRAC * w)
    rw = int(RING_WIDTH_FRAC * w)
    angles_arr, brightness = sample_ring(gray, cy, cx, r, rw, N_ANGLES)
    g1, g2, smooth = find_sail_gaps(brightness, N_ANGLES)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(f'Frame {frame_idx}  t={t:.2f}s', fontsize=11)

    axes[0].imshow(img_rgb)
    axes[0].plot(cx, cy, 'c+', markersize=15, markeredgewidth=2)
    axes[0].add_patch(plt.Circle((cx, cy), r, color='cyan', fill=False, lw=1.5))
    axes[0].set_title('Original + ring')

    axes[1].plot(np.degrees(angles_arr), brightness, 'w', lw=0.8, alpha=0.5, label='raw')
    axes[1].plot(np.degrees(angles_arr), smooth, 'yellow', lw=1.5, label='smoothed')
    if g1 is not None:
        for gi in [g1, g2]:
            axes[1].axvline(np.degrees(angles_arr[gi]), color='lime', ls='--', lw=1.5)
    axes[1].set_facecolor('black')
    axes[1].set_xlabel('Angle (deg)')
    axes[1].set_ylabel('Brightness')
    axes[1].set_title('Ring brightness profile')
    axes[1].legend()

    axes[2].imshow(img_rgb)
    axes[2].plot(cx, cy, 'c+', markersize=15, markeredgewidth=2)
    axes[2].add_patch(plt.Circle((cx, cy), r, color='cyan', fill=False, lw=1.5))
    if g1 is not None:
        sail_angle = np.degrees(angles_arr[g1])
        gap1_angle = angles_arr[g1]
        gap2_angle = angles_arr[g2]
        length = r * 1.3
        x1 = cx + length * np.cos(gap1_angle)
        y1 = cy + length * np.sin(gap1_angle)
        x2 = cx + length * np.cos(gap2_angle)
        y2 = cy + length * np.sin(gap2_angle)
        axes[2].plot([x1, x2], [y1, y2], 'lime', lw=2)
        axes[2].plot([x1, x2], [y1, y2], 'go', markersize=8)
        axes[2].set_title(f'Sail angle: {sail_angle:.1f}°')
    else:
        axes[2].set_title('No detection')

    plt.tight_layout()
    out_path = os.path.join(DIAG_DIR, f'diag_frame_{frame_idx:05d}.png')
    plt.savefig(out_path, dpi=100)
    plt.close(fig)


def angle_unwrap_180(angles_deg):
    """Unwrap a sequence of 180°-periodic sail angles into a continuous signal."""
    arr = np.deg2rad(np.array(angles_deg) % 180.0)
    unwrapped = np.unwrap(2 * arr) / 2.0
    return np.rad2deg(unwrapped)


def main():
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"Cannot open video: {VIDEO_PATH}")
        return

    fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w      = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h      = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Video: {w}x{h} @ {fps:.1f} fps, {n_frames} frames")

    if WRITE_VIDEO:
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        writer = cv2.VideoWriter(OUT_VIDEO, fourcc, fps, (w, h))

    times  = []
    angles = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % STRIDE == 0:
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            angle = detect_from_array(img_rgb)

            t = frame_idx / fps
            if angle is not None:
                times.append(t)
                angles.append(angle)

            if WRITE_VIDEO:
                annotated = frame.copy()
                cx = int(0.51 * w)
                cy = int(0.59 * h)
                r  = int(0.133 * w)
                cv2.circle(annotated, (cx, cy), r, (0, 255, 255), 1)
                if angle is not None:
                    a = np.deg2rad(angle)
                    length = int(r * 1.4)
                    x1 = int(cx + length * np.cos(a))
                    y1 = int(cy + length * np.sin(a))
                    x2 = int(cx + length * np.cos(a + np.pi))
                    y2 = int(cy + length * np.sin(a + np.pi))
                    cv2.line(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(annotated, f"{angle:.1f} deg  t={t:.2f}s",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                else:
                    cv2.putText(annotated, f"No detection  t={t:.2f}s",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                writer.write(annotated)

            if DIAG_STRIDE > 0 and frame_idx % DIAG_STRIDE == 0:
                save_diagnostic_frame(img_rgb, frame_idx, t)
                print(f"  saved diagnostic for frame {frame_idx}")

            if frame_idx % (10 * STRIDE) == 0:
                pct = 100 * frame_idx / max(n_frames, 1)
                print(f"  frame {frame_idx}/{n_frames} ({pct:.0f}%)  "
                      f"angle={angle:.1f}°" if angle is not None
                      else f"  frame {frame_idx}/{n_frames} ({pct:.0f}%)  no detection")

        frame_idx += 1

    cap.release()
    if WRITE_VIDEO:
        writer.release()
        print(f"Annotated video saved to {OUT_VIDEO}")
    if DIAG_STRIDE > 0:
        print(f"Diagnostic frames saved to {DIAG_DIR}/")

    if len(angles) < 2:
        print("Not enough detections to plot.")
        return

    times  = np.array(times)
    angles_raw = np.array(angles)
    angles_unwrapped = angle_unwrap_180(angles_raw.tolist())

    # estimate average rotation speed from unwrapped angle
    slope, _ = np.polyfit(times, np.deg2rad(angles_unwrapped), 1)  # rad/s
    rpm = slope / (2 * np.pi) * 60
    print(f"\nMean rotation rate: {rpm:.2f} RPM ({slope:.3f} rad/s)")

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)

    axes[0].plot(times, angles_raw % 180, '.', ms=2, color='steelblue')
    axes[0].set_ylabel('Raw angle mod 180° (deg)')
    axes[0].set_title(f'Sail angle vs time  |  mean {rpm:.2f} RPM')
    axes[0].set_ylim(0, 180)
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(times, angles_unwrapped, '-', lw=1, color='orange')
    fit_line = np.rad2deg(slope * times + np.deg2rad(angles_unwrapped[0]))
    axes[1].plot(times, fit_line, 'r--', lw=1, label=f'linear fit: {rpm:.2f} RPM')
    axes[1].set_ylabel('Unwrapped angle (deg)')
    axes[1].set_xlabel('Time (s)')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUT_PLOT, dpi=150)
    print(f"Plot saved to {OUT_PLOT}")


if __name__ == '__main__':
    main()
