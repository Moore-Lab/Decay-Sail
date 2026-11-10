"""Replay check of tracker centre candidates on the S1 video (2026-11-10).

    python3 centre_replay.py FRAMES.u8 [STRIDE]

FRAMES.u8 = raw Mono8 frames of output_basler_gps1478380390.avi (ffmpeg -f rawvideo -pix_fmt gray).
For each candidate centre, runs blob_core.Tracker with the pinned template
template_gps1477428272.npz (the angle zero used live, as live_blob_track.py does) on every
STRIDE-th frame and prints median / p10 / min ncc, r, and angle range. Then a grid scan
(1 px) around the candidates. Uses the unmodified camera_utils/tracking/blob_core.py.
"""
import sys, os, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
TRK = os.path.join(HERE, '../../../camera_utils/tracking'); sys.path.insert(0, TRK)
import blob_core
W, H = 256, 292
a = np.memmap(sys.argv[1], np.uint8, 'r').reshape(-1, H, W)
stride = int(sys.argv[2]) if len(sys.argv) > 2 else 10
T, ref_ang, _, ref_med = blob_core.load_template(os.path.join(TRK, 'template_gps1477428272.npz'))
fr = np.arange(0, len(a), stride)

def run(cx, cy, frames=fr):
    t = blob_core.Tracker(cx, cy, W, H, T, ref_ang)
    return np.array([t.process(a[i])[:4] for i in frames])

def summ(name, cx, cy):
    o = run(cx, cy)
    n = o[:, 2]
    print('%-22s (%6.1f,%6.1f) ncc med %.3f p10 %.3f min %.3f | r med %.2f std %.2f | ang p1..p99 %.1f..%.1f' % (
        name, cx, cy, np.median(n), np.percentile(n, 10), n.min(), np.median(o[:, 1]), o[:, 1].std(),
        np.percentile(o[:, 0], 1), np.percentile(o[:, 0], 99)))
    return o

cands = [('clicked 11-06', 117.5, 165.1), ('automatic 11-06', 119.1, 167.7), ('F3 stale', 122.8, 179.6)]
# board registration against the template video's median frame (what live_blob_track does without --centre)
med = np.median(a[::50], 0).astype(np.uint8)
cxr, cyr, sh, resp = blob_core.register_centre(med, ref_med, (132.3, 180.6))
print('registration vs template video: centre (%.1f, %.1f), shift %s, response %.3f' % (cxr, cyr, np.round(sh, 1), resp))
cands.append(('registered', cxr, cyr))
for extra in sys.argv[3:]:
    x, y = map(float, extra.split(',')); cands.append(('extra', x, y))
for c in cands: summ(*c)
# grid scan, coarse subsample
fr2 = fr[::5]
print('grid scan (every %d-th frame): median ncc' % (stride * 5))
best = []
for cy in np.arange(160, 175.1, 1.0):
    row = []
    for cx in np.arange(112, 126.1, 1.0):
        m = np.median(run(cx, cy, fr2)[:, 2]); row.append(m); best.append((m, cx, cy))
    print('%5.0f ' % cy + ' '.join('%.2f' % v for v in row))
best.sort(reverse=True); print('best grid points:', [(round(m, 3), cx, cy) for m, cx, cy in best[:6]])
