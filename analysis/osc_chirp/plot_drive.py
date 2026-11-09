"""Plot the oscillator chirp drive as recorded by the DAQ (V2, V3, V4 OUT_DQ), for one burst of a session.

    python3 plot_drive.py DATA_DIR [--burst -1] [--out plots/osc_chirp_drive.png]
    python3 plot_drive.py selftest            # synthetic chirp from osc_chirp_check.synth

DATA_DIR holds the session's Y1_RDS-OUTS_V{2,3,4}_OUT_DQ_<start>_<end>.h5 (batch_fetch format). A session has one
burst per drive command (G0 with outputs off also shows in OUT_DQ); --burst picks one (default: the last, R1).
Time zero is the start of the AC in the data, so no clock alignment is needed for this plot.

Panels (measured unless marked):
  1. the three channel commands, counts, whole burst (pedestal ramp, chirp, teardown)
  2. zoom on the first 25 s
  3. field amplitude |z| and 4. field frequency from the unwrapped phase, against the commanded schedule
  5. DERIVED: the voltage expected at each electrode = W2 gain (V/count) x the command, high-passed with each
     channel's measured AC-coupling tau (W2 grounded runs, 2026-11-03, WAVEFORM_HANDOFF.md)
"""
import glob
import os
import re
import sys

import numpy as np

PHI = {'V2': 0.0, 'V4': -120.0, 'V3': -240.0}
NAMES = {'V2': 'A (V2)', 'V4': 'B (V4)', 'V3': 'C (V3)'}
COLORS = {'V2': '#2a78d6', 'V4': '#eb6834', 'V3': '#1baf7a'}     # categorical slots 1-3 (validated reference palette)
GAIN = {'V2': 0.01241, 'V3': 0.01263, 'V4': 0.01273}              # V/count at the electrode, W2 chirp 0.3-10 Hz (mid)
TAU = {'V2': 5.69, 'V3': 5.56, 'V4': 5.43}                        # s, AC coupling, W2 grounded bburst
INK, MUTED, GRID = '#2b2b2b', '#6b6b6b', '#e4e4e0'


def load_dir(d):
    out = {}
    for ch in ('V2', 'V3', 'V4'):
        fn = sorted(glob.glob(os.path.join(d, f'*OUTS_{ch}_OUT_DQ*.h5')))
        if not fn:
            sys.exit(f'! no {ch} OUT_DQ file in {d}')
        import h5py
        with h5py.File(fn[-1], 'r') as h:
            x = np.asarray(h['data'][:], float); g0 = float(h['segments/gps_start'][0])
        m = re.search(r'_(\d{9,10})_(\d{9,10})\.h5$', fn[-1])
        fs = x.size / (int(m.group(2)) - int(m.group(1))) if m else 1024.0
        out[ch] = (g0, round(fs), x)
    fs = {v[1] for v in out.values()}; g = {v[0] for v in out.values()}
    if len(fs) != 1 or len(g) != 1:
        sys.exit(f'! the three files differ in rate or start: {fs} {g}')
    n = min(v[2].size for v in out.values())
    return out['V2'][1], {k: v[2][:n] for k, v in out.items()}


def bursts(V, fs, amp=6400.0, min_s=50.0):
    z = sum(V[k] * np.exp(-1j * np.radians(PHI[k])) for k in PHI) * 2 / 3 / amp
    on = np.abs(z) > 0.05
    edges = np.flatnonzero(np.diff(on.astype(int)))
    starts = [e + 1 for e in edges if on[e + 1]]; ends = [e + 1 for e in edges if not on[e + 1]]
    if on[0]:
        starts = [0] + starts
    if on[-1]:
        ends = ends + [on.size]
    return z, [(s, e) for s, e in zip(starts, ends) if (e - s) / fs >= min_s]


def hp(x, fs, tau):
    a = tau / (tau + 1.0 / fs); y = np.zeros_like(x); prev = x[0]
    for i in range(1, x.size):
        y[i] = a * (y[i - 1] + x[i] - prev); prev = x[i]
    return y


