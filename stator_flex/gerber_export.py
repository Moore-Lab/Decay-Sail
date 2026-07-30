"""Direct Gerber + Excellon export for the rev G flex board.

No EDA tool in the loop: the same parametric geometry that produced the DXFs
is turned into RS-274X Gerbers and an Excellon drill file, with real boolean
ground pours (shapely).  verify_gerber.py reads these files back and renders
them, so what we ship is what we checked.

Outputs (fab package, zip and send to PCBWay):
  flexG-F_Cu.gbr      top copper
  flexG-B_Cu.gbr      bottom copper
  flexG-F_Mask.gbr    top coverlay OPENINGS (bare ENIG)
  flexG-B_Mask.gbr    bottom coverlay OPENINGS
  flexG-Edge_Cuts.gbr board outline
  flexG-PTH.drl       all holes, plated: 41 vias (0.15) + 4 mount holes (3.0)
"""

import numpy as np
from shapely.geometry import Polygon, Point, LineString, MultiPolygon
from shapely.ops import unary_union

import generate_flex_revG as g

CLR = 0.10          # ground-pour clearance to live copper (rule min 0.08)
BOT_PAD_D = 4.00    # bottom pad: small annular ring (0.5 around the 3.0 hole)
LANE_R = 6.45       # escape lane radius: INSIDE the bottom pads (inner edge 7.0)
# A (inner ring) and C (outer ring) need no wrap: at A's pad azimuth (15 deg)
# both B and C are in their windows, and C is the outermost ring so nothing
# blocks it going outward.  Only B (middle) must exit through C's window and
# wrap around on the lane.
ESC = {"A": 15.0, "B": 29.0, "C": 195.0}
WRAP = {"A": False, "B": True, "C": False}
ANN = 0.10          # via annular ring
R_BOARD = g.R_BOARD


def pol(r, az):
    return (r * np.cos(np.radians(az)), r * np.sin(np.radians(az)))


def arc_pts(r, a0, a1, n=240):
    a1 = a1 + 360 * (a1 < a0)
    return [pol(r, t) for t in np.linspace(a0, a1, n)]


def disk(r, c=(0, 0)):
    return Point(c).buffer(r, quad_segs=64)


# ---------------- TOP copper ----------------
live_top = []
for p, net in g.sec_polys:
    live_top.append(Polygon(p))
for k, c in enumerate(g.SEC_CTR):                      # tabs
    live_top.append(LineString([pol(g.R_OUT - 0.10, c),
                                pol(g.VIA_RP[g.NET[k]], c)]).buffer(0.075, quad_segs=16))
live_top.append(disk(g.R_CTR))                         # CTR electrode
live_top.append(LineString([pol(g.R_CTR - 0.05, g.CTR_AZ),
                            pol(2.10, g.CTR_AZ)]).buffer(0.04, quad_segs=16))
live_top.append(LineString([pol(2.05, g.CTR_AZ),
                            pol(g.PAD_R, g.CTR_AZ)]).buffer(0.125, quad_segs=16))
for net, az in g.PAD_AZ.items():                       # 4 terminal pads
    live_top.append(disk(g.PAD_D / 2, pol(g.PAD_R, az)))
for k, c in enumerate(g.SEC_CTR):                      # via lands
    live_top.append(disk(g.VIA_PAD / 2, pol(g.VIA_RP[g.NET[k]], c)))
live_top_u = unary_union(live_top)

# top GND: guard + pour OUTSIDE r = R_POUR0 only.  No ground between sectors:
# grounded copper in the active area would screen the drive field and cut torque.
PAD_KEEP = 4.75       # TOP: clears screw head / washer / ring tongue
PAD_KEEP_BOT = 2.20   # BOTTOM: only clears the bottom pad (nothing clamps here),
                      # so the bottom ground stays ONE continuous sheet
