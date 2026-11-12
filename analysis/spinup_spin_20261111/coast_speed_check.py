#!/usr/bin/env python3
"""Does the trap depend on speed? Fit U(theta) separately to the fast and slow halves of the S1 coast (same method as
coast_trap.py: 1/2 w^2 = E(t) - U(theta)), and to alternating halves of the fast part (noise reference). Mac only."""
import numpy as np
import coast_trap as C
from scipy.signal import savgol_filter

t, toff, a, n = C.load()
th = np.degrees(np.unwrap(np.radians(a)))
w = np.radians(savgol_filter(th, 9, 3, deriv=1, delta=1 / C.FPS))
t0, t1 = C.STOP_HOST + 5 - toff, C.LAST_TURN_HOST - 20 - toff
base = (t >= t0) & (t <= t1) & (n >= 0.85)
tm = 0.5 * (t0 + t1)
grid = np.radians(np.arange(0, 360, 1.0))


def fit(m, M=16, NE=2):
    tt, x, ww = t[m], np.radians(th[m]), w[m]
    ts = (tt - tt.min()) / (tt.max() - tt.min())
    cols = [ts ** p for p in range(NE + 1)]
    for k in range(1, M + 1):
        cols += [-np.cos(k * x), -np.sin(k * x)]
    c, *_ = np.linalg.lstsq(np.column_stack(cols), 0.5 * ww ** 2, rcond=None)
    u = c[NE + 1:]
    U = sum(u[2 * (k - 1)] * np.cos(k * grid) + u[2 * (k - 1) + 1] * np.sin(k * grid) for k in range(1, M + 1))
    acc = -sum(k * (-u[2 * (k - 1)] * np.sin(k * grid) + u[2 * (k - 1) + 1] * np.cos(k * grid)) for k in range(1, M + 1))
    return U - U.min(), acc, float(np.mean(np.abs(ww))) / (2 * np.pi)


Uf, af, rf = fit(base & (t < tm))
Us, as_, rs = fit(base & (t >= tm))
turn = np.floor((th - th[0]) / 360.0).astype(int)
fast = base & (t < tm)
Ua, aa, _ = fit(fast & (turn % 2 == 0))
Ub, ab, _ = fit(fast & (turn % 2 == 1))
print(f'fast half: mean rate {rf:.3f} Hz; slow half: {rs:.3f} Hz')
print(f'barrier height fast {Uf.max():.2f} at {np.degrees(grid[np.argmax(Uf)]):.0f} deg, slow {Us.max():.2f} at '
      f'{np.degrees(grid[np.argmax(Us)]):.0f} deg; rest (U min) fast {np.degrees(grid[np.argmin(Uf)]):.0f}, slow {np.degrees(grid[np.argmin(Us)]):.0f}')
print(f'trap rms difference fast vs slow: {np.sqrt(np.mean((af - as_) ** 2)):.2f} rad/s^2; '
      f'noise reference (alternate turns within the fast half): {np.sqrt(np.mean((aa - ab) ** 2)):.2f} rad/s^2')
print(f'U rms difference fast vs slow: {np.sqrt(np.mean(((Uf - Uf.mean()) - (Us - Us.mean())) ** 2)):.3f}; '
      f'noise reference: {np.sqrt(np.mean(((Ua - Ua.mean()) - (Ub - Ub.mean())) ** 2)):.3f} rad^2/s^2')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 2, figsize=(13, 4.2))
ax[0].plot(np.degrees(grid), Uf, label=f'fast half ({rf:.2f} Hz)'); ax[0].plot(np.degrees(grid), Us, label=f'slow half ({rs:.2f} Hz)')
ax[0].set_xlabel('theta (deg)'); ax[0].set_ylabel('U (rad^2/s^2)'); ax[0].legend(fontsize=8)
ax[1].plot(np.degrees(grid), af, label='fast'); ax[1].plot(np.degrees(grid), as_, label='slow')
ax[1].plot(np.degrees(grid), aa - ab, color='0.6', lw=0.7, label='noise ref (alternate turns, fast)')
ax[1].set_xlabel('theta (deg)'); ax[1].set_ylabel('trap a (rad/s^2)'); ax[1].legend(fontsize=8)
fig.tight_layout(); fig.savefig('plots/coast_speed_check.png', dpi=95)
