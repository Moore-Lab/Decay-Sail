#!/usr/bin/env python3
"""Build a frequency-vs-time timeline from all LES PIT HDF5 files.

For each 600-second segment: decimate 1024→64 Hz, bandpass 0.1-6 Hz,
Hilbert → instantaneous frequency → median per segment.

Outputs:
    freq_timeline.npz   — compressed array (gps, freq_hz, amplitude)
    freq_timeline.png   — annotated multi-day plot

Known laser events (cymac GPS, laser counts) are overlaid as vertical markers.
"""

import numpy as np
import h5py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.signal import butter, sosfiltfilt, hilbert, decimate
from scipy.ndimage import uniform_filter1d
from datetime import datetime, timezone
import os, glob, time

DATA_DIR  = '/home/controls/rds-code/Decay-Sail/lab_utils/data'
OUT_NPZ   = '/home/controls/rds-code/Decay-Sail/lab_utils/freq_timeline.npz'
OUT_PNG   = '/home/controls/rds-code/Decay-Sail/lab_utils/freq_timeline.png'

FS_IN     = 1024.0
FS_RING   = 64.0        # after 2× decimate-by-4
F_LO      = 0.1
F_HI      = 6.0
SMOOTH_S  = 30.0

GPS_UNIX  = 315964782   # true GPS → Unix (GPS_epoch + 18 leapsec)
CYMAC_OFF = 3072        # cymac GPS is this many seconds AHEAD of true GPS

def cymac_to_utc(gps_cymac):
    """Convert cymac GPS timestamp to UTC datetime."""
    unix = (gps_cymac - CYMAC_OFF) + GPS_UNIX
    return datetime.fromtimestamp(unix, tz=timezone.utc)

def process_segment(raw, fs_in=FS_IN):
    """Return (median_freq_hz, rms_amplitude) for one raw segment."""
    if len(raw) < 256:
        return np.nan, np.nan
    try:
        y = decimate(decimate(raw.astype(np.float64), 4, zero_phase=True),
                     4, zero_phase=True)
        sos  = butter(4, [F_LO, F_HI], btype='bandpass', fs=FS_RING, output='sos')
        y_f  = sosfiltfilt(sos, y)
        analytic = hilbert(y_f)
        env      = np.abs(analytic)
        phase    = np.unwrap(np.angle(analytic))
        inst_f   = np.diff(phase) / (2 * np.pi / FS_RING)
        win      = max(1, int(SMOOTH_S * FS_RING))
        inst_f_s = uniform_filter1d(inst_f, size=win)
        env_s    = uniform_filter1d(env[:-1], size=win)
        # Only use samples where envelope is above 25th percentile
        thresh = np.percentile(env_s, 25)
        mask   = (env_s > thresh) & (inst_f_s > 0.05) & (inst_f_s < 10.0)
        if mask.sum() < 10:
            return np.nan, np.nan
        return float(np.median(inst_f_s[mask])), float(np.median(env_s[mask]))
    except Exception:
        return np.nan, np.nan

# ── Load and process all LES PIT files ───────────────────────────────────────
files = sorted(glob.glob(os.path.join(DATA_DIR, 'Y1_RDS-LES_PIT_IN1_DQ_146*.h5')))
print(f'Found {len(files)} LES PIT files:')
for f in files:
    print(f'  {os.path.basename(f)}')

all_gps  = []
all_freq = []
all_amp  = []

for filepath in files:
    t0 = time.time()
    fname = os.path.basename(filepath)
    with h5py.File(filepath, 'r') as f:
        data      = f['data']
        seg_t0    = f['segments/gps_start'][:]
        seg_idx   = f['segments/index_start'][:]
        seg_len   = f['segments/length'][:]
        n_segs    = len(seg_t0)

    print(f'\n{fname}  ({n_segs} segments)')
    gps_arr  = np.zeros(n_segs)
    freq_arr = np.zeros(n_segs)
    amp_arr  = np.zeros(n_segs)

    with h5py.File(filepath, 'r') as f:
        data = f['data']
        for i in range(n_segs):
            i0 = int(seg_idx[i])
            ln = int(seg_len[i])
            raw = data[i0:i0 + ln]
            gps_arr[i]  = seg_t0[i]
            freq_arr[i], amp_arr[i] = process_segment(np.array(raw))
            if (i + 1) % 50 == 0:
                pct = (i + 1) / n_segs * 100
                print(f'  {pct:.0f}%  seg {i+1}/{n_segs}', end='\r', flush=True)

    print(f'\n  Done in {time.time()-t0:.1f}s')
    all_gps.append(gps_arr)
    all_freq.append(freq_arr)
    all_amp.append(amp_arr)

