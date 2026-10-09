#!/usr/bin/env python3
"""Live rotor-frequency tracker for the electrode characterisation run.

Prints, once per poll, the commanded electrical frequency, the measured rotor
frequency, and the SLIP RATIO between them -- the number the scan exists to
measure. Appends the same to CSV. Read-only; it touches no setpoint.

Run it in its own terminal alongside stator_osc_drive.py.

USAGE

    # headless, logging to HDF5 (what you want for an unattended overnight scan)
    python3 track_drive.py --h5 scan_fwd.h5

    # live plot as well; needs DISPLAY, so run it from the worker2 desktop session
    python3 track_drive.py --gui --h5 scan_fwd.h5

    # --csv is still there and can be used alongside --h5

The GUI shows three panels: measured rotor frequency against the commanded
f_elec/8 (the gap between them IS the slip); SNR and kurtosis, for whether the
line is still worth believing and whether the rotor is still rotating; and
f_elec vs measured rotor frequency, which is the deliverable of the scan -- it
is expected to be NON-MONOTONIC, since an asynchronous drag drive has a
torque-vs-slip maximum beyond which more f_elec gives less speed.

Acquisition runs in a daemon thread, so an NDS2 fetch never freezes the window,
and the GUI and headless paths call the same poll_once() -- the plot cannot
drift away from the validated CLI. Closing the window stops the run cleanly.

HDF5 rows are appended and FLUSHED one at a time, so a kill, a dropped ssh
session or a dead X server costs at most the poll in flight. Re-running against
an existing file appends to it rather than truncating.

WHY NDS2 AND NOT cdsutils.getdata
    cdsutils.getdata(ch, 120) blocks for the full 120 s because it streams in
    real time, so a 120 s window costs 120 s of wall clock per poll. nds2 reads
    the same samples from the archive and returns at once, at the cost of
    running LAG seconds behind. Measured 2026-10-09: getdata timed out at 120 s,
    nds2 returned immediately.

WHY LES_PIT AND NOT LES_YAW
    The beam was realigned 2026-10-09 and that flipped which axis carries the
    signal. Measured the same day on a coasting rotor, 150 s window:

        PIT  line 397 counts  SNR 511      <- use this
        YAW  line 148 counts  SNR 212

    against the noise budget's reference of 331-539 counts and median SNR 622,
    which was LES_YAW *before* the realignment. Frequency precision goes as
    1/SNR, so YAW now costs a factor of 3. Every other tool in this directory
    still defaults to YAW.

WHY WINDOW IS 120 s AND NOT LONGER
    A coasting rotor chirps, so a long FFT smears the line rather than resolving
    it. At the measured -1.0e-4 Hz/s the coherent limit is
    sqrt(1/|df/dt|) ~ 100 s, and widening 150 s -> 600 s measurably made things
    WORSE: PIT SNR 511 -> 114, amplitude 397 -> 137. Do not raise WINDOW
    expecting finer resolution.

WHY THERE IS NO DIVISOR CONSTANT
    The sail is 2-fold so the 2x line is usually loudest -- but WHICH harmonic
    dominates varies between runs, and taking the loudest line as the
    fundamental is the single error that has cost this experiment three separate
    analyses (apparatus_log.md). So the fundamental comes from the comb: take
    the loudest line, then walk DOWN through f_dom/n and accept the lowest
    candidate that still carries real power of its own.

    Checked by hand against live data 2026-10-09 -- dominant 0.7100 Hz, genuine
    line at 0.3550 Hz (44 counts), nothing at 0.1775 Hz (3 counts), so the
    fundamental is 0.355 Hz and the loudest line was its 2nd harmonic.

    While the drive is on there is a second constraint: the rotor cannot outrun
    the travelling wave, so f_rot <= f_elec / 8. That is checked, not assumed --
    a violation is flagged rather than silently clipped.

KNOWN LIMITATION: RECTIFIED LIBRATION CAN DEFEAT THE COMB WALK
    This tool is for tracking ROTATION during a drive. A librating rotor
    rectifies in LES -- the channel responds to |theta|, so it completes a cycle
    on every one-way swing -- which also produces an even-harmonic comb, and the
    walk usually recovers the mechanical frequency from it correctly. But it can
    fail: on the 2026-09-09 libration record the true mechanical line carried
    only 1.7 counts against 71.5 at 2f, a ratio of 0.024, below
    SUBHARM_MIN_FRAC. On a record like that this tool reports 2x the mechanical
    frequency.

    THE KURTOSIS COLUMN IS THE GUARD. Rotating sits near -1.43, librating near
    +0.92. Anything above 0 is flagged 'cusped -- may be librating' and the
    frequency should not be trusted as a rotation rate. Note the 2026-09-14
    finding that single-window kurtosis does NOT cleanly separate the two across
    a real transition, so treat the flag as a prompt to look, not a verdict.
"""

