"""
Generate DXF files for laser-cut graphite disk with radial slots
to suppress eddy currents.

Produces two files:
  - slots.dxf:   internal radial cuts (interleaved parallel lines)
  - outline.dxf: outer circle cutout (run after slots are done)

Slots are cut as interleaved parallel lines to avoid slotting out walls
in thick material. E.g. for 75 µm slot at 25 µm step:
  offsets 0, 25, 50, 75 → cut order 0, 50, 25, 75 (evens first, then odds)
"""

import numpy as np
import ezdxf
import matplotlib.pyplot as plt

# ── Parameters (all in mm) ──────────────────────────────────────────
OUTER_RADIUS = 2.0            # disk outer radius

N_OUTER_SLOTS = 16            # number of outer radial slots
OUTER_SLOT_WIDTH = 0.100      # 100 µm
RING_GAP = 0.200              # 200 µm gap between inner and outer rings
RING_BOUNDARY = 0.65          # nominal boundary between inner/outer rings
OUTER_SLOT_R_INNER = RING_BOUNDARY + RING_GAP / 2   # = 0.75 mm
OUTER_SLOT_R_OUTER = OUTER_RADIUS                    # all the way to edge

INNER_CIRCLE_RADIUS = RING_BOUNDARY - RING_GAP / 2   # = 0.55 mm (open hole)

LINE_STEP = 0.025             # 25 µm step between parallel cut lines


# ── Derived angles ──────────────────────────────────────────────────
OUTER_ANGLES = np.linspace(0, 2 * np.pi, N_OUTER_SLOTS, endpoint=False)


# ── Geometry helpers ────────────────────────────────────────────────
def interleaved_offsets(slot_width, step):
    """
    Generate transverse offsets for parallel cut lines in interleaved order.
    Evens first (0, 2, 4, ...), then odds (1, 3, 5, ...) to maximize
    distance between consecutive cuts.

    Offsets are centered on the slot (range: -slot_width/2 to +slot_width/2).
    """
    n_lines = int(round(slot_width / step)) + 1
    positions = np.linspace(-slot_width / 2, slot_width / 2, n_lines)
    # Interleave: even indices first, then odd
    even_idx = list(range(0, n_lines, 2))
    odd_idx = list(range(1, n_lines, 2))
    order = even_idx + odd_idx
    return positions[order]


def slot_lines(angle, r_inner, r_outer, slot_width, step,
               cap_inner=True, cap_outer=True):
    """
    Return list of (start, end) line segments for one slot:
      - Interleaved parallel radial lines
      - Transverse end-cap lines (optionally at inner/outer ends)
    """
    c, s = np.cos(angle), np.sin(angle)
    r_hat = np.array([c, s])
    t_hat = np.array([-s, c])  # 90° CCW from radial

    offsets = interleaved_offsets(slot_width, step)
    hw = slot_width / 2.0
    lines = []

    # Interleaved radial lines
    for off in offsets:
        shift = t_hat * off
        p1 = r_hat * r_inner + shift
        p2 = r_hat * r_outer + shift
        lines.append((tuple(p1), tuple(p2)))

    # End-cap lines: interleaved parallel transverse cuts recessed INTO the slot
    n_cap = int(round(slot_width / step))
    cap_positions = np.arange(n_cap + 1) * step
    # Interleave: evens first, then odds
    even_idx = list(range(0, len(cap_positions), 2))
    odd_idx = list(range(1, len(cap_positions), 2))
    cap_order = even_idx + odd_idx
    cap_positions = cap_positions[cap_order]

    caps = []
    if cap_inner:
        caps.append((r_inner, +1))
    if cap_outer:
        caps.append((r_outer, -1))

    for r, sign in caps:
        for off in cap_positions:
            base = r_hat * (r + sign * off)
            p_left = base + t_hat * (-hw)
            p_right = base + t_hat * hw
            lines.append((tuple(p_left), tuple(p_right)))

    return lines


# ── Build interleaved cut lines ────────────────────────────────────
outer_offsets = interleaved_offsets(OUTER_SLOT_WIDTH, LINE_STEP)

print(f"Outer slots: {len(outer_offsets)} radial lines per slot "
      f"(offsets: {np.round(outer_offsets * 1000, 1)} µm)")
