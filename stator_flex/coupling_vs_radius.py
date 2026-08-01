"""Does the electrode annulus capture all the available m=8 torque?

Recomputes a_m(r) from the Snowflake V1.3 DXF and integrates the coupling
kernel  a_m(r) * exp(-m h / r) * r  over candidate electrode annuli, so the
current choice (r = 0.80 -> 1.90 mm) can be compared against the optimum.

Fringing: an electrode edge at radius R still drives the rotor a little beyond
R, over a scale ~h.  Modelled by convolving the electrode window with a
Gaussian of sigma = h (conservative), rather than a hard cut.
"""

import numpy as np
import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path

M = 8
H_LIST = [0.27, 0.37]          # rotor gap with / without the 0.1 mm shim
R_IN_NOW, R_OUT_NOW = 0.69, 1.95
DXF = "../Snowflake disk V1.3.DXF.dxf"
TOL = 1e-3

doc = ezdxf.readfile(DXF)
segs = []
for e in doc.modelspace():
    if e.dxftype() == "LINE":
        p0 = np.array([e.dxf.start.x, e.dxf.start.y])
        p1 = np.array([e.dxf.end.x, e.dxf.end.y])
        segs.append((p0, p1, np.array([p0, p1])))
    elif e.dxftype() == "ARC":
        c = np.array([e.dxf.center.x, e.dxf.center.y])
        a0, a1 = np.radians(e.dxf.start_angle), np.radians(e.dxf.end_angle)
        if a1 < a0:
            a1 += 2 * np.pi
        a = np.linspace(a0, a1, max(4, int(np.degrees(a1 - a0))))
        pts = c + e.dxf.radius * np.column_stack([np.cos(a), np.sin(a)])
        segs.append((pts[0], pts[-1], pts))

used = [False] * len(segs)
loops = []
for i in range(len(segs)):
    if used[i]:
        continue
    used[i] = True
    chain = list(segs[i][2])
    while True:
        tail, found = chain[-1], False
        for j in range(len(segs)):
            if used[j]:
                continue
            s, e2, pts = segs[j]
            if np.linalg.norm(s - tail) < TOL:
                chain.extend(pts[1:]); used[j] = True; found = True; break
            if np.linalg.norm(e2 - tail) < TOL:
                chain.extend(pts[::-1][1:]); used[j] = True; found = True; break
        if not found:
            break
    chain = np.array(chain)
    if np.linalg.norm(chain[0] - chain[-1]) < TOL and len(chain) > 3:
        loops.append(chain)

outer = max(loops, key=lambda c: np.ptp(c[:, 0]))
ctr = 0.5 * (outer.min(0) + outer.max(0))
loops = [c - ctr for c in loops]
R_DISK = np.max(np.linalg.norm(outer - ctr, axis=1))
paths = [Path(c) for c in loops]

NR, NTH = 400, 1024
r = np.linspace(0.005, R_DISK, NR)
th = np.linspace(0, 2 * np.pi, NTH, endpoint=False)
RR, TT = np.meshgrid(r, th, indexing="ij")
XY = np.column_stack([(RR * np.cos(TT)).ravel(), (RR * np.sin(TT)).ravel()])
cnt = np.zeros(len(XY), dtype=int)
for p in paths:
    cnt += p.contains_points(XY)
S = (cnt % 2 == 1).reshape(NR, NTH).astype(float)
a_m = np.abs(np.fft.fft(S, axis=1)[:, M]) / NTH        # |a_8(r)|

print(f"rotor radius {R_DISK:.3f} mm; m={M} modulation spans "
      f"r = {r[a_m > 0.02 * a_m.max()].min():.2f} - {r[a_m > 0.02 * a_m.max()].max():.2f} mm")

fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
for h in H_LIST:
    kern = a_m * np.exp(-M * h / r) * r                # coupling density
    total = np.trapezoid(kern, r)                      # ideal: electrodes everywhere

    def captured(r_in, r_out, sigma=None):
        sigma = h if sigma is None else sigma
        w = 0.5 * (np.tanh((r - r_in) / sigma) - np.tanh((r - r_out) / sigma))
        return np.trapezoid(kern * w, r)

    now = captured(R_IN_NOW, R_OUT_NOW)
    print(f"\nh = {h:.2f} mm:")
    print(f"  current annulus {R_IN_NOW}-{R_OUT_NOW}: captures "
          f"{100*now/total:.1f}% of available m=8 coupling")
    # scan inner and outer edges
    best, bi, bo = 0, None, None
    for ri in np.arange(0.4, 1.3, 0.05):
        for ro in np.arange(1.4, 2.6, 0.05):
            v = captured(ri, ro)
            if v > best:
                best, bi, bo = v, ri, ro
    print(f"  best annulus {bi:.2f}-{bo:.2f}: {100*best/total:.1f}% "
          f"(gain over current: {best/now:.3f}x)")
    for ri in [0.6, 0.7, 0.8, 0.9, 1.0]:
        print(f"    r_in={ri:.2f} (r_out=1.90): {100*captured(ri,1.90)/total:5.1f}%")
    for ro in [1.6, 1.75, 1.9, 2.1]:
        print(f"    r_out={ro:.2f} (r_in=0.80): {100*captured(0.80,ro)/total:5.1f}%")
    axes[0].plot(r, kern / kern.max(), label=f"h={h} mm")
    cum = np.cumsum(kern) / np.sum(kern)
    axes[1].plot(r, 100 * cum, label=f"h={h} mm")

for ax, lbl in zip(axes, ["coupling density (norm.)", "cumulative coupling [%]"]):
    ax.axvspan(R_IN_NOW, R_OUT_NOW, color="#2ca02c", alpha=0.15,
               label="electrode annulus")
    ax.axvline(R_DISK, color="k", ls="--", lw=0.8, label="rotor edge")
    ax.set_xlabel("r (mm)")
    ax.set_ylabel(lbl)
    ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig("coupling_vs_radius.png", dpi=170)
print("\nwrote coupling_vs_radius.png")
