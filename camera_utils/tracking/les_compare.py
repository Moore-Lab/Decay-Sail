"""Gate 6: align a tracked video with LES and compare frequencies.

    python les_compare.py BLOB.csv FRAMES.csv PIT.h5 YAW.h5 OUT_PREFIX

BLOB.csv    blob_track.py output (absolute angle per frame)
FRAMES.csv  the recorder's per-frame timestamps (output_basler_gps<GPS>.csv): host_time is
            Unix on worker2 (true GPS after -315964800+18); cam_timestamp_ns sets the spacing
PIT/YAW.h5  fetch_les_for_video.py output (front-end GPS, 1024 Hz)

1. Alignment. LES is low-passed to the 50 Hz frame grid. For every shift tau (front-end GPS
   minus true GPS) the LES is regressed on cos/sin(k*theta), k = 1..4, of the unwrapped video
   angle; tau is where R^2 peaks. Nothing assumes the divisor.
2. Rotation. In 2-s windows where |rate| > 0.2 rev/s and steady within 15%, the LES spectral
   peak divided by the video rate.
3. Swinging. Long-window spectra of the video angle, LES, and the 1x+2x model of LES built
   from the video angle, in given segments.
4. Direction. Sign of the band-passed LES (PIT, YAW) circulation vs the sign of the video rate.
Writes OUT_PREFIX_align.png, OUT_PREFIX_swing.png and prints the numbers.
First used 2026-10-30 on gps1477428272.
"""
import csv, sys
import numpy as np, h5py
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from scipy.signal import decimate, fftconvolve, spectrogram, welch
from scipy.ndimage import gaussian_filter1d

blob, frames, pit, yaw, out = sys.argv[1:6]
SWING = [(210, 261), (0, 55)]                    # segments of plain swinging, video s

rows = list(csv.DictReader(l for l in open(blob) if not l.startswith('#')))
th = np.deg2rad(np.unwrap([float(r['angle_deg']) for r in rows], period=360)); n = len(th)
ts = np.genfromtxt(frames, delimiter=',', names=True)
cam = (ts['cam_timestamp_ns'] - ts['cam_timestamp_ns'][0]) * 1e-9
host = ts['host_time'] - ts['host_time'][0]
c, *_ = np.linalg.lstsq(np.c_[np.ones(n), cam], host, rcond=None)
t_true0 = ts['host_time'][0] - 315964800 + 18 + c[0] + (host - c[0] - c[1] * cam).min()   # least-latency anchor
assert np.allclose(np.diff(cam), 0.02, atol=1e-5), 'frames not uniformly 50 fps'
print('frames %d, no drops, first frame true GPS %.3f' % (n, t_true0))

def load(f):
    with h5py.File(f) as h:
        x = h['data'][:].astype(float); t0 = h['segments/gps_start'][0]; fs = h.attrs['sample_rate']
        assert len(x) == round((h.attrs['gps_end'] - h.attrs['gps_start']) * fs), 'gaps in LES'
    return x, t0, fs
les = {}
for nm, f in [('PIT', pit), ('YAW', yaw)]:
    x, t0, fs = load(f); y = decimate(decimate(x, 4, ftype='fir'), 5, ftype='fir')     # 1024 -> 51.2 Hz
    tt = t0 + np.arange(len(y)) * 20 / fs; g = np.arange(t0, tt[-1], 0.02)
    les[nm] = (x, t0, fs, g, np.interp(g, tt, y))

X = np.column_stack([f(k * th) for k in (1, 2, 3, 4) for f in (np.cos, np.sin)]); X -= X.mean(0)
Q, _ = np.linalg.qr(X)
fig, ax = plt.subplots(2, 1, figsize=(12, 7))
taus = {}
for nm, (x, t0, fs, g, y) in les.items():
    cs = np.cumsum(np.r_[0, y]); cs2 = np.cumsum(np.r_[0, y * y])
    var = (cs2[n:] - cs2[:-n]) - (cs[n:] - cs[:-n])**2 / n
    per = [fftconvolve(y, Q[::-1, i], mode='valid')**2 for i in range(8)]
    r2 = sum(per) / var; j = int(np.argmax(r2)); tau = g[j] - t_true0; taus[nm] = (tau, j)
    away = np.abs(np.arange(len(r2)) - j) > 100
    print('%s: tau %.2f s, R2 %.3f (next-best >2 s away %.3f, median %.3f); R2 by harmonic 1..4: %s' % (
        nm, tau, r2[j], r2[away].max(), np.median(r2), ' '.join('%.3f' % ((per[2*k][j] + per[2*k+1][j]) / var[j]) for k in range(4))))
    ax[0].plot(g[:len(r2)] - t_true0, r2, lw=.6, label=nm)
ax[0].set_xlabel('front-end GPS - true GPS (s)'); ax[0].set_ylabel('R^2, LES on cos/sin(k theta), k=1..4')
ax[0].legend(); ax[0].set_title('alignment')

