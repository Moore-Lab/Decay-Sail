#!/usr/bin/env python3
"""
Sail angle detection via minimum-edge stripe (Method 6).

The mylar sail and its shadow create a smooth, texture-free stripe across the
graphite disk interior. Canny edge detection produces dense edges in the
graphite but a dark (edge-free) band along the sail direction. Scanning all
180 orientations and summing edge density along each gives the sail angle as
the orientation with fewest edges.

Gives ABSOLUTE angle per frame -- errors do not accumulate over time.

Usage:
    python3 sail_minedge_analysis.py <video>
    python3 sail_minedge_analysis.py <video> --start 100 --end 300
    python3 sail_minedge_analysis.py <video> --stride 10 --out /tmp/minedge

Outputs (in --out directory, default /tmp/minedge/):
    angle_vs_time.png   -- raw and smoothed angle vs time
    angle_data.npz      -- times, raw angles, smoothed angles
    sample_grid.png     -- annotated sample frames for visual verification
"""

import numpy as np
import cv2
import argparse
import os
from scipy.ndimage import uniform_filter1d

# -- CONFIG -------------------------------------------------------------------
DISK_CENTER_FRAC = (0.49, 0.45)   # (row_frac, col_frac) of disk centre
RING_RADIUS_FRAC = 0.133          # magnet ring radius / image width
INTERIOR_FRAC    = 0.80           # mask radius = INTERIOR_FRAC * ring_radius
BAND_FRAC        = 0.06           # half-width of scan band / ring_radius
PROFILE_SMOOTH   = 20             # deg -- running average on angle profile
OUTLIER_WINDOW   = 15             # frames -- rolling median window for outlier rejection
OUTLIER_THRESH   = 40.0           # deg -- flag if raw angle deviates > this from rolling median
# -----------------------------------------------------------------------------


def detect_angle(gray, cy, cx, disk_r):
    """
    Return sail angle in degrees (0-179) for one grayscale frame crop.
    Also returns the edge image for diagnostics.
    """
    h, w = gray.shape
    interior_r = int(disk_r * INTERIOR_FRAC)
    band_half  = max(3, int(disk_r * BAND_FRAC))

    # High-pass: flatten brightness gradient from off-axis LED
    blur_bg = cv2.GaussianBlur(gray, (31, 31), 0)
    hp = np.clip(gray.astype(np.float32) * 1.5
                 - blur_bg.astype(np.float32) * 0.5 + 128,
                 0, 255).astype(np.uint8)

    edges = cv2.Canny(hp, 10, 40).astype(np.float32)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, (cx, cy), interior_r, 255, -1)
    edges[mask == 0] = 0

    sums = np.zeros(180)
    for theta_deg in range(180):
        rad  = np.radians(theta_deg)
        perp = rad + np.pi / 2
        total = 0.0
        for offset in range(-band_half, band_half + 1):
            cx2 = cx + offset * np.cos(perp)
            cy2 = cy + offset * np.sin(perp)
            t_vals = np.linspace(-interior_r, interior_r, interior_r * 2)
            xs = np.clip((cx2 + t_vals * np.cos(rad)).astype(int), 0, w - 1)
            ys = np.clip((cy2 + t_vals * np.sin(rad)).astype(int), 0, h - 1)
            total += edges[ys, xs].sum()
        sums[theta_deg] = total

    sums_smooth = uniform_filter1d(sums, size=PROFILE_SMOOTH, mode='wrap')
    angle = int(np.argmin(sums_smooth))
    return angle, edges, interior_r


def get_crop(gray, cy, cx, margin):
    r0 = max(0, cy - margin)
    c0 = max(0, cx - margin)
    crop = gray[r0:cy + margin, c0:cx + margin]
    ccy  = cy - r0
    ccx  = cx - c0
    return crop, ccy, ccx