# stitching vias: one per inter-tab gap (guard wedges) + one per outer arc
STITCH_IN = [(3.15, a) for a in range(0, 360, 15) if a != int(g.CTR_AZ)]
STITCH_OUT = [(11.0, a) for a in (60, 150, 240, 330)]
STITCH = STITCH_IN + STITCH_OUT

gnd_top = [disk(R_BOARD - 0.30).difference(disk(g.R_POUR0))]
for _az in g.PAD_AZ.values():
    gnd_top[0] = gnd_top[0].difference(disk(PAD_KEEP, pol(g.PAD_R, _az)))
for _r, _a in STITCH:
    gnd_top.append(disk(g.VIA_PAD / 2, pol(_r, _a)))
for az in (60.0, 240.0):                               # optional GND pads
    gnd_top.append(disk(1.7, pol(10.8, az)))

gnd_top_u = unary_union(gnd_top).difference(live_top_u.buffer(CLR))


def keep_connected(geom, feed_pts):
    """Delete ground fragments that contain no stitching via: unconnectable
    copper would float at an uncontrolled potential."""
    from shapely.geometry import Point as _P
    parts = ([geom] if isinstance(geom, Polygon) else
             list(geom.geoms) if isinstance(geom, MultiPolygon) else [])
    keep, drop = [], 0.0
    for c in parts:
        if any(c.intersects(_P(p)) for p in feed_pts):
            keep.append(c)
        else:
            drop += c.area
    if drop > 1e-9:
        print(f"  dropped {drop:.3f} mm^2 of unconnectable ground copper")
    return unary_union(keep)


_feed = [pol(r_, a_) for r_, a_ in STITCH]
gnd_top_u = keep_connected(gnd_top_u, _feed)
top_cu = [gnd_top_u, live_top_u]      # ORDER MATTERS: pour, then islands

# ---------------- BOTTOM copper ----------------
live_bot = []
rmid = (g.GNDRING_R0 + g.GNDRING_R1) / 2
for net in g.PHASE:                                    # bus arcs
    a0, a1 = g.ARC_SPAN[net]
    live_bot.append(LineString(arc_pts(g.BUS_R[net], a0, a1)).buffer(g.BUS_W / 2,
                                                                     quad_segs=32))
for k, c in enumerate(g.SEC_CTR):                      # taps
    live_bot.append(LineString([pol(g.VIA_RP[g.NET[k]], c),
                                pol(g.BUS_R[g.NET[k]], c)]).buffer(0.075, quad_segs=32))
def escape_path(net):
    e_az, p_az = ESC[net], g.PAD_AZ[net]
    if not WRAP[net]:                                  # straight radial run
        return [pol(g.BUS_R[net], e_az), pol(g.PAD_R, p_az)]
    sweep = np.linspace(e_az, p_az, 160)
    return ([pol(g.BUS_R[net], e_az), pol(LANE_R, e_az)] +
            [pol(LANE_R, t) for t in sweep] + [pol(g.PAD_R, p_az)])


for net in g.PHASE:                                    # escapes
    live_bot.append(LineString(escape_path(net)).buffer(g.TRACE_W / 2, quad_segs=32))
    live_bot.append(disk(BOT_PAD_D / 2, pol(g.PAD_R, g.PAD_AZ[net])))
for k, c in enumerate(g.SEC_CTR):
    live_bot.append(disk(g.VIA_PAD / 2, pol(g.VIA_RP[g.NET[k]], c)))
live_bot_u = unary_union(live_bot)

# bottom GND: full pour (the grounded magnet is pressed against it anyway) plus
# the contact ring; keeps sector-to-ground capacitance defined and shields traces
ring = disk(g.GNDRING_R1).difference(disk(g.GNDRING_R0))
# no ground inside the bus-ring band: the via lands chop it into unconnectable
# slivers, and ground between the phase rings buys nothing
BAND0, BAND1 = 4.30, 6.15
gnd_bot = [disk(R_BOARD - 0.30), ring]
gnd_bot[0] = gnd_bot[0].difference(disk(BAND1).difference(disk(BAND0)))
gnd_bot[0] = gnd_bot[0].difference(unary_union(
    [disk(PAD_KEEP_BOT, pol(g.PAD_R, _az)) for _az in g.PAD_AZ.values()]))