import argparse
import os
import queue
import sys
import threading
import time
from datetime import datetime, timezone

import numpy as np
import nds2
import h5py
from scipy.signal import decimate
from scipy.stats import kurtosis as kurt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settled_check import peak_in_band       # validated estimator -- do not reimplement

from epics import caget

CHANNEL_DEFAULT = 'Y1:RDS-LES_PIT_IN1_DQ'
NDS_HOST, NDS_PORT = 'cymac1', 8088
GPS_PV = 'Y1:DAQ-DC0_GPS'
FREQ_PV = 'Y1:RDS-OUTS_DRV_FREQ'
SIN_PV, COS_PV = 'Y1:RDS-OUTS_DRV_SINGAIN', 'Y1:RDS-OUTS_DRV_COSGAIN'
DRVON_PV = 'Y1:RDS-OUTS_DRVON'

M_DRIVE = 8                  # rotor = f_elec / M_DRIVE  (m = 8 stator)
DECIM = (8, 8)               # 1024 Hz -> 16 Hz
WIDE_BAND = (0.05, 4.0)      # fundamental search with nothing driving
DRIVEN_BAND = (0.15, 3.0)    # ... as a fraction of f_elec/8 when driving
MAX_SUBHARM = 4              # how far down the comb to walk
SUBHARM_MIN_SNR = 6.0        # ... and stand this far above the LOCAL noise floor
SUBHARM_MIN_FRAC = 0.04      # ... and carry at least this much of the peak
HARM_TOL_BINS = 2
FLOOR_BINS = 60              # half-width for the local median, as in peak_in_band

KURT_ROTATING, KURT_LIBRATING = -1.43, 0.92   # measured 2026-09-09, watch_capture.py


def spectrum(x, fs):
    """Hann amplitude spectrum, corrected for coherent gain."""
    ac = x - x.mean()
    X = np.abs(np.fft.rfft(ac * np.hanning(len(ac))))
    fr = np.fft.rfftfreq(len(ac), 1.0 / fs)
    return fr, X, X / (len(ac) / 4.0)


def amp_at(fr, amp, f):
    """Amplitude at f, max over +/- HARM_TOL_BINS. 0.0 if out of range."""
    if not np.isfinite(f) or f <= fr[1] or f >= fr[-1]:
        return 0.0
    i = int(np.argmin(np.abs(fr - f)))
    lo, hi = max(0, i - HARM_TOL_BINS), min(len(amp), i + HARM_TOL_BINS + 1)
    return float(amp[lo:hi].max())


def floor_at(fr, amp, f):
    """Local noise floor near f -- median over +/- FLOOR_BINS, as peak_in_band does."""
    if not np.isfinite(f) or f <= fr[1] or f >= fr[-1]:
        return np.inf
    i = int(np.argmin(np.abs(fr - f)))
    lo, hi = max(0, i - FLOOR_BINS), min(len(amp), i + FLOOR_BINS + 1)
    med = float(np.median(amp[lo:hi]))
    return med if med > 0 else np.inf


