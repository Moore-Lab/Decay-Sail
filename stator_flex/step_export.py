"""3D solid model of the rev G flex board -> STEP (and STL), for the CAD assembly.

Built from the same parametric geometry as the Gerbers, so the model and the
fabricated board cannot drift apart.

Coordinate frame (matches mounting_plate_sketch.dxf and all the DXFs):
  origin = trap / magnet axis, z = 0 is the BOTTOM face of the flex,
  i.e. the surface that presses against the PEEK plate and the magnet.
  +z is up, toward the rotor.  Mount holes at r = 9.0, az 15/105/195/285.

Bodies in the STEP assembly:
  flex_core   polyimide, z 0 -> 0.025 (+ bottom copper 0.018 below? see note)
  Actually the stack is built as:
      bottom copper   z = -0.018 .. 0      (touches the plate/magnet)
      PI core         z =  0     .. 0.025
      top copper      z =  0.025 .. 0.043  (electrodes; rotor gap starts here)
  so the board's overall thickness is 0.061 mm plus coverlay (not modelled;
  coverlay adds ~0.025 mm where present, outside the active area).

Optional: PI shim disk (Ø5.8 x 0.1) that sets the rotor gap - exported as a
separate body so it can be swapped/suppressed in CAD.
"""

import numpy as np
import cadquery as cq
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

import gerber_export as G          # reuses the exact copper geometry
import generate_flex_revG as g

T_CU = 0.018
T_PI = 0.025
Z_BOT_CU = -T_CU
R_BOARD = g.R_BOARD
SHIM_D, SHIM_T = 5.8, 0.10


def shp_to_wires(geom, tol=0.004):
    """shapely -> list of (exterior, [interiors]) point lists, lightly simplified."""
    polys = []
    if isinstance(geom, Polygon):
        polys = [geom]
    elif isinstance(geom, MultiPolygon):
        polys = list(geom.geoms)
    out = []
    for p in polys:
        p = p.simplify(tol, preserve_topology=True)
        if p.is_empty or p.area < 1e-4:
            continue
        ext = [(x, y) for x, y in p.exterior.coords[:-1]]
        ints = [[(x, y) for x, y in r.coords[:-1]] for r in p.interiors
                if Polygon(r).area > 1e-4]
        out.append((ext, ints))
    return out


def extrude(geom, z0, thick, tol=0.004):
    """Extrude a shapely (Multi)Polygon into a cadquery solid."""
    solid = None
    for ext, ints in shp_to_wires(geom, tol):
        wp = cq.Workplane("XY", origin=(0, 0, z0)).polyline(ext).close()
        body = wp.extrude(thick)
        for hole in ints:
            cut = cq.Workplane("XY", origin=(0, 0, z0 - 0.01)).polyline(hole)\
                    .close().extrude(thick + 0.02)
            body = body.cut(cut)
        solid = body if solid is None else solid.union(body)
    return solid


print("building copper geometry...")
top_cu = unary_union(G.top_cu)          # pour + islands, already boolean-clean
bot_cu = unary_union(G.bot_cu)
core = G.disk(R_BOARD)

mount = [g.pol(g.PAD_R, az) for az in g.PAD_AZ.values()]


def drill(body, z0, thick):
    for x, y in mount:
        cutter = cq.Workplane("XY", origin=(x, y, z0 - 0.05)).circle(1.5)\
                   .extrude(thick + 0.1)
        body = body.cut(cutter)
    return body


print("extruding PI core...")
core_solid = drill(extrude(core, 0, T_PI), 0, T_PI)
print("extruding top copper...")
top_solid = drill(extrude(top_cu, T_PI, T_CU), T_PI, T_CU)
print("extruding bottom copper...")
bot_solid = drill(extrude(bot_cu, Z_BOT_CU, T_CU), Z_BOT_CU, T_CU)

shim = cq.Workplane("XY", origin=(0, 0, -SHIM_T - T_CU)).circle(SHIM_D / 2)\
         .extrude(SHIM_T)

asm = (cq.Assembly(name="flexG_rev_G")
       .add(core_solid, name="polyimide_core", color=cq.Color(0.85, 0.72, 0.35))
       .add(top_solid, name="top_copper_electrodes", color=cq.Color(0.80, 0.55, 0.25))
       .add(bot_solid, name="bottom_copper", color=cq.Color(0.60, 0.45, 0.25))
       .add(shim, name="OPTIONAL_shim_D5p8x0p1", color=cq.Color(0.55, 0.75, 0.95)))

asm.save("flexG_board.step")
print("wrote flexG_board.step")

# simplified single-solid version: board outline only, for quick fit checks
simple = drill(extrude(core, Z_BOT_CU, T_CU * 2 + T_PI), Z_BOT_CU, T_CU * 2 + T_PI)
cq.exporters.export(simple, "flexG_board_simple.step")
print("wrote flexG_board_simple.step (Ø25.4 x 0.061 slab + 4 holes)")

bb = top_solid.val().BoundingBox()
print(f"top copper extent: x {bb.xmin:.2f}..{bb.xmax:.2f}, "
      f"y {bb.ymin:.2f}..{bb.ymax:.2f}, z {bb.zmin:.3f}..{bb.zmax:.3f}")
print(f"electrode top surface at z = {T_PI + T_CU:.3f} mm above the plate face")
print(f"rotor gap h = levitation_height - {T_PI + T_CU:.3f} mm (no shim)")