print(f"Inner circle cutout at r = {INNER_CIRCLE_RADIUS} mm")

all_lines = []  # (start, end) tuples for all cut lines

# Outer slots (no outer end cap — outline circles will cut there)
for angle in OUTER_ANGLES:
    all_lines.extend(slot_lines(angle, OUTER_SLOT_R_INNER,
                                OUTER_SLOT_R_OUTER, OUTER_SLOT_WIDTH,
                                LINE_STEP, cap_outer=False))


# ── Write slots DXF ────────────────────────────────────────────────
doc_slots = ezdxf.new("R2010")
msp_slots = doc_slots.modelspace()

for p1, p2 in all_lines:
    msp_slots.add_line(p1, p2)

doc_slots.saveas("slots.dxf")
print(f"Saved slots.dxf ({len(all_lines)} lines)")


# ── Write outline DXF ──────────────────────────────────────────────
doc_outline = ezdxf.new("R2010")
msp_outline = doc_outline.modelspace()

def interleaved_circles(msp, center_radius, n_circles, step, grow_inward=True):
    """Add interleaved concentric circles to modelspace."""
    if grow_inward:
        radii = [center_radius - i * step for i in range(n_circles)]
    else:
        radii = [center_radius + i * step for i in range(n_circles)]
    even_idx = list(range(0, len(radii), 2))
    odd_idx = list(range(1, len(radii), 2))
    order = even_idx + odd_idx
    for idx in order:
        msp.add_circle((0, 0), radii[idx])
    return [radii[i] for i in order]

# Outer circle cutout: interleaved circles growing inward from outer edge
n_outer = int(round(OUTER_SLOT_WIDTH / LINE_STEP)) + 1
outer_r = interleaved_circles(msp_outline, OUTER_RADIUS, n_outer, LINE_STEP,
                              grow_inward=True)
print(f"Outer outline: {n_outer} circles at r = "
      f"{[round(r*1000, 1) for r in outer_r]} µm")

# Inner circle cutout: interleaved circles growing outward from inner edge
n_inner = int(round(OUTER_SLOT_WIDTH / LINE_STEP)) + 1
inner_r = interleaved_circles(msp_outline, INNER_CIRCLE_RADIUS, n_inner,
                              LINE_STEP, grow_inward=False)
print(f"Inner outline: {n_inner} circles at r = "
      f"{[round(r*1000, 1) for r in inner_r]} µm")

doc_outline.saveas("outline.dxf")
print("Saved outline.dxf")


# ── Simple outline DXFs (outer edge only) ─────────────────────────
for spacing_um, suffix in [(10, "10um"), (20, "20um")]:
    spacing = spacing_um / 1000.0  # convert to mm
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    interleaved_circles(msp, OUTER_RADIUS, 5, spacing, grow_inward=False)
    fname = f"outline_simple_{suffix}.dxf"
    doc.saveas(fname)
    radii = [OUTER_RADIUS + i * spacing for i in range(5)]
    print(f"Saved {fname} (5 circles, radii: "
          f"{[round(r*1000, 1) for r in radii]} µm)")


# ── 2-pen outline (deep + cleanup) ────────────────────────────────
# For Monport 50W fiber laser using EZCAD2 with two pens:
#   Pen 1 "DEEP"   (red,   ACI=1): full-power penetration cut, multiple
#                                  passes if needed, mark-end-delay set
#                                  to let smoke clear
#   Pen 2 "CLEANUP" (green, ACI=3): low-power edge cleanup, single pass
#
# Cleanup is offset 10 µm outward from the deep cut. With ~20 µm kerf
# this overlaps the deep kerf edge and cleans the wall.
KERF = 0.020                      # 20 µm assumed laser kerf
DEEP_RADIUS = OUTER_RADIUS        # set to OUTER_RADIUS + KERF/2 for exact 2 mm edge
CLEANUP_OFFSET = 0.010            # 10 µm cleanup offset

doc_2pen = ezdxf.new("R2010")
doc_2pen.layers.add("DEEP", color=5)       # blue   → EZCAD2 pen 1 (deep, 80%)
doc_2pen.layers.add("CLEANUP", color=7)    # white/black → EZCAD2 pen 0 (cleanup, 50%)
msp_2pen = doc_2pen.modelspace()
# Deep cut
msp_2pen.add_circle((0, 0), DEEP_RADIUS,
                    dxfattribs={"layer": "DEEP", "color": 5})
