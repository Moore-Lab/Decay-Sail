"""
Generate a DXF for cutting SOLID graphite disks (no slots, no inner hole)
to find which outer diameter gives the best magnetic levitation height.

Produces one combined file, solid_disks.dxf, with four disks corner-packed
into the smallest possible square: finished OD = 2.5, 3.0, 3.5, 4.0 mm.

Each disk perimeter uses the verified working kerf pattern (the same as
the OUTSIDE pen of disk_full.dxf):
  4 concentric circles at 25 um spacing = 75 um kerf, cut in interleaved
  order (0, 50, 25, 75 um) so consecutive cuts are spread apart.

One pen:
  CUT (black, ACI 7) -- the 4-circle perimeter cut for every disk
"""

import itertools
import math

import ezdxf
import matplotlib.pyplot as plt

# -- Parameters (all in mm) ------------------------------------------
FINISHED_ODS = [2.5, 3.0, 3.5, 4.0]   # finished outer diameters to test

KERF = 0.020          # ~20 um laser kerf; finished edge is the inner
                      # wall of the innermost cut, so the innermost cut
                      # circle sits KERF/2 outside the finished radius.
KERF_STEP = 0.025     # 25 um spacing between the 4 parallel cut circles
KERF_LINES = 4        # 4 concentric circles per perimeter (75 um kerf)

SPACING = 0.5         # gap between adjacent disks' outermost cut circles


def interleaved_order(n):
    """Indices 0..n-1 reordered evens-first then odds (heat-spreading)."""
    return list(range(0, n, 2)) + list(range(1, n, 2))


def pack_into_square(outer_radii, gap):
    """Corner-pack four circles into the smallest square.

    Each circle is pushed into one corner of the square (tangent to its
    two walls). All circle/circle pairs must keep `gap` between their
    outermost cut circles. Tries every corner assignment and returns the
    smallest square side and the circle centres (square at [0,S]x[0,S]).
    """
    rho = [r + gap / 2.0 for r in outer_radii]   # inflated radius

    def centres(perm, S):
        # perm -> circle index at (BL, BR, TL, TR)
        R = outer_radii
        c = [None] * 4
        c[perm[0]] = (R[perm[0]], R[perm[0]])              # bottom-left
        c[perm[1]] = (S - R[perm[1]], R[perm[1]])          # bottom-right
        c[perm[2]] = (R[perm[2]], S - R[perm[2]])          # top-left
        c[perm[3]] = (S - R[perm[3]], S - R[perm[3]])      # top-right
        return c

    def feasible(perm, S):
        c = centres(perm, S)
        for i in range(4):
            for j in range(i + 1, 4):
                d = math.hypot(c[i][0] - c[j][0], c[i][1] - c[j][1])
                if d < rho[i] + rho[j] - 1e-9:
                    return False
        return True

    best_side, best_centres = None, None
    for perm in itertools.permutations(range(4)):
        lo, hi = 0.0, 4 * sum(outer_radii)   # hi is comfortably feasible
        for _ in range(100):
            mid = (lo + hi) / 2.0
            if feasible(perm, mid):
                hi = mid
            else:
                lo = mid
        if best_side is None or hi < best_side:
            best_side = hi
            best_centres = centres(perm, hi)
    return best_side, best_centres


# -- Disk geometry ---------------------------------------------------
# outermost cut radius of each disk = finished radius + KERF/2 (kerf
# correction) + (KERF_LINES-1)*KERF_STEP (the 4-circle kerf width)
finished_radii = [od / 2.0 for od in FINISHED_ODS]
inner_cut_radii = [r + KERF / 2.0 for r in finished_radii]
outer_cut_radii = [r0 + (KERF_LINES - 1) * KERF_STEP for r0 in inner_cut_radii]

# -- Pack into the smallest square -----------------------------------
side, centres = pack_into_square(outer_cut_radii, SPACING)
# centre the square's bounding box on the origin
shift = side / 2.0
centres = [(x - shift, y - shift) for (x, y) in centres]

