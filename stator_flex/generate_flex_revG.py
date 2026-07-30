"""Rev G: rev F + center charge-drive electrode on the 4th post, compliant
with the PCBWay flex rules (design_rules.pdf): min track/space 0.08/0.08,
min via drill/pad 0.15/0.35, 0.1 mm 2-layer PI stack, 18 um Cu, ENIG,
coverlay with openings.

Key routing (all clearances >= 0.08, live bottom copper outside r=4.0):
- CTR: center disk r=0.60 -> TOP trace (0.08 wide, 0.08 clearance) through a
  widened sector boundary at az 285 -> pad @285.  Flanking sectors 18/19 are
  clipped to r>=0.95 there so no copper sliver is narrower than 0.08.
- Sector connections: top tabs run radially to STAGGERED via radii per phase
  (A 4.25, B 4.895, C 5.585) so each phase's via lands between/beyond the
  inner bus rings without bottom-layer crossings.  Bus rings A/B/C at
  r = 4.55 / 5.24 / 5.93 (0.18 wide, 0.69 pitch: via pad + 2x0.08 fits
  between rings).  Escapes at az 7.5 (A), 36.5 (B), 352.5 (C) through the
  ring windows; lanes at r = 7.0 thread BETWEEN pad footprints; radial rises
  at the pad azimuths to 3-via clusters under the pads.
- GND: exposed bottom ENIG contact ring (r 2.95-3.40, coverlay opening)
  pressed on the grounded magnet; 8 stitching vias at r=3.2 up to top pour.
  Center shim (if used) must be <= Ø5.8 to not lift the contact ring.

Outputs: flexG_top_copper.dxf, flexG_bottom_copper.dxf, flexG_outline.dxf,
flexG_preview.png/pdf.
"""

import numpy as np
import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly, Circle as MplCirc

# ---------------- parameters (mm, deg) ----------------
M, N_SEC, GAP = 8, 24, 0.10
R_IN, R_OUT = 0.69, 1.95   # inner edge set by 0.08 min Cu; outer clears rotor
R_CTR, CTR_AZ = 0.58, 285.0
CTR_W_FINE, CTR_W = 0.08, 0.25       # PCBWay min track 0.08
EXTRA_PULL = 0.095                   # channel: 0.08 trace + >=0.09 each side
R_IN_CLIP = 1.12                     # flanking sectors: keeps their Cu >= 0.08
R_POUR0, R_BOARD, KEEPOUT_R = 2.00, 12.70, 4.00
TAB_W = 0.15
VIA_DRILL, VIA_PAD = 0.15, 0.35      # PCBWay minimum
VIA_RP = {"A": 4.27, "B": 4.96, "C": 5.66}    # staggered per phase (margin to inner rings)
BUS_R = {"A": 4.55, "B": 5.24, "C": 5.93}
BUS_W = 0.18
LANE_R, TRACE_W = 7.00, 0.25
PAD_R, PAD_D, HOLE_D = 9.0, 6.5, 3.0
PAD_AZ = {"A": 15.0, "B": 105.0, "C": 195.0, "CTR": 285.0}
ESC_AZ = {"A": 7.5, "B": 36.5, "C": 352.5}     # all inside outer-ring windows
ARC_SPAN = {"A": (7.5, 322.5), "B": (22.5, 337.5), "C": (37.5, 352.5)}
GNDRING_R0, GNDRING_R1, GND_VIA_R = 2.95, 3.40, 3.20
GND_VIA_AZ = [30, 75, 120, 165, 210, 255, 315, 345]

SEC_CTR = [7.5 + 15 * k for k in range(N_SEC)]
PHASE = ["A", "B", "C"]
NET = [PHASE[k % 3] for k in range(N_SEC)]
COLN = {"A": "#d62728", "B": "#2ca02c", "C": "#1f77b4", "CTR": "#7f7f7f",
        "GND": "0.55"}


def annsec(r0, r1, a_lo, a_hi, gap, n=24, pull_lo=0.0, pull_hi=0.0):
    pts = []
    for r, rng, rev in [(r0, (a_lo, a_hi), False), (r1, (a_hi, a_lo), True)]:
        dlo = np.degrees((gap / 2 + pull_lo) / r)
        dhi = np.degrees((gap / 2 + pull_hi) / r)
        if not rev:
            a = np.linspace(rng[0] + dlo, rng[1] - dhi, n)
        else:
            a = np.linspace(rng[0] - dhi, rng[1] + dlo, n)
        pts += [(r * np.cos(np.radians(t)), r * np.sin(np.radians(t))) for t in a]
    return pts