# Cleanup on both sides: inward (cleans disk edge) + outward (widens kerf)
msp_2pen.add_circle((0, 0), DEEP_RADIUS - CLEANUP_OFFSET,
                    dxfattribs={"layer": "CLEANUP", "color": 7})
msp_2pen.add_circle((0, 0), DEEP_RADIUS + CLEANUP_OFFSET,
                    dxfattribs={"layer": "CLEANUP", "color": 7})
doc_2pen.saveas("outline_2pen.dxf")
print(f"Saved outline_2pen.dxf "
      f"(DEEP @ {DEEP_RADIUS*1000:.0f} µm red, "
      f"CLEANUP @ {(DEEP_RADIUS-CLEANUP_OFFSET)*1000:.0f} & "
      f"{(DEEP_RADIUS+CLEANUP_OFFSET)*1000:.0f} µm green)")


# ── Working-recipe outline (4-circle kerf + cleanup + pause pen) ──
# Mimics the verified through-cut pattern from the lab notebook:
#   4 cuts at 0, 25, 50, 75 µm spacing (75 µm wide kerf),
#   20 processes, 2000 mm/s, 75% power, ~20-30 reps.
# Adds:
#   - Cleanup pen (light pass on both sides of kerf for wall finish)
#   - Pause pen (slow no-laser line that acts as smoke-clear delay,
#                in case EZCAD2 End TC delay isn't working)
KERF_LINES = 4                   # number of parallel cuts (matches working file)
KERF_STEP = 0.025                # 25 µm between cuts
PAUSE_LINE_LENGTH = 10.0         # 10 mm long pause line
PAUSE_LINE_OFFSET = 10.0         # placed at x = 10 mm (well outside 2 mm disk)

doc_w = ezdxf.new("R2010")
doc_w.layers.add("DEEP", color=5)       # blue  — pen 1 (75% power)
doc_w.layers.add("CLEANUP", color=7)    # black — pen 0 (50% power)
doc_w.layers.add("PAUSE", color=2)      # yellow — pen 2 (0% power, slow)
msp_w = doc_w.modelspace()

# Deep cut: 4 concentric circles at r = R, R+25, R+50, R+75 µm
# Interleaved order: 0, 50, 25, 75 (evens first then odds) for heat spread
deep_radii = [OUTER_RADIUS + i * KERF_STEP for i in range(KERF_LINES)]
even_idx = list(range(0, KERF_LINES, 2))
odd_idx = list(range(1, KERF_LINES, 2))
for idx in even_idx + odd_idx:
    msp_w.add_circle((0, 0), deep_radii[idx],
                     dxfattribs={"layer": "DEEP", "color": 5})

# Cleanup: 2 circles bracketing the deep kerf (10 µm inside innermost,
# 10 µm outside outermost) — same offset as before so params transfer to slots
cleanup_inner = deep_radii[0] - CLEANUP_OFFSET   # = 1.990 mm
cleanup_outer = deep_radii[-1] + CLEANUP_OFFSET  # = 2.085 mm
msp_w.add_circle((0, 0), cleanup_inner,
                 dxfattribs={"layer": "CLEANUP", "color": 7})
msp_w.add_circle((0, 0), cleanup_outer,
                 dxfattribs={"layer": "CLEANUP", "color": 7})

# Pause pen: a single line outside the work piece. At slow speed with
# laser power = 0, the galvos move but nothing marks. Length/speed sets
# the pause duration (e.g. 10 mm at 10 mm/s = 1 s).
msp_w.add_line((PAUSE_LINE_OFFSET, 0),
               (PAUSE_LINE_OFFSET, PAUSE_LINE_LENGTH),
               dxfattribs={"layer": "PAUSE", "color": 2})

doc_w.saveas("outline_2pen_working.dxf")
print(f"Saved outline_2pen_working.dxf")
print(f"  DEEP    (blue)  : {KERF_LINES} circles, r = "
      f"{[round(r*1000) for r in deep_radii]} µm")
print(f"  CLEANUP (black) : 2 circles, r = "
      f"[{round(cleanup_inner*1000)}, {round(cleanup_outer*1000)}] µm")
