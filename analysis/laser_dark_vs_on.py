#!/usr/bin/env python3
"""Laser power noise: DARK (laser-off) vs ON, floor-corrected, plus a PD-vs-power-meter
cross-check.

Based on analysis/laser_rin.ipynb (same load_h5 / to_uW / thermal-requirement / Welch
methods), but instead of "before vs after the laser tweak" it compares:

  * ON   record : laser-on 22 h PD record  -> laser power noise + detector floor
  * DARK record : laser-off 22 h PD record -> detector / electronic noise floor alone

Because both are 22 h, the Welch estimate reaches deep into the 0.3-10 mHz requirement
band (the original 900 s record only touched the top of it). The dark record lets us:
  1. quadrature-subtract the detector floor  ->  the *true* laser power noise;
  2. tag which spectral lines are electronic (present with the laser off).

The counts->mW calibration is taken from the Ophir StarLab power-meter log recorded over
the SAME window (PD median counts / meter mean mW), so the analysis is valid at WHATEVER
power the run sat at -- this pair is ~3 mW; point it at a higher-power pair later and it
recalibrates itself.

Memory: these are 81 M-sample records and worker2 has little spare RAM, so the pipeline
loads float32, deglitches in O(N), processes one record at a time, caps the high-f
estimate to HI_HOURS, and block-averages to FS_LO for the low band. Run headless:

    python laser_dark_vs_on.py
"""
import os
import subprocess
import sys

import h5py
import numpy as np
import matplotlib
matplotlib.use('Agg')                       # headless; no display needed
import matplotlib.pyplot as plt
from datetime import datetime, timezone
from scipy.signal import welch, find_peaks, correlate
from scipy.ndimage import median_filter, uniform_filter1d

# --------------------------------------------------------------------------- data sources
DROPBOX_PD    = 'dropbox:Microspheres/TFINER/data/PD'
DROPBOX_POWER = 'dropbox:Microspheres/TFINER/laser_power'
ON_H5    = 'Y1_RDS-PD_IN1_DQ_1469307101_1469386301.h5'    # laser-on, 22 h  (Jul 28-29)
DARK_H5  = 'Y1_RDS-PD_IN1_DQ_1469220701_1469299901.h5'    # laser-off, 22 h (Jul 27-28)
POWER_TXT = '260728_laser_power.txt'                       # Ophir StarLab log, 660 nm
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_pd_cache')
RCLONE = os.path.expanduser('~/.local/bin/rclone')

# --------------------------------------------------------------------------- tunables
HI_HOURS   = 2.0          # hours of full-rate data used for the high-frequency estimate
NPERSEG_HI = 16384        # 16 s segments (high-f)
FS_LO      = 16           # Hz: block-averaged rate for the low-frequency estimate
SEG_LO_S   = 300          # 300 s segments (low-f) -> ~3.3 mHz resolution

# --------------------------------------------------------------------------- constants
# (identical to laser_rin.ipynb; TORQUE_PER_MW is gain-independent so it carries over even
#  though the PD gain here differs.)
GPS_UNIX_OFFSET = 315964800 - 18
def gps_to_dt(g):
    return datetime.fromtimestamp(g + GPS_UNIX_OFFSET, tz=timezone.utc)

KB_J, T_BATH = 1.380649e-23, 300.0
I_KGM2     = 1.88e-11
TAU_FREE_S = 67.65 * 60.0
GAMMA      = 1.0 / TAU_FREE_S
S_N_THERMAL = np.sqrt(4 * KB_J * T_BATH * GAMMA * I_KGM2)      # N m / sqrt(Hz)
KAPPA_PD_OLD   = 7.3499e-16
CTS_PER_MW_OLD = 167.6 / 10.34
TORQUE_PER_MW  = KAPPA_PD_OLD * CTS_PER_MW_OLD                 # N m per mW (gain-independent)
REQ_UW  = S_N_THERMAL / TORQUE_PER_MW * 1e3                    # uW/sqrt(Hz), freq-independent
TARGET_UW = 1.0

E_CHARGE, RESPONSIVITY = 1.602176634e-19, 0.7                  # A/W; adjust to the diode