# -- Build the DXF ---------------------------------------------------
doc = ezdxf.new("R2010")
doc.layers.add("CUT", color=7)      # black -> EZCAD2 cut pen
msp = doc.modelspace()

print("Solid-disk perimeter cuts (verified 4-circle, 75 um kerf):")
print(f"  Packed into a {side:.3f} x {side:.3f} mm square "
      f"({SPACING*1000:.0f} um between disks).")
for od, r0, (xc, yc) in zip(FINISHED_ODS, inner_cut_radii, centres):
    radii = [r0 + i * KERF_STEP for i in range(KERF_LINES)]
    for idx in interleaved_order(KERF_LINES):
        msp.add_circle((xc, yc), radii[idx],
                       dxfattribs={"layer": "CUT", "color": 7})
    print(f"  OD {od:.1f} mm  centre ({xc:+.3f}, {yc:+.3f})  "
          f"cut radii = {[round(r * 1000, 1) for r in radii]} um")

doc.saveas("solid_disks.dxf")
print("Saved solid_disks.dxf")


# -- Pen settings note -----------------------------------------------
pen_settings = f"""\
EZCAD2 Pen Settings for solid_disks.dxf
========================================
Four SOLID graphite disks (no slots), finished OD = 2.5, 3.0, 3.5, 4.0 mm,
corner-packed into a {side:.2f} x {side:.2f} mm square ({SPACING*1000:.0f} um
between adjacent disks). Goal: find which OD gives the best magnetic
levitation height.

Same verified through-cut recipe as disk_full.dxf:
  4 cuts at 25 um spacing (75 um kerf), 20 processes (Loop Count),
  2000 mm/s, 75% power, Mark Count ~20-30 cycles.

Kerf note: the innermost cut circle is KERF/2 = {KERF/2*1000:.0f} um larger
than the finished radius, so the finished disk edges land at exactly
2.5 / 3.0 / 3.5 / 4.0 mm OD. If the cut kerf differs from {KERF*1000:.0f} um,
adjust KERF in generate_solid_disks.py and re-run.

The DXF has ONE colored layer on a single pen:
  Black (ACI 7) -- CUT pen: all four 4-circle perimeters

-----------------------------------------------------------------
PEN 1: CUT   (BLACK entities)
-----------------------------------------------------------------
  Power:       75 %
  Speed:       2000 mm/s
  Frequency:   your usual MOPA/Q-switch frequency
  Loop Count:  20
  Start TC:    0 ms
  End TC:      0 ms

-----------------------------------------------------------------
GLOBAL SETTINGS  (F2 Mark dialog)
-----------------------------------------------------------------
  Mark Count:  20-30
"""
with open("solid_disks_pen_settings.txt", "w") as f:
    f.write(pen_settings)
print("Saved solid_disks_pen_settings.txt")


# -- Preview plot ----------------------------------------------------
fig, ax = plt.subplots(figsize=(7, 7))

# the bounding square
ax.add_patch(plt.Rectangle((-side / 2, -side / 2), side, side,
                           fill=False, ec="tab:red", lw=1.0, ls="--"))

for od, r0, (xc, yc) in zip(FINISHED_ODS, inner_cut_radii, centres):
    finished_r = od / 2.0
    ax.add_patch(plt.Circle((xc, yc), finished_r, fc="#dddddd", ec="none"))
    for i in range(KERF_LINES):
        ax.add_patch(plt.Circle((xc, yc), r0 + i * KERF_STEP,
                                fill=False, ec="black", lw=0.6))

m = side / 2 + 1
ax.set_xlim(-m, m)
ax.set_ylim(-m, m)
ax.set_aspect("equal")
ax.set_xlabel("mm")
ax.set_ylabel("mm")
ax.set_title(f"solid_disks.dxf -- four disks in a {side:.2f} mm square")
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig("solid_disks_preview.png", dpi=200, bbox_inches="tight")
plt.close()
print("Saved solid_disks_preview.png")
