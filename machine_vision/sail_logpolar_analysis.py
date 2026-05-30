#!/usr/bin/env python3
"""
Sail angle tracking via log-polar cross-correlation.

Converts a circular crop of each frame to polar coordinates centered on the
disk.  Cross-correlating consecutive polar frames in the angular (θ) direction
gives Δθ per frame; integrating gives cumulative angle vs time.

Works with asymmetric lighting because the lighting envelope is FIXED while
only the sail/disk texture rotates — so the cross-correlation tracks the
rotating features regardless of which part of the ring is bright.

Usage:
    python3 sail_logpolar_analysis.py <video>
    python3 sail_logpolar_analysis.py <video> --start 105 --end 165
    python3 sail_logpolar_analysis.py <video> --start 105 --end 165 --stride 2
    python3 sail_logpolar_analysis.py <video> --diag_frame 50  # show polar of frame 50
"""

import numpy as np
import cv2
import argparse
import os
from skimage.registration import phase_cross_correlation

# ── CONFIG ───────────────────────────────────────────────────────────────────
DISK_CENTER_FRAC = (0.49, 0.45)   # (row_frac, col_frac) of disk centre
DISK_RADIUS_FRAC = 0.165          # crop radius as fraction of image width
                                  # (ring sits at 0.133, this adds a margin)
THETA_BINS = 720                  # angular bins in polar image (0.5° steps)
R_BINS     = 100                  # radial bins in polar image
UPSAMPLE   = 20                   # sub-pixel factor for phase correlation
MAX_DELTA  = 45.0                 # degrees — reject shifts larger than this
                                  # (filters out spurious correlation jumps)
# ─────────────────────────────────────────────────────────────────────────────


def get_polar(gray_f32, cy, cx, r_max):
    """Warp a grayscale float32 image into (R_BINS × THETA_BINS) polar coords."""
    polar = cv2.warpPolar(
        gray_f32,
        (THETA_BINS, R_BINS),
        (cx, cy),
        r_max,
        cv2.WARP_POLAR_LINEAR | cv2.INTER_LINEAR,
    )
    return polar  # shape: (R_BINS, THETA_BINS)


def find_delta_theta(polar1, polar2):
    """
    Return Δθ in degrees between two consecutive polar frames.
    Uses phase cross-correlation in the Fourier domain.
    Returns None if the shift exceeds MAX_DELTA (likely a spurious correlation).
    """
    def norm(p):
        m, s = p.mean(), p.std()
        return (p - m) / (s + 1e-6)

    shift, _, _ = phase_cross_correlation(norm(polar1), norm(polar2),
                                          upsample_factor=UPSAMPLE)
    # shift = [Δrow (radial), Δcol (angular)] in pixels
    delta_px = shift[1]
    # Unwrap: choose the smallest-magnitude equivalent shift
    if delta_px > THETA_BINS / 2:
        delta_px -= THETA_BINS
    elif delta_px < -THETA_BINS / 2:
        delta_px += THETA_BINS
    delta_deg = delta_px / THETA_BINS * 360.0
    if abs(delta_deg) > MAX_DELTA:
        return None
    return delta_deg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('video')
    parser.add_argument('--start',  type=float, default=0.0,  help='start time (s)')
    parser.add_argument('--end',    type=float, default=None, help='end time (s)')
    parser.add_argument('--stride', type=int,   default=1,    help='process every Nth frame')
    parser.add_argument('--out',    default='/tmp/logpolar',  help='output directory')
    parser.add_argument('--diag_frame', type=int, default=None,
                        help='save polar image of this frame index for diagnostics')
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {args.video}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 27.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start_frame = int(args.start * fps)
    end_frame = int(args.end * fps) if args.end is not None else total_frames
    end_frame = min(end_frame, total_frames)

    print(f"Video: {total_frames} frames @ {fps:.1f} fps")
    print(f"Processing frames {start_frame}–{end_frame}  "
          f"({(end_frame-start_frame)/fps:.1f}s, stride={args.stride})")

    frame_times, cumulative_angles, delta_list = [], [], []
    cumulative = 0.0
    prev_polar = None
    skipped = 0

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    frame_idx = start_frame

    while frame_idx < end_frame:
        ret, frame = cap.read()
        if not ret:
            break

        process = (frame_idx - start_frame) % args.stride == 0

        if args.diag_frame is not None and frame_idx == args.diag_frame:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
            h, w = gray.shape
            cy = int(DISK_CENTER_FRAC[0] * h)
            cx = int(DISK_CENTER_FRAC[1] * w)
            r_max = int(DISK_RADIUS_FRAC * w)
            polar = get_polar(gray, cy, cx, r_max)
            _save_diag_polar(gray, polar, cy, cx, r_max, args.out, frame_idx)
            print(f"Diagnostic polar saved for frame {frame_idx}.")

        if process:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
            h, w = gray.shape
            cy = int(DISK_CENTER_FRAC[0] * h)
            cx = int(DISK_CENTER_FRAC[1] * w)
            r_max = int(DISK_RADIUS_FRAC * w)
            polar = get_polar(gray, cy, cx, r_max)

            if prev_polar is not None:
                delta = find_delta_theta(prev_polar, polar)
                if delta is None:
                    skipped += 1
                    delta = 0.0  # hold position on bad frame
                cumulative += delta
                frame_times.append(frame_idx / fps)
                cumulative_angles.append(cumulative)
                delta_list.append(delta)

            prev_polar = polar

        frame_idx += 1

    cap.release()

    frame_times = np.array(frame_times)
    angles = np.array(cumulative_angles)
    deltas = np.array(delta_list)

    print(f"\nProcessed {len(angles)} frame pairs  ({skipped} skipped / out-of-range)")
    if len(angles) > 0:
        total_rot = angles[-1]
        duration = frame_times[-1] - frame_times[0]
        avg_rate = total_rot / duration if duration > 0 else 0.0
        rps = avg_rate / 360.0
        print(f"Total rotation: {total_rot:.1f}°  over {duration:.1f}s")
        print(f"Average rate:   {avg_rate:.1f} °/s = {rps:.3f} rev/s = {rps*60:.2f} RPM")

    _save_plots(frame_times, angles, deltas, args.out, fps, args.stride)
    _save_data(frame_times, angles, deltas, args.out)


