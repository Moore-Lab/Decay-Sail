"""
Generate a DXF for cutting ONE slotted graphite disk:
  - Finished outer diameter: 3.5 mm
  - 16 radial slots extending all the way to the outer edge
    (no eddy-current ring remains)
  - Open central hole

Uses the verified working kerf pattern (4 cuts at 25 um spacing = 75 um
kerf) for both the slot sides and the perimeter, plus kerf correction
so the finished edges land exactly at the nominal radii.

Three pens:
  INSIDE  (blue,  ACI 5) -- all 16 regular slots + inner circle cutout
                            (cut through)
  OUTSIDE (black, ACI 7) -- outer perimeter
  PARTIAL (red,   ACI 1) -- 2 slightly-wider extra slots on the
                            horizontal axis (angles 0 and pi),
                            overlaid on the INSIDE slots. These
                            extend in to the inner circle (no inner
                            end cap -- they open into the hole) so
                            the sail tab can sit in them. Cut at
                            half the Mark Count of the other pens
                            so they only widen the slot part-way
                            through the graphite thickness.

Outputs:
  slotted_disk_3p5.dxf
  slotted_disk_3p5_pen_settings.txt
  slotted_disk_3p5_preview.png
"""

import numpy as np
import ezdxf
import matplotlib.pyplot as plt

# -- Finished geometry (all in mm) -----------------------------------
FINISHED_OD       = 3.5
FINISHED_OR       = FINISHED_OD / 2.0     # 1.75 mm

# Inner hole + slot layout (same scheme as disk_full.dxf)
FINISHED_INNER_R  = 0.55                   # nominal inner hole radius
RING_GAP          = 0.20                   # 200 um gap between inner cutout
                                           # and slot inner ends
SLOT_R_INNER      = FINISHED_INNER_R + RING_GAP  # = 0.75 mm
N_SLOTS           = 16

# Kerf pattern (verified through-cut recipe)
KERF              = 0.020                  # ~20 um laser kerf
KERF_STEP         = 0.025                  # 25 um between parallel cuts
KERF_LINES        = 4                      # 4 lines per cut group
SLOT_WIDTH        = (KERF_LINES - 1) * KERF_STEP   # 75 um nominal slot width

# Partial-depth wider slots on the horizontal axis ------------------
# These two slots get a third pen so they can be configured separately
# (half the Mark Count -> only cuts part-way through the graphite).
# Widening: 6 cuts at 25 um = 125 um (1.67x the regular 75 um); the
# closest "1.5x as wide" we can do without changing the verified
# 25-um-step kerf pattern.
PARTIAL_SLOT_INDICES = [0, 8]              # angles 0 and pi (16 slots total)
PARTIAL_KERF_LINES   = 6
PARTIAL_SLOT_WIDTH   = (PARTIAL_KERF_LINES - 1) * KERF_STEP   # 125 um
# Inner end of partial slots reaches past the inner hole edge so the
# slot opens directly into the inner hole (no end cap needed). Drop
# 50 um inside the finished inner edge to guarantee overlap with the
# inner-hole cuts.
PARTIAL_SLOT_R_INNER = FINISHED_INNER_R - 0.05    # = 0.50 mm


# -- Kerf-corrected cut radii ----------------------------------------
# Outer perimeter: the finished edge is the inner kerf wall of the
# innermost cut. To land at FINISHED_OR exactly, innermost cut is at
# FINISHED_OR + KERF/2.
OUTER_CUT_R0      = FINISHED_OR + KERF / 2.0           # innermost outer cut
OUTER_CUT_RADII   = [OUTER_CUT_R0 + i * KERF_STEP for i in range(KERF_LINES)]

# Inner hole: the finished inner edge is the outer kerf wall of the
# outermost (largest) inner cut. To land at FINISHED_INNER_R exactly,
# outermost inner cut is at FINISHED_INNER_R - KERF/2.
INNER_CUT_R0      = FINISHED_INNER_R - KERF / 2.0      # outermost inner cut
INNER_CUT_RADII   = [INNER_CUT_R0 - i * KERF_STEP for i in range(KERF_LINES)]

# Slots run from SLOT_R_INNER out to the innermost perimeter cut so the
# wedges are definitely severed by the OUTSIDE pen.
SLOT_R_OUTER      = OUTER_CUT_R0


# -- Helpers ---------------------------------------------------------
def interleaved(seq):
    """evens-first then odds (spreads heat between consecutive cuts)."""
    return seq[0::2] + seq[1::2]


def interleaved_offsets(slot_width, step):
    """Transverse offsets for parallel cut lines, evens-first then odds."""
    n = int(round(slot_width / step)) + 1
    positions = np.linspace(-slot_width / 2, slot_width / 2, n).tolist()
    return interleaved(positions)


