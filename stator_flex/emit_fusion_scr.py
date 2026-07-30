"""Emit flexG_fusion.scr: an Eagle/Fusion-Electronics command script that
builds the rev G board as REAL PCB objects (net-named polygons, plated vias,
NPTH mount holes, board outline, bottom copper restrict, coverlay openings).

Run in Fusion: New Electronics Design -> New PCB, then File > Run Script
(or type SCRIPT in the command box) and select this file.  Grid is mm.

Reuses the geometry by importing generate_flex_revG (which regenerates the
DXFs as a side effect — harmless).
"""

import numpy as np
import generate_flex_revG as g

# Fusion Electronics layer NAMES (equivalent to Eagle 1/16/20/29/30)
L_TOP, L_BOT = "Top", "Bottom"
L_DIM = "BoardOutline"
L_TSTOP, L_BSTOP = "SolderMaskTop", "SolderMaskBottom"
POLY_W = 0.08      # polygon outline width (>= DRC min width)
lines = ["GRID MM 1 ON;"]


def fmt(p):
    return f"({p[0]:.4f} {p[1]:.4f})"


def polygon(net, pts, layer, w=POLY_W):
    pts = list(pts)
    if np.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) > 1e-6:
        pts.append(pts[0])
    lines.append(f"LAYER {layer};")
    lines.append(f"POLYGON '{net}' {w} " + " ".join(fmt(p) for p in pts) + ";")


def wire(net, pts, width, layer):
    lines.append(f"LAYER {layer};")
    lines.append(f"WIRE '{net}' {width} " + " ".join(fmt(p) for p in pts) + ";")


def via(net, x, y, drill=0.15, dia=0.35):
    lines.append(f"CHANGE DRILL {drill};")
    lines.append(f"VIA '{net}' {dia} round ({x:.4f} {y:.4f});")


def circle_pts(r, c=(0, 0), n=64):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return [(c[0] + r * np.cos(t), c[1] + r * np.sin(t)) for t in a]


# board outline (Dimension) and bottom copper restrict over the magnet zone
lines.append(f"LAYER {L_DIM};")
lines.append(f"CIRCLE 0 (0 0) ({g.R_BOARD:.3f} 0);")

# top copper: sectors, tabs, CTR, pads
for p, net in g.sec_polys:
    polygon(net, p, L_TOP)
for k, c in enumerate(g.SEC_CTR):   # tabs as WIRES: endpoint on via = bonded
    wire(g.NET[k], [g.pol(g.R_OUT - 0.10, c), g.pol(g.VIA_RP[g.NET[k]], c)],
         0.15, L_TOP)
for p in g.ctr_polys:
    polygon("CTR", p, L_TOP)
for net, az in g.PAD_AZ.items():
    polygon(net, circle_pts(g.PAD_D / 2, c=g.pol(g.PAD_R, az)), L_TOP)

# bottom copper: GND contact ring, bus arcs, taps + escapes as wires
rmid = (g.GNDRING_R0 + g.GNDRING_R1) / 2
az = np.linspace(0, 360, 180)
wire("GND", [g.pol(rmid, t) for t in az], g.GNDRING_R1 - g.GNDRING_R0, L_BOT)
for net in g.PHASE:                      # bus arcs as WIRES: copper without pour
    a0, a1 = g.ARC_SPAN[net]
    a1 = a1 + 360 * (a1 < a0)
    az = np.linspace(a0, a1, 240)
    wire(net, [g.pol(g.BUS_R[net], t) for t in az], g.BUS_W, L_BOT)
for path, net in g.bot_lines:
    w = 0.15 if len(path) == 2 else g.TRACE_W
    wire(net, path, w, L_BOT)

# vias: sector (staggered radii), GND stitching, pad clusters
for k, c in enumerate(g.SEC_CTR):
    x, y = g.pol(g.VIA_RP[g.NET[k]], c)
    via(g.NET[k], x, y)
for az in g.GND_VIA_AZ:
    x, y = g.pol(g.GND_VIA_R, az)
    via("GND", x, y)
    wire("GND", [g.pol(rmid, az), (x, y)], 0.2, L_BOT)
    wire("GND", [(x, y), g.pol(10.8, 60.0)], 0.25, L_TOP) if az == 30 else None
for net, p_az in g.PAD_AZ.items():
    if net == "CTR":
        continue           # CTR arrives on top; no bottom trace
    x, y = g.pol(g.PAD_R, p_az)
    for d, azd in [(0.9, 0), (0.9, 120), (0.9, 240)]:
        vx = x + d * np.cos(np.radians(azd))
        vy = y + d * np.sin(np.radians(azd))
        via(net, vx, vy)
        wire(net, [(x, y), (vx, vy)], 0.25, L_BOT)

# NPTH 4-40 mount holes through the pads
lines.append(f"CHANGE DRILL {g.HOLE_D};")
for net, az in g.PAD_AZ.items():
    x, y = g.pol(g.PAD_R, az)
    lines.append(f"HOLE ({x:.4f} {y:.4f});")

# coverlay (stop) openings: top active area, top pads, bottom contact ring
lines.append(f"LAYER {L_TSTOP};")
lines.append("CIRCLE 0 (0 0) (6.2 0);")
for net, az in g.PAD_AZ.items():
    x, y = g.pol(g.PAD_R, az)
    lines.append(f"CIRCLE 0 ({x:.4f} {y:.4f}) ({x + 3.6:.4f} {y:.4f});")
# optional external-GND pads: bare-ENIG spots on the top pour, az 60/240
lines.append("CHANGE RANK 1;")
for az in (60.0, 240.0):
    polygon("GND", circle_pts(1.7, c=g.pol(10.8, az)), L_TOP)
    x, y = g.pol(10.8, az)
    lines.append(f"LAYER {L_TSTOP};")
    lines.append(f"CIRCLE 0 ({x:.4f} {y:.4f}) ({x + 1.6:.4f} {y:.4f});")
lines.append(f"LAYER {L_BSTOP};")
rm = (g.GNDRING_R0 + g.GNDRING_R1) / 2
lines.append(f"CIRCLE {g.GNDRING_R1 - g.GNDRING_R0 + 0.2:.3f} (0 0) ({rm:.4f} 0);")

polygon("GND", circle_pts(g.R_BOARD - 0.30, n=90), L_TOP)
polygon("GND", circle_pts(g.R_BOARD - 0.30, n=90), L_BOT)
lines.append("RATSNEST;")   # must be the LAST command
lines.append(f"LAYER {L_TOP};")
open("flexG_fusion.scr", "w").write("\n".join(lines) + "\n")
n_poly = sum(1 for l in lines if l.startswith("POLYGON"))
n_via = sum(1 for l in lines if l.startswith("VIA"))
n_wire = sum(1 for l in lines if l.startswith("WIRE"))
print(f"flexG_fusion.scr: {n_poly} polygons, {n_wire} wires, {n_via} vias, "
      f"{len(g.PAD_AZ)} NPTH holes, {len(lines)} commands")