print(f"  PAUSE   (yellow): 1 line, {PAUSE_LINE_LENGTH} mm long "
      f"at x = {PAUSE_LINE_OFFSET} mm")


# ── Pen settings text file ────────────────────────────────────────
pen_settings = """\
EZCAD2 Pen Settings for outline_2pen_working.dxf
=================================================
Based on the verified through-cut recipe from lab notes:
  20 processes (Loop Count), 2000 mm/s, 75% power,
  repeated ~20-30 times (Mark Count) — went through 0.5 mm graphite
  without damaging Al backing.

The file has THREE colored entities:
  Blue  (ACI 5) — DEEP cut pen
  Black (ACI 7) — CLEANUP pen
  Yellow (ACI 2) — PAUSE pen (acts as smoke-clear delay)


-----------------------------------------------------------------
PEN: DEEP   (assign to BLUE entities)
-----------------------------------------------------------------
  Geometry:    4 concentric circles, r = 2.000, 2.025, 2.050, 2.075 mm
  Power:       75 %
  Speed:       2000 mm/s
  Frequency:   your usual MOPA/Q-switch frequency (e.g. 20-50 kHz)
  Loop Count:  20      (passes per Mark cycle — from working recipe)
  Start TC:    0 ms
  End TC:      1000 ms (try this; if EZCAD ignores it, the PAUSE
                        pen below does the same job)


-----------------------------------------------------------------
PEN: CLEANUP   (assign to BLACK entities)
-----------------------------------------------------------------
  Geometry:    2 concentric circles, r = 1.990 mm (inner)
                                       2.085 mm (outer)
  Power:       50 %
  Speed:       2000 mm/s
  Frequency:   same as DEEP
  Loop Count:  5       (lighter pass — adjust if walls still rough)
  Start TC:    0 ms
  End TC:      1000 ms


-----------------------------------------------------------------
PEN: PAUSE   (assign to YELLOW entity)
-----------------------------------------------------------------
  Geometry:    1 line, 10 mm long, placed at x = 10 mm (off-work-piece)
  Power:       0 %      (laser does NOT fire — galvos just traverse)
  Speed:       10 mm/s  (line is 10 mm, so takes 1.0 s = 1 s pause)
  Frequency:   any
  Loop Count:  1

  Notes on the pause pen:
    - With Power = 0, the laser is disabled and nothing marks.
      The galvo head still moves at the configured speed, so the
      execution time equals (line_length / speed).
    - To change the pause duration, edit either the line length
      in the DXF or the speed setting on this pen.
        Example: 50 mm/s on a 10 mm line → 0.2 s pause
        Example: 5 mm/s on a 10 mm line → 2.0 s pause
    - The line is placed 10 mm off the disk (at x = 10 mm) so even
      if some residual power gets through, it won't hit the part.


-----------------------------------------------------------------
GLOBAL SETTINGS  (F2 Mark dialog / right-side panel)
-----------------------------------------------------------------
  Mark Count:  20-30     (number of times the whole sequence repeats;
                          start at 20 and check if it's through;
                          add more reps if not)

  Pen ORDER in pen list (drag pens vertically — top runs first):
    1. DEEP    (heavy penetration cut)
    2. PAUSE   (smoke clears)
    3. CLEANUP (smooths the kerf walls)


-----------------------------------------------------------------
TUNING NOTES
-----------------------------------------------------------------
- If End TC delays DO work for you, you can delete the PAUSE pen
  from the design and just use End TC = 1000 ms on DEEP.
- If you see the disk separating before all reps finish, that's
  fine — extra reps on through-cut just polish the edge.
- If walls are still rough after CLEANUP, try:
    * More CLEANUP Loop Count (5 -> 10)
    * Lower CLEANUP power (50% -> 30%)
- If the disk's outer radius comes out smaller than 2 mm (it will,
  by ~kerf/2 ≈ 10 µm), shift the DEEP_RADIUS in
  generate_eddy_current_disk.py up by 10 µm and re-run.
"""

# (pen_settings string is replaced below by the full-disk version,
#  so we skip writing it here)


