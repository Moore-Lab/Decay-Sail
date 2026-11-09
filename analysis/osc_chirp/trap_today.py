"""Trap shape from today's 10-min free swing (drive off), compared with the 11-04 joint fit (f3_check.TRAP_CU).

    python3 trap_today.py

Energy is conserved within a swing apart from slow damping: 1/2 w^2 + U(phi) = E0 + E1 t. Fit U as harmonics 1..4
(constant fixed so U(0) = 0) together with E0, E1, by least squares over all frames. Frames within 3 s after a
tracker gap are dropped (host_time is processing time; after a stall the frames come out in a burst).
"""
import math
import numpy as np
from scipy.signal import savgol_filter
import analyze_r1 as A
import f3_check as f3

t, phi, ncc, bad = A.load_tracker(A.D_DEF)
dt = np.median(np.diff(t))
gaps = t[1:][np.diff(t) > 0.2]
keep = np.ones(t.size, bool)
for g in gaps:
    keep &= ~((t >= g - 0.5) & (t <= g + 3.0))
sel = (t >= A.FREE[0]) & (t <= A.FREE[1]) & keep
ps = savgol_filter(phi, 11, 3); w = np.radians(savgol_filter(phi, 11, 3, deriv=1, delta=dt))
r = np.radians(ps[sel]); tt = t[sel] - A.FREE[0]
cols = []
for n in range(1, 5):
    cols += [np.cos(n * r) - 1.0, np.sin(n * r)]          # U(0) = 0
X = np.column_stack(cols + [-np.ones_like(r), -tt])        # U - E0 - E1 t = -1/2 w^2
Y = -0.5 * w[sel] ** 2
c, *_ = np.linalg.lstsq(X, Y, rcond=None)
res = Y - X @ c
U_today = lambda p: sum(c[2 * (n - 1)] * (math.cos(n * math.radians(p)) - 1) + c[2 * (n - 1) + 1] * math.sin(n * math.radians(p)) for n in range(1, 5))
U_1104 = lambda p: f3.trap_U(p) - f3.trap_U(0.0)
grid = np.arange(-95, 106, 5)
d = np.array([U_today(p) - U_1104(p) for p in grid])
print(f'frames {sel.sum()}; range {np.degrees(r.min()):.0f}..{np.degrees(r.max()):.0f} deg; energy residual rms {res.std():.3f} rad^2/s^2; '
      f'E0 {c[8]:.2f}, dE/dt {c[9]:.2e}')
print('harmonics today [cos1 sin1 cos2 sin2 ...]:', np.round(c[:8], 3).tolist())
print('11-04 joint fit                           :', np.round(f3.TRAP_CU[1:], 3).tolist())
print(f'U_today - U_11-04 over -95..+105 deg: rms {d.std():.2f}, max |diff| {np.abs(d).max():.2f} rad^2/s^2 '
      f'(at {grid[np.argmax(np.abs(d))]} deg); U_11-04 itself spans 0..{max(U_1104(p) for p in grid):.1f}')
for p in (-90, -45, 45, 90, 105):
    print(f'   U({p:+d}): today {U_today(p):.2f}, 11-04 {U_1104(p):.2f}')
w2 = np.mean(w[sel] ** 2)
print(f'damping from this fit: tau = <w^2>/(-dE/dt) = {w2:.3f}/{-c[9]:.2e} = {w2 / -c[9]:.0f} s ({w2 / -c[9] / 60:.0f} min) (derived)')