for _r, _a in STITCH:
    gnd_bot.append(disk(g.VIA_PAD / 2, pol(_r, _a)))
# radial ground spoke at az 0: the only azimuth where all three bus arcs are in
# their window.  It stitches the inter-ring bands to the central pour and the
# outer pour, so the bottom ground is a single connected sheet.
GND_SPOKE_AZ = 0.0
gnd_bot.append(LineString([pol(3.0, GND_SPOKE_AZ),
                           pol(7.2, GND_SPOKE_AZ)]).buffer(0.15, quad_segs=32))
gnd_bot_u = unary_union(gnd_bot).difference(live_bot_u.buffer(CLR))
gnd_bot_u = keep_connected(gnd_bot_u, _feed + [pol((g.GNDRING_R0+g.GNDRING_R1)/2, 0)])
bot_cu = [gnd_bot_u, live_bot_u]

# CTR terminal: bottom side is GND pour cleared around the screw, plus a
# bottom pad so the ring terminal cannot short CTR to the pour through the screw
ctr_c = pol(g.PAD_R, g.PAD_AZ["CTR"])
bot_cu[0] = bot_cu[0].difference(disk(BOT_PAD_D / 2 + CLR, ctr_c))
bot_cu.append(disk(BOT_PAD_D / 2, ctr_c))

# ---------------- mask (coverlay) openings ----------------
f_mask = [disk(6.2)]                                   # active area, bare ENIG
for net, az in g.PAD_AZ.items():
    f_mask.append(disk(g.PAD_D / 2 + 0.1, pol(g.PAD_R, az)))
for az in (60.0, 240.0):
    f_mask.append(disk(1.8, pol(10.8, az)))
f_mask_u = unary_union(f_mask)
b_mask_u = disk(g.GNDRING_R1 + 0.1).difference(disk(g.GNDRING_R0 - 0.1))
b_mask_u = unary_union([b_mask_u] + [disk(g.PAD_D / 2 + 0.1, pol(g.PAD_R, az))
                                     for az in g.PAD_AZ.values()])

edge = disk(R_BOARD).exterior

# ---------------- Gerber writer ----------------
HDR = ("%FSLAX46Y46*%\n%MOMM*%\n%LPD*%\n%ADD10C,0.050000*%\nD10*\n")


def coord(x, y):
    return f"X{round(x * 1e6):d}Y{round(y * 1e6):d}"


def region(ring_coords):
    s = ["G36*"]
    pts = list(ring_coords)
    s.append(coord(*pts[0]) + "D02*")
    for p in pts[1:]:
        s.append(coord(*p) + "D01*")
    s.append("G37*")
    return "\n".join(s)


def _polys(geom):
    if isinstance(geom, Polygon):
        return [geom] if not geom.is_empty else []
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return []


def geom_to_gerber(geoms, path, name):
    """geoms: ORDERED list, painted back-to-front.  Anything with clear-polarity
    holes must come BEFORE the copper it must not erase (pour first, islands
    last) -- Gerber polarity is a painter's algorithm, same as the fab's CAM."""
    if not isinstance(geoms, (list, tuple)):
        geoms = [geoms]
    out = [f"G04 {name} - flexG rev G*", HDR.rstrip("\n")]
    n = 0
    for geom in geoms:
        for p in _polys(geom):
            n += 1
            out.append("%LPD*%")
            out.append(region(p.exterior.coords))
            for h in p.interiors:
                out.append("%LPC*%")
                out.append(region(h.coords))
    out.append("M02*")
    open(path, "w").write("\n".join(out) + "\n")
    return n