tau, j = taus['PIT']; p = les['PIT'][4][j:j + n]; t = np.arange(n) * 0.02
M = np.column_stack([np.ones(n)] + [f(k * th) for k in (1, 2) for f in (np.cos, np.sin)])
cP, *_ = np.linalg.lstsq(M, p, rcond=None); model = M @ cP
c1, *_ = np.linalg.lstsq(M[:, :3], p, rcond=None)
print('PIT = %.0f + %.0f counts x (1x term) + %.0f counts x (2x term); R2 1x only %.3f, 1x+2x %.3f' % (
    cP[0], np.hypot(*cP[1:3]), np.hypot(*cP[3:5]), 1 - np.var(p - M[:, :3] @ c1) / np.var(p), 1 - np.var(p - model) / np.var(p)))
s = (t >= 150) & (t < 175)
ax[1].plot(t[s], p[s], lw=.9, label='LES PIT'); ax[1].plot(t[s], model[s], lw=.9, label='1x+2x of video angle')
ax[1].plot(t[s], (M[:, :3] @ c1)[s], lw=.9, alpha=.7, label='1x only'); ax[1].legend(fontsize=8); ax[1].set_xlabel('video time (s)')
fig.tight_layout(); fig.savefig(out + '_align.png', dpi=80)

w = gaussian_filter1d(np.gradient(th, 0.02), 10) / (2 * np.pi)
for nm, (x, t0, fs, g, y) in les.items():
    i0 = int(round((t_true0 + taus[nm][0] - t0) * fs)); xs = x[i0:i0 + int(n * 0.02 * fs)]
    f, tc, S = spectrogram(xs - xs.mean(), fs=fs, nperseg=2048, noverlap=1792)
    rat = []
    for k, tm in enumerate(tc):
        m = (t > tm - 1) & (t < tm + 1); wv = np.abs(w[m]).mean()
        if wv > 0.2 and np.abs(w[m]).std() < 0.15 * wv:
            b = (f > 0.05) & (f < 6); rat.append(f[b][np.argmax(S[b, k])] / wv)
    print('%s rotation: %d windows, LES peak / video rate median %.2f (p25 %.2f, p75 %.2f)' % (
        nm, len(rat), np.median(rat), *np.percentile(rat, [25, 75])))

fig, axs = plt.subplots(1, len(SWING), figsize=(13, 4))
for ax_, (t1, t2) in zip(axs, SWING):
    m = (t >= t1) & (t < t2); R2 = 1 - np.var(p[m] - model[m]) / np.var(p[m])
    peaks = []
    for sig, nm in [(np.degrees(th[m]), 'video angle'), (p[m], 'LES PIT'), (model[m], 'model of LES from video angle')]:
        f, S = welch(sig - sig.mean(), fs=50, nperseg=m.sum(), window='hann', nfft=8 * m.sum())
        b = (f > 0.05) & (f < 5); fp = f[b][np.argmax(S[b])]; peaks.append(fp)
        ax_.semilogy(f, S / S[b].max(), lw=.9, ls='--' if 'model' in nm else '-', label='%s (peak %.3f Hz)' % (nm, fp))
    print('swing %d-%d s: half-range %.0f deg, rms x sqrt2 %.0f deg; peaks video %.3f, LES %.3f (%.2fx), model %.3f Hz; model R2 %.2f' % (
        t1, t2, np.ptp(np.degrees(th[m])) / 2, np.degrees(th[m]).std() * np.sqrt(2), peaks[0], peaks[1], peaks[1] / peaks[0], peaks[2], R2))
    ax_.set_xlim(0, 3); ax_.set_ylim(1e-4, 2); ax_.set_xlabel('Hz'); ax_.legend(fontsize=8)
    ax_.set_title('swinging %d-%d s, model R^2 %.2f' % (t1, t2, R2), fontsize=10)
fig.tight_layout(); fig.savefig(out + '_swing.png', dpi=80)

# direction: sense of the LES (PIT, YAW) circulation vs the sign of the video rate
from scipy.signal import butter, sosfiltfilt
yv = les['YAW'][4][taus['YAW'][1]:taus['YAW'][1] + n]
for nm, sig in [('PIT', p), ('YAW', yv)]:
    cc, *_ = np.linalg.lstsq(M, sig, rcond=None); print('%s 2x amplitude %.0f counts, phase %.1f deg' % (
        nm, np.hypot(*cc[3:5]), np.degrees(np.arctan2(-cc[4], cc[3]))))
sos = butter(2, [0.1, 4], btype='band', fs=50, output='sos'); bp, by_ = sosfiltfilt(sos, p), sosfiltfilt(sos, yv)
circ = gaussian_filter1d(bp * np.gradient(by_) - by_ * np.gradient(bp), 25)
w1 = gaussian_filter1d(np.gradient(th, 0.02), 25) / (2 * np.pi)
for thr in (0.1, 0.2, 0.3):
    m = np.abs(w1) > thr; agree = np.mean(np.sign(circ[m]) == np.sign(w1[m]))
    print('direction, |rate| > %.1f rev/s (%.0f s): LES circulation sign = video sign in %.1f%%, opposite in %.1f%%' % (
        thr, m.sum() * 0.02, 100 * agree, 100 * (1 - agree)))
