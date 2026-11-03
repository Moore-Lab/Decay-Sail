#!/usr/bin/env python3
"""Test waveforms for the three stator electrodes (Problem 1: arbitrary signals at ~10 Hz bandwidth).

Pure numpy, no hardware. awg_waveform_drive.py plays these through the front-end AWG on
V2/V3/V4_EXC; waveform_check.py scores the recorded OUT_DQ against them.

    python3 waveforms.py list            # names, lengths, peak values
    python3 waveforms.py plot NAME       # quick look (matplotlib)

Every waveform is the AC part only, in units of the amplitude (peak |w| <= 1 on each electrode);
the player multiplies by --amp and adds the pedestal on V{n}_OFFSET. All start and end at 0.

Electrode order is A, B, C = V2, V4, V3 (docs/DECISIONS.md). A "field angle" psi gives
V_A = cos(psi), V_B = cos(psi - 120 deg), V_C = cos(psi - 240 deg): increasing psi is the forward
sequence A->B->C, the same as stator_osc_drive.py's forward matrix (V2 cos, V4 cos(-120), V3 cos(-240)).

Waveforms (proposed with Molly 2026-11-03; durations are choices, change freely):
  sine    three-phase 2 Hz electrical, 10 s, 0.5 s tapers
  chirp   three-phase, logarithmic 0.1 -> 10 Hz electrical over 60 s, 0.5 s tapers
  pulse   50 ms raised-cosine pulses: V2 alone, V3 alone, V4 alone, then all three together (x2)
          -> identifies the scope channel map and the inter-channel alignment
  step    three-phase field that JUMPS by 90 deg every 0.5 s (sharp, sample-to-sample), 8 s
          -> the F2 staircase made at 2048 Hz: does OUT_DQ still ring after a clean step?
  spinup  three-phase field following a smooth rotor spin-up: electrical 0 -> 9.6 Hz -> 0 over 24 s
          (rotor 0 -> 1.2 rev/s, F2's top speed was 1.17) -> the arbitrary waveform Problem 2 needs
"""
import sys
import numpy as np

FS = 2048.0                      # y1rds model rate (DECISIONS; F1b filter-state read)
ELECTRODES = (2, 3, 4)           # output order of every waveform array: V2, V3, V4
DELTA = {2: 0.0, 4: 120.0, 3: 240.0}   # A=V2, B=V4, C=V3, phase lag in deg


def _t(dur):
    return np.arange(int(round(dur * FS))) / FS


def _taper(t, ramp):
    """Raised-cosine ramp in and out over `ramp` s; 1 in between."""
    w = np.ones_like(t)
    if ramp <= 0:
        return w
    dur = t[-1] + 1 / FS
    a = t < ramp
    w[a] = 0.5 - 0.5 * np.cos(np.pi * t[a] / ramp)
    b = t > dur - ramp
    w[b] = 0.5 - 0.5 * np.cos(np.pi * (dur - t[b]) / ramp)
    return w


def three_phase(psi_deg, env=None):
    """(3, N) array for V2, V3, V4 from a field angle psi(t) in deg."""
    out = np.array([np.cos(np.radians(psi_deg - DELTA[n])) for n in ELECTRODES])
    return out if env is None else out * env


def sine(f=2.0, dur=10.0, ramp=0.5):
    t = _t(dur)
    return t, three_phase(360.0 * f * t, _taper(t, ramp))


def chirp(f1=0.1, f2=10.0, dur=60.0, ramp=0.5):
    t = _t(dur)
    k = np.log(f2 / f1) / dur
    phase_cycles = f1 * (np.exp(k * t) - 1) / k          # integral of f1*exp(k t)
    return t, three_phase(360.0 * phase_cycles, _taper(t, ramp))


def pulse(width=0.05, gap=1.0, repeats=2):
    """Raised-cosine pulses, positive, peak 1. Sequence: V2, V3, V4, all; repeated."""
    seq = [(2,), (3,), (4,), (2, 3, 4)] * repeats
    dur = gap * (len(seq) + 1)
    t = _t(dur)
    out = np.zeros((3, t.size))
    for k, chans in enumerate(seq):
        tc = gap * (k + 1)
        m = np.abs(t - tc) < width / 2
        shape = 0.5 + 0.5 * np.cos(2 * np.pi * (t[m] - tc) / width)
        for n in chans:
            out[ELECTRODES.index(n), m] = shape
    return t, out


def step(dwell=0.5, jump=90.0, dur=8.0, ramp=0.5):
    """Field angle jumps by `jump` every `dwell` s. The envelope ramps in/out slowly so the only
    sharp edges are the angle jumps (each a sample-to-sample step on all three electrodes)."""
    t = _t(dur)
    psi = jump * np.floor(t / dwell)
    return t, three_phase(psi, _taper(t, ramp))


def spinup(fmax=9.6, dur=24.0, ramp=0.5):
    """Electrical frequency follows a smooth bump 0 -> fmax -> 0 (sin^2 in time)."""
    t = _t(dur)
    f = fmax * np.sin(np.pi * t / dur) ** 2
    psi = 360.0 * np.cumsum(f) / FS
    return t, three_phase(psi, _taper(t, ramp))


WAVES = {'sine': sine, 'chirp': chirp, 'pulse': pulse, 'step': step, 'spinup': spinup}


def make(name):
    """-> (t, w) with w shape (3, N) for V2, V3, V4, peak |w| <= 1."""
    if name not in WAVES:
        raise SystemExit(f'unknown waveform {name!r}; choose from {", ".join(WAVES)}')
    t, w = WAVES[name]()
    w[:, 0] = 0.0
    w[:, -1] = 0.0
    return t, w


def main():
    if len(sys.argv) < 2 or sys.argv[1] == 'list':
        for name in WAVES:
            t, w = make(name)
            print(f'{name:7s} {t[-1] + 1 / FS:6.1f} s  {t.size:7d} samples/channel  '
                  f'min {w.min():+.3f}  max {w.max():+.3f}')
        return
    if sys.argv[1] == 'plot':
        import matplotlib.pyplot as plt
        t, w = make(sys.argv[2])
        for k, n in enumerate(ELECTRODES):
            plt.plot(t, w[k] + 2.2 * k, label=f'V{n}')
        plt.legend(); plt.xlabel('s'); plt.title(sys.argv[2]); plt.show()


if __name__ == '__main__':
    main()