def outline_to_gerber(ring_geom, path):
    out = [f"G04 Edge_Cuts - flexG rev G*",
           "%FSLAX46Y46*%", "%MOMM*%", "%LPD*%", "%ADD10C,0.100000*%", "D10*"]
    pts = list(ring_geom.coords)
    out.append(coord(*pts[0]) + "D02*")
    for p in pts[1:]:
        out.append(coord(*p) + "D01*")
    out.append("M02*")
    open(path, "w").write("\n".join(out) + "\n")


n1 = geom_to_gerber(top_cu, "flexG-F_Cu.gbr", "F.Cu")
n2 = geom_to_gerber(bot_cu, "flexG-B_Cu.gbr", "B.Cu")
n3 = geom_to_gerber(f_mask_u, "flexG-F_Mask.gbr", "F.Mask openings")
n4 = geom_to_gerber(b_mask_u, "flexG-B_Mask.gbr", "B.Mask openings")
outline_to_gerber(edge, "flexG-Edge_Cuts.gbr")

# ---------------- Excellon ----------------
def drill_file(path, tools):
    out = ["M48", "METRIC,TZ", "FILE_FORMAT=3:3"]
    for i, (dia, _) in enumerate(tools, start=1):
        out.append(f"T{i}C{dia:.3f}")
    out.append("%")
    out.append("G90")
    out.append("M71")
    for i, (dia, pts) in enumerate(tools, start=1):
        out.append(f"T{i}")
        for x, y in pts:
            out.append(f"X{round(x*1000):d}Y{round(y*1000):d}")
    out.append("T0")
    out.append("M30")
    open(path, "w").write("\n".join(out) + "\n")


via_pts = [pol(g.VIA_RP[g.NET[k]], c) for k, c in enumerate(g.SEC_CTR)]
via_pts += [pol(r_, a_) for r_, a_ in STITCH]
for net, p_az in g.PAD_AZ.items():
    if net == "CTR":
        continue
    x, y = pol(g.PAD_R, p_az)
    via_pts += [(x + 0.9 * np.cos(np.radians(a)), y + 0.9 * np.sin(np.radians(a)))
                for a in (0, 120, 240)]
mount_pts = [pol(g.PAD_R, az) for az in g.PAD_AZ.values()]
# single plated drill file: 0.15 vias + 3.0 mount holes.  The mount holes are
# PLATED - each already has same-net copper top and bottom (A/B/C via their pad
# via-clusters, CTR via its dedicated bottom pad), so the barrel only parallels
# an existing connection and gives the ring-terminal screw a solid contact.
drill_file("flexG-PTH.drl", [(0.150, via_pts), (3.000, mount_pts)])
import os
if os.path.exists("flexG-NPTH.drl"):
    os.remove("flexG-NPTH.drl")

print(f"F.Cu {n1} polys, B.Cu {n2} polys, F.Mask {n3}, B.Mask {n4}, "
      f"PTH {len(via_pts)} holes, NPTH {len(mount_pts)} holes")
ta = unary_union(top_cu).area
ba = unary_union(bot_cu).area
print(f"top copper area {ta:.2f} mm^2, bottom {ba:.2f} mm^2")
sec_area = sum(Polygon(p).area for p, _ in g.sec_polys)
print(f"sector electrode area in F_Cu: {sec_area:.2f} mm^2 "
      f"(present: {unary_union(top_cu).intersection(unary_union([Polygon(p) for p,_ in g.sec_polys])).area:.2f})")
