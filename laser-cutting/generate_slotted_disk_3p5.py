"""
Generate a DXF for cutting ONE slotted graphite disk:
  - Finished outer diameter: 3.5 mm
  - Inner hole radius: 0.55 mm (1.1 mm OD hole)
  - 16 symmetric radial slots extending all the way to the outer edge
    (no eddy-current ring remains)

All cuts now use a 6-line kerf pattern (125 um wide) -- the previous
4-line / 75 um pattern was too narrow to fit the sail tab, and the
various "partial" / "asymmetric extra-wide slot" tricks broke the
disk. By making every slot 6 lines wide, the disk stays symmetric
AND the sail can be sized to fit.

The slot inner radius is shifted outward so the material bridge
between adjacent slots at the slot inner end (the thinnest spot --
arc length r*Delta_theta - slot_width) is the same as the 4-line
baseline (r = 0.75 mm, w = 75 um). Inner hole and outer perimeter
finished dimensions are unchanged.

Two pens:
  INSIDE  (blue,  ACI 5) -- 16 slots + inner circle cutout
  OUTSIDE (black, ACI 7) -- outer perimeter

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
FINISHED_OR       = FINISHED_OD / 2.0       # 1.75 mm
FINISHED_INNER_R  = 0.55                     # inner hole radius
N_SLOTS           = 16

# Kerf pattern -- now 6 lines on every cut group ---------------------
KERF              = 0.020                    # ~20 um laser kerf
KERF_STEP         = 0.025                    # 25 um between parallel cuts
KERF_LINES        = 6                        # was 4 in the original
SLOT_WIDTH        = (KERF_LINES - 1) * KERF_STEP   # = 125 um

# Slot inner radius is shifted outward so the inner-end arc bridge
# between adjacent slots ( = r*(2*pi/N) - slot_width ) is the same as
# the 4-line baseline ( r = 0.75 mm, w = 75 um ).
SLOT_ANGULAR_SPACING = 2 * np.pi / N_SLOTS
_BASELINE_INNER_R    = 0.75
_BASELINE_WIDTH      = 0.075                 # = (4-1) * KERF_STEP
SLOT_R_INNER         = _BASELINE_INNER_R \
                       + (SLOT_WIDTH - _BASELINE_WIDTH) / SLOT_ANGULAR_SPACING


# -- Kerf-corrected cut radii ----------------------------------------
# Outer perimeter: finished edge = inner kerf wall of innermost cut
OUTER_CUT_R0      = FINISHED_OR + KERF / 2.0
OUTER_CUT_RADII   = [OUTER_CUT_R0 + i * KERF_STEP for i in range(KERF_LINES)]

# Inner hole: finished inner edge = outer kerf wall of outermost cut
INNER_CUT_R0      = FINISHED_INNER_R - KERF / 2.0
INNER_CUT_RADII   = [INNER_CUT_R0 - i * KERF_STEP for i in range(KERF_LINES)]

# Slots run to the innermost perimeter cut so the wedges separate
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
      - parallel radial lines at KERF_STEP spacing
      - interleaved transverse end-cap lines at the inner end
    """
    c, s = np.cos(angle), np.sin(angle)
    r_hat = np.array([c, s])
    t_hat = np.array([-s, c])       # 90 CCW from radial

    hw = slot_width / 2.0
    lines = []

    for off in interleaved_offsets(slot_width, step):
        shift = t_hat * off
        p1 = r_hat * r_inner + shift
        p2 = r_hat * r_outer + shift
        lines.append((tuple(p1), tuple(p2)))

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
msp = doc.modelspace()

preview_lines   = []
preview_circles = []

# All 16 slots on INSIDE pen
slot_angles = np.linspace(0, 2 * np.pi, N_SLOTS, endpoint=False)
for a in slot_angles:
    for p1, p2 in slot_lines(a, SLOT_R_INNER, SLOT_R_OUTER,
                             SLOT_WIDTH, KERF_STEP,
                             cap_inner=True, cap_outer=False):
        msp.add_line(p1, p2, dxfattribs={"layer": "INSIDE", "color": 5})
        preview_lines.append((p1, p2, "INSIDE"))

# Inner circle cutout (interleaved)
for r in interleaved(INNER_CUT_RADII):
    msp.add_circle((0, 0), r, dxfattribs={"layer": "INSIDE", "color": 5})
    preview_circles.append((r, "INSIDE"))

# Outer perimeter (interleaved)
for r in interleaved(OUTER_CUT_RADII):
    msp.add_circle((0, 0), r, dxfattribs={"layer": "OUTSIDE", "color": 7})
    preview_circles.append((r, "OUTSIDE"))

doc.saveas("slotted_disk_3p5.dxf")

