#!/usr/bin/env python3
"""
Real-time spindown GUI.
Fetches LES PIT or YAW from NDS2, computes instantaneous frequency via Hilbert
transform, fits an exponential decay, and displays live tau estimate.

Usage:
    python3 spindown_gui.py              # defaults: PIT, 60 min window
    python3 spindown_gui.py --ch YAW --window 30
"""

import argparse
import time
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.gridspec import GridSpec
import nds2
from scipy.signal import decimate, butter, sosfiltfilt, hilbert
from scipy.optimize import curve_fit
from scipy.ndimage import uniform_filter1d
from epics import caget

# ── CLI args ─────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument('--ch',     default='PIT', choices=['PIT', 'YAW'],
                    help='LES channel to use (default: PIT)')
parser.add_argument('--window', type=int, default=60,
                    help='Rolling window in minutes (default: 60)')
parser.add_argument('--env-min', type=float, default=None,
                    help='envelope gate lower bound (default: 5%% of the '
                         'observed maximum). Drops the noise floor.')
parser.add_argument('--env-max', type=float, default=None,
                    help='envelope gate upper bound (default: 1.5x the '
                         'observed maximum). Drops saturation.')
parser.add_argument('--update', type=int, default=60,
                    help='Update interval in seconds (default: 60)')
args = parser.parse_args()

CHANNEL      = f'Y1:RDS-LES_{args.ch}_IN1_DQ'
WINDOW_MIN   = args.window
UPDATE_SEC   = args.update

# ── Constants ─────────────────────────────────────────────────────────────────
FS_IN        = 1024.0
FS_RING      = 64.0
F_LOW        = 0.005
F_HIGH       = 6.0
SMOOTH_SEC   = 30.0
ENV_MIN      = args.env_min      # None = scale from the data
ENV_MAX      = args.env_max
CYMAC_OFFSET = 3072        # cymac1 GPS clock ahead of true GPS (measured 2026-07-09)
GPS_UNIX_OFF = 315964782   # GPS epoch offset including 18 leap seconds
LASER_PV     = 'Y1:RDS-OUTS_LASER_OFFSET'
NDS2_HOST    = 'cymac1'
NDS2_PORT    = 8088

# ── DSP (from spindown_20260702.ipynb) ────────────────────────────────────────
def hilbert_freq(y_filt, fs, smooth_sec=SMOOTH_SEC):
    analytic  = hilbert(y_filt)
    envelope  = np.abs(analytic)
    phase     = np.unwrap(np.angle(analytic))
    dt        = 1.0 / fs
    inst_freq = np.diff(phase) / (2 * np.pi * dt)
    win       = max(1, int(smooth_sec * fs))
    return (uniform_filter1d(inst_freq,     size=win),
            uniform_filter1d(envelope[:-1], size=win),
            dt / 2)

def exp_decay(t, A, gamma):
    return A * np.exp(-gamma * t)

def cymac_gps_now():
    """Front-end GPS, read LIVE from the DAQ rather than computed.

    This used to be `time.time() - GPS_UNIX_OFF + CYMAC_OFFSET`, with
    CYMAC_OFFSET a constant measured on 2026-07-09. THAT OFFSET DRIFTS, badly:
    3072 s when it was measured, 5836 s on 06-03, 7630 s on 08-21, 8376 s on
    08-28, and 9536 s on 09-08. By 2026-09-08 the hardcoded value was wrong by
    6464 s -- nearly two hours -- so every fetch landed in the wrong window and
    the display showed stale data or nothing.

    Y1:DAQ-DC0_GPS is the front end's own clock. Reading it costs one caget and
    can never go stale. Falls back to the old arithmetic only if EPICS is
    unreachable, and says so.
    """
    try:
        from epics import caget
        v = caget('Y1:DAQ-DC0_GPS', timeout=2.0)
        if v:
            return int(v)
    except Exception:
        pass
    print('  [warn] could not read Y1:DAQ-DC0_GPS; falling back to the stale '
          'CYMAC_OFFSET constant -- times will likely be wrong')
    return int(time.time()) - GPS_UNIX_OFF + CYMAC_OFFSET

