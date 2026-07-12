#!/usr/bin/env python3
"""Real-time damping-rate monitor: τ vs laser power.

Fetches LES data from NDS2, auto-detects libration vs rotation, fits
exponential decay, and accumulates τ vs laser-power scatter in real time.

Libration mode  (dominant freq < MODE_THRESH):
    bandpass 0.03-0.8 Hz → Hilbert envelope → fit A·exp(-t/τ)

Rotation mode   (dominant freq ≥ MODE_THRESH):
    bandpass 0.1-6 Hz → Hilbert inst. freq → fit f·exp(-t/τ)

Panels:
    Top    — filtered LES signal + Hilbert envelope
    Middle — envelope/freq on log scale + fit  (shows current τ)
    Bottom — τ vs laser counts scatter (accumulated this session)

Usage:
    python3 damping_monitor_gui.py
    python3 damping_monitor_gui.py --ch YAW --window 45 --update 120
    python3 damping_monitor_gui.py --mode libration --window 60
"""

import argparse
import csv
import os
import time
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.gridspec import GridSpec
import nds2
from scipy.signal import butter, sosfiltfilt, hilbert, decimate
from scipy.optimize import curve_fit
from scipy.ndimage import uniform_filter1d
from epics import caget
from datetime import datetime, timezone

# ── CLI ───────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--ch',     default='PIT', choices=['PIT', 'YAW'])
parser.add_argument('--window', type=int, default=45,
                    help='Rolling data window in minutes (default 45)')
parser.add_argument('--update', type=int, default=120,
                    help='GUI update interval in seconds (default 120)')
parser.add_argument('--mode',   default='auto',
                    choices=['auto', 'libration', 'rotation'],
                    help='Force analysis mode (default: auto-detect)')
parser.add_argument('--log',    default='',
                    help='CSV log path (auto-named if omitted)')
args = parser.parse_args()

CHANNEL      = f'Y1:RDS-LES_{args.ch}_IN1_DQ'
WINDOW_MIN   = args.window
UPDATE_SEC   = args.update
LASER_PV     = 'Y1:RDS-OUTS_LASER_OFFSET'
NDS2_HOST    = 'cymac1'
NDS2_PORT    = 8088
CYMAC_OFFSET = 3072
GPS_UNIX_OFF = 315964782

FS_IN        = 1024.0
FS_RING      = 64.0        # after 2× decimate-by-4

F_LIB_LO    = 0.03         # libration bandpass (Hz)
F_LIB_HI    = 0.80
F_ROT_LO    = 0.10         # rotation bandpass (Hz)
F_ROT_HI    = 6.00
SMOOTH_SEC   = 15.0        # instantaneous-freq smoothing (rotation mode)
MODE_THRESH  = 0.5         # Hz: dominant FFT peak below → libration mode
ENV_SMOOTH_S = 5.0         # envelope smoothing for libration mode

LOG_FILE = args.log or f'damping_monitor_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.csv'

# ── Helpers ───────────────────────────────────────────────────────────────────
def cymac_gps_now():
    return int(time.time()) - GPS_UNIX_OFF + CYMAC_OFFSET

def dominant_freq(y, fs):
    """FFT peak in Hz (ignores DC)."""
    fft  = np.abs(np.fft.rfft(y - y.mean()))
    freq = np.fft.rfftfreq(len(y), 1.0 / fs)
    mask = freq > 0.01
    return float(freq[mask][np.argmax(fft[mask])])