def schedule(t, f_a=0.40, f_b=0.15, n=26, dwell=4.0, glide=3.5, t_sweep=5.5):
    fs_ = np.linspace(f_a, f_b, n); f = np.full(t.size, np.nan)
    for i, tt in enumerate(t):
        t1 = tt - t_sweep
        if tt < 0:
            continue
        if t1 < 0:
            f[i] = f_a; continue
        # step k writes fs_[k] at t_sweep + k*dwell and glides there from fs_[k-1] (step 0 writes f_a itself)
        k = min(int(t1 // dwell), n - 1)
        prev = fs_[k - 1] if k > 0 else f_a
        f[i] = prev + (fs_[k] - prev) * min(1.0, (t1 - k * dwell) / glide)
    return f


def plot(fs, V, which=-1, out='plots/osc_chirp_drive.png', title='Oscillator chirp, R1: the drive as recorded'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    z, bl = bursts(V, fs)
    if not bl:
        sys.exit('! no burst of AC longer than 50 s found')
    print(f'{len(bl)} burst(s): ' + ', '.join(f'{(e - s) / fs:.0f} s at sample {s}' for s, e in bl) + f'; plotting #{which}')
    s, e = bl[which]
    i0 = max(0, s - int(20 * fs)); i1 = min(z.size, e + int(20 * fs))
    t = (np.arange(i0, i1) - s) / fs
    seg = {k: v[i0:i1] for k, v in V.items()}; zz = z[i0:i1]
    ph = np.unwrap(np.angle(zz)); k = int(0.5 * fs)
    f_inst = np.convolve(np.gradient(ph) * fs / (2 * np.pi), np.ones(k) / k, mode='same')
    live = np.abs(zz) > 0.5
    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED,
                         'ytick.color': MUTED, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, ax = plt.subplots(5, 1, figsize=(10, 12.5), constrained_layout=True,
                           gridspec_kw={'height_ratios': [1.3, 1.1, 0.6, 0.9, 1.3]})
    order = ('V2', 'V4', 'V3')
    for a in ax:
        a.grid(True, color=GRID, lw=0.6); a.set_axisbelow(True)
    for ch in order:
        ax[0].plot(t, seg[ch], lw=0.8, color=COLORS[ch], label=NAMES[ch])
    ax[0].set_ylabel('command, counts'); ax[0].set_ylim(-300, 15200)
    ax[0].axhline(12800, color=MUTED, lw=0.8, ls=':'); ax[0].text(t[-1], 12800, ' limit 12800', va='center', color=MUTED, fontsize=8)
    ax[0].set_title('V2, V4, V3 commands (OUT_DQ): pedestal ramp, chirp 0.40 → 0.15 Hz, teardown', loc='left', color=INK)
    ax[0].legend(loc='upper left', frameon=False, ncol=3)
    z0 = (t >= -15) & (t <= 25)
    for ch in order:
        ax[1].plot(t[z0], seg[ch][z0], lw=1.0, color=COLORS[ch], label=NAMES[ch])
    ax[1].set_xlim(-15, 25); ax[1].set_ylabel('counts')
    ax[1].set_title('first 25 s: pedestal ramps together, AC ramps in over 3.5 s, three phases 120° apart', loc='left', color=INK)
    ax[2].plot(t, np.abs(zz), lw=1.0, color=INK)
    ax[2].set_ylabel('|field| / 6400'); ax[2].set_ylim(-0.05, 1.15)
    ax[2].set_title('field amplitude', loc='left', color=INK)
    sch = schedule(t)
    ax[3].plot(t, sch, lw=2.5, color=GRID, label='commanded (26 × 4 s steps, 3.5 s glides)')
    ax[3].plot(t[live], f_inst[live], lw=1.0, color=COLORS['V2'], label='measured from the field phase')
    ax[3].axhspan(0.30, 0.32, color='#eda100', alpha=0.15, lw=0); ax[3].text(t[live][0] + 2, 0.322, 'trap f₀ ≈ 0.31 Hz (DECISIONS)', color=MUTED, fontsize=8)
    ax[3].set_ylabel('field frequency, Hz'); ax[3].set_ylim(0.12, 0.43)
    ax[3].legend(loc='upper right', frameon=False)
    ax[3].set_title('field rotation frequency', loc='left', color=INK)
    for ch in order:
        v = GAIN[ch] * hp(seg[ch], fs, TAU[ch])
        ax[4].plot(t, v, lw=0.8, color=COLORS[ch], label=NAMES[ch])
    ax[4].set_ylabel('volts at electrode'); ax[4].set_xlabel('time from the start of the AC, s')
    ax[4].set_title('DERIVED, not measured: expected electrode voltage (W2 gains × command, AC-coupled τ 5.4–5.7 s)',
                    loc='left', color=INK)
    lo, hi = ax[4].get_ylim(); ax[4].set_ylim(lo, hi + 0.35 * (hi - lo))
    ax[4].legend(loc='upper left', frameon=False, ncol=3)
    for a in (ax[0], ax[2], ax[3], ax[4]):
        a.set_xlim(t[0], t[-1])
    fig.suptitle(title, x=0.01, ha='left', fontsize=12, color=INK)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    fig.savefig(out, dpi=200)
    print('wrote', out)
    return out


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        here = os.path.dirname(os.path.abspath(__file__))
        for p in (os.path.join(here, '..', '..', 'lab_utils'), os.path.join(here, '..', '..', '..', 'decay_sail_wt_chirp', 'lab_utils')):
            if os.path.exists(os.path.join(p, 'osc_chirp_check.py')):
                sys.path.insert(0, p); break
        import osc_chirp_check as cc
        V = cc.synth(); V = {k: np.concatenate([np.zeros(20 * 1024), v]) for k, v in V.items()}
        plot(1024.0, V, out='plots/osc_chirp_drive_selftest.png', title='SELFTEST (synthetic chirp, not data)')
        return
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    which = int(sys.argv[sys.argv.index('--burst') + 1]) if '--burst' in sys.argv else -1
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else 'plots/osc_chirp_drive.png'
    fs, V = load_dir(sys.argv[1])
    plot(fs, V, which, out)


if __name__ == '__main__':
    main()