def pol(r, az):
    return (r * np.cos(np.radians(az)), r * np.sin(np.radians(az)))


def radial_trace(az, r0, r1, w):
    a = np.radians(az)
    u = np.array([np.cos(a), np.sin(a)])
    v = np.array([-u[1], u[0]]) * w / 2
    return [tuple(r0 * u + v), tuple(r1 * u + v), tuple(r1 * u - v), tuple(r0 * u - v)]


def circle(r, n=180, c=(0, 0)):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return [(c[0] + r * np.cos(t), c[1] + r * np.sin(t)) for t in a]


class DXF:
    def __init__(self):
        self.e = []

    def poly(self, pts, layer, closed=True):
        s = [f"0\nPOLYLINE\n8\n{layer}\n66\n1\n70\n{1 if closed else 0}\n"]
        for x, y in pts:
            s.append(f"0\nVERTEX\n8\n{layer}\n10\n{x:.4f}\n20\n{y:.4f}\n")
        s.append("0\nSEQEND\n")
        self.e.append("".join(s))

    def circ(self, cx, cy, r, layer):
        self.e.append(f"0\nCIRCLE\n8\n{layer}\n10\n{cx:.4f}\n20\n{cy:.4f}\n40\n{r:.4f}\n")

    def save(self, path):
        with open(path, "w") as f:
            f.write("0\nSECTION\n2\nENTITIES\n" + "".join(self.e) + "0\nENDSEC\n0\nEOF\n")



def path_solid(dxf, path, w, layer):
    """Emit an open path as per-segment rectangles + joint circles so CAD
    tools (Fusion) can extrude it as a solid trace of width w."""
    path = [np.array(p) for p in path]
    for p0, p1 in zip(path[:-1], path[1:]):
        d = p1 - p0
        L = np.hypot(*d)
        if L < 1e-6:
            continue
        u = d / L
        v = np.array([-u[1], u[0]]) * w / 2
        dxf.poly([tuple(p0 + v), tuple(p1 + v), tuple(p1 - v), tuple(p0 - v)],
                 layer)
    for p in path[1:-1]:
        dxf.circ(p[0], p[1], w / 2, layer)


# ---------------- top copper ----------------
top = DXF()
sec_polys, tab_polys = [], []
for k, c in enumerate(SEC_CTR):
    pull_lo = EXTRA_PULL if k == 19 else 0.0
    pull_hi = EXTRA_PULL if k == 18 else 0.0
    r0 = R_IN_CLIP if k in (18, 19) else R_IN
    p = annsec(r0, R_OUT, c - 7.5, c + 7.5, GAP, pull_lo=pull_lo, pull_hi=pull_hi)
    sec_polys.append((p, NET[k]))
    top.poly(p, f"CU_TOP_SEC_{NET[k]}")
    rv = VIA_RP[NET[k]]
    t = radial_trace(c, R_OUT - 0.05, rv + VIA_PAD / 2, TAB_W)
    tab_polys.append((t, NET[k]))
    top.poly(t, f"CU_TOP_TAB_{NET[k]}")
    x, y = pol(rv, c)
    top.circ(x, y, VIA_PAD / 2, "VIA_PAD")
    top.circ(x, y, VIA_DRILL / 2, "DRILL_VIA")
ctr_polys = [circle(R_CTR),
             radial_trace(CTR_AZ, R_CTR - 0.05, 2.55, CTR_W_FINE),
             radial_trace(CTR_AZ, 2.50, PAD_R, CTR_W)]
for p in ctr_polys:
    top.poly(p, "CU_TOP_CTR")
top.poly(circle(R_POUR0), "CU_TOP_POUR_INNER_EDGE")
for net, az in PAD_AZ.items():
    top.poly(circle(PAD_D / 2, c=pol(PAD_R, az)), f"CU_TOP_PAD_{net}")
for az in GND_VIA_AZ:
    x, y = pol(GND_VIA_R, az)
    top.circ(x, y, VIA_PAD / 2, "VIA_PAD_GND")
    top.circ(x, y, VIA_DRILL / 2, "DRILL_VIA")
for az_g in (60.0, 240.0):
    top.poly(circle(1.7, c=pol(10.8, az_g)), "CU_TOP_GNDPAD_OPT")
