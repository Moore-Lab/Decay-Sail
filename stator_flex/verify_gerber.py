"""Independent check: parse the emitted Gerber/Excellon files and render them.

Deliberately does NOT import the geometry generator — it only reads the files
that will be sent to the fab, so the rendering verifies the shipped package.
"""

import re
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly

CO = re.compile(r"X(-?\d+)Y(-?\d+)D0([12])")


def parse_gerber(path):
    """Return list of (points, polarity) regions plus stroked path points."""
    regions, strokes = [], []
    pol_dark = True
    cur, inreg, curstroke = [], False, []
    for line in open(path):
        line = line.strip()
        if line.startswith("%LPD"):
            pol_dark = True
        elif line.startswith("%LPC"):
            pol_dark = False
        elif line == "G36*":
            inreg, cur = True, []
        elif line == "G37*":
            if len(cur) > 2:
                regions.append((np.array(cur), pol_dark))
            inreg = False
        else:
            m = CO.search(line)
            if m:
                x, y, d = int(m.group(1)) / 1e6, int(m.group(2)) / 1e6, m.group(3)
                if inreg:
                    cur.append((x, y))
                else:
                    if d == "2":
                        if len(curstroke) > 1:
                            strokes.append(np.array(curstroke))
                        curstroke = [(x, y)]
                    else:
                        curstroke.append((x, y))
    if len(curstroke) > 1:
        strokes.append(np.array(curstroke))
    return regions, strokes


def parse_drill(path):
    pts, tools, cur = [], {}, None
    for line in open(path):
        line = line.strip()
        m = re.match(r"T(\d+)C([\d.]+)", line)
        if m:
            tools[m.group(1)] = float(m.group(2))
            continue
        m = re.match(r"T(\d+)$", line)
        if m and m.group(1) != "0":
            cur = tools.get(m.group(1))
            continue
        m = re.match(r"X(-?\d+)Y(-?\d+)", line)
        if m and cur:
            pts.append((int(m.group(1)) / 1000, int(m.group(2)) / 1000, cur))
    return pts



from matplotlib.path import Path as MPath


def raster(path_gbr, ext, n=900, c=(0, 0)):
    """True painter's-algorithm raster of a Gerber - what the fab CAM sees."""
    xs = np.linspace(c[0] - ext, c[0] + ext, n)
    ys = np.linspace(c[1] - ext, c[1] + ext, n)
    X, Y = np.meshgrid(xs, ys)
    P = np.column_stack([X.ravel(), Y.ravel()])
    cu = np.zeros(len(P), bool)
    for pts, dark in parse_gerber(path_gbr)[0]:
        m = MPath(pts).contains_points(P)
        cu[m] = dark
    return cu.reshape(n, n), (c[0]-ext, c[0]+ext, c[1]-ext, c[1]+ext)


from matplotlib.colors import ListedColormap
CU = ListedColormap([(0.97, 0.95, 0.91, 1), (0.72, 0.45, 0.20, 1)])
CUB = ListedColormap([(0.97, 0.95, 0.91, 1), (0.54, 0.42, 0.23, 1)])

fig, axes = plt.subplots(1, 4, figsize=(21, 5.6))
for ax in axes:
    ax.set_aspect("equal")
    ax.set_xlabel("mm")

img, extent = raster("flexG-F_Cu.gbr", 13.0)
axes[0].imshow(img, extent=extent, origin="lower", cmap=CU, interpolation="nearest")
axes[0].set_title("TOP copper (F_Cu) - rasterized from file", fontsize=10)
img, extent = raster("flexG-B_Cu.gbr", 13.0)
axes[1].imshow(img, extent=extent, origin="lower", cmap=CUB, interpolation="nearest")
axes[1].set_title("BOTTOM copper (B_Cu), viewed from top", fontsize=10)
for x, y, d in parse_drill("flexG-PTH.drl"):
    for ax in axes[:2]:
        ax.add_patch(plt.Circle((x, y), d / 2, fc="w", ec="k", lw=0.3, zorder=5))


ax = axes[2]
for pth, c, lbl in [("flexG-F_Mask.gbr", "#2ca02c", "F_Mask openings"),
                    ("flexG-B_Mask.gbr", "#1f77b4", "B_Mask openings")]:
    for i, (pts, dark) in enumerate(parse_gerber(pth)[0]):
        ax.add_patch(MplPoly(pts, closed=True, fc=c if dark else "w", ec="none",
                             alpha=0.45, zorder=1 + i * 0.001))
    ax.plot([], [], "s", color=c, label=lbl)
for st in parse_gerber("flexG-Edge_Cuts.gbr")[1]:
    ax.plot(st[:, 0], st[:, 1], "k-", lw=1.2, zorder=40)
ax.legend(fontsize=8, loc="lower center")
ax.set_title("Coverlay openings + Edge_Cuts", fontsize=10)

img, extent = raster("flexG-F_Cu.gbr", 2.6)
axes[3].imshow(img, extent=extent, origin="lower", cmap=CU, interpolation="nearest")
th_ = np.linspace(0, 2 * np.pi, 300)
axes[3].plot(1.75 * np.cos(th_), 1.75 * np.sin(th_), "k--", lw=1.0)
axes[3].set_title("ZOOM active area: 24 sectors + CTR\n(beige = bare polyimide)",
                  fontsize=10)
for ax in axes[:3]:
    ax.set_xlim(-13.2, 13.2)
    ax.set_ylim(-13.2, 13.2)
axes[3].set_xlim(-2.6, 2.6)
axes[3].set_ylim(-2.6, 2.6)
fig.tight_layout()
fig.savefig("flexG_gerber_check.png", dpi=170)

pth = parse_drill("flexG-PTH.drl")
print(f"plated holes: {len(pth)} @ {sorted(set(round(p[2],3) for p in pth))} mm")
for x, y, d in [p for p in pth if p[2] > 1]:
    print(f"  mount hole r={np.hypot(x,y):.3f} az={np.degrees(np.arctan2(y,x))%360:6.1f}")
print("wrote flexG_gerber_check.png")
