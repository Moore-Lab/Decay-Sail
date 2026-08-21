#!/usr/bin/env python3
"""
Build a median background image from a video for sail angle detection.
Samples every STRIDE-th frame within an optional time range, computes
pixel-wise median, and saves the result.

Usage:
    python3 build_background.py <video_path> [--stride N] [--start T] [--end T]

    --stride N   sample every Nth frame (default: 30)
    --start T    start time in seconds (default: 0)
    --end T      end time in seconds (default: end of video)

Outputs:
    /tmp/sail_background.npy   -- background array (float32)
    /tmp/sail_background.png   -- diagnostic image
"""

import sys
import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import cv2
from skimage.color import rgb2gray

OUT_NPY = '/tmp/sail_background.npy'
OUT_PNG = '/tmp/sail_background.png'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('video_path')
    parser.add_argument('--stride', type=int, default=30)
    parser.add_argument('--start',  type=float, default=0.0,  help='start time (s)')
    parser.add_argument('--end',    type=float, default=None, help='end time (s)')
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {args.video_path}")

    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps      = cap.get(cv2.CAP_PROP_FPS) or 27.0
    duration = n_frames / fps

    frame_start = int(args.start * fps)
    frame_end   = int(args.end * fps) if args.end is not None else n_frames
    frame_end   = min(frame_end, n_frames)

    n_sampled = (frame_end - frame_start) // args.stride
    print(f"Video: {n_frames} frames @ {fps:.1f} fps ({duration/60:.1f} min)")
    print(f"Using {args.start:.1f}s – {frame_end/fps:.1f}s  "
          f"(frames {frame_start}–{frame_end})")
    print(f"Sampling every {args.stride}th frame → ~{n_sampled} frames")

    frames = []
    for i in range(frame_start, frame_end, args.stride):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            continue
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frames.append(rgb2gray(img_rgb).astype(np.float32))
        if len(frames) % 50 == 0:
            print(f"  loaded {len(frames)}/{n_sampled} frames...")

    cap.release()
    print(f"Computing median over {len(frames)} frames...")
    stack = np.stack(frames, axis=0)
    background = np.median(stack, axis=0).astype(np.float32)

    np.save(OUT_NPY, background)
    print(f"Background saved to {OUT_NPY}")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(f"Background ({len(frames)} frames, stride={args.stride}, "
                 f"{args.start:.0f}s–{frame_end/fps:.0f}s)", fontsize=11)

    axes[0].imshow(background, cmap='gray')
    axes[0].set_title('Median background')

    std_img = stack.std(axis=0)
    axes[1].imshow(std_img, cmap='hot')
    axes[1].set_title('Std across frames\n(sail region should be bright)')
    plt.colorbar(axes[1].images[0], ax=axes[1])

    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=150)
    print(f"Diagnostic saved to {OUT_PNG}")
    print("Done — load background with: bg = np.load('/tmp/sail_background.npy')")


if __name__ == '__main__':
    main()