# ── Data fetch ────────────────────────────────────────────────────────────────
def fetch_les(conn, gps_end, window_sec):
    gps_start = gps_end - window_sec
    y_list, t_list = [], []
    t = gps_start
    while t < gps_end:
        stop = min(gps_end, t + 600)
        try:
            bufs = conn.fetch(t, stop, [CHANNEL])
        except Exception as e:
            print(f'  [warn] fetch t={t}: {e}')
            t = stop
            continue
        for b in bufs:
            x = np.array(b.data, dtype=np.float64)
            if len(x) < 32:
                continue
            t0    = b.gps_seconds + b.gps_nanoseconds * 1e-9
            y_dec = decimate(decimate(x, 4, zero_phase=True), 4, zero_phase=True)
            t_dec = t0 + np.arange(len(y_dec)) / FS_RING
            y_list.append(y_dec)
            t_list.append(t_dec)
        t = stop
    if not y_list:
        return None, None
    return np.concatenate(t_list), np.concatenate(y_list)

# ── Analysis: libration ───────────────────────────────────────────────────────
def analyze_libration(t_gps, y):
    sos  = butter(4, [F_LIB_LO, F_LIB_HI], btype='bandpass', fs=FS_RING, output='sos')
    y_f  = sosfiltfilt(sos, y)
    env  = np.abs(hilbert(y_f))
    env_sm = uniform_filter1d(env, size=max(1, int(ENV_SMOOTH_S * FS_RING)))

    f_lib = dominant_freq(y_f, FS_RING)

    # Require signal above noise floor
    noise  = np.percentile(env_sm, 10)
    signal = np.percentile(env_sm, 90)
    if signal < 2.0 * max(noise, 1e-12):
        return None

    # Skip first 2 s to avoid filter transient
    trim  = max(1, int(2.0 * FS_RING))
    t_s   = t_gps[trim:] - t_gps[trim]   # seconds from window start
    e     = env_sm[trim:]
    win_s = float(t_s[-1])

    try:
        popt, pcov = curve_fit(
            lambda t, A, tau: A * np.exp(-t / tau),
            t_s, e,
            p0=[e[0], win_s],
            bounds=([0, 30.0], [np.inf, win_s * 200]),
            maxfev=8000)
        A0, tau_s = popt
        tau_err   = float(np.sqrt(np.diag(pcov))[1])
        # Sub-sample for plotting
        idx = np.linspace(0, len(t_s) - 1, min(600, len(t_s)), dtype=int)
        return dict(
            mode='libration',
            tau_s=tau_s, tau_err=tau_err,
            A0=A0, f_lib=f_lib,
            t_min=(t_gps - t_gps[0]) / 60.0,
            y_f=y_f, env=env_sm,
            t_fit_min=t_s[idx] / 60.0,
            env_fit=A0 * np.exp(-t_s[idx] / tau_s),
        )
    except Exception:
        return None

# ── Analysis: rotation ────────────────────────────────────────────────────────
def analyze_rotation(t_gps, y):
    sos     = butter(4, [F_ROT_LO, F_ROT_HI], btype='bandpass', fs=FS_RING, output='sos')
    y_f     = sosfiltfilt(sos, y)
    analytic = hilbert(y_f)
    env      = np.abs(analytic)
    phase    = np.unwrap(np.angle(analytic))
    inst_f   = np.diff(phase) / (2 * np.pi / FS_RING)
    win      = max(1, int(SMOOTH_SEC * FS_RING))
    inst_f_s = uniform_filter1d(inst_f, size=win)
    env_s    = uniform_filter1d(env[:-1], size=win)

    t_min = (t_gps[:-1] - t_gps[0]) / 60.0
    mask  = (env_s > np.percentile(env_s, 20)) & np.isfinite(inst_f_s) & (inst_f_s > 0)
    if mask.sum() < 100:
        return None

    valid  = np.where(mask)[0]
    peak_i = valid[np.argmax(inst_f_s[valid])]
    post   = mask.copy()
    post[:peak_i] = False
    if post.sum() < 50:
        return None

    t_fit = t_min[post]
    f_fit = inst_f_s[post]
    t0    = t_fit[0]
    t_s   = (t_fit - t0) * 60.0

    try:
        popt, pcov = curve_fit(
            lambda t, A, g: A * np.exp(-g * t),
            t_s, f_fit,
            p0=[f_fit[0], 1.0 / 3600.0],
            bounds=([0, 1e-7], [np.inf, 1.0]),
            maxfev=10000)
        A_fit, gamma = popt
        tau_s   = 1.0 / gamma
        tau_err = float(np.sqrt(np.diag(pcov))[1]) / gamma**2
        t_curve = np.linspace(t_fit[0], t_fit[-1], 400)
        return dict(
            mode='rotation',
            tau_s=tau_s, tau_err=tau_err,
            A0=A_fit, f0=float(f_fit[0]),
            t_min=t_min, inst_f=inst_f_s, env=env_s, mask=mask,
            t_fit=t_fit, f_fit=f_fit,
            t_curve=t_curve,
            f_curve=A_fit * np.exp(-gamma * (t_curve - t0) * 60.0),
        )
    except Exception:
        return None