# ── FULL DISK PATTERN ────────────────────────────────────────────
# Combined DXF mirroring the verified working recipe (4 cuts at 25 µm
# spacing = 75 µm wide kerf). Three pens:
#   INSIDE  (blue, ACI 5)  — 16 radial slots + inner circle cutout
#   OUTSIDE (black, ACI 7) — outer perimeter (4-line kerf)
#   DELAY   (yellow, ACI 2) — single circle for optional smoke-clear pause
# Geometry: 4.5 mm OD (R = 2.25), nominal inner hole R = 0.55 mm,
# 200 µm structural gap between inner cutout and slot inner ends,
# 16 slots extending all the way to the outer edge so no eddy-current
# ring remains after cutting.

FULL_OUTER_RADIUS = 1.625   # 3.25 mm OD
FULL_INNER_RADIUS = 0.55
FULL_N_SLOTS = 16
FULL_KERF_STEP = 0.025
FULL_KERF_LINES = 4
FULL_SLOT_WIDTH = (FULL_KERF_LINES - 1) * FULL_KERF_STEP   # 75 µm
FULL_RING_GAP = 0.200
FULL_SLOT_R_INNER = FULL_INNER_RADIUS + FULL_RING_GAP      # 0.75 mm
FULL_SLOT_R_OUTER = FULL_OUTER_RADIUS                       # extends to edge
FULL_DELAY_RADIUS = 2.50

doc_full = ezdxf.new("R2010")
doc_full.layers.add("INSIDE", color=5)
doc_full.layers.add("OUTSIDE", color=7)
doc_full.layers.add("DELAY", color=2)
msp_full = doc_full.modelspace()

# Track entities for the preview plot
full_lines_list = []      # (p1, p2, layer)
full_circles_list = []    # (radius, layer)

# INSIDE pen: 16 slots
slot_angles_full = np.linspace(0, 2*np.pi, FULL_N_SLOTS, endpoint=False)
for angle in slot_angles_full:
    lines = slot_lines(angle, FULL_SLOT_R_INNER, FULL_SLOT_R_OUTER,
                       FULL_SLOT_WIDTH, FULL_KERF_STEP,
                       cap_inner=True, cap_outer=False)
    for p1, p2 in lines:
        msp_full.add_line(p1, p2,
                          dxfattribs={"layer": "INSIDE", "color": 5})
        full_lines_list.append((p1, p2, "INSIDE"))

# INSIDE pen: inner circle cutout — 4 concentric circles, interleaved,
# growing inward from FULL_INNER_RADIUS
inner_cut_radii = [FULL_INNER_RADIUS - i * FULL_KERF_STEP
                   for i in range(FULL_KERF_LINES)]
e_idx = list(range(0, FULL_KERF_LINES, 2))
o_idx = list(range(1, FULL_KERF_LINES, 2))
for idx in e_idx + o_idx:
    msp_full.add_circle((0, 0), inner_cut_radii[idx],
                        dxfattribs={"layer": "INSIDE", "color": 5})
    full_circles_list.append((inner_cut_radii[idx], "INSIDE"))

# OUTSIDE pen: 4 concentric circles, interleaved, growing outward
outer_cut_radii = [FULL_OUTER_RADIUS + i * FULL_KERF_STEP
                   for i in range(FULL_KERF_LINES)]
for idx in e_idx + o_idx:
    msp_full.add_circle((0, 0), outer_cut_radii[idx],
                        dxfattribs={"layer": "OUTSIDE", "color": 7})
    full_circles_list.append((outer_cut_radii[idx], "OUTSIDE"))

# DELAY pen: single circle outside the disk
msp_full.add_circle((0, 0), FULL_DELAY_RADIUS,
                    dxfattribs={"layer": "DELAY", "color": 2})
full_circles_list.append((FULL_DELAY_RADIUS, "DELAY"))

doc_full.saveas("disk_full.dxf")
print(f"Saved disk_full.dxf")
print(f"  INSIDE  (blue)  : {FULL_N_SLOTS} slots ({FULL_KERF_LINES} radial "
      f"+ {FULL_KERF_LINES} end-cap lines each) + 4 inner circles @ "
      f"r = {[round(r*1000) for r in inner_cut_radii]} µm")
print(f"  OUTSIDE (black) : 4 outer circles @ "
      f"r = {[round(r*1000) for r in outer_cut_radii]} µm")