def annotate(gray_crop, angle, ccy, ccx, disk_r, interior_r):
    ann = cv2.cvtColor(gray_crop, cv2.COLOR_GRAY2BGR)
    sail_rad = np.radians(angle)
    L = int(disk_r * 1.3)
    p1 = (int(ccx - L * np.cos(sail_rad)), int(ccy - L * np.sin(sail_rad)))
    p2 = (int(ccx + L * np.cos(sail_rad)), int(ccy + L * np.sin(sail_rad)))
    cv2.line(ann, p1, p2, (0, 255, 0), 2)
    cv2.circle(ann, (ccx, ccy), 4, (0, 0, 255), -1)
    cv2.circle(ann, (ccx, ccy), interior_r, (255, 200, 0), 1)
    return ann


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('video')
    parser.add_argument('--start',  type=float, default=0.0)
    parser.add_argument('--end',    type=float, default=None)
    parser.add_argument('--stride', type=int,   default=10,
                        help='process every Nth frame (default 10 ~ 3fps at 30fps)')
    parser.add_argument('--out',    default='/tmp/minedge')
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open: {args.video}")

    fps          = cap.get(cv2.CAP_PROP_FPS) or 27.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start_frame  = int(args.start * fps)
    end_frame    = int(args.end   * fps) if args.end else total_frames
    end_frame    = min(end_frame, total_frames)

    print(f"Video: {total_frames} frames @ {fps:.1f} fps  ({total_frames/fps:.0f}s)")
    print(f"Window: {start_frame/fps:.1f}s - {end_frame/fps:.1f}s  stride={args.stride}")

    frame_times, raw_angles = [], []
    n_processed = 0

    for fi in range(start_frame, end_frame, args.stride):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        cy     = int(DISK_CENTER_FRAC[0] * h)
        cx     = int(DISK_CENTER_FRAC[1] * w)
        disk_r = int(RING_RADIUS_FRAC * w)
        margin = int(0.22 * w)

        crop, ccy, ccx = get_crop(gray, cy, cx, margin)
        angle, _, _ = detect_angle(crop, ccy, ccx, disk_r)

        frame_times.append(fi / fps)
        raw_angles.append(angle)
        n_processed += 1

        if n_processed % 100 == 0:
            print(f"  {n_processed} frames processed  (t={fi/fps:.0f}s, angle={angle}°)")

    cap.release()

    frame_times = np.array(frame_times, dtype=float)
    raw_angles  = np.array(raw_angles,  dtype=float)

    # Rolling median outlier rejection
    half = OUTLIER_WINDOW // 2
    smoothed = raw_angles.copy()
    for i in range(len(raw_angles)):
        lo = max(0, i - half)
        hi = min(len(raw_angles), i + half + 1)
        med = np.median(raw_angles[lo:hi])
        diff = abs(raw_angles[i] - med)
        # Handle 180-deg wrap
        diff = min(diff, 180.0 - diff)
        if diff > OUTLIER_THRESH:
            smoothed[i] = med
    # Final smooth pass
    smoothed = uniform_filter1d(smoothed, size=OUTLIER_WINDOW, mode='nearest')

    print(f"\nProcessed {n_processed} frames")
    print(f"Raw angle range: {raw_angles.min():.0f}° - {raw_angles.max():.0f}°")

    _save_plots(frame_times, raw_angles, smoothed, args.out)
    np.savez(os.path.join(args.out, 'angle_data.npz'),
             times=frame_times, raw=raw_angles, smoothed=smoothed)
    print(f"Data saved to {args.out}/angle_data.npz")

    _save_sample_grid(args.video, fps, frame_times, smoothed, args.out)


def _save_plots(times, raw, smoothed, out_dir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(14, 5), facecolor='#111111')
    ax.set_facecolor('black')
    ax.plot(times, raw,      color='cyan',   lw=0.6, alpha=0.5, label='raw')
    ax.plot(times, smoothed, color='yellow', lw=1.5, label='smoothed')
    ax.set_xlabel('Time (s)', color='white')
    ax.set_ylabel('Sail angle (deg)', color='white')
    ax.set_title('Sail angle vs time — min-edge stripe method', color='white')
    ax.tick_params(colors='white')
    ax.legend(labelcolor='white', facecolor='#222')
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 180)
    fig.tight_layout()
    out = os.path.join(out_dir, 'angle_vs_time.png')
    plt.savefig(out, dpi=150, facecolor='#111111')
    print(f"Plot saved to {out}")
    plt.close()


def _save_sample_grid(video_path, fps, times, angles, out_dir, n=16):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    cap = cv2.VideoCapture(video_path)
    idx = np.linspace(0, len(times) - 1, n, dtype=int)

    fig, axes = plt.subplots(4, 4, figsize=(20, 20), facecolor='#111111')
    fig.suptitle('Min-edge stripe — sample annotated frames', color='white', fontsize=12)

    for ax, i in zip(axes.flatten(), idx):
        t = times[i]; ang = angles[i]
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ret, frame = cap.read()
        if not ret:
            ax.axis('off'); continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        cy     = int(DISK_CENTER_FRAC[0] * h)
        cx     = int(DISK_CENTER_FRAC[1] * w)
        disk_r = int(RING_RADIUS_FRAC * w)
        margin = int(0.22 * w)
        interior_r = int(disk_r * INTERIOR_FRAC)

        crop, ccy, ccx = get_crop(gray, cy, cx, margin)
        ann = annotate(crop, int(ang), ccy, ccx, disk_r, interior_r)

        ax.imshow(ann[:, :, ::-1])
        ax.set_title(f't={t:.0f}s  {ang:.0f}°', color='lime', fontsize=9)
        ax.axis('off')

    cap.release()
    plt.tight_layout()
    out = os.path.join(out_dir, 'sample_grid.png')
    plt.savefig(out, dpi=100, facecolor='#111111')
    print(f"Sample grid saved to {out}")
    plt.close()


if __name__ == '__main__':
    main()
