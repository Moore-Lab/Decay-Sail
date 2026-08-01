"""Fourier analysis of the Snowflake V1.3 bottom surface from the real DXF.

Chains the ARC/LINE segments into closed loops, rasterizes the material
footprint S(r,theta) (even-odd rule), and computes the angular harmonics
a_m(r).  Capacitance harmonic seen through the gap h (quasi-planar):

    C_m = (eps0/h) * | integral a_m(r) * exp(-m h / r) * r dr |   over the
          electrode annulus, and  tau_max ~ 0.5 * m * C_m * V0^2 * eta,
          eta = 0.5 (floating-rotor factor).

Outputs snowflake_harmonics.png and printed numbers.
"""

import numpy as np
import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path

DXF = "../Snowflake disk V1.3.DXF.dxf"
EPS0 = 8.854e-12
V0 = 100.0
ETA = 0.5
I_TOT = 1.88e-11
TOL = 1e-3  # mm endpoint-matching tolerance

# ---------- read segments ----------
doc = ezdxf.readfile(DXF)
segs = []  # (start, end, points)
for e in doc.modelspace():
    if e.dxftype() == "LINE":
        p0 = np.array([e.dxf.start.x, e.dxf.start.y])
        p1 = np.array([e.dxf.end.x, e.dxf.end.y])
        segs.append((p0, p1, np.array([p0, p1])))
    elif e.dxftype() == "ARC":
        c = np.array([e.dxf.center.x, e.dxf.center.y])
        r = e.dxf.radius
        a0, a1 = np.radians(e.dxf.start_angle), np.radians(e.dxf.end_angle)
        if a1 < a0:
            a1 += 2 * np.pi
        n = max(4, int(np.degrees(a1 - a0)))
        a = np.linspace(a0, a1, n)
        pts = c + r * np.column_stack([np.cos(a), np.sin(a)])
        segs.append((pts[0], pts[-1], pts))

# ---------- chain into loops ----------
used = [False] * len(segs)
loops = []
for i in range(len(segs)):
    if used[i]:
        continue
    used[i] = True
    chain = list(segs[i][2])
    while True:
        tail = chain[-1]
        found = False
        for j in range(len(segs)):
            if used[j]:
                continue
            s, e, pts = segs[j]
            if np.linalg.norm(s - tail) < TOL:
                chain.extend(pts[1:])
                used[j] = True
                found = True
                break
            if np.linalg.norm(e - tail) < TOL:
                chain.extend(pts[::-1][1:])
                used[j] = True
                found = True
                break
        if not found:
            break
    chain = np.array(chain)
    closed = np.linalg.norm(chain[0] - chain[-1]) < TOL
    loops.append((chain, closed))

closed_loops = [c for c, cl in loops if cl and len(c) > 3]
print(f"{len(segs)} segments -> {len(loops)} chains, {len(closed_loops)} closed")

# center on the outer (disk-edge) loop
allpts = np.vstack(closed_loops)
rmax_loop = max(closed_loops, key=lambda c: np.ptp(c[:, 0]))
ctr = 0.5 * (rmax_loop.min(0) + rmax_loop.max(0))
closed_loops = [c - ctr for c in closed_loops]
R_disk = np.max(np.linalg.norm(rmax_loop - ctr, axis=1))
print(f"disk radius from DXF: {R_disk:.3f} mm, {len(closed_loops)} loops")
for c in closed_loops:
    rr = np.linalg.norm(c, axis=1)
    print(f"  loop: {len(c)} pts, r range {rr.min():.3f}-{rr.max():.3f} mm")

paths = [Path(c) for c in closed_loops]

# ---------- polar rasterization ----------
NR, NTH = 176, 1024
r_mm = np.linspace(0.01, R_disk, NR)
th = np.linspace(0, 2 * np.pi, NTH, endpoint=False)
RR, TT = np.meshgrid(r_mm, th, indexing="ij")
XY = np.column_stack([(RR * np.cos(TT)).ravel(), (RR * np.sin(TT)).ravel()])
count = np.zeros(len(XY), dtype=int)
for p in paths:
    count += p.contains_points(XY)
S = (count % 2 == 1).reshape(NR, NTH).astype(float)
fill = S.mean(axis=1)