def _save_plots(frame_times, angles, deltas, out_dir, fps, stride):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), facecolor='#111111')
    fig.suptitle('Sail rotation — log-polar cross-correlation', color='white')

    ax = axes[0]
    ax.set_facecolor('black')
    ax.plot(frame_times, angles, color='cyan', lw=1)
    ax.set_xlabel('Time (s)', color='white')
    ax.set_ylabel('Cumulative angle (°)', color='white')
    ax.set_title('Cumulative rotation', color='white')
    ax.tick_params(colors='white')
    ax.grid(True, alpha=0.3)

    ax2 = axes[1]
    ax2.set_facecolor('black')
    if len(deltas) > 1:
        # smooth instantaneous rate
        dt = np.diff(frame_times, prepend=frame_times[0])
        dt = np.where(dt < 1e-6, 1.0 / fps, dt)
        rate = deltas / dt
        # rolling median to suppress spikes
        from scipy.ndimage import median_filter
        rate_smooth = median_filter(rate, size=max(1, int(fps // stride)))
        ax2.plot(frame_times, np.abs(rate_smooth), color='orange', lw=1)
        ax2.set_xlabel('Time (s)', color='white')
        ax2.set_ylabel('|Spin rate| (°/s)', color='white')
        ax2.set_title('Instantaneous spin rate (smoothed)', color='white')
        ax2.tick_params(colors='white')
        ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    out = os.path.join(out_dir, 'angle_vs_time.png')
    plt.savefig(out, dpi=150, facecolor='#111111')
    print(f"Plot saved to {out}")
    plt.close()


def _save_data(frame_times, angles, deltas, out_dir):
    out = os.path.join(out_dir, 'angle_data.npz')
    np.savez(out, times=frame_times, angles=angles, deltas=deltas)
    print(f"Raw data saved to {out}")


def _save_diag_polar(gray, polar, cy, cx, r_max, out_dir, frame_idx):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), facecolor='#111111')
    fig.suptitle(f'Polar diagnostic — frame {frame_idx}', color='white')

    ax = axes[0]
    ax.imshow(gray, cmap='gray')
    ax.plot(cx, cy, 'c+', markersize=15, markeredgewidth=2)
    circle = plt.Circle((cx, cy), r_max, color='cyan', fill=False, lw=1.5)
    ax.add_patch(circle)
    ax.set_title(f'Original (crop radius={r_max}px)', color='white')
    ax.tick_params(colors='white')

    ax2 = axes[1]
    ax2.imshow(polar, cmap='gray', aspect='auto',
               extent=[0, 360, r_max, 0])
    ax2.set_xlabel('Angle θ (°)', color='white')
    ax2.set_ylabel('Radius (px)', color='white')
    ax2.set_title('Polar transform\n(sail stripe should appear as vertical band)', color='white')
    ax2.tick_params(colors='white')

    fig.tight_layout()
    out = os.path.join(out_dir, f'polar_frame_{frame_idx:04d}.png')
    plt.savefig(out, dpi=150, facecolor='#111111')
    plt.close()


if __name__ == '__main__':
    main()