def find_fundamental(y, fs, lo, hi):
    """Fundamental from the comb rather than from the loudest line.

    Returns (f0, snr, n, harmonics) -- n is which harmonic of f0 was loudest,
    harmonics is the amplitude of 1f..4f for the chosen f0.
    """
    f_dom, snr = peak_in_band(y, fs, lo, hi)
    if not np.isfinite(f_dom) or f_dom <= 0:
        return np.nan, 0.0, 0, []
    fr, _, amp = spectrum(y, fs)
    a_dom = amp_at(fr, amp, f_dom)
    # A sub-harmonic is real only if it stands above the LOCAL NOISE FLOOR.
    # Fraction-of-peak alone is not enough: on the known-good 09-11 record the
    # true fundamental carries just 8.6% of the dominant line, so any threshold
    # strict enough to reject noise at low SNR would also have rejected it.
    n = 1
    for cand in range(2, MAX_SUBHARM + 1):
        f_c = f_dom / cand
        a_c = amp_at(fr, amp, f_c)
        if a_c >= SUBHARM_MIN_FRAC * a_dom and a_c >= SUBHARM_MIN_SNR * floor_at(fr, amp, f_c):
            n = cand
    f0 = f_dom / n
    return f0, snr, n, [amp_at(fr, amp, m * f0) for m in (1, 2, 3, 4)]


def fetch(conn, channel, win, lag):
    fe = caget(GPS_PV)
    if fe is None:
        raise RuntimeError(f'no readback from {GPS_PV}')
    b = int(fe) - lag
    a = b - win
    buf = conn.fetch(a, b, [channel])[0]
    return np.asarray(buf.data, float), float(buf.channel.sample_rate), a, b


# ----------------------------------------------------------------- acquisition

def poll_once(conn, channel, win, lag):
    """One estimate. Returns a dict of everything worth keeping, or raises."""
    y, fs, a, b = fetch(conn, channel, win, lag)

    f_elec = caget(FREQ_PV) or 0.0
    gain = max(abs(caget(SIN_PV) or 0.0), abs(caget(COS_PV) or 0.0))
    drvon = int(caget(DRVON_PV) or 0)
    driving = bool(drvon and gain > 1e-6)

    yd = y - y.mean()
    for q in DECIM:
        yd = decimate(yd, q, ftype='fir')
    fsd = fs / float(np.prod(DECIM))

    if driving and f_elec > 0:
        fe8 = f_elec / M_DRIVE
        lo, hi = DRIVEN_BAND[0] * fe8, DRIVEN_BAND[1] * fe8
    else:
        lo, hi = WIDE_BAND

    f0, snr, n, harm = find_fundamental(yd, fsd, lo, hi)
    k, rms = float(kurt(yd)), float(yd.std())
    harm = (list(harm) + [0.0] * 4)[:4]

    notes = []
    if not np.isfinite(f0):
        notes.append('NO LINE')
    if driving and np.isfinite(f0) and f0 > 1.2 * f_elec / M_DRIVE:
        notes.append('f_rot > f_elec/8 -- UNPHYSICAL, check the comb')
    if snr < 20:
        notes.append(f'low SNR {snr:.0f}')
    if k > 0.0:
        notes.append('cusped -- may be librating')

    # Slip only means something while the drive is on. DRV_FREQ keeps its last
    # value after a run, so a ratio against it when the electrodes are idle is a
    # confident-looking number that means nothing.
    slip = (f0 / (f_elec / M_DRIVE)) if (driving and f_elec > 0 and np.isfinite(f0)) \
        else float('nan')

    return dict(gps_start=a, gps_end=b, f_elec=f_elec, f_rot=f0, slip=slip,
                n_harmonic=n, snr=snr, kurtosis=k, rms=rms,
                a1=harm[0], a2=harm[1], a3=harm[2], a4=harm[3],
                drvon=drvon, gain=gain, driving=driving, note='; '.join(notes))


FIELDS = ('gps_start', 'gps_end', 'f_elec', 'f_rot', 'slip', 'n_harmonic',
          'snr', 'kurtosis', 'rms', 'a1', 'a2', 'a3', 'a4', 'drvon', 'gain')


def fmt_row(row):
    if row['driving'] and np.isfinite(row['slip']):
        fe_s, slip_s = f"{row['f_elec']:7.3f}", f"{row['slip']:6.3f}"
    else:
        fe_s, slip_s = '   idle', '    --'
    return (f"{datetime.now():%H:%M:%S} {row['gps_start']:11d} {fe_s} "
            f"{row['f_rot']:8.4f} {slip_s} {row['n_harmonic']:2d} {row['snr']:6.0f} "
            f"{row['kurtosis']:+6.2f} {row['rms']:7.1f}  {row['note']}")


