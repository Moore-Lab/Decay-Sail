import cv2
import numpy as np
from pyueye import ueye

# --- Camera Initialization ---
hCam = ueye.HIDS(0)  # first camera
ueye.is_InitCamera(hCam, None)

# Set color mode
ueye.is_SetColorMode(hCam, ueye.IS_CM_BGR8_PACKED)

# --- Define hardware ROI (x, y, width, height) ---
roi_x, roi_y, roi_w, roi_h = 440, 250, 560, 510

rect_aoi = ueye.IS_RECT()
rect_aoi.s32X = roi_x
rect_aoi.s32Y = roi_y
rect_aoi.s32Width = roi_w
rect_aoi.s32Height = roi_h

# Apply AOI to camera
ueye.is_AOI(hCam, ueye.IS_AOI_IMAGE_SET_AOI, rect_aoi, ueye.sizeof(rect_aoi))

# --- Allocate image memory for this AOI ---
MemPtr = ueye.c_mem_p()
MemID = ueye.int()
ueye.is_AllocImageMem(hCam, roi_w, roi_h, 24, MemPtr, MemID)
ueye.is_SetImageMem(hCam, MemPtr, MemID)
ueye.is_SetDisplayMode(hCam, ueye.IS_SET_DM_DIB)

#Set exposure
desired_exposure_ms = 12.0 #ms
actual_exposure = ueye.double(desired_exposure_ms)

# Apply exposure time
ueye.is_Exposure(hCam, ueye.IS_EXPOSURE_CMD_SET_EXPOSURE, actual_exposure, ueye.sizeof(actual_exposure))

# Verify what exposure camera actually applied
ueye.is_Exposure(hCam, ueye.IS_EXPOSURE_CMD_GET_EXPOSURE, actual_exposure, ueye.sizeof(actual_exposure))
print("Exposure set to:", actual_exposure.value, "ms")

# --- Start Capture ---
ueye.is_CaptureVideo(hCam, ueye.IS_DONT_WAIT)

# --- OpenCV Video Writer ---
fps = 60.0   # use your camera’s max ROI frame rate
fourcc = cv2.VideoWriter_fourcc(*'XVID')
out = cv2.VideoWriter("output_roi.avi", fourcc, fps, (roi_w, roi_h))

print("Streaming ROI... press 'q' to quit.")
while True:
    # Copy ROI image directly from camera buffer
    array = ueye.get_data(MemPtr, roi_w, roi_h, 24, pitch=roi_w*3, copy=True)
    frame = np.reshape(array, (roi_h, roi_w, 3))

    # Save & show ROI
    out.write(frame)
    cv2.imshow("Hardware ROI Stream", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# --- Cleanup ---
out.release()
cv2.destroyAllWindows()
ueye.is_StopLiveVideo(hCam, ueye.IS_FORCE_VIDEO_STOP)
ueye.is_ExitCamera(hCam)