# Inner-end arc bridge between adjacent slots (sanity-check)
_bridge_old = _BASELINE_INNER_R * SLOT_ANGULAR_SPACING - _BASELINE_WIDTH
_bridge_new = SLOT_R_INNER       * SLOT_ANGULAR_SPACING - SLOT_WIDTH

print("Saved slotted_disk_3p5.dxf")
print(f"  Finished OD = {FINISHED_OD} mm  "
      f"(innermost OUTSIDE cut at r = {OUTER_CUT_R0*1000:.1f} um)")
print(f"  Finished inner hole r = {FINISHED_INNER_R} mm  "
      f"(outermost INSIDE cut at r = {INNER_CUT_R0*1000:.1f} um)")
print(f"  {N_SLOTS} slots, r = {SLOT_R_INNER:.3f} .. {SLOT_R_OUTER:.3f} mm "
      f"(length {SLOT_R_OUTER - SLOT_R_INNER:.3f} mm)")
print(f"  All cuts: {KERF_LINES} parallel cuts at {KERF_STEP*1000:.0f} um "
      f"= {SLOT_WIDTH*1000:.0f} um kerf")
print(f"  Slot inner radius shifted "
      f"{_BASELINE_INNER_R*1000:.0f} -> {SLOT_R_INNER*1000:.0f} um "
      f"to preserve inner-end material bridge")
print(f"  Inner-end bridge length: baseline {_bridge_old*1000:.1f} um, "
      f"new {_bridge_new*1000:.1f} um")
print(f"  Inner cut radii  (um): "
      f"{[round(r*1000,1) for r in INNER_CUT_RADII]}")
print(f"  Outer cut radii  (um): "
      f"{[round(r*1000,1) for r in OUTER_CUT_RADII]}")


# -- Pen settings ----------------------------------------------------
pen_settings = f"""\
EZCAD2 Pen Settings for slotted_disk_3p5.dxf
=============================================
ONE slotted graphite disk, finished OD = {FINISHED_OD} mm, inner hole
radius = {FINISHED_INNER_R} mm, {N_SLOTS} symmetric radial slots extending to
the outer edge (no eddy-current ring remains).

All cuts use a {KERF_LINES}-line / {SLOT_WIDTH*1000:.0f} um kerf pattern (was 4-line / 75 um).
The slot inner radius is shifted outward from {_BASELINE_INNER_R} to
{SLOT_R_INNER:.3f} mm so the material bridge between adjacent slots at
the slot inner end is the same as the 4-line baseline (about
{_bridge_new*1000:.0f} um arc length). Inner hole and outer perimeter
finished dimensions are unchanged.

Same through-cut recipe as before, but {KERF_LINES} cuts now:
  {KERF_LINES} cuts at 25 um spacing ({SLOT_WIDTH*1000:.0f} um kerf), 20 processes
  (Loop Count), 2000 mm/s, 75 % power, Mark Count ~ 20-30 cycles.

Kerf correction is applied so the finished disk edges land exactly at
the nominal radii (assuming a {KERF*1000:.0f} um kerf).

Two pens / layers in the DXF:
  Blue   (ACI 5)  INSIDE   {N_SLOTS} slots + inner cutout
  Black  (ACI 7)  OUTSIDE  outer perimeter


-----------------------------------------------------------------
PEN 0: INSIDE   (BLUE)
-----------------------------------------------------------------
  Power:       75 %
  Speed:       2000 mm/s
  Loop Count:  20
  End TC:      0 ms


-----------------------------------------------------------------
PEN 1: OUTSIDE   (BLACK)
-----------------------------------------------------------------
  Power:       75 %
  Speed:       2000 mm/s
  Loop Count:  20
  End TC:      0 ms


-----------------------------------------------------------------
GLOBAL SETTINGS  (F2 Mark dialog)
-----------------------------------------------------------------
  Mark Count:  20-30
  Pen order in pen list (drag vertically -- top runs first):
    1. INSIDE   2. OUTSIDE
"""
with open("slotted_disk_3p5_pen_settings.txt", "w") as f:
    f.write(pen_settings)
print("Saved slotted_disk_3p5_pen_settings.txt")


# -- Preview ---------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(14, 7))
layer_colors = {"INSIDE": "tab:blue", "OUTSIDE": "black"}

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
ax.set_title(f"slotted_disk_3p5.dxf -- finished OD = {FINISHED_OD} mm, "
             f"{SLOT_WIDTH*1000:.0f}-um slots")
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
ax.set_xlim(-0.2, 0.2); ax.set_ylim(0.45, 1.05)
ax.set_aspect("equal")
ax.set_xlabel("mm"); ax.set_ylabel("mm")
ax.set_title("Zoom -- slot inner end + inner cutout boundary")
ax.grid(True, alpha=0.3)

fig.tight_layout()
fig.savefig("slotted_disk_3p5_preview.png", dpi=200, bbox_inches="tight")
plt.close()
print("Saved slotted_disk_3p5_preview.png")
