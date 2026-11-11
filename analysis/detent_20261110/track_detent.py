"""Track the rotor angle through the detent video (2026-11-10, run 1 3200 and run 2 6400 counts).

    python3 track_detent.py FRAMES.u8 FRAME_CSV [OUT.csv]

FRAMES.u8 = raw Mono8 frames of output_basler_gps1478391767.avi, made with
    ffmpeg -nostdin -v error -i output_basler_gps1478391767.avi -f rawvideo -pix_fmt gray FRAMES.u8
(OpenCV on the Mac cannot read FFV1). FRAME_CSV = the camera's per-frame CSV (frame_index, block_id,
cam_timestamp_ns, host_time). Same method as the S1 tracking (rotor_angle_s1.csv): unmodified
camera_utils/tracking/blob_core.Tracker, centre (117.5, 165.1) (confirmed by Molly), pinned template
template_gps1477428272.npz (angle zero of 11-06; full 360 deg search). Every frame.
host_time = the camera CSV's host stamp (rows joined by frame order, as S1). host_time_cam = camera
clock mapped to host by the median offset (smoother; jitter of host_time removed). Also prints the
board registration against the template video as a centre check.
"""
import sys, os, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
TRK = os.path.join(HERE, '../../camera_utils/tracking'); sys.path.insert(0, TRK)
import blob_core
W, H = 256, 292
CX, CY = 117.5, 165.1
a = np.memmap(sys.argv[1], np.uint8, 'r').reshape(-1, H, W)
fc = pd.read_csv(sys.argv[2])
out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, 'rotor_angle_detent.csv')
assert len(fc) == len(a), (len(fc), len(a))
T, ref_ang, _, ref_med = blob_core.load_template(os.path.join(TRK, 'template_gps1477428272.npz'))
med = np.median(a[::50], 0).astype(np.uint8)
cxr, cyr, sh, resp = blob_core.register_centre(med, ref_med, (132.3, 180.6))
print('registration vs template video: centre (%.1f, %.1f), shift %s, response %.3f (using %.1f, %.1f)' % (cxr, cyr, np.round(sh, 1), resp, CX, CY))
t = blob_core.Tracker(CX, CY, W, H, T, ref_ang)
rows = [t.process(a[i]) for i in range(len(a))]
d = pd.DataFrame(rows, columns=['angle_deg', 'r_px', 'ncc', 'ncc_elsewhere', 'source'])
cam = fc.cam_timestamp_ns.values * 1e-9
off = np.median(fc.host_time.values - cam)
d.insert(0, 'host_time_cam', cam + off); d.insert(0, 'host_time', fc.host_time.values); d.insert(0, 'frame', np.arange(len(a)))
d.to_csv(out, index=False, float_format='%.6f')
dt = fc.host_time.values - (cam + off)
print('host - cam-mapped: std %.1f ms, p1..p99 %.1f..%.1f ms' % (dt.std() * 1e3, *np.percentile(dt, [1, 99]) * 1e3))
print('ncc median %.3f p1 %.3f min %.3f; frames ncc<0.9: %d; source blanked: %d' % (
    d.ncc.median(), d.ncc.quantile(0.01), d.ncc.min(), (d.ncc < 0.9).sum(), (d.source == 'blanked').sum()))