print(f"  DELAY   (yellow): 1 circle @ r = {FULL_DELAY_RADIUS*1000:.0f} µm")


# ── Pen settings text file (for disk_full.dxf) ───────────────────
full_circ = 2 * np.pi * FULL_DELAY_RADIUS  # delay circle circumference
pen_settings = f"""\
EZCAD2 Pen Settings for disk_full.dxf
======================================
Based on the verified through-cut recipe from lab notes:
  4 cuts at 25 µm spacing (75 µm total kerf width),
  20 processes (Loop Count), 2000 mm/s, 75% power,
  Mark Count ~20-30 cycles → through 0.5 mm graphite,
  no damage to Al backing.

GEOMETRY (R = {FULL_OUTER_RADIUS} mm = {FULL_OUTER_RADIUS*2} mm OD)
  Inner hole radius (nominal): {FULL_INNER_RADIUS} mm
  Slots: {FULL_N_SLOTS} radial, from r = {FULL_SLOT_R_INNER:.3f} mm
         to r = {FULL_SLOT_R_OUTER:.3f} mm (extends to outer edge)
  Slot width: {FULL_SLOT_WIDTH*1000:.0f} µm (4 parallel cuts at 25 µm spacing)
  Outer perimeter: 4 circles at r = {[round(r,3) for r in outer_cut_radii]} mm
  Delay circle: r = {FULL_DELAY_RADIUS} mm (off the workpiece)

The DXF has THREE colored layers, each on its own pen:
  Blue   (ACI 5) — INSIDE  pen: slots + inner cutout
  Black  (ACI 7) — OUTSIDE pen: outer perimeter
  Yellow (ACI 2) — DELAY   pen: optional pause (no marking)


-----------------------------------------------------------------
PEN 1: INSIDE   (BLUE entities)
-----------------------------------------------------------------
  Power:       75 %
  Speed:       2000 mm/s
  Frequency:   your usual MOPA/Q-switch frequency
  Loop Count:  20      (matches "20 processes" in working recipe)
  Start TC:    0 ms
  End TC:      0 ms    (rely on DELAY pen instead)


-----------------------------------------------------------------
PEN 2: OUTSIDE   (BLACK entities)
-----------------------------------------------------------------
  Power:       75 %
  Speed:       2000 mm/s
  Frequency:   same as INSIDE
  Loop Count:  20
  Start TC:    0 ms
  End TC:      0 ms


-----------------------------------------------------------------
PEN 3: DELAY   (YELLOW entity)
-----------------------------------------------------------------
  Power:       0 %       (laser does NOT fire — galvos traverse only)
  Speed:       {full_circ:.1f} mm/s   (delay circle circumference is
                                       {full_circ:.2f} mm so 1 pass at this
                                       speed takes 1.00 s)
  Frequency:   any
  Loop Count:  1

  Notes:
    - The delay circle has circumference 2π × {FULL_DELAY_RADIUS} mm
      = {full_circ:.2f} mm. Time per pass = circumference / speed.
    - For longer pauses, slow this pen down (e.g. speed = {full_circ/2:.1f}
      mm/s gives 2.0 s; speed = {full_circ*2:.1f} mm/s gives 0.5 s).
    - To disable the delay entirely, set Loop Count = 0 on this pen
      (or untick it in the pen list).


-----------------------------------------------------------------
GLOBAL SETTINGS  (F2 Mark dialog)
-----------------------------------------------------------------
  Mark Count:  20-30      (each cycle does 20 INSIDE passes, then 20
                           OUTSIDE passes, then 1 DELAY pause; start at
                           20, add more if not through)

  Pen ORDER in pen list (drag vertically — top runs first):
    1. INSIDE  (slots + inner cutout — biggest material removal)
    2. OUTSIDE (perimeter — frees the disk)
    3. DELAY   (smoke clears before next cycle starts)


-----------------------------------------------------------------
NOTES
-----------------------------------------------------------------
- Kerf width: ~20 µm. The disk's actual OD will end up ~10 µm smaller
  than nominal (so ~4.48 mm). Bump FULL_OUTER_RADIUS up by 10 µm
  in generate_eddy_current_disk.py if you need exact 4.5 mm.
- After all INSIDE cuts are done, the disk is in 16 wedges held
  together by the inner annular core (between the inner cutout and
  the slot inner ends). The OUTSIDE cut frees them all from the
  substrate.
- The 200 µm gap between the inner cutout and slot inner ends keeps
  the wedges attached to the central core during cutting.
- Same recipe should work for outline_2pen_working.dxf if you want
  to test the perimeter cut by itself first.
"""

