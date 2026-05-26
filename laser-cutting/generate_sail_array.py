"""
Generate sail_array.dxf -- 10 copies of the chosen sail geometry
for cutting on 1.5 mil aluminum foil. Stacked vertically, 1 mm
between each sail.

Chosen geometry (after the mechanical-fit test):
  - 2 x 2 mm wings
  - 3 mm wing-to-wing gap (7 mm total width)
  - 0.5 mm tall strut connecting the wings
  - 1.1 mm wide x 0.5 mm deep tab (fits diametrically in disk's
    central hole, flush bottom)
  - Single-line outline cut (foil is thin enough)
"""

import ezdxf
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

# -- Sail dimensions (mm) -------------------------------------------
WING_SIZE     = 2.0     # upsized from the test cut
GAP           = 3.0     # 2 + 3 + 2 = 7 mm total width
TAB_WIDTH     = 1.3     # central hole measured ~1.4 mm top / 1.2 mm bot,
                        # so 1.3 mm is the average -- wedges in part way
TAB_DEPTH     = 0.3     # shortened from 0.5 mm; 1.3 mm tab can't reach the
                        # narrow bottom of the conical hole anyway (only the
                        # top ~0.25 mm of the hole is wider than 1.3 mm)
STRUT_HEIGHT  = 0.5

N_SAILS       = 10
LAYOUT_GAP    = 1.0     # spacing between adjacent sails in the array


def sail_outline(g, s, x_offset=0.0, y_offset=0.0):
    """CCW outline of a single sail (wings + strut + tab)."""
    xL = -g / 2 - s
    xR =  g / 2 + s
    pts = [
        (xL,             0),
        (-g / 2,         0),
        (-TAB_WIDTH / 2, 0),
        (-TAB_WIDTH / 2, -TAB_DEPTH),
        ( TAB_WIDTH / 2, -TAB_DEPTH),
        ( TAB_WIDTH / 2, 0),
        ( g / 2,         0),
        (xR,             0),
        (xR,             s),
        ( g / 2,         s),
        ( g / 2,         STRUT_HEIGHT),
        (-g / 2,         STRUT_HEIGHT),
        (-g / 2,         s),
        (xL,             s),
    ]
    return [(x + x_offset, y + y_offset) for x, y in pts]


# -- Build DXF ------------------------------------------------------
doc = ezdxf.new("R2010")
doc.layers.add("CUT", color=7)
msp = doc.modelspace()

y_baseline = 0.0
preview_polys = []
for i in range(N_SAILS):
    y_off = y_baseline + TAB_DEPTH
    outline = sail_outline(GAP, WING_SIZE, x_offset=0.0, y_offset=y_off)
    msp.add_lwpolyline(outline, close=True,
                       dxfattribs={"layer": "CUT", "color": 7})
    preview_polys.append(outline)
    y_baseline = y_off + WING_SIZE + LAYOUT_GAP

doc.saveas("sail_array.dxf")

total_w = GAP + 2 * WING_SIZE
total_h = y_baseline - LAYOUT_GAP
print(f"Saved sail_array.dxf -- {N_SAILS} sails, "
      f"wing {WING_SIZE} mm, gap {GAP} mm (total width {total_w} mm)")
print(f"  Bounding box: {total_w:.1f} mm x {total_h:.1f} mm")


# -- Pen settings ---------------------------------------------------
pen_settings = f"""\
EZCAD2 Pen Settings for sail_array.dxf
=======================================
{N_SAILS} copies of the chosen sail geometry on 1.5 mil (38 um)
aluminum foil:
  - {WING_SIZE} x {WING_SIZE} mm wings
  - {GAP} mm wing-to-wing gap ({total_w} mm total width)
  - {STRUT_HEIGHT} mm strut between wings
  - {TAB_WIDTH} mm wide x {TAB_DEPTH} mm deep tab (flush in disk
    central hole)
  - Single-line outline cut

Layout: vertically stacked, {LAYOUT_GAP} mm between sails.
Bounding box: {total_w:.1f} mm x {total_h:.1f} mm.

Use the same Al-foil recipe that worked for sail_test.dxf:

-----------------------------------------------------------------
PEN 1: CUT   (BLACK entities)
-----------------------------------------------------------------
  Power:       60-75 %        (whatever cut the test cleanly)
  Speed:       1000 mm/s
  Frequency:   30-50 kHz
  Loop Count:  5-10
  Start TC:    0 ms
  End TC:      0 ms

-----------------------------------------------------------------
GLOBAL  (F2 Mark dialog)
-----------------------------------------------------------------
  Mark Count:  1-3   (whatever worked on the test)

Same fixturing as the test cut: tape the foil flat to a sacrificial
backing, focus on the foil surface, no/gentle air assist.
"""
with open("sail_array_pen_settings.txt", "w") as f:
    f.write(pen_settings)
print("Saved sail_array_pen_settings.txt")


# -- Preview --------------------------------------------------------
fig, ax = plt.subplots(figsize=(6, 12))
for outline in preview_polys:
    poly = Polygon(outline, closed=True, fc="#cccccc", ec="black", lw=0.5)
    ax.add_patch(poly)

xs = [x for ol in preview_polys for x, _ in ol]
ys = [y for ol in preview_polys for _, y in ol]
m = 1.0
ax.set_xlim(min(xs) - m, max(xs) + m)
ax.set_ylim(min(ys) - m, max(ys) + m)
ax.set_aspect("equal")
ax.set_xlabel("mm")
ax.set_ylabel("mm")
ax.set_title(f"sail_array.dxf -- {N_SAILS} sails, "
             f"wing {WING_SIZE} mm, gap {GAP} mm")
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig("sail_array_preview.png", dpi=160, bbox_inches="tight")
plt.close()
print("Saved sail_array_preview.png")
