#!/usr/bin/env python3
"""
Closed-loop sail spin control.
Reads sail angle from a USB camera, estimates angular velocity,
and adjusts the drive frequency via EPICS to maintain a target spin rate.

Set DRY_RUN = True to test without touching EPICS.
"""

import cv2
import numpy as np
import time
import csv
import sys
from collections import deque
from epics import caget, caput

sys.path.insert(0, '/Users/mollywatts/Library/CloudStorage/OneDrive-Personal/VSCode/Decay-Sail/linux_code')
from sail_angle_diagnostic import detect_from_array

# ── CONFIG ──────────────────────────────────────────────────────────────────
CAMERA_INDEX  = 0        # USB camera index (try 1 or 2 if 0 is wrong)
TARGET_RPM    = 30.0     # target rotation speed in RPM (positive = CCW in image)
KP            = 0.05     # proportional gain: freq_correction = KP * rpm_error
FREQ_MIN      = 0.3      # Hz — clamp drive frequency to this range
FREQ_MAX      = 5.0      # Hz
LOOP_DT       = 0.1      # seconds between control updates
ANGLE_HISTORY = 20       # number of frames used to fit angular velocity
LOG_FILE      = '/tmp/sail_control_log.csv'
DRY_RUN       = True     # if True, print EPICS commands instead of running them
SHOW_VIDEO    = True     # show annotated live feed (requires display)

PV      = 'Y1:RDS-OUTS_DRV'
FREQ_PV = f'{PV}_FREQ'
# ────────────────────────────────────────────────────────────────────────────


def open_camera(index):
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index {index}. Try CAMERA_INDEX = 1 or 2.")
    print(f"Camera {index} opened: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
          f"{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} @ "
          f"{cap.get(cv2.CAP_PROP_FPS):.0f} fps")
    return cap


def estimate_omega_rps(times, angles_deg):
    """
    Fit angular velocity (rev/s) from a history of (time, angle) pairs.
    The sail has 180° symmetry, so angles are folded to [0, 180) before unwrapping.
    Returns signed angular velocity in rev/s, or None if not enough data.
    """
    if len(times) < 4:
        return None
    t = np.array(times)
    a = np.deg2rad(np.array(angles_deg) % 180.0)  # fold to [0, π)
    # double the angle so np.unwrap can handle the π periodicity
    unwrapped = np.unwrap(2 * a) / 2.0
    slope, _ = np.polyfit(t - t[0], unwrapped, 1)  # rad/s
    return slope / (2 * np.pi)  # convert to rev/s


def annotate_frame(frame, sail_angle, omega_rps, drive_freq):
    out = frame.copy()
    h, w = out.shape[:2]
    if sail_angle is not None:
        # draw sail line through center
        cx = int(0.51 * w)
        cy = int(0.59 * h)
        r  = int(0.133 * w)
        a  = np.deg2rad(sail_angle)
        length = int(r * 1.4)
        x1 = int(cx + length * np.cos(a))
        y1 = int(cy + length * np.sin(a))
        x2 = int(cx + length * np.cos(a + np.pi))
        y2 = int(cy + length * np.sin(a + np.pi))
        cv2.line(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(out, (cx, cy), r, (0, 255, 255), 1)
        cv2.putText(out, f"Angle: {sail_angle:.1f} deg", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    if omega_rps is not None:
        rpm = omega_rps * 60
        cv2.putText(out, f"Speed: {rpm:.1f} RPM", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.putText(out, f"Drive: {drive_freq:.3f} Hz", (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    cv2.putText(out, mode, (10, h - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 100, 255) if DRY_RUN else (0, 255, 0), 2)
    return out


def main():
    cap = open_camera(CAMERA_INDEX)
    target_rps = TARGET_RPM / 60.0

    if DRY_RUN:
        print(f"DRY RUN — no EPICS commands will be sent. Target: {TARGET_RPM:.1f} RPM")
        current_freq = 1.0
    else:
        current_freq = float(caget(FREQ_PV) or 1.0)
        print(f"LIVE mode. Current drive freq: {current_freq:.3f} Hz. Target: {TARGET_RPM:.1f} RPM")

    times  = deque(maxlen=ANGLE_HISTORY)
    angles = deque(maxlen=ANGLE_HISTORY)
    omega_rps = None

    with open(LOG_FILE, 'w', newline='') as logf:
        writer = csv.writer(logf)
        writer.writerow(['time', 'sail_angle_deg', 'omega_rps', 'drive_freq_hz'])

        print("Running — press Ctrl-C to stop, or 'q' in the video window.")
        try:
            while True:
                t0 = time.time()
                ret, frame = cap.read()
                if not ret:
                    print("Camera read failed, retrying...")
                    time.sleep(0.2)
                    continue

                # OpenCV gives BGR — convert to RGB for detection
                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                sail_angle = detect_from_array(img_rgb)

                if sail_angle is not None:
                    now = time.time()
                    times.append(now)
                    angles.append(sail_angle)
                    omega_rps = estimate_omega_rps(list(times), list(angles))

                    if omega_rps is not None:
                        actual_rpm = omega_rps * 60
                        error_rps  = target_rps - abs(omega_rps)
                        new_freq   = float(np.clip(current_freq + KP * error_rps, FREQ_MIN, FREQ_MAX))

                        print(f"Angle: {sail_angle:6.1f}°  |  Speed: {actual_rpm:+6.1f} RPM  |  "
                              f"Drive: {current_freq:.3f} → {new_freq:.3f} Hz")

                        if not DRY_RUN:
                            caput(FREQ_PV, new_freq)
                        current_freq = new_freq

                        writer.writerow([now, sail_angle, omega_rps, current_freq])
                        logf.flush()
                    else:
                        print(f"Angle: {sail_angle:6.1f}°  |  Speed: accumulating history...")
                else:
                    print("Sail not detected in frame")

                if SHOW_VIDEO:
                    annotated = annotate_frame(frame, sail_angle, omega_rps, current_freq)
                    cv2.imshow('Sail Control', annotated)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

                elapsed = time.time() - t0
                time.sleep(max(0.0, LOOP_DT - elapsed))

        except KeyboardInterrupt:
            print("\nControl loop stopped by user.")
        finally:
            cap.release()
            if SHOW_VIDEO:
                cv2.destroyAllWindows()
            print(f"Log saved to {LOG_FILE}")


if __name__ == '__main__':
    main()