gps  = np.concatenate(all_gps)
freq = np.concatenate(all_freq)
amp  = np.concatenate(all_amp)

# Sort by time
order = np.argsort(gps)
gps   = gps[order]
freq  = freq[order]
amp   = amp[order]

np.savez_compressed(OUT_NPZ, gps=gps, freq=freq, amp=amp)
print(f'\nSaved timeline: {OUT_NPZ}')
print(f'  GPS range : {gps[0]:.0f} → {gps[-1]:.0f}')
print(f'  N points  : {len(gps)}')
print(f'  Freq range: {np.nanmin(freq):.3f} – {np.nanmax(freq):.3f} Hz')

# ── Known laser events (cymac GPS, laser counts) ──────────────────────────────
# July 9 spindown script timeline (started 17:14 EDT = 21:14 UTC July 9)
# EDT = UTC-4, cymac GPS at 2026-07-09 21:14 UTC:
#   Unix ≈ 1783383240  → cymac GPS = unix - GPS_UNIX + CYMAC_OFF
#        = 1783383240 - 315964782 + 3072 = 1467421530 ... let me compute properly
# From context: script started at 17:14 EDT July 9 = 21:14 UTC July 9
# Approx Unix: datetime(2026,7,9,21,14, tzinfo=utc).timestamp()
# = need to compute...
# Using GPS values from batch_fetch_spindown.py: GPS_START=1467665587
# Script started around 17:14 EDT = cymac GPS ~ 1467665587 - 2000 ≈ 1467663587?
# Actually let me just use the known step times from the tmux output we saw:
# [fine 2/850] 848 counts | 23:44:44 (wall clock)
# Wall clock 23:44 UTC+? -- in EDT (UTC-4): 23:44 local on July 9 = 03:44 UTC July 10
# Cymac GPS for 03:44 UTC July 10 = (unix) - GPS_UNIX + CYMAC_OFF
# This is approximate; I'll derive from the step structure

# Spindown start: 950 counts at cymac GPS ~1467665587 (approx start of spindown file)
# Actually from context: script started tmux creation 17:14:40 EDT July 9
# 17:14:40 EDT = 21:14:40 UTC, July 9, 2026
# Unix ≈ datetime(2026,7,9,21,14,40,tzinfo=timezone.utc).timestamp()
# = hard to compute without running datetime; let's use GPS
# From batch_fetch_spindown GPS_START=1467665587 which is cymac GPS for spindown start
# The script started ~12 min into the 950-count level (from context: "already ~12 min in")
# So script actually started at cymac GPS ≈ 1467665587 - 720 ≈ 1467664867
# But the fixed level (950 counts, 60 min) started at ~1467664867

# Approximate laser step schedule (cymac GPS):
# From spindown_gui context and laser_spindown_fine.py parameters
LASER_STEPS = [
    # (cymac_gps_approx, counts, label)
    # Coarse steps (60 min each), starting ~17:14 EDT July 9
    # Using GPS_START=1467665587 as reference for spindown window
    # Step start times estimated from 60-min intervals
    (1467664800, 950,  '950 cts'),
    (1467668400, 925,  '925 cts'),
    (1467672000, 900,  '900 cts'),
    (1467675600, 875,  '875 cts'),
    (1467679200, 850,  '850 cts'),
    # Fine steps (90 min each) from 849 downward
    (1467682800, 849,  '849 cts'),
    (1467688200, 848,  '848 cts'),
    (1467693600, 847,  '847 cts'),
    (1467699000, 846,  '846 cts'),
    (1467704400, 845,  '845 cts'),
    (1467709800, 844,  '844 cts'),
    (1467715200, 843,  '843 cts'),
    (1467720600, 842,  '842 cts'),
    (1467726000, 841,  '841 cts'),
    (1467731400, 840,  '840 cts'),
    (1467736800, 839,  '839 cts'),
]