# ── Data fetch & process ──────────────────────────────────────────────────────
def fetch_and_process(conn, channel, gps_end, window_sec):
    gps_start = gps_end - window_sec
    y_list, t_list = [], []
    t = gps_start

    while t < gps_end:
        stop = min(gps_end, t + 600)
        try:
            bufs = conn.fetch(t, stop, [channel])
        except Exception as e:
            print(f"  [warn] fetch t={t}: {e}")
            t = stop
            continue
        for b in bufs:
            x = np.array(b.data, dtype=np.float64)
            if len(x) < 32:
                t = stop
                continue
            t0 = b.gps_seconds + b.gps_nanoseconds * 1e-9
            y_dec = decimate(decimate(x, 4, zero_phase=True), 4, zero_phase=True)
            t_dec = t0 + np.arange(len(y_dec)) / FS_RING
            y_list.append(y_dec)
            t_list.append(t_dec)
        t = stop

    if not y_list:
        return None

    t_gps = np.concatenate(t_list)
    y     = np.concatenate(y_list)

    if len(y) < int(3 * SMOOTH_SEC * FS_RING):
        return None

    sos  = butter(4, [F_LOW, F_HIGH], btype='bandpass', fs=FS_RING, output='sos')
    y_f  = sosfiltfilt(sos, y)

    freq, env, dt_half = hilbert_freq(y_f, FS_RING)
    t_freq = t_gps[:-1] + dt_half

    # minutes from window start
    t_min  = (t_freq - gps_start) / 60.0

    # Envelope gate, ADAPTIVE. ENV_MIN/ENV_MAX used to be hardcoded at 10 and
    # 300, which silently rejected everything once the signal grew: LES_YAW runs
    # rms ~1400 (envelope ~2000), so every sample failed env <= 300, the
    # frequency panel plotted nothing and the fit printed "Fitting..." forever.
    # Those constants suited PIT, which is thousands of times smaller.
    #
    # The gate's real jobs are to drop the noise floor at the bottom and any
    # saturation at the top, both of which are relative to the signal actually
    # present. So scale them off the data unless overridden on the command line.
    lo = ENV_MIN if ENV_MIN is not None else max(1e-9, 0.05 * np.nanmax(env))
    hi = ENV_MAX if ENV_MAX is not None else 1.5 * np.nanmax(env)
    mask = (env >= lo) & (env <= hi) & np.isfinite(freq)
    if mask.sum() < 100:
        print(f'  [warn] envelope gate kept only {mask.sum()} samples '
              f'(env range {np.nanmin(env):.1f}-{np.nanmax(env):.1f}, '
              f'gate {lo:.1f}-{hi:.1f}) -- widen with --env-min/--env-max')

    return t_min, freq, env, mask

def fit_spindown(t_min, freq, mask):
    if mask.sum() < 100:
        return None

    # peak in valid region
    valid_idx = np.where(mask)[0]
    peak_i    = valid_idx[np.argmax(freq[valid_idx])]

    post = mask.copy()
    post[:peak_i] = False

    t_fit = t_min[post]
    f_fit = freq[post]
    if len(t_fit) < 50:
        return None

    t0   = t_fit[0]
    t_s  = (t_fit - t0) * 60.0  # seconds from peak

    try:
        popt, pcov = curve_fit(exp_decay, t_s, f_fit,
                               p0=[f_fit[0], 1.0 / 3600.0],
                               bounds=([0, 1e-7], [np.inf, 1.0]),
                               maxfev=10000)
        A_fit, gamma = popt
        A_err, g_err = np.sqrt(np.diag(pcov))
        tau_s   = 1.0 / gamma
        tau_err = g_err / gamma**2
        return tau_s, tau_err, A_fit, t0, t_fit, f_fit
    except Exception:
        return None