# ----------------------------------------------------------------------- HDF5

class H5Logger:
    """Append-as-you-go HDF5 log.

    Every row is written and FLUSHED as it arrives, so a kill -9, a lost ssh
    session or a dead X server costs at most the poll in flight. Resizable
    datasets rather than one array at the end, for the same reason -- an
    overnight scan that only writes on clean exit is an overnight scan you can
    lose.
    """

    def __init__(self, path, attrs):
        self.path = path
        new = not os.path.exists(path)
        self.f = h5py.File(path, 'a')
        if new:
            for k, v in attrs.items():
                self.f.attrs[k] = v
            for name in FIELDS:
                self.f.create_dataset(name, shape=(0,), maxshape=(None,),
                                      dtype='f8', chunks=(64,))
            self.f.create_dataset('note', shape=(0,), maxshape=(None,),
                                  dtype=h5py.string_dtype(), chunks=(64,))
            self.f.flush()
        self.n = self.f[FIELDS[0]].shape[0]

    def append(self, row):
        i = self.n
        for name in FIELDS:
            d = self.f[name]
            d.resize((i + 1,))
            d[i] = float(row[name])
        d = self.f['note']
        d.resize((i + 1,))
        d[i] = row['note']
        self.n = i + 1
        self.f.flush()

    def close(self):
        try:
            self.f.close()
        except Exception:
            pass


def acquisition_loop(args, out_q, stop_evt, h5, echo):
    """Fetch forever. Shared by the headless and GUI paths -- one estimator,
    one code path, so the GUI cannot drift from the validated CLI."""
    conn = None
    win, lag = int(args.window), int(args.lag)
    while not stop_evt.is_set():
        try:
            if conn is None:
                conn = nds2.connection(NDS_HOST, NDS_PORT)
                conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')
            row = poll_once(conn, args.channel, win, lag)
        except Exception as exc:
            print(f'{datetime.now():%H:%M:%S} fetch failed: {exc}', flush=True)
            conn = None
            stop_evt.wait(10)
            continue
        if echo:
            print(fmt_row(row), flush=True)
        if h5 is not None:
            try:
                h5.append(row)
            except Exception as exc:
                print(f'  ! h5 append failed: {exc}', flush=True)
        if out_q is not None:
            out_q.put(row)
        stop_evt.wait(max(1.0, args.step))


# ------------------------------------------------------------------------ GUI