# ---------- harmonics ----------
F = np.fft.fft(S, axis=1) / NTH          # a_m(r), complex
ms = np.arange(1, 37)
print("\nglobal harmonic weights  integral |a_m(r)| r dr  (no gap atten):")
w = [np.trapezoid(np.abs(F[:, m]) * r_mm, r_mm) for m in ms]
top = np.argsort(w)[::-1][:6]
for i in top:
    print(f"  m={ms[i]:2d}: {w[i]:.4f} mm^2")

# ---------- torque vs gap for candidate harmonics ----------
def torque(m, h_mm, r_in, r_out):
    sel = (r_mm >= r_in) & (r_mm <= r_out)
    att = np.exp(-m * h_mm / r_mm[sel])
    Am = np.abs(np.trapezoid(F[sel, m] * att * r_mm[sel], r_mm[sel]))  # mm^2
    Cm = EPS0 * Am * 1e-6 / (h_mm * 1e-3)
    return 0.5 * m * Cm * V0**2 * ETA, Cm

print("\ntau_max (N m) at 100 V vs gap h, full coupling integral:")
cands = [2, 8, 16, 24, 32]
print(f"{'h (mm)':>7} " + " ".join(f"m={m:<2d}      " for m in cands))
for h in [0.20, 0.25, 0.27, 0.31, 0.37, 0.40]:
    row = [torque(m, h, 0.05, R_disk)[0] for m in cands]
    print(f"{h:7.2f} " + " ".join(f"{t:9.2e}" for t in row))

h = 0.31
print(f"\nat h={h} mm, per-harmonic detail:")
for m in cands:
    t, Cm = torque(m, h, 0.05, R_disk)
    prof_m = np.abs(F[:, m]) * np.exp(-m * h / r_mm) * r_mm
    cum_m = np.cumsum(prof_m) / prof_m.sum()
    rlo = r_mm[np.searchsorted(cum_m, 0.05)]
    rhi = r_mm[np.searchsorted(cum_m, 0.95)]
    om_lib = np.sqrt(m * t / I_TOT)
    print(f"  m={m:2d}: tau={t:.2e} N m, C_m={Cm*1e15:6.2f} fF, 90% band "
          f"r={rlo:.2f}-{rhi:.2f} mm, capture {om_lib/2/np.pi:.2f} Hz, "
          f"0->10Hz {2*np.pi*10/(0.5*t/I_TOT):6.0f} s, "
          f"3-ph sectors N={3*m}, pitch {360/(3*m):.1f} deg, "
          f"min Cu width at r=1.4: {np.radians(360/(3*m))*1.4-0.10:.3f} mm")

prof = np.abs(F[:, 16]) * np.exp(-16 * h / r_mm) * r_mm
cum = np.cumsum(prof) / prof.sum()
r_lo = r_mm[np.searchsorted(cum, 0.05)]
r_hi = r_mm[np.searchsorted(cum, 0.95)]

# ---------- figure ----------
fig = plt.figure(figsize=(13, 4.4))
ax1 = fig.add_subplot(131)
ax1.set_title("Rotor footprint from DXF")
X = RR * np.cos(TT)
Y = RR * np.sin(TT)
ax1.pcolormesh(X, Y, S, cmap="gray_r", shading="auto")
ax1.set_aspect("equal")
ax1.set_xlabel("mm")

ax2 = fig.add_subplot(132)
ax2.set_title(r"harmonic weight $\int |a_m| r\,dr$")
ax2.bar(ms, w, color="#1f77b4")
ax2.set_xlabel("m")
ax2.set_xticks([2, 6, 12, 18, 24, 30, 36])

ax3 = fig.add_subplot(133)
ax3.set_title("m=8 (green) / m=16 (black) integrand, h=0.31 mm")
ax3.plot(r_mm, prof / prof.max(), "k-", label="m=16")
p8 = np.abs(F[:, 8]) * np.exp(-8 * h / r_mm) * r_mm
ax3.plot(r_mm, p8 / p8.max(), "g-", label="m=8")
ax3.axvspan(r_lo, r_hi, color="#d62728", alpha=0.15, label="m=16 90% band")
ax3.set_xlabel("r (mm)")
ax3.legend(fontsize=8)
fig.tight_layout()
fig.savefig("snowflake_harmonics.png", dpi=170)
print("wrote snowflake_harmonics.png")