# ── Plot ──────────────────────────────────────────────────────────────────────
utc_times = [cymac_to_utc(g) for g in gps]
step_utc  = [cymac_to_utc(g) for g, c, l in LASER_STEPS]

fig, axes = plt.subplots(3, 1, figsize=(16, 12),
                          gridspec_kw={'height_ratios': [3, 1.5, 1.5]},
                          sharex=True)
fig.patch.set_facecolor('#1a1a2e')
for ax in axes:
    ax.set_facecolor('#16213e')
    ax.tick_params(colors='white', labelsize=8)
    for spine in ax.spines.values():
        spine.set_color('#334466')
    ax.grid(True, color='#334466', lw=0.4, alpha=0.6)

# ── Panel 1: frequency timeline ───────────────────────────────────────────────
ax = axes[0]
valid = np.isfinite(freq) & (freq > 0.05)
ax.plot([utc_times[i] for i in range(len(utc_times)) if valid[i]],
        freq[valid], '.', color='#4cc9f0', ms=2, alpha=0.7)

# Overlay known laser steps
for g, c, lbl in LASER_STEPS:
    dt = cymac_to_utc(g)
    ax.axvline(dt, color='#f72585', lw=0.8, alpha=0.5)
    ax.text(dt, ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 5,
            f'{c}', color='#f72585', fontsize=6, ha='left', va='top', rotation=90)

ax.set_ylabel('Rotation frequency (Hz)', color='white')
ax.set_title('LES PIT instantaneous frequency — multi-day timeline', color='white')
ax.set_ylim(bottom=0)

# ── Panel 2: df/dt — rate of frequency change (settling indicator) ────────────
ax = axes[1]
# Compute df/dt using gps midpoints
gps_valid = gps[valid]
freq_valid = freq[valid]
dt_arr2   = np.diff(gps_valid)
df_arr2   = np.diff(freq_valid)
dfdt2     = df_arr2 / dt_arr2
t_mid2    = [cymac_to_utc(float(gps_valid[i] + gps_valid[i+1]) / 2)
             for i in range(len(gps_valid)-1)]
# Only plot where time gaps are < 700s (consecutive segments)
consec    = dt_arr2 < 700
ax.plot([t_mid2[i] for i in range(len(t_mid2)) if consec[i]],
        [dfdt2[i] for i in range(len(dfdt2)) if consec[i]],
        '.', color='#f4a261', ms=2, alpha=0.6)
ax.axhline(0, color='white', lw=0.5, alpha=0.5)
ax.set_ylabel('df/dt  (Hz/s)', color='white')
ax.set_title('Frequency drift rate  (≈0 = at steady state)', color='white')

# Mark laser steps
for g, c, lbl in LASER_STEPS:
    axes[1].axvline(cymac_to_utc(g), color='#f72585', lw=0.8, alpha=0.5)

# ── Panel 3: signal amplitude (envelope) ─────────────────────────────────────
ax = axes[2]
ax.plot([utc_times[i] for i in range(len(utc_times)) if valid[i]],
        amp[valid], '.', color='#06d6a0', ms=2, alpha=0.7)
ax.set_ylabel('LES amplitude (arb)', color='white')
ax.set_title('Signal envelope (drop = libration or loss of rotation)', color='white')

for g, c, lbl in LASER_STEPS:
    axes[2].axvline(cymac_to_utc(g), color='#f72585', lw=0.8, alpha=0.5)

# ── x-axis formatting ─────────────────────────────────────────────────────────
axes[2].xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
axes[2].xaxis.set_major_locator(mdates.HourLocator(interval=6))
plt.setp(axes[2].xaxis.get_majorticklabels(), rotation=30, ha='right', color='white')
axes[2].set_xlabel('UTC time', color='white')

plt.suptitle('Rotor frequency timeline — July 7-10, 2026\n'
             'Pink lines = known laser step events',
             color='white', fontsize=11)
plt.savefig(OUT_PNG, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
print(f'Saved plot: {OUT_PNG}')