def slot_lines(angle, r_inner, r_outer, slot_width, step,
               cap_inner=True, cap_outer=False):
    """
    Build the line segments for one radial slot:
      - 4 parallel radial lines at 25 um spacing
      - Interleaved transverse end-cap lines at the inner end
    """
    c, s = np.cos(angle), np.sin(angle)
    r_hat = np.array([c, s])
    t_hat = np.array([-s, c])       # 90 CCW from radial

    hw = slot_width / 2.0
    lines = []

    # Parallel radial lines (interleaved transverse positions)
    for off in interleaved_offsets(slot_width, step):
        shift = t_hat * off
        p1 = r_hat * r_inner + shift
        p2 = r_hat * r_outer + shift
        lines.append((tuple(p1), tuple(p2)))

    # End caps: parallel transverse lines recessed into the slot
    n_cap = int(round(slot_width / step))
    cap_positions = [i * step for i in range(n_cap + 1)]
    cap_order = interleaved(cap_positions)
    caps = []
    if cap_inner:
        caps.append((r_inner, +1))
    if cap_outer:
        caps.append((r_outer, -1))
    for r, sign in caps:
        for off in cap_order:
            base = r_hat * (r + sign * off)
            p_left  = base + t_hat * (-hw)
            p_right = base + t_hat *  hw
            lines.append((tuple(p_left), tuple(p_right)))

    return lines


# -- Build the DXF ---------------------------------------------------
doc = ezdxf.new("R2010")
doc.layers.add("INSIDE",  color=5)        # blue
doc.layers.add("OUTSIDE", color=7)        # black
doc.layers.add("PARTIAL", color=1)        # red -- wider partial-depth slots
msp = doc.modelspace()

# Trackers for the preview
preview_lines   = []   # (p1, p2, layer)
preview_circles = []   # (r, layer)

# Slots
# Every angle gets the regular through-cut slot on INSIDE.
# The two horizontal-axis angles ALSO get a wider partial-depth slot
# on PARTIAL (overlays the INSIDE slot, widens it, and extends in
# to the inner hole). The INSIDE pen still cuts those slots through.
slot_angles = np.linspace(0, 2 * np.pi, N_SLOTS, endpoint=False)
for idx, a in enumerate(slot_angles):
    # Regular through-cut slot (every angle, INSIDE pen)
    for p1, p2 in slot_lines(a, SLOT_R_INNER, SLOT_R_OUTER,
                             SLOT_WIDTH, KERF_STEP,
                             cap_inner=True, cap_outer=False):
        msp.add_line(p1, p2, dxfattribs={"layer": "INSIDE", "color": 5})
        preview_lines.append((p1, p2, "INSIDE"))

    # Wider partial-depth slot (PARTIAL pen, only for horizontal axis)
    if idx in PARTIAL_SLOT_INDICES:
        for p1, p2 in slot_lines(a, PARTIAL_SLOT_R_INNER, SLOT_R_OUTER,
                                 PARTIAL_SLOT_WIDTH, KERF_STEP,
                                 cap_inner=False, cap_outer=False):
            msp.add_line(p1, p2,
                         dxfattribs={"layer": "PARTIAL", "color": 1})
            preview_lines.append((p1, p2, "PARTIAL"))

# Inner circle cutout (4 circles growing inward, interleaved order)
for r in interleaved(INNER_CUT_RADII):
    msp.add_circle((0, 0), r, dxfattribs={"layer": "INSIDE", "color": 5})
    preview_circles.append((r, "INSIDE"))

# Outer perimeter (4 circles growing outward, interleaved order)
for r in interleaved(OUTER_CUT_RADII):
    msp.add_circle((0, 0), r, dxfattribs={"layer": "OUTSIDE", "color": 7})
    preview_circles.append((r, "OUTSIDE"))

doc.saveas("slotted_disk_3p5.dxf")
print("Saved slotted_disk_3p5.dxf")
print(f"  Finished OD = {FINISHED_OD} mm  "
      f"(innermost OUTSIDE cut at r = {OUTER_CUT_R0*1000:.1f} um)")
print(f"  Finished inner hole r = {FINISHED_INNER_R} mm  "
      f"(outermost INSIDE cut at r = {INNER_CUT_R0*1000:.1f} um)")
print(f"  {N_SLOTS} slots, r = {SLOT_R_INNER:.3f} .. {SLOT_R_OUTER:.3f} mm")
print(f"  Regular slots (INSIDE, blue): {SLOT_WIDTH*1000:.0f} um wide, "
      f"{KERF_LINES} cuts each")
print(f"  Wider partial slots (PARTIAL, red): {PARTIAL_SLOT_WIDTH*1000:.0f} um wide, "
      f"{PARTIAL_KERF_LINES} cuts each, at angles 0 and pi, "
      f"r = {PARTIAL_SLOT_R_INNER:.3f} .. {SLOT_R_OUTER:.3f} mm "
      f"(opens into inner hole)")
print(f"  Inner cut radii  (um): "
      f"{[round(r*1000,1) for r in INNER_CUT_RADII]}")
print(f"  Outer cut radii  (um): "
      f"{[round(r*1000,1) for r in OUTER_CUT_RADII]}")