top.poly(circle(R_BOARD, n=256), "REF_OUTLINE_DELETE_AFTER_IMPORT")
top.save("flexG_top_copper.dxf")

# ---------------- bottom copper ----------------
bot = DXF()
bot.poly(circle(KEEPOUT_R), "BOT_KEEPOUT_LIVE_NETS")
ring = annsec(GNDRING_R0, GNDRING_R1, 0, 360, 0, n=240)
bot.poly(ring, "CU_BOT_GND_CONTACT_RING_BARE_ENIG")
bot_polys, bot_lines = [(ring, "GND")], []
for net in PHASE:
    r = BUS_R[net]
    a0, a1 = ARC_SPAN[net]
    p = annsec(r - BUS_W / 2, r + BUS_W / 2, a0, a1 + 360 * (a1 < a0), 0, n=240)
    bot_polys.append((p, net))
    bot.poly(p, f"CU_BOT_BUS_{net}")
for k, c in enumerate(SEC_CTR):     # short radial tap: staggered via -> own ring
    ln = [pol(VIA_RP[NET[k]], c), pol(BUS_R[NET[k]], c)]
    bot_lines.append((ln, NET[k]))
    path_solid(bot, ln, 0.15, f"CU_BOT_TAP_{NET[k]}")
for net in PHASE:                   # escape -> lane at 7.0 -> rise at pad az
    e_az, p_az = ESC_AZ[net], PAD_AZ[net]
    path = [pol(BUS_R[net], e_az), pol(LANE_R, e_az)]
    sweep = np.linspace(e_az, p_az if net != "C" else p_az, 80)
    path += [pol(LANE_R, t) for t in sweep] + [pol(PAD_R, p_az)]
    bot_lines.append((path, net))
    path_solid(bot, path, TRACE_W, f"CU_BOT_ESC_{net}")
    x, y = pol(PAD_R, p_az)
    for d, azd in [(0.9, 0), (0.9, 120), (0.9, 240)]:
        vx, vy = x + d * np.cos(np.radians(azd)), y + d * np.sin(np.radians(azd))
        bot.circ(vx, vy, VIA_PAD / 2, "VIA_PAD")
        bot.circ(vx, vy, VIA_DRILL / 2, "DRILL_VIA")
bot.poly(circle(R_BOARD - 0.3), "CU_BOT_POUR_EDGE")
bot.poly(circle(R_BOARD, n=256), "REF_OUTLINE_DELETE_AFTER_IMPORT")
bot.save("flexG_bottom_copper.dxf")

out = DXF()
out.poly(circle(R_BOARD, n=256), "OUTLINE")
for net, az in PAD_AZ.items():
    x, y = pol(PAD_R, az)
    out.circ(x, y, HOLE_D / 2, "DRILL_MOUNT_4-40")
out.save("flexG_outline.dxf")

# ---------------- design-rule self-check ----------------
print("DRC vs PCBWay flex rules (0.08/0.08, via 0.15/0.35):")
w_in = np.radians(15) * R_IN - GAP
w_clip = np.radians(15) * R_IN_CLIP - GAP - EXTRA_PULL
ring_gap = BUS_R["B"] - BUS_R["A"] - BUS_W
viaB_clear = (VIA_RP["B"] - VIA_PAD / 2) - (BUS_R["A"] + BUS_W / 2)
viaC_clear = (VIA_RP["C"] - VIA_PAD / 2) - (BUS_R["B"] + BUS_W / 2)
lane_clear = (LANE_R - TRACE_W / 2) - (BUS_R["C"] + BUS_W / 2)
checks = [
    ("sector Cu width @ r_in", w_in),
    ("clipped sector width @ 0.95 (channel side)", w_clip),
    ("sector-sector gap", GAP),
    ("CTR trace / clearance", CTR_W_FINE),
    ("bus ring gap", ring_gap),
    ("B via pad to A ring", viaB_clear),
    ("C via pad to B ring", viaC_clear),
    ("lane to C ring", lane_clear),
    ("keepout to A via pad", VIA_RP["A"] - VIA_PAD / 2 - KEEPOUT_R),
]
for name, v in checks:
    print(f"  {name:44s} {v:6.3f} mm  {'OK' if v >= 0.079 else 'FAIL'}")