# ── GUI ───────────────────────────────────────────────────────────────────────
class DampingMonitor:
    BG    = '#1a1a2e'
    PANEL = '#16213e'
    C_SIG = '#4cc9f0'    # raw signal / inst. freq
    C_ENV = '#f4a261'    # envelope
    C_FIT = '#f72585'    # fit curve
    C_TAU = '#06d6a0'    # τ scatter
    CTXT  = '#a8dadc'

    def __init__(self, conn):
        self.conn     = conn
        self.tau_log  = []   # list of (counts, tau_s, tau_err, mode)

        # Open log file
        self._csv = open(LOG_FILE, 'w', newline='')
        self._writer = csv.writer(self._csv)
        self._writer.writerow(['utc', 'cymac_gps', 'laser_counts',
                               'mode', 'tau_s', 'tau_err_s', 'f_signal_hz'])
        self._csv.flush()

        self.fig = plt.figure(figsize=(13, 10))
        self.fig.patch.set_facecolor(self.BG)
        gs = GridSpec(3, 1, figure=self.fig, hspace=0.45,
                      top=0.93, bottom=0.07, left=0.09, right=0.97)

        self.ax1 = self.fig.add_subplot(gs[0])   # signal + envelope
        self.ax2 = self.fig.add_subplot(gs[1])   # log-scale + fit
        self.ax3 = self.fig.add_subplot(gs[2])   # τ vs laser power

        self._style_axes()

        # Panel 1
        self.l_sig, = self.ax1.plot([], [], color=self.C_SIG,  lw=0.6, alpha=0.7)
        self.l_env, = self.ax1.plot([], [], color=self.C_ENV,  lw=1.5)
        self.ax1.set_xlabel('Time in window (min)', color='white')
        self.ax1.set_ylabel('LES (arb)',            color='white')
        self.ax1.set_title('Filtered signal + envelope', color='white')

        # Panel 2 (log scale)
        self.l_env2, = self.ax2.semilogy([], [], '.', color=self.C_ENV, ms=1.5, alpha=0.4)
        self.l_fit2, = self.ax2.semilogy([], [], '-', color=self.C_FIT, lw=2.0)
        self.ax2.set_xlabel('Time in window (min)', color='white')
        self.ax2.set_ylabel('Envelope / Freq (log)', color='white')
        self.ax2.set_title('Exponential fit',        color='white')
        self.tau_box = self.ax2.text(
            0.97, 0.95, '', transform=self.ax2.transAxes,
            ha='right', va='top', color='white', fontsize=11,
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#0f3460', alpha=0.85))

        # Panel 3
        self.sc_tau = self.ax3.errorbar(
            [], [], yerr=[], fmt='o', color=self.C_TAU,
            ms=6, lw=1.2, capsize=4)
        self.ax3.set_xlabel('Laser (counts)',  color='white')
        self.ax3.set_ylabel('τ (hours)',       color='white')
        self.ax3.set_title('Damping time vs laser power', color='white')
        self.ax3.invert_xaxis()   # high power on left → stepping down to the right

        self.status = self.fig.text(
            0.5, 0.967, 'Fetching first data...', ha='center',
            color=self.CTXT, fontsize=9)

        self.ani = animation.FuncAnimation(
            self.fig, self.update,
            interval=UPDATE_SEC * 1000,
            cache_frame_data=False)

        self.update(0)

    def _style_axes(self):
        for ax in [self.ax1, self.ax2, self.ax3]:
            ax.set_facecolor(self.PANEL)
            ax.tick_params(colors='white', labelsize=9)
            for spine in ax.spines.values():
                spine.set_color('#334466')
            ax.grid(True, color='#334466', lw=0.4, alpha=0.6)

    def _read_laser(self):
        try:
            v = caget(LASER_PV)
            return int(round(v)) if v is not None else None
        except Exception:
            return None

    def _redraw_scatter(self):
        if not self.tau_log:
            return
        counts = np.array([r[0] for r in self.tau_log], dtype=float)
        taus   = np.array([r[1] for r in self.tau_log]) / 3600.0   # → hours
        errs   = np.array([r[2] for r in self.tau_log]) / 3600.0
        # Rebuild — errorbar doesn't support set_data cleanly
        self.ax3.cla()
        self._style_axes()
        self.ax3.set_facecolor(self.PANEL)
        self.ax3.errorbar(counts, taus, yerr=errs, fmt='o',
                          color=self.C_TAU, ms=6, lw=1.2, capsize=4)
        self.ax3.set_xlabel('Laser (counts)', color='white')
        self.ax3.set_ylabel('τ (hours)',      color='white')
        self.ax3.set_title('Damping time vs laser power', color='white')
        if len(counts) > 1:
            self.ax3.invert_xaxis()

    def update(self, _frame):
        t0_wall = time.time()
        gps_end    = cymac_gps_now()
        window_sec = WINDOW_MIN * 60
        laser_cts  = self._read_laser()
        laser_str  = f'{laser_cts} cts' if laser_cts is not None else '?'

        t_gps, y = fetch_les(self.conn, gps_end, window_sec)
        elapsed   = time.time() - t0_wall

        if t_gps is None or len(y) < int(3 * FS_RING):
            self.status.set_text(
                f'{CHANNEL}  |  Laser: {laser_str}  |  No data  |  '
                f'{time.strftime("%H:%M:%S")}')
            self.fig.canvas.draw_idle()
            return

        # ── Auto-detect or force mode ─────────────────────────────────────────
        if args.mode == 'auto':
            sos_test = butter(4, [0.01, 10.0], btype='bandpass', fs=FS_RING, output='sos')
            y_test   = sosfiltfilt(sos_test, y)
            f_dom    = dominant_freq(y_test, FS_RING)
            mode     = 'libration' if f_dom < MODE_THRESH else 'rotation'
        else:
            mode = args.mode

        # ── Run analysis ──────────────────────────────────────────────────────
        result = analyze_libration(t_gps, y) if mode == 'libration' \
            else analyze_rotation(t_gps, y)

        t_min_full = (t_gps - t_gps[0]) / 60.0

        # ── Panel 1: signal + envelope ────────────────────────────────────────
        if result is not None:
            y_plot  = result.get('y_f', y)
            env_plot = result.get('env',  np.abs(hilbert(y_plot)))
            t_plot   = result.get('t_min', t_min_full)
            # Sub-sample for plotting speed
            step = max(1, len(t_plot) // 2000)
            self.l_sig.set_data(t_plot[::step], y_plot[::step])
            self.l_env.set_data(t_plot[::step], env_plot[::step])
            self.ax1.set_xlim(0, WINDOW_MIN)
            peak = np.percentile(np.abs(y_plot), 99)
            self.ax1.set_ylim(-peak * 1.3, peak * 1.3)
        else:
            step = max(1, len(t_min_full) // 2000)
            self.l_sig.set_data(t_min_full[::step], y[::step])
            self.l_env.set_data([], [])
            self.ax1.set_xlim(0, WINDOW_MIN)

        # ── Panel 2: log envelope + fit ───────────────────────────────────────
        if result is not None and mode == 'libration':
            t_fit_min = result['t_fit_min']
            env_fit   = result['env_fit']
            self.l_env2.set_data(t_min_full[::step], result['env'][::step])
            self.l_fit2.set_data(t_fit_min, env_fit)
            tau_s = result['tau_s']
            tau_err = result['tau_err']
            self.tau_box.set_text(
                f'τ = {tau_s/3600:.2f} h  ({tau_s/60:.0f} min)\n'
                f'  ± {tau_err/60:.0f} min\n'
                f'f_lib = {result["f_lib"]:.3f} Hz  ({1/result["f_lib"]:.1f} s)\n'
                f'Laser: {laser_str}')
            pos_vals = result['env'][result['env'] > 0]
            if len(pos_vals):
                self.ax2.set_ylim(pos_vals.min() * 0.5, pos_vals.max() * 2)

        elif result is not None and mode == 'rotation':
            self.l_env2.set_data(result['t_min'][::step], result['inst_f'][::step])
            self.l_fit2.set_data(result['t_curve'], result['f_curve'])
            tau_s   = result['tau_s']
            tau_err = result['tau_err']
            self.tau_box.set_text(
                f'τ = {tau_s/3600:.2f} h  ({tau_s/60:.0f} min)\n'
                f'  ± {tau_err/60:.0f} min\n'
                f'f_rot = {result["f0"]:.3f} Hz\n'
                f'Laser: {laser_str}')
            pos_vals = result['inst_f'][result['inst_f'] > 0]
            if len(pos_vals):
                self.ax2.set_ylim(pos_vals.min() * 0.5, pos_vals.max() * 2)
        else:
            self.l_env2.set_data([], [])
            self.l_fit2.set_data([], [])
            self.tau_box.set_text(f'Mode: {mode}\nFit failed\nLaser: {laser_str}')

        self.ax2.set_xlim(0, WINDOW_MIN)

        # ── Log + accumulate τ vs power ───────────────────────────────────────
        if result is not None and laser_cts is not None:
            tau_s   = result['tau_s']
            tau_err = result['tau_err']
            f_sig   = result.get('f_lib', result.get('f0', float('nan')))

            self.tau_log.append((laser_cts, tau_s, tau_err, mode))
            self._redraw_scatter()

            utc_str = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            self._writer.writerow([utc_str, gps_end, laser_cts, mode,
                                   f'{tau_s:.1f}', f'{tau_err:.1f}', f'{f_sig:.4f}'])
            self._csv.flush()

        # ── Status bar ────────────────────────────────────────────────────────
        mode_tag = f'[{mode}]'
        self.status.set_text(
            f'{CHANNEL}  |  {WINDOW_MIN} min window  |  {mode_tag}  |  '
            f'Laser: {laser_str}  |  Fetch: {elapsed:.1f}s  |  '
            f'{time.strftime("%H:%M:%S")}')

        self.fig.canvas.draw_idle()


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print(f'Connecting to NDS2 {NDS2_HOST}:{NDS2_PORT} ...')
    conn = nds2.connection(NDS2_HOST, NDS2_PORT)
    conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')
    conn.set_parameter('GAP_HANDLER', 'STATIC_HANDLER_NAN')
    print(f'Connected.')
    print(f'Channel : {CHANNEL}')
    print(f'Window  : {WINDOW_MIN} min  |  Update: {UPDATE_SEC} s')
    print(f'Mode    : {args.mode}')
    print(f'Log     : {LOG_FILE}\n')

    monitor = DampingMonitor(conn)
    plt.show()
    monitor._csv.close()