# -- Pen settings ----------------------------------------------------
pen_settings = f"""\
EZCAD2 Pen Settings for slotted_disk_3p5.dxf
=============================================
ONE slotted graphite disk, finished OD = {FINISHED_OD} mm, inner hole
radius = {FINISHED_INNER_R} mm, {N_SLOTS} radial slots extending to the
outer edge (no eddy-current ring remains).

The two slots on the horizontal axis (at angles 0 and pi) get an
EXTRA wider cut on a separate pen, OVERLAID on the regular slot cuts.
INSIDE still cuts all 16 slots through; PARTIAL adds a {PARTIAL_SLOT_WIDTH*1000:.0f} um wide
overlay that extends in to the inner hole (so the sail tab can sit
in the resulting wider partial-depth groove). Run PARTIAL at half
the cycles of the other pens.

Same verified through-cut recipe used elsewhere in this folder:
  4 cuts at 25 um spacing (75 um kerf), 20 processes (Loop Count),
  2000 mm/s, 75 % power, Mark Count ~ 20-30 cycles.

Kerf correction is applied so the finished disk edges land exactly at
the nominal radii (assuming a {KERF*1000:.0f} um kerf).

Three pens / layers in the DXF:
  Blue   (ACI 5)  INSIDE   14 regular slots + inner cutout
  Black  (ACI 7)  OUTSIDE  outer perimeter
  Red    (ACI 1)  PARTIAL  2 wider slots on the horizontal axis (partial depth)


-----------------------------------------------------------------
PEN 1: INSIDE   (BLUE entities)
-----------------------------------------------------------------
  Power:       75 %
  Speed:       2000 mm/s
  Loop Count:  20
  End TC:      0 ms


-----------------------------------------------------------------
PEN 2: OUTSIDE   (BLACK entities)
-----------------------------------------------------------------
  Power:       75 %
  Speed:       2000 mm/s
  Loop Count:  20
  End TC:      0 ms


-----------------------------------------------------------------
PEN 3: PARTIAL   (RED entities)
-----------------------------------------------------------------
  Same parameters as INSIDE/OUTSIDE, but HALF the Loop Count so this
  pen only cuts partway through the graphite:

  Power:       75 %
  Speed:       2000 mm/s
  Loop Count:  10   (= half of the other pens' 20)
  End TC:      0 ms

  Alternative: leave Loop Count = 20 and run the file twice -- first
  pass with PARTIAL enabled, then disable PARTIAL and run again with
  the same Mark Count. Either way works; pen-level Loop Count is
  simpler.


-----------------------------------------------------------------
GLOBAL SETTINGS  (F2 Mark dialog)
-----------------------------------------------------------------
  Mark Count:  20-30
  Pen order in pen list (drag vertically -- top runs first):
    1. INSIDE   2. PARTIAL   3. OUTSIDE
"""
with open("slotted_disk_3p5_pen_settings.txt", "w") as f:
    f.write(pen_settings)
print("Saved slotted_disk_3p5_pen_settings.txt")


# -- Preview ---------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(14, 7))
layer_colors = {"INSIDE": "tab:blue", "OUTSIDE": "black", "PARTIAL": "tab:red"}

ax = axes[0]
ax.add_patch(plt.Circle((0, 0), FINISHED_OR,
                        fill=True, fc="#dddddd", ec="none"))
for p1, p2, layer in preview_lines:
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]],
            color=layer_colors[layer], lw=0.5, alpha=0.85)
for r, layer in preview_circles:
    ax.add_patch(plt.Circle((0, 0), r, fill=False,
                            ec=layer_colors[layer], lw=0.6, alpha=0.9))
m = OUTER_CUT_RADII[-1] + 0.3
ax.set_xlim(-m, m); ax.set_ylim(-m, m); ax.set_aspect("equal")
ax.set_xlabel("mm"); ax.set_ylabel("mm")
ax.set_title(f"slotted_disk_3p5.dxf -- finished OD = {FINISHED_OD} mm")
ax.grid(True, alpha=0.3)

ax = axes[1]
ax.add_patch(plt.Circle((0, 0), FINISHED_OR,
                        fill=True, fc="#dddddd", ec="none"))
for p1, p2, layer in preview_lines:
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]],
            color=layer_colors[layer], lw=0.7, alpha=0.9)
for r, layer in preview_circles:
    ax.add_patch(plt.Circle((0, 0), r, fill=False,
                            ec=layer_colors[layer], lw=0.7, alpha=0.9))
ax.set_xlim(-0.15, 0.15); ax.set_ylim(0.45, 0.95)
ax.set_aspect("equal")
ax.set_xlabel("mm"); ax.set_ylabel("mm")
ax.set_title("Zoom -- slot inner end + inner cutout boundary")
ax.grid(True, alpha=0.3)

fig.tight_layout()
fig.savefig("slotted_disk_3p5_preview.png", dpi=200, bbox_inches="tight")
plt.close()
print("Saved slotted_disk_3p5_preview.png")