def run_gui(args, h5):
    """Live plot. Acquisition runs in a daemon thread so an NDS2 fetch never
    freezes the window."""
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker

    q, stop_evt = queue.Queue(), threading.Event()
    th = threading.Thread(target=acquisition_loop,
                          args=(args, q, stop_evt, h5, True), daemon=True)
    th.start()

    t0 = time.time()
    T, FR, FE8, SNR, KU, SLIP, FEL = [], [], [], [], [], [], []

    fig = plt.figure(figsize=(11, 8.5))
    fig.canvas.manager.set_window_title(f'track_drive — {args.channel}')
    gs = fig.add_gridspec(3, 1, height_ratios=[2.2, 1.3, 2.2], hspace=0.30,
                          top=0.93, bottom=0.07, left=0.09, right=0.93)
    ax_f = fig.add_subplot(gs[0])
    ax_h = fig.add_subplot(gs[1], sharex=ax_f)      # same time base as the top panel
    ax_s = fig.add_subplot(gs[2])

    ax_f.set_ylabel('rotor frequency (Hz)')
    ax_f.tick_params(labelbottom=False)             # shared x, label it once below
    ax_f.grid(alpha=.3)
    l_fr, = ax_f.plot([], [], 'o-', ms=4, color='navy', label='measured f_rot')
    l_fe, = ax_f.plot([], [], '--', color='darkorange', label='commanded f_elec/8')
    ax_f.legend(loc='upper left', fontsize=9)

    ax_h.set_ylabel('SNR', color='teal')
    ax_h.set_xlabel('minutes since start')
    ax_h.grid(alpha=.3)
    ax_h.set_yscale('log')
    # plain decade ticks -- the default log minor labels turn this short axis
    # into unreadable clutter
    ax_h.yaxis.set_major_locator(mticker.LogLocator(base=10))
    ax_h.yaxis.set_minor_formatter(mticker.NullFormatter())
    ax_h.tick_params(axis='y', labelcolor='teal')
    l_snr, = ax_h.plot([], [], '-', color='teal')
    ax_h.axhline(20, color='teal', ls=':', lw=1)    # the 09-14 'line is gone' threshold
    ax_k = ax_h.twinx()
    ax_k.set_ylabel('kurtosis', color='crimson')
    ax_k.tick_params(axis='y', labelcolor='crimson')
    ax_k.set_ylim(-1.8, 1.4)                        # fixed: both reference states in view
    l_ku, = ax_k.plot([], [], '-', color='crimson')
    # the two states this channel can be in, measured 2026-09-09
    ax_k.axhline(KURT_ROTATING, color='crimson', ls='--', lw=1)
    ax_k.axhline(KURT_LIBRATING, color='crimson', ls=':', lw=1)
    ax_k.text(0.995, KURT_ROTATING, ' rotating', transform=ax_k.get_yaxis_transform(),
              va='bottom', ha='right', fontsize=7, color='crimson')
    ax_k.text(0.995, KURT_LIBRATING, ' librating', transform=ax_k.get_yaxis_transform(),
              va='bottom', ha='right', fontsize=7, color='crimson')

    # This panel IS the deliverable of the scan: the f_elec -> rotor curve,
    # which is non-monotonic if the drive has a torque-vs-slip maximum.
    ax_s.set_xlabel('commanded f_elec (Hz)')
    ax_s.set_ylabel('measured rotor f (Hz)')
    ax_s.grid(alpha=.3)
    sc = ax_s.scatter([], [], c=[], cmap='viridis', s=26)
    l_sync, = ax_s.plot([], [], ':', color='grey', label='synchronous, f_elec/8')
    ax_s.legend(loc='upper left', fontsize=9)
    txt = fig.text(0.01, 0.985, '', va='top', family='monospace', fontsize=9)

    def update():
        # Redraw ONLY when a new estimate has actually arrived. FuncAnimation
        # would repaint the whole canvas every interval regardless, which at 1 Hz
        # against a 60 s data cadence is ~60x more repaints than there is new
        # data -- barely noticeable locally, but the thing that makes a plot feel
        # sluggish over `ssh -Y`. A plain canvas timer plus an explicit
        # draw_idle() costs nothing when nothing has changed.
        got = False
        while True:
            try:
                r = q.get_nowait()
            except queue.Empty:
                break
            got = True
            T.append((time.time() - t0) / 60.0)
            FR.append(r['f_rot'])
            FE8.append(r['f_elec'] / M_DRIVE if r['driving'] else np.nan)
            SNR.append(max(r['snr'], 1e-3))
            KU.append(r['kurtosis'])
            if r['driving'] and np.isfinite(r['f_rot']):
                FEL.append(r['f_elec'])
                SLIP.append(r['f_rot'])
        if not got:
            return
        l_fr.set_data(T, FR)
        l_fe.set_data(T, FE8)
        l_snr.set_data(T, SNR)
        l_ku.set_data(T, KU)
        for ax in (ax_f, ax_h):
            ax.relim(); ax.autoscale_view()
        ax_k.relim(); ax_k.autoscale_view(scaley=False)   # keep the fixed kurtosis scale
        if FEL:
            sc.set_offsets(np.column_stack([FEL, SLIP]))
            sc.set_array(np.arange(len(FEL), dtype=float))
            xs = np.array([min(FEL), max(FEL)])
            l_sync.set_data(xs, xs / M_DRIVE)
            ax_s.relim(); ax_s.autoscale_view()
        last = dict(f_rot=FR[-1], snr=SNR[-1], kurtosis=KU[-1])
        state = ('rotating' if last['kurtosis'] < -0.6 else
                 'LIBRATING?' if last['kurtosis'] > 0.0 else 'ambiguous')
        txt.set_text(f"f_rot {last['f_rot']:.4f} Hz   SNR {last['snr']:.0f}   "
                     f"kurt {last['kurtosis']:+.2f} ({state})   n={len(T)} polls"
                     + (f"   h5: {os.path.basename(args.h5)}" if args.h5 else ''))
        fig.canvas.draw_idle()

    timer = fig.canvas.new_timer(interval=int(args.gui_interval * 1000))
    timer.add_callback(update)
    timer.start()
    fig._track_drive_timer = timer      # keep a reference or it is garbage-collected
    try:
        plt.show()                      # closing the window returns from here
    finally:
        timer.stop()
        stop_evt.set()


