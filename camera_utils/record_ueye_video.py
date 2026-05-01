import signal
import sys
import cv2
import numpy as np
from pyueye import ueye
from datetime import datetime

def _cleanup_and_exit(sig, frame):
    print("\nInterrupted — cleaning up...")
    try:
        cv2.destroyAllWindows()
    except Exception:
        pass
    sys.exit(0)

signal.signal(signal.SIGINT, _cleanup_and_exit)
signal.signal(signal.SIGTERM, _cleanup_and_exit)

# sometimes the working cam is the 2nd one and using hCam = ueye.HIDS(1) does not work

# --- Camera Initialization ---
hCam = ueye.HIDS(0)
ueye.is_InitCamera(hCam, None)

ueye.is_SetColorMode(hCam, ueye.IS_CM_BGR8_PACKED)
ueye.is_SetDisplayMode(hCam, ueye.IS_SET_DM_DIB)

# --- Define hardware ROI (x, y, width, height) ---
roi_x, roi_y, roi_w, roi_h = 440, 250, 560, 510

rect_aoi = ueye.IS_RECT()
rect_aoi.s32X = roi_x
rect_aoi.s32Y = roi_y
rect_aoi.s32Width = roi_w
rect_aoi.s32Height = roi_h
ueye.is_AOI(hCam, ueye.IS_AOI_IMAGE_SET_AOI, rect_aoi, ueye.sizeof(rect_aoi))

# --- Allocate single image buffer ---
MemPtr = ueye.c_mem_p()
MemID = ueye.int()
ueye.is_AllocImageMem(hCam, roi_w, roi_h, 24, MemPtr, MemID)
ueye.is_SetImageMem(hCam, MemPtr, MemID)

# --- Set exposure ---
desired_exposure_ms = 12.0
actual_exposure = ueye.double(desired_exposure_ms)
ueye.is_Exposure(hCam, ueye.IS_EXPOSURE_CMD_SET_EXPOSURE, actual_exposure, ueye.sizeof(actual_exposure))
ueye.is_Exposure(hCam, ueye.IS_EXPOSURE_CMD_GET_EXPOSURE, actual_exposure, ueye.sizeof(actual_exposure))
print("Exposure set to:", actual_exposure.value, "ms")

# --- Calibrate actual FPS ---
# is_FreezeVideo(IS_WAIT) triggers a hardware capture and blocks until the frame
# is delivered, so each call counts exactly one real frame.
print("Calibrating frame rate (2 seconds)...")
calibration_frames = 0
calibration_start = datetime.now()
calibration_duration = 2.0

while True:
    ueye.is_FreezeVideo(hCam, ueye.IS_WAIT)
    calibration_frames += 1
    elapsed = (datetime.now() - calibration_start).total_seconds()
    if elapsed >= calibration_duration:
        break

actual_fps = calibration_frames / elapsed
# Fallback to exposure-based estimate if calibration gives an implausible result
if actual_fps < 1.0 or actual_fps > 10000.0:
    actual_fps = 1000.0 / actual_exposure.value
print(f"Measured actual FPS: {actual_fps:.1f}")

# --- OpenCV Video Writer ---
# MJPG has no FPS/timebase restrictions unlike XVID/MPEG4
fps = actual_fps
fourcc = cv2.VideoWriter_fourcc(*'MJPG')
ts_start = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
out = cv2.VideoWriter(f"output_roi_{ts_start}.avi", fourcc, fps, (roi_w, roi_h))

if not out.isOpened():
    raise RuntimeError(f"VideoWriter failed to open (fps={fps:.1f})")

print(f"Recording at {fps:.1f} fps... press 'q' to quit.")
while True:
    ueye.is_FreezeVideo(hCam, ueye.IS_WAIT)
    array = ueye.get_data(MemPtr, roi_w, roi_h, 24, pitch=roi_w * 3, copy=True)
    frame = np.reshape(array, (roi_h, roi_w, 3))
    frame = cv2.flip(frame, -1)  # Flip vertically & horizontally

    out.write(frame)
    cv2.imshow("Hardware ROI Stream", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# --- Cleanup ---
out.release()
cv2.destroyAllWindows()
ueye.is_FreeImageMem(hCam, MemPtr, MemID)
ueye.is_ExitCamera(hCam)
