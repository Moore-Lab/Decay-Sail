"""
Generate sail_array.dxf -- 10 copies of the chosen sail geometry
for cutting on 1.5 mil aluminum foil. Stacked vertically, 1 mm
between each sail.

Updated design (no central tab; two side tabs straddle the disk and
slot into two opposite radial slots):

  +--------+              +--------+
  |        |              |        |
  |  sq1   |   strut bar  |  sq2   |     <- 2 x 2 mm wings + thin strut
  |        |              |        |
  +--------+--------------+--------+
           |              |
         tab|              |tab            <- 0.75 mm wide x 0.4 mm
           +--+        +--+                deep tabs at the BOTTOM-INSIDE
              <- 1.75->                    of each wing; 1.75 mm inside
                                           space between them

The 1.75 mm inside space matches the inner-end diameter of the radial
slots on slotted_disk_3p5.dxf, so the two tabs drop into opposite
slots and the sail straddles the disk's central hole.
"""

import ezdxf
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

# -- Sail dimensions (mm) -------------------------------------------
WING_SIZE       = 2.0      # square wing side
STRUT_HEIGHT    = 0.5      # thin band joining the two wings

SIDE_TAB_WIDTH  = 0.75     # each tab's horizontal extent in flat layout
SIDE_TAB_DEPTH  = 0.4      # how far each tab drops below the bar
INSIDE_SPACE    = 1.75     # gap between the two tabs' inner edges
                           # (= 2 x slot inner radius on the disk)

# Derived: tab outer edges = wing inner edges
_TAB_OUTER_X    = INSIDE_SPACE / 2 + SIDE_TAB_WIDTH    # = 1.625
_TAB_INNER_X    = INSIDE_SPACE / 2                     # = 0.875

N_SAILS         = 10
LAYOUT_GAP      = 1.0      # spacing between sails in the array


def sail_outline(x_offset=0.0, y_offset=0.0):
    """
    CCW polygon of one sail in flat layout. Origin = center of the bar
    bottom; y points up (wings above), y < 0 = tabs below.
    """
    s   = WING_SIZE
    h_in  = _TAB_INNER_X        # tab inner edge x
    h_out = _TAB_OUTER_X        # tab outer edge x = wing inner edge x
    h_sq  = h_out + s           # wing outer edge x
    d     = SIDE_TAB_DEPTH

    pts = [
        # Left wing: top-left -> down left edge
        (-h_sq,  s),
        (-h_sq,  0),
        # Bottom edge of left wing, then down into left tab
        (-h_out, 0),
        (-h_out, -d),
        (-h_in,  -d),
        (-h_in,  0),
        # Bar bottom (gap between tabs)
        ( h_in,  0),
        # Right tab: down, across, up
        ( h_in,  -d),
        ( h_out, -d),
        ( h_out, 0),
        # Right wing: bottom, right side, top
        ( h_sq,  0),
        ( h_sq,  s),
        ( h_out, s),
        # Down to strut top, across, back up to left wing top
        ( h_out, STRUT_HEIGHT),
        (-h_out, STRUT_HEIGHT),
        (-h_out, s),
    ]
    # Closing edge goes from (-h_out, s) back to (-h_sq, s)
    return [(x + x_offset, y + y_offset) for x, y in pts]


# -- Build DXF ------------------------------------------------------
doc = ezdxf.new("R2010")
doc.layers.add("CUT", color=7)
msp = doc.modelspace()

y_baseline = 0.0
preview_polys = []
for i in range(N_SAILS):
    y_off = y_baseline + SIDE_TAB_DEPTH   # tab bottom sits at y_baseline
    outline = sail_outline(x_offset=0.0, y_offset=y_off)
    msp.add_lwpolyline(outline, close=True,
                       dxfattribs={"layer": "CUT", "color": 7})
    preview_polys.append(outline)
    y_baseline = y_off + WING_SIZE + LAYOUT_GAP

doc.saveas("sail_array.dxf")

total_w = 2 * (_TAB_OUTER_X + WING_SIZE)
total_h = y_baseline - LAYOUT_GAP
print(f"Saved sail_array.dxf -- {N_SAILS} sails")
print(f"  Wing:           {WING_SIZE} x {WING_SIZE} mm")
print(f"  Strut height:   {STRUT_HEIGHT} mm")
print(f"  Side tab:       {SIDE_TAB_WIDTH} mm wide x {SIDE_TAB_DEPTH} mm deep")
print(f"  Inside space:   {INSIDE_SPACE} mm (between the two tabs)")
print(f"  Total width:    {total_w:.2f} mm")
print(f"  Bounding box:   {total_w:.2f} mm x {total_h:.2f} mm")


# -- Pen settings ---------------------------------------------------
pen_settings = f"""\
EZCAD2 Pen Settings for sail_array.dxf
=======================================
{N_SAILS} copies of the updated sail geometry on 1.5 mil (38 um)
aluminum foil:
  - {WING_SIZE} x {WING_SIZE} mm wings
  - {STRUT_HEIGHT} mm strut between wings
  - Two side tabs at the bottom-inside of each wing,
    {SIDE_TAB_WIDTH} mm wide x {SIDE_TAB_DEPTH} mm deep, {INSIDE_SPACE} mm inside space
    (drops into two opposite radial slots on the slotted disk)
  - Total width {total_w:.2f} mm
  - Single-line outline cut

Layout: vertically stacked, {LAYOUT_GAP} mm between sails.
Bounding box: {total_w:.2f} mm x {total_h:.2f} mm.

Same Al-foil recipe as the previous sail_array.dxf cut:

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

Same fixturing as before: tape the foil flat to a sacrificial
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
ax.set_title(f"sail_array.dxf -- {N_SAILS} sails, two side tabs")
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig("sail_array_preview.png", dpi=160, bbox_inches="tight")
plt.close()
print("Saved sail_array_preview.png")
