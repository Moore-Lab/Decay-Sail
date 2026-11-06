"""Oscillator drive (fixed rate or chirp) on the measured plant: trap and per-hold coupling from F3 2026-11-04
(f3_check.py, branch feedback-drive). Coupling measured at amp 4000; scaled to other amplitudes as linear term ~ V,
2x term ~ V^2 (ASSUMED above 4000). Rotor angle in deg from rest; no damping over these minutes.

    python3 osc_sim.py c2      # check against C2 (2026-11-02) holds, amp 4000 and 6400
    python3 osc_sim.py chirp   # the osc_chirp runbook's chirp and hold
"""
import math
import os
import sys

import numpy as np

_here = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(_here, '..', '..', 'lab_utils'), os.path.join(_here, '..', '..', '..', 'decay_sail_wt_fb', 'lab_utils')):
    if os.path.exists(os.path.join(_p, 'f3_check.py')):
        sys.path.insert(0, _p); break
import f3_check as f3  # noqa: E402

REST = 229.8


def run(schedule, T, amp=6400, direction=1, ramp=4.0, phi0=0.3, w0=0.0, psi0=0.0, coupling=f3.COUPLING_HOLD):
    """schedule(t) -> f_elec (Hz); gains ramp in linearly over `ramp` s. Returns t, angle (deg)."""
    s = amp / 4000.0; c0, c1, s1, c2, s2 = coupling
    dt = 1e-3; ph = math.radians(phi0); om = math.radians(w0); psi = psi0
    tt, pp = [], []
    for i in range(int(T / dt)):
        t = i * dt
        g = min(1.0, t / ramp) if ramp > 0 else 1.0
        psi += direction * 2 * np.pi * schedule(t) * dt
        D = psi + 8 * (math.radians(REST) + ph)
        tq = s * g * (c0 + c1 * math.cos(D) + s1 * math.sin(D)) + (s * g) ** 2 * (c2 * math.cos(2 * D) + s2 * math.sin(2 * D))
        om += (f3.trap_acc(math.degrees(ph)) + tq) * dt; ph += om * dt
        if i % 20 == 0:
            tt.append(t); pp.append(math.degrees(ph))
    return np.array(tt), np.array(pp)


def swing_amp(t, p, t0, t1):
    m = (t >= t0) & (t < t1); y = p[m] - p[m].mean()
    return math.sqrt(2) * y.std()


def free_swing_state(A, phase):
    """(phi, w) on a free swing of amplitude A deg at a given phase (energy from the trap)."""
    E = f3.trap_U(A) - f3.trap_U(0.0)
    phi = A * math.cos(phase)
    w2 = max(0.0, 2 * (E - (f3.trap_U(phi) - f3.trap_U(0.0))))
    return phi, -math.copysign(math.degrees(math.sqrt(w2)), math.sin(phase) or 1.0)


def c2():
    # C2 holds (analysis/c2_20261102/README.md): (hold, f_elec, start amplitude from the previous gap, measured end)
    holds = [(1, 0.1, 0.0, 39), (2, 0.2, 46.8, 49), (3, 0.4, 51.1, 41), (4, 0.1, 3.9, 54), (5, 0.2, 56.7, 96),
             (6, 0.4, 97.5, 99), (7, 0.155, 102.7, 111)]
    print('C2 holds, 150 s, sim end amplitude (last 20 s) over 4 start phases x 2 directions; measured end in []')
    for amp in (4000, 6400):
        print(f' amp {amp}:')
        for h, fe, A0, meas in holds:
            ends = []; over = 0
            for d in (1, -1):
                for k in range(4):
                    phi, w = free_swing_state(A0, k * np.pi / 2) if A0 > 0 else (0.3, 0.0)
                    t, p = run(lambda t: fe, 150.0, amp=amp, direction=d, ramp=5.0, phi0=phi, w0=w, psi0=k * 1.3)
                    tc, _ = f3.turns(t, p)
                    if tc.size:
                        over += 1
                    else:
                        ends.append(swing_amp(t, p, 130, 150))
            rng = f'{min(ends):.0f}..{max(ends):.0f}' if ends else '-'
            print(f'   hold {h} f {fe:5.3f} from {A0:5.1f}: end {rng} deg, over the top in {over}/8   [{meas}]')


def chirp():
    f_a, f_b, n, dwell = 0.40, 0.15, 26, 4.0
    fs = np.linspace(f_a, f_b, n)
    glide = 3.5
    def sched(t, settle=glide + 2.0):
        t1 = t - settle
        if t1 < 0:
            return f_a
        i = int(t1 // dwell)
        if i >= n - 1:
            return f_b
        frac = min(1.0, (t1 - i * dwell) / glide)
        return fs[i] + (fs[i + 1] - fs[i]) * frac
    T = 5.5 + n * dwell
    for amp in (4000, 6400):
        res = []
        for d in (1, -1):
            for k in range(3):
                t, p = run(sched, T, amp=amp, direction=d, ramp=glide, psi0=k * 2.1)
                tc, dc = f3.turns(t, p)
                res.append(f'{"no" if not tc.size else f"{tc[0]:.0f}s{int(dc[0]):+d}"}/{np.max(np.abs(p)):.0f}')
        print(f'chirp 0.40->0.15 Hz, amp {amp}: over-the-top time/max |angle| (2 dirs x 3 phases): {res}')
    for amp in (4000, 6400):
        res = []
        for d in (1, -1):
            for k in range(3):
                t, p = run(lambda t: 0.31, 125.0, amp=amp, direction=d, ramp=5.0, psi0=k * 2.1)
                tc, dc = f3.turns(t, p)
                res.append(f'{"no" if not tc.size else f"{tc[0]:.0f}s{int(dc[0]):+d}"}/{np.max(np.abs(p)):.0f}')
        print(f'hold 0.31 Hz 120 s from rest, amp {amp}: {res}')


if __name__ == '__main__':
    {'c2': c2, 'chirp': chirp}[sys.argv[1] if len(sys.argv) > 1 else 'c2']()
