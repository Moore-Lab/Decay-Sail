"""Per-frame blob angle, shared by blob_track.py (offline) and live_blob_track.py (camera).

One frame in, one absolute angle out; no state carried between frames. See blob_track.py
for the method. A Tracker is built from a centre and a template; a template file (.npz)
holds the polar template, the angle it was cut at, the centre it was cut about, and the
median frame of that video (for finding the centre of a later recording by registration).
"""
import numpy as np, cv2

R0, R1, HW, DR = 12, 36, 28, 8          # template rows r = R0..R1-1, half-width deg, radial search
PAD = HW + 1
K7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))


class Tracker:
    def __init__(self, cx, cy, W, H, template=None, ref_angle=None):
        self.cx, self.cy = cx, cy
        Y, X = np.mgrid[:H, :W]; self.dx, self.dy = X - cx, Y - cy
        self.ann = (np.hypot(self.dx, self.dy) > 8) & (np.hypot(self.dx, self.dy) < 40)
        # sail finder: line through the centre, bright on both halves (median, so the blob can't carry it)
        self.sth = np.deg2rad(np.arange(0, 180, 0.5)); srr = np.r_[np.arange(-38, -9), np.arange(10, 39)]
        self.SX = (cx + np.outer(np.cos(self.sth), srr)).astype(np.float32)
        self.SY = (cy + np.outer(np.sin(self.sth), srr)).astype(np.float32)
        TH = np.deg2rad(np.arange(360.)); RR = np.arange(42.)   # polar grid, 1 deg x 1 px
        self.MX = (cx + np.outer(RR, np.cos(TH))).astype(np.float32)
        self.MY = (cy + np.outer(RR, np.sin(TH))).astype(np.float32)
        self.T, self.ref_angle = template, ref_angle

    def unwrap(self, f):
        """Raw and sail-blanked polar images of one Mono8 frame."""
        g = f.astype(np.float32)
        s = (cv2.morphologyEx(f, cv2.MORPH_OPEN, K7) - cv2.GaussianBlur(g, (0, 0), 12)) * self.ann
        prof = cv2.remap(s.astype(np.float32), self.SX, self.SY, cv2.INTER_LINEAR)
        t = self.sth[np.argmax(np.minimum(np.median(prof[:, :29], 1), np.median(prof[:, 29:], 1)))]
        h = g - cv2.GaussianBlur(g, (0, 0), 8)
        raw = cv2.remap(h, self.MX, self.MY, cv2.INTER_LINEAR)
        h[np.abs(-np.sin(t) * self.dx + np.cos(t) * self.dy) < 5] = 0
        return raw, cv2.remap(h, self.MX, self.MY, cv2.INTER_LINEAR)

    def cut_template(self, f, ref_angle):
        k0 = int(round(ref_angle))
        self.T = self.unwrap(f)[0][R0:R1, np.arange(k0 - HW, k0 + HW + 1) % 360]
        self.ref_angle = ref_angle
        return self.T

    def _match(self, p):
        img = np.concatenate([p[:, -PAD:], p, p[:, :PAD]], 1)[R0 - DR:R1 + DR]
        c = cv2.matchTemplate(img, self.T, cv2.TM_CCOEFF_NORMED); j = np.unravel_index(np.argmax(c), c.shape)
        col = c.max(0); d = np.abs(((np.arange(len(col)) - j[1]) + 180) % 360 - 180)
        da = _sub(c[j[0], j[1] - 1], c[j], c[j[0], (j[1] + 1) % c.shape[1]])
        dr = _sub(c[j[0] - 1, j[1]], c[j], c[j[0] + 1, j[1]]) if 0 < j[0] < c.shape[0] - 1 else 0.
        return (j[1] + da - PAD + HW) % 360, (R0 + R1 - 1) / 2 + j[0] - DR + dr, c[j], col[d > 20].max()

    def process(self, f):
        """(angle_deg, r_px, ncc, ncc_elsewhere, source) for one frame."""
        raw, blk = self.unwrap(f)
        A, B = self._match(raw), self._match(blk)
        return (*A, 'raw') if A[2] >= B[2] else (*B, 'blanked')


def _sub(y0, y1, y2):
    q = y0 - 2 * y1 + y2
    return 0.5 * (y0 - y2) / q if q < 0 else 0.


def save_template(path, tracker, median_frame, source_video, ref_frame):
    np.savez_compressed(path, template=tracker.T, ref_angle=tracker.ref_angle,
                        centre=np.array([tracker.cx, tracker.cy]), median_frame=median_frame,
                        source_video=source_video, ref_frame=ref_frame)


def load_template(path):
    d = np.load(path)
    return d['template'], float(d['ref_angle']), tuple(d['centre']), d['median_frame']


def register_centre(median_frame, ref_median, ref_centre, mask_r=60):
    """Centre for a new recording: shift of the static board between the two median frames.

    The rotor region (within mask_r of the reference centre) is blanked in both, so the
    rotor's own angle cannot pull the shift. Returns (cx, cy, (dx, dy), response)."""
    H, W = ref_median.shape; Y, X = np.mgrid[:H, :W]
    keep = np.hypot(X - ref_centre[0], Y - ref_centre[1]) > mask_r
    a = np.where(keep, ref_median, ref_median[keep].mean()).astype(np.float32)
    b = np.where(keep, median_frame, median_frame[keep].mean()).astype(np.float32)
    win = cv2.createHanningWindow((W, H), cv2.CV_32F)
    (dx, dy), resp = cv2.phaseCorrelate(a, b, win)
    return ref_centre[0] + dx, ref_centre[1] + dy, (dx, dy), resp
