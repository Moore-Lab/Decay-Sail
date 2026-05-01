import cv2
import numpy as np
from pyueye import ueye
from datetime import datetime

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

# --- Set exposure ---
desired_exposure_ms = 12.0
actual_exposure = ueye.double(desired_exposure_ms)
ueye.is_Exposure(hCam, ueye.IS_EXPOSURE_CMD_SET_EXPOSURE, actual_exposure, ueye.sizeof(actual_exposure))
ueye.is_Exposure(hCam, ueye.IS_EXPOSURE_CMD_GET_EXPOSURE, actual_exposure, ueye.sizeof(actual_exposure))
print("Exposure set to:", actual_exposure.value, "ms")

# --- Allocate ring buffer (allows continuous streaming without dropped frames) ---
NUM_BUFFERS = 10
mem_list = []
for _ in range(NUM_BUFFERS):
    mem_ptr = ueye.c_mem_p()
    mem_id = ueye.int()
    ueye.is_AllocImageMem(hCam, roi_w, roi_h, 24, mem_ptr, mem_id)
    ueye.is_AddToSequence(hCam, mem_ptr, mem_id)
    mem_list.append((mem_ptr, mem_id))

# --- Start live capture ---
ueye.is_CaptureVideo(hCam, ueye.IS_DONT_WAIT)

reported_fps = ueye.double()
ueye.is_GetFramesPerSecond(hCam, reported_fps)
print(f"Camera reported FPS: {reported_fps.value:.1f}")

# --- Calibrate actual FPS by counting real frames from the ring buffer ---
# is_WaitForNextImage blocks until a new frame arrives, so this counts
# actual hardware frames, not buffer re-reads.
print("Calibrating frame rate (2 seconds)...")
calibration_frames = 0
calibration_start = datetime.now()
calibration_duration = 2.0

img_ptr = ueye.c_mem_p()
img_id = ueye.int()

while True:
    ret = ueye.is_WaitForNextImage(hCam, 1000, img_ptr, img_id)
    if ret == ueye.IS_SUCCESS:
        ueye.is_UnlockSeqBuf(hCam, img_id, img_ptr)
        calibration_frames += 1
    elapsed = (datetime.now() - calibration_start).total_seconds()
    if elapsed >= calibration_duration:
        break

actual_fps = calibration_frames / elapsed
print(f"Measured actual FPS: {actual_fps:.1f}")

# --- OpenCV Video Writer ---
# MJPG has no FPS/timebase restrictions unlike XVID/MPEG4 (which caps at ~65k denominator)
fps = actual_fps
fourcc = cv2.VideoWriter_fourcc(*'MJPG')
ts_start = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
out = cv2.VideoWriter(f"output_roi_{ts_start}.avi", fourcc, fps, (roi_w, roi_h))

print(f"Recording at {fps:.1f} fps... press 'q' to quit.")
while True:
    ret = ueye.is_WaitForNextImage(hCam, 1000, img_ptr, img_id)
    if ret != ueye.IS_SUCCESS:
        continue

    array = ueye.get_data(img_ptr, roi_w, roi_h, 24, pitch=roi_w * 3, copy=True)
    ueye.is_UnlockSeqBuf(hCam, img_id, img_ptr)

    frame = np.reshape(array, (roi_h, roi_w, 3))
    frame = cv2.flip(frame, -1)  # Flip vertically & horizontally

    out.write(frame)
    cv2.imshow("Hardware ROI Stream", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# --- Cleanup ---
out.release()
cv2.destroyAllWindows()
ueye.is_StopLiveVideo(hCam, ueye.IS_FORCE_VIDEO_STOP)
ueye.is_ClearSequence(hCam)
for mem_ptr, mem_id in mem_list:
    ueye.is_FreeImageMem(hCam, mem_ptr, mem_id)
ueye.is_ExitCamera(hCam)
