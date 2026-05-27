"""
Generate sail_test.dxf for cutting on 1.5 mil aluminum foil.

Three sails with different wing separations (3, 4, 5 mm) so we can
test which one mechanically fits and stays put in the disk's central
hole.

Each sail layout (flat 2D, before insertion):

  +--------+              +--------+
  |  sq1   |              |  sq2   |     <- 1.5 x 1.5 mm wings
  |        |              |        |
  +--------+--strut(0.5)--+--------+     <- 0.5 mm tall connecting strut
           |              |
           |    tab       |              <- 1.1 mm wide x 0.5 mm deep
           +--------------+

After insertion the tab sits diametrically in the disk's 1.1 mm
central hole, flush with the bottom of the disk (tab depth = disk
thickness = 0.5 mm). Wings + strut sit above the disk surface.

One pen (black). Cut as single-line outline -- foil is thin enough
that the 4-cut kerf trick from the graphite isn't needed.
"""

import ezdxf
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

# -- Sail dimensions (mm) -------------------------------------------
WING_SIZE     = 1.5     # square wing side
TAB_WIDTH     = 1.1     # matches disk central hole diameter
TAB_DEPTH     = 0.5     # = disk thickness, flush bottom
STRUT_HEIGHT  = 0.5     # thin band joining the two wings
GAPS          = [3.0, 4.0, 5.0]
LAYOUT_GAP    = 1.5     # spacing between sails in the cut layout (mm)


def sail_outline(g, x_offset=0.0, y_offset=0.0):
    """
    CCW polygon vertices for a sail with wing-to-wing gap g.

    Coordinate convention (before offset):
      x = 0 is the sail's vertical axis of symmetry
      y = 0 is the disk's top surface (strut bottom)
      Tab goes to y = -TAB_DEPTH (into the disk)
      Wings & strut go up to y = WING_SIZE (above the disk)
    """
    s = WING_SIZE
    xL = -g / 2 - s     # left wing left edge
    xR =  g / 2 + s     # right wing right edge

    pts = [
        # Left wing bottom-left, going CCW
        (xL,            0),
        (-g / 2,        0),
        (-TAB_WIDTH / 2, 0),
        (-TAB_WIDTH / 2, -TAB_DEPTH),
        ( TAB_WIDTH / 2, -TAB_DEPTH),
        ( TAB_WIDTH / 2, 0),
        ( g / 2,        0),
        (xR,            0),
        (xR,            s),
        ( g / 2,        s),
        ( g / 2,        STRUT_HEIGHT),
        (-g / 2,        STRUT_HEIGHT),
        (-g / 2,        s),
        (xL,            s),
    ]
    return [(x + x_offset, y + y_offset) for x, y in pts]


# -- Build the DXF --------------------------------------------------
doc = ezdxf.new("R2010")
doc.layers.add("CUT", color=7)
msp = doc.modelspace()

# Stack the sails vertically (tab pointing down), spaced by LAYOUT_GAP
y_baseline = 0.0     # bottom of the next sail's tab
preview_polys = []
for g in GAPS:
    y_off = y_baseline + TAB_DEPTH       # strut-bottom y for this sail
    outline = sail_outline(g, x_offset=0.0, y_offset=y_off)
    msp.add_lwpolyline(outline, close=True,
                       dxfattribs={"layer": "CUT", "color": 7})
    preview_polys.append((g, outline))
    y_baseline = y_off + WING_SIZE + LAYOUT_GAP

doc.saveas("sail_test.dxf")
total_w = 2 * (max(GAPS) / 2 + WING_SIZE)
total_h = y_baseline - LAYOUT_GAP   # subtract trailing gap
print(f"Saved sail_test.dxf -- 3 sails, "
      f"g = {GAPS} mm, bounding box ~ {total_w:.1f} x {total_h:.1f} mm")


# -- Pen settings ---------------------------------------------------
pen_settings = """\
EZCAD2 Pen Settings for sail_test.dxf
======================================
THREE sails on 1.5 mil (38 um) aluminum foil for a mechanical fit test:
  - 1.5 x 1.5 mm wings, separated by 3, 4, or 5 mm (one sail each)
  - 1.1 mm wide x 0.5 mm deep tab (fits diametrically in disk's
    central hole, flush bottom)
  - 0.5 mm tall strut between the wings
  - Single-line outline cut (foil is thin enough)


ALUMINUM FOIL is reflective at 1064 nm -- recipe is very different
from the graphite cutting recipe. Below are starting parameters; tune
with a 5 mm straight test cut on a scrap of foil before running the
sail file.

-----------------------------------------------------------------
PEN 1: CUT   (BLACK entities)
-----------------------------------------------------------------
  Power:       60-75 %
  Speed:       1000 mm/s
  Frequency:   30-50 kHz   (lower freq = higher per-pulse peak power,
                            better coupling to reflective Al)
  Loop Count:  5-10        (start at 5, add passes if not through)
  Start TC:    0 ms
  End TC:      0 ms

-----------------------------------------------------------------
GLOBAL  (F2 Mark dialog)
-----------------------------------------------------------------
  Mark Count:  1-3   (try 1 first, then add)


FIXTURING / SETUP (matters more than the parameters)
-----------------------------------------------------------------
  - Tape the foil FLAT to a backing (cardboard, masking tape on
    a glass slide, etc.).  If the foil flexes or curls, the focus
    drifts and the cut goes uneven.
  - Sacrificial backing UNDER the foil to absorb forward-scattered
    light.  Black cardstock or black-anodized Al is good.  DO NOT
    leave bare polished metal directly under the foil.
  - Focus on the foil surface, not the cardboard.
  - Air assist OFF (or very gentle) -- too much will flap the foil.


TEST FIRST
-----------------------------------------------------------------
Cut a 5 mm straight line at the proposed settings.  Visually score:
  - Clean through-cut, no melted balls along the kerf      -> good
  - Through but melted "balls" on edges                    -> drop power 10%,
                                                              bump speed 20%
  - Not through                                            -> bump Loop Count
  - Edges look heat-damaged                                -> drop power, add
                                                              cooldown delay
                                                              between cycles
"""
with open("sail_test_pen_settings.txt", "w") as f:
    f.write(pen_settings)
print("Saved sail_test_pen_settings.txt")


# -- Preview plot ---------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 8))
for g, outline in preview_polys:
    poly = Polygon(outline, closed=True, fc="#cccccc", ec="black", lw=0.6)
    ax.add_patch(poly)
    cx = max(p[0] for p in outline) + 0.8
    cy = sum(p[1] for p in outline) / len(outline)
    ax.text(cx, cy, f"gap = {g:.1f} mm\nwidth = {g + 2*WING_SIZE:.1f} mm",
            va="center", fontsize=10)

xs_all = [x for _, ol in preview_polys for x, _ in ol]
ys_all = [y for _, ol in preview_polys for _, y in ol]
m = 1
ax.set_xlim(min(xs_all) - m, max(xs_all) + 6)
ax.set_ylim(min(ys_all) - m, max(ys_all) + m)
ax.set_aspect("equal")
ax.set_xlabel("mm")
ax.set_ylabel("mm")
ax.set_title("sail_test.dxf -- three sails, 1.5 mil Al foil")
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig("sail_test_preview.png", dpi=160, bbox_inches="tight")
plt.close()
print("Saved sail_test_preview.png")