A1SQ, I_TOT = 0.438, 1.88e-11
for label, tau_raw in [("no shim, h~0.37", 3.37e-12), ("shim<=Ø5.8, h~0.27", 9.81e-12)]:
    tau = tau_raw * A1SQ * 4
    print(f"{label} mm, 200 V: tau ~ {tau:.1e} N m, "
          f"0->10 Hz {2*np.pi*10/(0.5*tau/I_TOT)/60:.1f} min")
eps0, h, a = 8.854e-12, 0.31e-3, 0.60e-3
Ez = 10.0 / h * (1 - h / np.sqrt(h**2 + a**2))
kz = 9.89e-6 * (2 * np.pi * 15.0) ** 2
print(f"CTR charge drive, 10 V: E_z ~ {Ez:.2e} V/m; F/e = {Ez*1.602e-19:.1e} N; "
      f"z per e (off-res, f_z=15 Hz) = {Ez*1.602e-19/kz*1e12:.2f} pm (xQ on res)")

# ---------------- preview ----------------
plate = ezdxf.readfile("mounting_plate_sketch.dxf")
plate_circ = [(e.dxf.center.x, e.dxf.center.y, e.dxf.radius)
              for e in plate.modelspace() if e.dxftype() == "CIRCLE"]
fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13.5, 6.8))
for a_ in (ax, ax2):
    a_.set_aspect("equal")
    a_.set_xlabel("mm")
ax.set_title("Rev G: CTR charge electrode to pad 4; staggered vias; GND magnet ring")
ax.add_patch(plt.Circle((0, 0), R_BOARD, fc="0.93", ec="k", lw=0.8, zorder=0))
for p, net in sec_polys + tab_polys:
    ax.add_patch(MplPoly(p, closed=True, fc=COLN[net], ec="k", lw=0.15, zorder=2))
for p in ctr_polys:
    ax.add_patch(MplPoly(p, closed=True, fc=COLN["CTR"], ec="k", lw=0.2, zorder=2.5))
for p, net in bot_polys:
    ax.add_patch(MplPoly(p, closed=True, fc=COLN[net], ec="none", alpha=0.35, zorder=3))
for ln, net in bot_lines:
    xs, ys = zip(*ln)
    ax.plot(xs, ys, color=COLN[net], lw=1.5, alpha=0.4, zorder=3)
for net, az in PAD_AZ.items():
    x, y = pol(PAD_R, az)
    ax.add_patch(MplCirc((x, y), PAD_D / 2, fc="#c9a227", ec="k", lw=0.6, zorder=4))
    ax.add_patch(MplCirc((x, y), HOLE_D / 2, fc="w", ec="k", lw=0.6, zorder=5))
    ax.annotate(net, pol(PAD_R + 4.2, az), ha="center", va="center", fontsize=9)
th = np.linspace(0, 2 * np.pi, 100)
ax.plot(1.75 * np.cos(th), 1.75 * np.sin(th), "k--", lw=0.9, zorder=6)
ax.plot(3.5 * np.cos(th), 3.5 * np.sin(th), "k:", lw=0.9, zorder=6)
ax.text(0, -13.9, "gray bottom ring 2.95-3.40 = GND contact to magnet (bare ENIG)",
        ha="center", fontsize=8)
ax.set_xlim(-14.5, 14.5)
ax.set_ylim(-15.2, 14.5)
ax2.set_title("Fit on PEEK plate")
ax2.add_patch(plt.Circle((0, 0), 19.05, fc="0.95", ec="k", lw=1.0, zorder=0))
for x, y, r in plate_circ:
    if abs(r - 19.05) > 1e-6:
        ax2.add_patch(MplCirc((x, y), r, fc="w", ec="0.4", lw=0.8, zorder=1))
ax2.add_patch(plt.Circle((0, 0), R_BOARD, fc="#f2e2b8", ec="k", lw=1.0,
                         alpha=0.85, zorder=2))
for net, az in PAD_AZ.items():
    x, y = pol(PAD_R, az)
    ax2.add_patch(MplCirc((x, y), PAD_D / 2, fc="#c9a227", ec="k", lw=0.5, zorder=3))
    ax2.add_patch(MplCirc((x, y), HOLE_D / 2, fc="w", ec="k", lw=0.5, zorder=4))
ax2.set_xlim(-21, 21)
ax2.set_ylim(-21, 21)
fig.tight_layout()
fig.savefig("flexG_preview.png", dpi=180)
fig.savefig("flexG_preview.pdf")
print("wrote flexG_top_copper.dxf, flexG_bottom_copper.dxf, flexG_outline.dxf, preview")