# --------------------------------------------------------------------------- io helpers
def ensure_local(remote_dir, name):
    """Return a local path to `name`, rclone-pulling it from Dropbox once and caching."""
    os.makedirs(CACHE, exist_ok=True)
    local = os.path.join(CACHE, name)
    if not os.path.exists(local):
        print(f'  fetching {name} from Dropbox ...', flush=True)
        r = subprocess.run([RCLONE, 'copyto', f'{remote_dir}/{name}', local])
        if r.returncode != 0 or not os.path.exists(local):
            sys.exit(f'ERROR: could not fetch {name} from {remote_dir}')
    return local


def load_h5(path):
    """Segment-aware read (from laser_rin.ipynb, float32 for memory). Returns (t, y, fs)."""
    ts, ys = [], []
    with h5py.File(path, 'r') as f:
        fs = float(f.attrs['sample_rate'])
        for g0, ix, n in zip(f['segments/gps_start'][:].astype(np.float64),
                             f['segments/index_start'][:].astype(np.int64),
                             f['segments/length'][:].astype(np.int64)):
            y = f['data'][ix:ix + n].astype(np.float32)
            ts.append(g0 + np.arange(len(y), dtype=np.float64) / fs)
            ys.append(y)
    t = np.concatenate(ts); y = np.concatenate(ys)
    o = np.argsort(t)
    return t[o], y[o], fs


def to_uW(psd_counts, cts_per_mW):
    """PSD in counts^2/Hz -> amplitude spectral density in uW/sqrt(Hz)."""
    return np.sqrt(psd_counts) / cts_per_mW * 1e3


def deglitch(y, fs, nsigma=8.0, pad=16):
    """O(N) glitch repair: box-smoothed baseline (not a 2048-wide median, which is far too
    heavy on an 81 M-sample record), robust sigma from a decimated residual, spikes replaced
    by the baseline. Same intent as laser_rin.ipynb cell 5, made linear-time."""
    base = uniform_filter1d(y, size=int(2 * fs), mode='nearest')
    resid = y - base
    sub = resid[::16]                                   # robust sigma needs only a sample
    sigma = np.median(np.abs(sub - np.median(sub))) * 1.4826
    flag = np.abs(resid) > nsigma * sigma
    n = int(flag.sum())
    if n:
        if pad:
            flag = uniform_filter1d(flag.astype(np.float32), size=2 * pad + 1) > 0
        y = y.copy()
        y[flag] = base[flag]                            # baseline fill (interp-equivalent, light)
    return y, n, float(sigma)