with open("pen_settings.txt", "w") as f:
    f.write(pen_settings)
print("Saved pen_settings.txt (updated for disk_full.dxf)")


# ── Preview plot (disk_full.dxf) ────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(14, 7))

layer_colors = {"INSIDE": "tab:blue", "OUTSIDE": "black", "DELAY": "gold"}

# Left: full disk
ax = axes[0]
disk_patch = plt.Circle((0, 0), FULL_OUTER_RADIUS, fill=True,
                        fc="#dddddd", ec="none")
ax.add_patch(disk_patch)
for p1, p2, layer in full_lines_list:
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]],
            color=layer_colors[layer], lw=0.4, alpha=0.8)
for r, layer in full_circles_list:
    circ = plt.Circle((0, 0), r, fill=False,
                      ec=layer_colors[layer], lw=0.5, alpha=0.9)
    ax.add_patch(circ)
ax.set_xlim(-2.8, 2.8)
ax.set_ylim(-2.8, 2.8)
ax.set_aspect("equal")
ax.set_xlabel("mm")
ax.set_ylabel("mm")
ax.set_title("disk_full.dxf — full pattern")
ax.grid(True, alpha=0.3)

# Right: zoom on a single slot inner end to show interleaving + cap
ax = axes[1]
disk_patch2 = plt.Circle((0, 0), FULL_OUTER_RADIUS, fill=True,
                         fc="#dddddd", ec="none")
ax.add_patch(disk_patch2)
for p1, p2, layer in full_lines_list:
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]],
            color=layer_colors[layer], lw=0.6, alpha=0.9)
for r, layer in full_circles_list:
    circ = plt.Circle((0, 0), r, fill=False,
                      ec=layer_colors[layer], lw=0.6, alpha=0.9)
    ax.add_patch(circ)
ax.set_xlim(-0.15, 0.15)
ax.set_ylim(0.45, 0.95)
ax.set_aspect("equal")
ax.set_xlabel("mm")
ax.set_ylabel("mm")
ax.set_title("Zoom — slot inner end + inner cutout boundary")
ax.grid(True, alpha=0.3)

fig.tight_layout()
fig.savefig("disk_full_preview.png", dpi=200, bbox_inches="tight")
plt.close()
print("Saved disk_full_preview.png")


# ── (Legacy preview, kept for the old slot pattern) ──────────────
fig, axes = plt.subplots(1, 2, figsize=(14, 7))

# Left: full view showing slot regions
ax = axes[0]
disk = plt.Circle((0, 0), OUTER_RADIUS, fill=True, fc="#cccccc",
                  ec="black", lw=1)
ax.add_patch(disk)
for p1, p2 in all_lines:
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 'r-', lw=0.3, alpha=0.7)
ax.set_xlim(-2.3, 2.3)
ax.set_ylim(-2.3, 2.3)
ax.set_aspect("equal")
ax.set_xlabel("mm")
ax.set_ylabel("mm")
ax.set_title("Full disk — cut lines")
ax.grid(True, alpha=0.3)

# Right: zoomed view of a few slots to show interleaving
ax = axes[1]
disk2 = plt.Circle((0, 0), OUTER_RADIUS, fill=True, fc="#cccccc",
                   ec="black", lw=1)
ax.add_patch(disk2)
for p1, p2 in all_lines:
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 'r-', lw=0.5, alpha=0.8)
ax.set_xlim(-0.15, 0.15)
ax.set_ylim(0.3, 0.8)
ax.set_aspect("equal")
ax.set_xlabel("mm")
ax.set_ylabel("mm")
ax.set_title("Zoom — interleaved cut lines")
ax.grid(True, alpha=0.3)

fig.tight_layout()
fig.savefig("eddy_current_disk_preview.png", dpi=200, bbox_inches="tight")
plt.close()
print("Preview saved to eddy_current_disk_preview.png")