# sanity: no live-net copper should touch GND pour
active = disk(g.R_POUR0)
intrude = unary_union(top_cu).difference(live_top_u).intersection(active).area
print(f"ground copper inside active area (must be ~0): {intrude:.4f} mm^2")
tu, bu = unary_union(top_cu), unary_union(bot_cu)
for netn, azn in g.PAD_AZ.items():
    c = Point(pol(g.PAD_R, azn))
    ok_t = tu.contains(c.buffer(1.6))
    ok_b = bu.contains(c.buffer(1.6))
    print(f"  mount hole {netn:4s}: copper top {ok_t}, bottom {ok_b} "
          f"-> plating {'OK' if (ok_t and ok_b) else 'CHECK'}")
# largest metal head/washer that can rest on a pad without touching ANOTHER net
others = {}
for netn, azn in g.PAD_AZ.items():
    c = Point(pol(g.PAD_R, azn))
    foreign = [gnd_top_u, gnd_bot_u]          # ground is the nearest other net
    for n2, a2 in g.PAD_AZ.items():
        if n2 != netn:
            foreign.append(disk(g.PAD_D / 2, pol(g.PAD_R, a2)))
    d_min = min(f.distance(c) for f in foreign if not f.is_empty)
    others[netn] = 2 * d_min
    print(f"  {netn:4s}: clear metal head / washer OD up to {2*d_min:.2f} mm")
print(f"  -> use screw heads and washers <= {min(others.values()):.1f} mm OD")
nets_bot = {n: [] for n in list(g.PHASE) + ["CTR"]}
for net in g.PHASE:
    a0, a1 = g.ARC_SPAN[net]
    nets_bot[net].append(LineString(arc_pts(g.BUS_R[net], a0, a1)).buffer(g.BUS_W/2, quad_segs=32))
    nets_bot[net].append(LineString(escape_path(net)).buffer(g.TRACE_W/2, quad_segs=32))
    nets_bot[net].append(disk(BOT_PAD_D/2, pol(g.PAD_R, g.PAD_AZ[net])))
    for kk, cc in enumerate(g.SEC_CTR):
        if g.NET[kk] == net:
            nets_bot[net].append(LineString([pol(g.VIA_RP[net], cc), pol(g.BUS_R[net], cc)]).buffer(0.075, quad_segs=32))
            nets_bot[net].append(disk(g.VIA_PAD/2, pol(g.VIA_RP[net], cc)))
nets_bot["CTR"].append(disk(BOT_PAD_D/2, pol(g.PAD_R, g.PAD_AZ["CTR"])))
nets_bot = {n: unary_union(v) for n, v in nets_bot.items()}
nets_bot["GND"] = gnd_bot_u
print("BOTTOM layer net-to-net clearances (min 0.08):")
names = list(nets_bot)
worst = 9
for i in range(len(names)):
    for j in range(i+1, len(names)):
        d = nets_bot[names[i]].distance(nets_bot[names[j]])
        worst = min(worst, d)
        flag = "OK" if d >= 0.079 else "*** SHORT/VIOLATION ***"
        print(f"  {names[i]:4s} - {names[j]:4s}: {d:6.3f} mm  {flag}")
print(f"worst bottom clearance: {worst:.3f} mm")
# ---- TOP layer per-net clearances ----
nets_top = {n: [] for n in list(g.PHASE) + ["CTR"]}
for kk, cc in enumerate(g.SEC_CTR):
    n = g.NET[kk]
    nets_top[n].append(Polygon(g.sec_polys[kk][0]))
    nets_top[n].append(LineString([pol(g.R_OUT - 0.10, cc),
                                   pol(g.VIA_RP[n], cc)]).buffer(0.075, quad_segs=32))
    nets_top[n].append(disk(g.VIA_PAD / 2, pol(g.VIA_RP[n], cc)))
for n, az_ in g.PAD_AZ.items():
    nets_top[n].append(disk(g.PAD_D / 2, pol(g.PAD_R, az_)))
nets_top["CTR"].append(disk(g.R_CTR))
nets_top["CTR"].append(LineString([pol(g.R_CTR - 0.05, g.CTR_AZ),
                                   pol(2.55, g.CTR_AZ)]).buffer(0.04, quad_segs=32))