def block_average(y, d):
    """Anti-aliasing decimation by integer factor d via non-overlapping block means."""
    m = (len(y) // d) * d
    return y[:m].reshape(-1, d).mean(axis=1)


def parse_starlab(path):
    """Parse an Ophir StarLab log. Returns (t_elapsed_s, power_mW, header_stats dict)."""
    t, p, stats = [], [], {}
    with open(path, 'r', errors='replace') as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s[0] in ';!':
                for key in ('Average', 'Std.Dev.', 'Min', 'Max', 'Duration'):
                    if s.lstrip(';').startswith(key + ':'):
                        stats[key] = s.split(':', 1)[1].strip()
                continue
            parts = s.split()
            if len(parts) >= 2:
                try:
                    t.append(float(parts[0])); p.append(float(parts[1]) * 1e3)  # W -> mW
                except ValueError:
                    pass
    return np.asarray(t), np.asarray(p), stats


def spectra_for(path, cts_per_mW):
    """Load one record, deglitch, return dict of high-f and low-f PSDs (+ a decimated mW
    series for plotting/meter overlay). Big arrays are freed before returning."""
    t, y, fs = load_h5(path)
    dur = len(y) / fs
    y, n_gl, sigma = deglitch(y, fs)
    level = float(np.median(y[::64]))                   # counts (subsample median)

    # high-f: first HI_HOURS at full rate (plenty of 16 s averages, bounded memory)
    n_hi = int(min(HI_HOURS * 3600, dur) * fs)
    f_hi, P_hi = welch(y[:n_hi].astype(np.float64) - float(np.mean(y[:n_hi])),
                       fs=fs, nperseg=NPERSEG_HI)

    # low-f: block-average the whole record to FS_LO, then 300 s segments
    ylo = block_average(y, int(fs // FS_LO))
    f_lo, P_lo = welch(ylo.astype(np.float64) - float(ylo.mean()),
                       fs=FS_LO, nperseg=int(SEG_LO_S * FS_LO))

    mW_lo = ylo / cts_per_mW if cts_per_mW else ylo     # decimated series in mW
    t_lo = t[0] + np.arange(len(ylo)) / FS_LO
    out = dict(t0=t[0], dur=dur, fs=fs, level=level, n_gl=n_gl, sigma=sigma,
               f_hi=f_hi, P_hi=P_hi, f_lo=f_lo, P_lo=P_lo, t_lo=t_lo, mW_lo=mW_lo)
    del t, y, ylo
    return out


# --------------------------------------------------------------------------- 1. calibrate
print('== fetching / loading data ==')
on_path   = ensure_local(DROPBOX_PD, ON_H5)
dark_path = ensure_local(DROPBOX_PD, DARK_H5)
pow_path  = ensure_local(DROPBOX_POWER, POWER_TXT)

tm_s, pm_mW, pm_stats = parse_starlab(pow_path)
meter_mean_mW = float(np.mean(pm_mW))

# ON record first (needed for the calibration), then DARK on the same grid.
on = spectra_for(on_path, cts_per_mW=None)          # placeholder cal; fix level below
CTS_PER_MW = on['level'] / meter_mean_mW
P_CHAMBER_MW = meter_mean_mW
on['mW_lo'] = on['mW_lo'] / CTS_PER_MW               # apply real calibration
dk = spectra_for(dark_path, cts_per_mW=CTS_PER_MW)

print('\n== calibration (data-driven from the meter) ==')
print(f'ON  : {gps_to_dt(on["t0"]):%Y-%m-%d %H:%M} UTC, {on["dur"]/3600:.1f} h @ {on["fs"]:.0f} Hz')
print(f'DARK: {gps_to_dt(dk["t0"]):%Y-%m-%d %H:%M} UTC, {dk["dur"]/3600:.1f} h @ {dk["fs"]:.0f} Hz')
print(f'METER: {len(pm_mW):,} pts   header stats: {pm_stats}')
print(f'PD ON level         : {on["level"]:.1f} counts (median)')
print(f'meter average power : {meter_mean_mW:.4f} mW  (Ophir PD300, 660 nm)')
print(f'=> counts/mW        : {CTS_PER_MW:.1f}   (this record sits at {P_CHAMBER_MW:.3f} mW)')
print(f'dark level          : {dk["level"]:.2f} counts (electronic offset)')
print(f'glitches repaired   : ON {on["n_gl"]:,}  DARK {dk["n_gl"]:,}')
print(f'thermal REQUIREMENT : {REQ_UW:.3f} uW/sqrt(Hz)  (frequency-independent)')

# --------------------------------------------------------------------------- 2. ASDs
uw_on_hi = to_uW(on['P_hi'], CTS_PER_MW); uw_dk_hi = to_uW(dk['P_hi'], CTS_PER_MW)
uw_on_lo = to_uW(on['P_lo'], CTS_PER_MW); uw_dk_lo = to_uW(dk['P_lo'], CTS_PER_MW)
uw_ex_hi = to_uW(np.clip(on['P_hi'] - dk['P_hi'], 0, None), CTS_PER_MW)
uw_ex_lo = to_uW(np.clip(on['P_lo'] - dk['P_lo'], 0, None), CTS_PER_MW)
f_hi, f_lo = on['f_hi'], on['f_lo']

fig, ax = plt.subplots(figsize=(12, 7))
ax.loglog(f_lo[1:], uw_on_lo[1:], lw=0.9, color='darkorange', label='laser ON (low-f, 300 s)')
ax.loglog(f_hi[1:], uw_on_hi[1:], lw=0.7, color='orange', alpha=0.7, label='laser ON (high-f, 16 s)')
ax.loglog(f_lo[1:], uw_dk_lo[1:], lw=0.9, color='dimgray', label='DARK floor (low-f)')
ax.loglog(f_hi[1:], uw_dk_hi[1:], lw=0.7, color='gray', alpha=0.7, label='DARK floor (high-f)')
ax.loglog(f_lo[1:], uw_ex_lo[1:], lw=1.3, color='navy', label='laser noise, floor-corrected')
ax.axhline(REQ_UW, color='firebrick', ls='--', lw=1.8,
           label=f'thermal requirement {REQ_UW:.2f} $\\mu$W/$\\sqrt{{Hz}}$')
ax.axhline(TARGET_UW, color='seagreen', ls='-.', lw=1.3, label=f'goal {TARGET_UW:.0f} $\\mu$W/$\\sqrt{{Hz}}$')
ax.axvspan(3e-4, 1e-2, color='firebrick', alpha=0.07)
ax.text(4e-4, 4e1, 'requirement band\n0.3-10 mHz', fontsize=9, color='firebrick')
ax.set_xlabel('Fourier frequency (Hz)', fontsize=12)
ax.set_ylabel('power noise ASD ($\\mu$W/$\\sqrt{Hz}$ at chamber)', fontsize=12)
ax.set_title(f'Laser power noise vs dark floor ({P_CHAMBER_MW:.2f} mW at chamber)', fontsize=13)
sec = ax.secondary_yaxis('right', functions=(lambda x: x * 1e-3 / P_CHAMBER_MW,
                                             lambda r: r * P_CHAMBER_MW * 1e3))
sec.set_ylabel('RIN (1/$\\sqrt{Hz}$)', fontsize=10)
ax.legend(fontsize=8, loc='upper right'); ax.grid(True, which='both', alpha=0.3)
plt.tight_layout(); plt.savefig('laser_dark_vs_on_ASD.png', dpi=130); plt.close()
print('\nwrote laser_dark_vs_on_ASD.png')

# --------------------------------------------------------------------------- 3. band table
print('\n== broadband ASD by band (median): ON, DARK floor, floor-corrected laser ==')
print(f"{'band (Hz)':>15} | {'ON':>9} | {'DARK':>9} | {'laser':>9} | {'laser/req':>9} | detector-limited?")
print('-' * 90)
for lo, hi, src in [(0.003, 0.01, 'lo'), (0.01, 0.1, 'lo'), (0.1, 0.5, 'lo'),
                    (0.5, 2, 'hi'), (2, 10, 'hi'), (10, 50, 'hi'),
                    (50, 200, 'hi'), (200, 500, 'hi')]:
    (ff, uon, udk, uex) = ((f_lo, uw_on_lo, uw_dk_lo, uw_ex_lo) if src == 'lo'
                           else (f_hi, uw_on_hi, uw_dk_hi, uw_ex_hi))
    b = (ff > lo) & (ff < hi)
    if not b.any():
        continue
    on_m, dk_m, ex_m = np.median(uon[b]), np.median(udk[b]), np.median(uex[b])
    limited = 'YES (floor dominates)' if dk_m > 0.5 * on_m else 'no'
    print(f'{lo:6.3f}-{hi:6.3f} | {on_m:9.4f} | {dk_m:9.4f} | {ex_m:9.4f} | '
          f'{ex_m/REQ_UW:8.2f}x | {limited}')

# --------------------------------------------------------------------------- 4. lines
print('\n== spectral lines above 0.2 Hz (tagged electronic if also in DARK) ==')
m = f_hi > 0.2
fm, um_on, um_dk = f_hi[m], uw_on_hi[m], uw_dk_hi[m]
base = median_filter(um_on, size=101)
pk, _ = find_peaks(um_on / base, height=8, distance=3)
order = np.argsort(um_on[pk])[::-1]
print(f"{'f (Hz)':>9} | {'ON uW/rtHz':>11} | {'DARK uW/rtHz':>13} | {'x req':>7} | origin")
print('-' * 66)
for i in pk[order][:15]:
    electronic = um_dk[i] > 0.5 * um_on[i]
    print(f'{fm[i]:9.2f} | {um_on[i]:11.3f} | {um_dk[i]:13.3f} | {um_on[i]/REQ_UW:6.1f}x | '
          f'{"electronic (in dark)" if electronic else "optical"}')

# --------------------------------------------------------------------------- 5. PD vs meter
# Both series measure the same laser power. The meter's internal clock is wrong (StarLab
# header reads 2006), so align by cross-correlating the fluctuations on a common grid
# rather than by absolute timestamp.
print('\n== PD vs power-meter cross-check ==')
gp = np.arange(0, min(on['dur'], tm_s[-1] - tm_s[0]))              # 1 Hz grid
pd_1hz = np.interp(gp, on['t_lo'] - on['t_lo'][0], on['mW_lo'])
pm_1hz = np.interp(gp, tm_s - tm_s[0], pm_mW)
a = pd_1hz - pd_1hz.mean(); b = pm_1hz - pm_1hz.mean()
if a.std() > 0 and b.std() > 0:
    xc = correlate(a, b, mode='full')
    lag = int(np.arange(-len(a) + 1, len(a))[np.argmax(xc)])
    s = slice(max(0, lag), None); s2 = slice(max(0, -lag), None)
    nlap = min(len(a[s]), len(b[s2]))
    r = float(np.corrcoef(a[s][:nlap], b[s2][:nlap])[0, 1]) if nlap > 10 else float('nan')
else:
    lag, r = 0, float('nan')
print(f'meter mean {meter_mean_mW:.4f} mW  vs  PD mean {np.mean(on["mW_lo"]):.4f} mW  '
      f'(match built into the calibration)')
print(f'meter std  {np.std(pm_mW)*1e3:.2f} uW (~15 Hz)  vs  PD std {np.std(on["mW_lo"])*1e3:.2f} uW ({FS_LO} Hz)')
print(f'best-fit lag PD-vs-meter: {lag} s   correlation of fluctuations r = {r:.3f}')
print('(low r is expected if the laser was flat -- few common features to lock onto)')

fig, axes = plt.subplots(2, 1, figsize=(12, 8))
axes[0].plot((on['t_lo'] - on['t_lo'][0]) / 3600,
             uniform_filter1d(on['mW_lo'], 5 * FS_LO), lw=0.8, color='darkorange',
             label='PD (DAQ), 5 s avg')
axes[0].plot((tm_s - tm_s[0]) / 3600, pm_mW, lw=0.6, color='navy', alpha=0.7,
             label='Ophir meter')
axes[0].set_xlabel('hours from record start'); axes[0].set_ylabel('power (mW)')
axes[0].set_title('PD vs power meter (time series; independent start clocks)', fontsize=11)
axes[0].legend(fontsize=9); axes[0].grid(True, alpha=0.3)
dev = (on['mW_lo'] - np.mean(on['mW_lo'])) * 1e3
axes[1].hist(dev, bins=200, color='darkorange', density=True)
axes[1].set_xlabel('PD deviation from mean ($\\mu$W)'); axes[1].set_ylabel('density')
axes[1].set_title(f'PD std {dev.std():.1f} $\\mu$W  |  meter std {np.std(pm_mW)*1e3:.1f} $\\mu$W',
                  fontsize=11)
axes[1].grid(True, alpha=0.3)
plt.tight_layout(); plt.savefig('laser_dark_vs_on_meter.png', dpi=130); plt.close()
print('wrote laser_dark_vs_on_meter.png')

# --------------------------------------------------------------------------- 6. shot noise
hf = (f_hi > 100) & (f_hi < 400)
floor_uW = float(np.median(uw_on_hi[hf]))
floor_rin = floor_uW * 1e-3 / P_CHAMBER_MW
shot_rin = np.sqrt(2 * E_CHARGE / (RESPONSIVITY * P_CHAMBER_MW * 1e-3))
print('\n== shot-noise context ==')
print(f'measured floor (100-400 Hz): {floor_uW:.4f} uW/sqrt(Hz) = {floor_rin:.2e} /sqrt(Hz)')
print(f'shot-noise RIN at {P_CHAMBER_MW:.2f} mW: {shot_rin:.2e} /sqrt(Hz) '
      f'-> {shot_rin*P_CHAMBER_MW*1e3:.4f} uW/sqrt(Hz)')
print(f'measured floor is {floor_rin/shot_rin:.0f}x above shot noise '
      '(implementation-limited, not fundamental)')
print('\nDONE.')