# ----------------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--channel', default=CHANNEL_DEFAULT,
                   help=f'LES channel (default {CHANNEL_DEFAULT} -- see module docstring '
                        f'for why it is PIT and not YAW)')
    p.add_argument('--window', type=float, default=120.0,
                   help='seconds per estimate (default 120; see docstring -- do NOT raise '
                        'this expecting finer resolution, the line chirps)')
    p.add_argument('--lag', type=float, default=30.0,
                   help='seconds behind the front-end clock to end each fetch (default 30)')
    p.add_argument('--step', type=float, default=60.0,
                   help='seconds between estimates (default 60)')
    p.add_argument('--h5', default=None,
                   help='append every estimate to this HDF5 file, flushed per row')
    p.add_argument('--csv', default=None, help='also append rows here as CSV')
    p.add_argument('--gui', action='store_true',
                   help='live plot (needs DISPLAY; works over ssh -X/-Y)')
    p.add_argument('--gui-interval', type=float, default=2.0,
                   help='seconds between GUI checks for new data (default 2). The plot '
                        'only repaints when an estimate actually arrives, so raising this '
                        'costs nothing but responsiveness.')
    args = p.parse_args()

    if args.gui and not os.environ.get('DISPLAY'):
        print('! --gui needs DISPLAY: run from the worker2 desktop session, reconnect with '
              'ssh -X (or -Y), or drop --gui and use --h5 alone.')
        return 1

    print(f'# channel {args.channel}   window {int(args.window)} s   '
          f'lag {int(args.lag)} s   step {args.step:g} s')
    print(f'# rotor = f_elec / {M_DRIVE};  slip = f_rot / (f_elec/{M_DRIVE})')
    print(f'# kurtosis reference: rotating {KURT_ROTATING:+.2f}, '
          f'librating {KURT_LIBRATING:+.2f}')

    h5 = None
    if args.h5:
        h5 = H5Logger(args.h5, dict(
            channel=args.channel, window_s=float(args.window), lag_s=float(args.lag),
            step_s=float(args.step), m_drive=M_DRIVE, decim=str(DECIM),
            created_utc=datetime.now(timezone.utc).isoformat(),
            host=os.uname().nodename,
            note='rotor frequency from the harmonic comb; no divisor constant. '
                 'f_rot is the fundamental; n_harmonic is which harmonic was loudest.'))
        print(f'# h5 -> {args.h5} (flushed every row; {h5.n} rows already present)')

    csv_fh = None
    if args.csv:
        new = not os.path.exists(args.csv)
        csv_fh = open(args.csv, 'a', buffering=1)
        if new:
            csv_fh.write(','.join(FIELDS) + ',note\n')

    class _Tee:
        def __init__(self, h5, fh): self.h5, self.fh = h5, fh
        def append(self, row):
            if self.h5: self.h5.append(row)
            if self.fh:
                self.fh.write(','.join(f'{row[k]}' for k in FIELDS)
                              + ',' + row['note'].replace(',', ';') + '\n')
    sink = _Tee(h5, csv_fh)

    print(f'{"time":>8} {"gps":>11} {"f_elec":>7} {"f_rot":>8} {"slip":>6} '
          f'{"n":>2} {"snr":>6} {"kurt":>6} {"rms":>7}  notes', flush=True)
    try:
        if args.gui:
            run_gui(args, sink)
        else:
            acquisition_loop(args, None, threading.Event(), sink, True)
    except KeyboardInterrupt:
        print('\nstopped.')
    finally:
        if h5:
            h5.close()
        if csv_fh:
            csv_fh.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
