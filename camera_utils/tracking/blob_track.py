"""Track the white blob's angle about a fixed rotation centre (gate 2).

    python blob_track.py VIDEO.avi WIDTH HEIGHT CENTRE.json REF_FRAME REF_ANGLE_DEG OUT.csv
                         [--save-template T.npz] [--template T.npz]

--save-template stores the template cut here (plus this video's median frame, for
registering later recordings); --template uses a stored one instead of cutting a new one
(REF_FRAME/REF_ANGLE are then ignored), so the angle zero stays the same across videos.
The per-frame maths is in blob_core.py, shared with live_blob_track.py.

Each frame is high-passed and unwrapped to polar (r, theta) about the centre, so a
rotation is a shift in theta. A blob template (r 12-35 px, +-28 deg) cut from REF_FRAME
at REF_ANGLE_DEG is matched to every frame by normalised cross-correlation, which does
not care how bright the blob is (side lighting makes it bright at the bottom of its orbit
and grey at the top). The search is over all 360 deg and +-8 px in r.

Two unwraps are matched and the higher NCC kept per frame:
  raw      works when the blob is bright;
  blanked  the sail (a bright line through the centre) zeroed first, so the template
           cannot lock onto it when the blob is dim. The sail finder is pulled onto the
           blob when the blob is bright, which is why the raw unwrap is kept too.
The angle is an absolute angle per frame (no tracking from frame to frame).

Columns: frame, angle_deg (image coords, x right, y down), r_px (template centre's
distance from the centre), ncc, ncc_elsewhere (best match >20 deg away), source.
First used 2026-10-30 on output_basler_gps1477419607.avi with REF 1100 at 82 deg.
"""
import json, subprocess, sys
import numpy as np
import blob_core

video, W, H, centre_file, REF, REF_ANG, out = sys.argv[1:8]
W, H, REF, REF_ANG = int(W), int(H), int(REF), float(REF_ANG)
opt = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
cx, cy = json.load(open(centre_file))['centre_xy_px']


def frames(video, W, H):
    """Stream gray frames from ffmpeg one at a time (a 30 min recording is ~6.6 GB)."""
    pr = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', video, '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                          stdout=subprocess.PIPE)
    while True:
        b = pr.stdout.read(W * H)
        if len(b) < W * H:
            break
        yield np.frombuffer(b, np.uint8).reshape(H, W)
    pr.stdout.close()
    if pr.wait():
        sys.exit('ffmpeg failed on %s' % video)


trk = blob_core.Tracker(cx, cy, W, H)
if opt('--template'):
    T, ref_ang, _, _ = blob_core.load_template(opt('--template'))
    trk.T, trk.ref_angle = T, ref_ang; tag = 'template=%s' % opt('--template').split('/')[-1]
else:
    tag = 'ref=%d@%.0fdeg' % (REF, REF_ANG)
    for i, f in enumerate(frames(video, W, H)):
        if i == REF:
            trk.cut_template(f, REF_ANG); break
if opt('--save-template'):
    sub = np.array([f for i, f in enumerate(frames(video, W, H)) if i % 5 == 0])
    blob_core.save_template(opt('--save-template'), trk, np.median(sub, 0).astype(np.uint8),
                            video.split('/')[-1], REF)
    del sub

rows = [(i, *trk.process(f)) for i, f in enumerate(frames(video, W, H))]
n = len(rows)
with open(out, 'w') as fh:
    fh.write('# blob_track.py %s centre=(%.1f,%.1f) %s\n' % (video.split('/')[-1], cx, cy, tag))
    fh.write('frame,angle_deg,r_px,ncc,ncc_elsewhere,source\n')
    for row in rows: fh.write('%d,%.2f,%.2f,%.3f,%.3f,%s\n' % row)

ang = np.array([x[1] for x in rows]); rad = np.array([x[2] for x in rows])
step = np.abs((np.diff(ang) + 180) % 360 - 180)
xb, yb = cx + rad * np.cos(np.deg2rad(ang)), cy + rad * np.sin(np.deg2rad(ang))
M = np.c_[2 * xb, 2 * yb, np.ones(n)]; (fx, fy, fc), *_ = np.linalg.lstsq(M, xb**2 + yb**2, rcond=None)
print('%d frames; largest frame-to-frame step %.1f deg; r median %.2f px, std %.2f' % (n, step.max(), np.median(rad), rad.std()))
print('orbit circle fit (%.2f, %.2f) R=%.2f, %.2f px from the centre; radial scatter %.2f px' % (
    fx, fy, np.sqrt(fc + fx**2 + fy**2), np.hypot(fx - cx, fy - cy), np.hypot(xb - fx, yb - fy).std()))