# ── GUI ───────────────────────────────────────────────────────────────────────
class SpindownGUI:
    BG    = '#1a1a2e'
    PANEL = '#16213e'
    C1    = '#4cc9f0'   # frequency scatter
    C2    = '#4361ee'   # fit region scatter
    CFIT  = '#f72585'   # fit curve
    CTXT  = '#a8dadc'

    def __init__(self, conn):
        self.conn = conn

        self.fig = plt.figure(figsize=(13, 8))
        self.fig.patch.set_facecolor(self.BG)
        gs = GridSpec(2, 1, figure=self.fig, hspace=0.4,
                      top=0.91, bottom=0.08, left=0.08, right=0.97)

        self.ax1 = self.fig.add_subplot(gs[0])
        self.ax2 = self.fig.add_subplot(gs[1])
        self._style_axes()

        # Top: full rolling frequency
        self.l_freq,    = self.ax1.plot([], [], color=self.C1, lw=0.8, alpha=0.85)
        self.ax1.set_xlim(0, WINDOW_MIN)
        self.ax1.set_ylim(0, 10)
        self.ax1.set_xlabel('Time in window (min)', color='white')
        self.ax1.set_ylabel('Frequency (Hz)',        color='white')
        self.ax1.set_title('Instantaneous rotation frequency', color='white')

        # Bottom: scatter + fit
        self.l_all,  = self.ax2.plot([], [], '.', color=self.C1,  ms=1.5, alpha=0.25)
        self.l_fit_s,= self.ax2.plot([], [], '.', color=self.C2,  ms=2.5, alpha=0.7)
        self.l_fit,  = self.ax2.plot([], [], '-', color=self.CFIT, lw=2.0)
        self.ax2.set_xlim(0, WINDOW_MIN)
        self.ax2.set_ylim(0, 10)
        self.ax2.set_xlabel('Time in window (min)', color='white')
        self.ax2.set_ylabel('Frequency (Hz)',        color='white')
        self.ax2.set_title('Exponential fit',        color='white')

        self.tau_box = self.ax2.text(
            0.97, 0.95, '', transform=self.ax2.transAxes,
            ha='right', va='top', color='white', fontsize=11,
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#0f3460', alpha=0.85))

        self.status = self.fig.text(
            0.5, 0.965, 'Fetching first data...', ha='center',
            color=self.CTXT, fontsize=9)

        self.ani = animation.FuncAnimation(
            self.fig, self.update,
            interval=UPDATE_SEC * 1000,
            cache_frame_data=False)

        self.update(0)   # immediate first draw

    def _style_axes(self):
        for ax in [self.ax1, self.ax2]:
            ax.set_facecolor(self.PANEL)
            ax.tick_params(colors='white', labelsize=9)
            for spine in ax.spines.values():
                spine.set_color('#334466')
            ax.grid(True, color='#334466', lw=0.4, alpha=0.6)

    def update(self, _frame):
        t0 = time.time()
        gps_end    = cymac_gps_now()
        window_sec = WINDOW_MIN * 60

        try:
            laser = caget(LASER_PV)
            laser_str = f'{laser:.0f} cts' if laser is not None else '?'
        except Exception:
            laser_str = '?'

        result = fetch_and_process(self.conn, CHANNEL, gps_end, window_sec)
        elapsed = time.time() - t0

        if result is None:
            self.status.set_text(
                f'{CHANNEL}  |  {WINDOW_MIN} min window  |  '
                f'Laser: {laser_str}  |  No data  |  {time.strftime("%H:%M:%S")}')
            self.fig.canvas.draw_idle()
            return

        t_min, freq, env, mask = result

        # ── top panel ──
        self.l_freq.set_data(t_min[mask], freq[mask])
        f_max = freq[mask].max() * 1.2 if mask.any() else 10.0
        self.ax1.set_ylim(0, max(f_max, 0.5))

        # ── bottom panel ──
        self.l_all.set_data(t_min[mask], freq[mask])
        self.ax2.set_ylim(0, max(f_max, 0.5))

        fit = fit_spindown(t_min, freq, mask)
        if fit is not None:
            tau_s, tau_err, A_fit, t_peak, t_fit, f_fit = fit
            self.l_fit_s.set_data(t_fit, f_fit)

            t_curve = np.linspace(t_fit[0], t_fit[-1], 500)
            t_s_c   = (t_curve - t_peak) * 60.0
            self.l_fit.set_data(t_curve, exp_decay(t_s_c, A_fit, 1.0 / tau_s))

            self.tau_box.set_text(
                f'τ = {tau_s:.0f} s  ({tau_s/60:.1f} min)\n'
                f'  ± {tau_err:.0f} s\n'
                f'A₀ = {A_fit:.3f} Hz')
        else:
            self.l_fit_s.set_data([], [])
            self.l_fit.set_data([], [])
            self.tau_box.set_text('Fitting...')

        self.status.set_text(
            f'{CHANNEL}  |  {WINDOW_MIN} min window  |  '
            f'Laser: {laser_str}  |  '
            f'Fetch: {elapsed:.1f}s  |  {time.strftime("%H:%M:%S")}')

        self.fig.canvas.draw_idle()


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print(f"Connecting to NDS2 {NDS2_HOST}:{NDS2_PORT} ...")
    conn = nds2.connection(NDS2_HOST, NDS2_PORT)
    conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')
    conn.set_parameter('GAP_HANDLER', 'STATIC_HANDLER_NAN')
    print(f"Connected. Channel: {CHANNEL}, window: {WINDOW_MIN} min, "
          f"update: {UPDATE_SEC}s\n")

    gui = SpindownGUI(conn)
    plt.show()