nets_top["CTR"].append(LineString([pol(2.50, g.CTR_AZ),
                                   pol(g.PAD_R, g.CTR_AZ)]).buffer(0.125, quad_segs=32))
nets_top = {n: unary_union(v) for n, v in nets_top.items()}
nets_top["GND"] = gnd_top_u
print("TOP layer net-to-net clearances (min 0.08):")
nt = list(nets_top)
worst_t = 9
for i in range(len(nt)):
    for j in range(i + 1, len(nt)):
        d = nets_top[nt[i]].distance(nets_top[nt[j]])
        worst_t = min(worst_t, d)
        print(f"  {nt[i]:4s} - {nt[j]:4s}: {d:6.3f} mm  "
              f"{'OK' if d >= 0.079 else '*** VIOLATION ***'}")
print(f"worst top clearance: {worst_t:.3f} mm")
# ---- FLOATING COPPER CHECK: every island must reach a terminal pad ----
def _cmp(geom):
    return [geom] if isinstance(geom, Polygon) else (
        list(geom.geoms) if isinstance(geom, MultiPolygon) else [])

all_vias = [pol(g.VIA_RP[g.NET[k]], c) for k, c in enumerate(g.SEC_CTR)]
all_vias += [pol(r_, a_) for r_, a_ in STITCH]
for netn, p_az in g.PAD_AZ.items():
    if netn != "CTR":
        x_, y_ = pol(g.PAD_R, p_az)
        all_vias += [(x_ + 0.9*np.cos(np.radians(a)), y_ + 0.9*np.sin(np.radians(a)))
                     for a in (0, 120, 240)]
all_vias += [pol(g.PAD_R, a_) for a_ in g.PAD_AZ.values()]   # plated mount holes

islands = ([(c, "TOP") for c in _cmp(unary_union(top_cu))] +
           [(c, "BOT") for c in _cmp(unary_union(bot_cu))])
# union-find over islands linked by a shared via/hole
parent = list(range(len(islands)))
def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]; i = parent[i]
    return i
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[ra] = rb
for v in all_vias:
    P = Point(v)
    touch = [i for i, (c, _) in enumerate(islands) if c.intersects(P)]
    for t in touch[1:]:
        union(touch[0], t)
# a group is "controlled" if it contains a terminal pad (screw) or the contact ring
anchors = [Point(pol(g.PAD_R, a_)) for a_ in g.PAD_AZ.values()]
anchors.append(Point(pol((g.GNDRING_R0+g.GNDRING_R1)/2, 0)))
groups = {}
for i, (c, layer) in enumerate(islands):
    groups.setdefault(find(i), []).append(i)
floating = []
for root, members in groups.items():
    ok = any(islands[m][0].intersects(a) for m in members for a in anchors)
    if not ok:
        area = sum(islands[m][0].area for m in members)
        floating.append((area, [islands[m][1] for m in members], members))
print(f"copper islands: {len(islands)}, electrically distinct groups: {len(groups)}")
if floating:
    print(f"*** FLOATING COPPER: {len(floating)} group(s) with no controlled potential")
    for area, layers, mem in sorted(floating, reverse=True)[:8]:
        c0 = islands[mem[0]][0].centroid
        print(f"    area {area:7.3f} mm^2 on {set(layers)} near "
              f"r={np.hypot(c0.x, c0.y):5.2f} az={np.degrees(np.arctan2(c0.y, c0.x))%360:5.1f}")
    print(f"    total floating area: {sum(f[0] for f in floating):.3f} mm^2")
else:
    print("no floating copper: every island reaches a screw terminal or the magnet ring")
print("min live-GND separation OK:",
      live_top_u.buffer(CLR - 0.005).intersection(gnd_top_u).area < 1e-6,
      live_bot_u.buffer(CLR - 0.005).intersection(gnd_bot_u).area < 1e-6)
