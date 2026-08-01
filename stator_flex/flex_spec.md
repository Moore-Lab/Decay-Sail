# Stator flex — design spec (rev G, final)

Under-rotor sector-electrode board that drives the diamagnetically levitated
**Snowflake V1.3** rotor as a variable-capacitance synchronous motor. Mounts on
the PEEK plate (`mounting_plate_sketch.dxf`) with four 4-40 screws that double
as the electrical terminals.

All geometry comes from `generate_flex_revG.py`; `gerber_export.py` writes the
fab files and runs the electrical checks; `verify_gerber.py` reads the shipped
Gerbers back and rasterises them; `step_export.py` builds the CAD model.

## Drive

24 sectors on a 15° pitch, 3-phase (0/120/240°), synthesising a rotating **m = 8**
potential matched to the rotor's underside modulation (see
`analyze_snowflake_dxf.py` — the modulation is in the m=8 family, *not* m=12).

**Rotor speed = f_electrical / 8. Reverse by swapping any two phases.**

| Gap h | Drive | τ_max | Capture (mech) | 0 → 10 Hz mech |
|---|---|---|---|---|
| 0.37 mm (no shim) | 100 V | 1.2e-12 N·m | 0.12 Hz | 32 min |
| 0.37 mm (no shim) | 200 V | 5.0e-12 N·m | 0.23 Hz | 7.9 min |
| 0.27 mm (0.1 mm shim) | 100 V | 3.8e-12 N·m | 0.20 Hz | 10 min |
| **0.27 mm (0.1 mm shim)** | **200 V** | **1.5e-11 N·m** | **0.41 Hz** | **2.6 min** |

Includes the 3-phase stator amplitude (a₁² = 0.438) and the fraction of the
rotor's available coupling the electrode annulus actually sees (89.4% at
h = 0.27, 84.2% at h = 0.37, from `coupling_vs_radius.py`). Torque ∝ V² and
rises steeply as h shrinks: **the shim is the main tuning knob (2-3×)**.
h = levitation height − 0.043 mm (board thickness above the plate face).

## Geometry (mm)

| Item | Value |
|---|---|
| Sectors | 24, 15° pitch, annulus **r = 0.69 → 1.95**, 0.10 gaps |
| Sector Cu at r_in | 0.081 (at the 0.08 fab floor — sets the inner radius) |
| CTR electrode | disk r = 0.58; 0.08 trace out through the sector boundary at az 285°, widening to 0.25 beyond r = 2.50 |
| Sector vias (staggered) | A 4.27 / B 4.96 / C 5.66 |
| Bus arcs (bottom) | A 4.55 / B 5.24 / C 5.93, 0.18 wide, 315° each |
| Escapes | **A and C run straight radially to their pads** (nothing blocks them); only **B** exits through C's window at az 29° and wraps on the lane at r = 6.45 |
| Top pads | Ø6.5 at r = 9.0, az 15/105/195/285° |
| Bottom pads | Ø4.0 (0.5 ring around the 3.0 hole) |
| Ground keep-away | top 4.75 (screw head), bottom 2.20 (nothing clamps) |
| GND contact ring | bottom, r 2.95-3.40, bare ENIG, presses on the magnet |
| Optional GND pads | top, Ø3.4 at r = 10.8, az 60/240°, bare ENIG |
| Ground stitching | 23 vias at r = 3.15 (one per inter-tab gap) + 4 at r = 11.0 + a radial spoke at az 0° |
| Board | Ø25.4, 0.1 mm, 2-layer PI, 18 µm Cu, ENIG |

## Nets

| Terminal | Net | Function |
|---|---|---|
| 15° | A | phase 0° |
| 105° | B | phase 120° |
| 195° | C | phase 240° |
| 285° | CTR | centre electrode: charge drive / DC height trim |
| — | GND | magnet contact ring + 2 optional top pads |

**CTR as a charge probe:** 10 V gives E_z ≈ 1.7e4 V/m on axis → 2.7e-15 N per
elementary charge; driven at the vertical trap frequency with Q ~ 1e3-1e4,
few-electron resolution by lock-in is plausible. Calibrate against a
UV/filament charge step.

## Verified on every export

| Check | Result |
|---|---|
| Per-net clearance, both layers | worst 0.100 mm (rule 0.08) |
| Floating copper | none — 48 islands → exactly 5 net groups |
| Ground in the active area | 0.000 mm² (it would screen the drive field) |
| Mount-hole plating safety | same-net copper both sides, all 4 |
| Max screw head / washer OD | 9.5 mm (fits all standard 4-40 hardware) |
| Unconnectable ground fragments | deleted, not left floating (0.178 mm² dropped) |

## Fab (PCBWay flex)

2 layers, polyimide, 0.1 mm total, 0.5 oz (18 µm) Cu, ENIG 1U", coverlay both
sides **with openings**, 100% e-test, no stiffener, no silkscreen.
Min track/space 0.08, min drill 0.15. One plated drill file: **64 holes**
(60 × 0.15 vias + 4 × 3.0 mounting).

> The Ø12.4 top coverlay opening is the working electrode surface and must stay
> bare gold; the bottom ring opening is a pressure contact. See
> `fab/FAB_README.txt` — without that note a CAM engineer may "fix" it.

## Assembly

- Screws thread into tapped PEEK, so they are isolated from the plate — but the
  plated barrels make **all four screws live** (up to 200 V). Use stainless or
  silver-plated hardware; check screw length so no tip protrudes toward ground.
- Clock ring-terminal tongues radially outward.
- Screw-in-hole fit centres the pattern to ~±0.1 mm, which meets the m=8
  concentricity requirement without separate fiducials.
- The GND contact ring is the primary ground; a shim must be ≤ Ø5.8 mm so it
  does not lift the ring off the magnet. The two optional top pads are the
  fallback if that pressure contact measures high.

## Operating protocol

1. Neutralise rotor charge; ground A/B/C when not driving.
2. Spin-up: 3-phase ramp f_elec 0 → 8·f_target at ≤50% torque margin.
   Fixed-frequency starts below ~0.4 Hz mech capture directly.
3. Reverse: swap two phases, ramp through zero.
4. Science runs: A/B/C to GND — the board becomes a clean ground plane.

## First-article tests

1. Continuity at the four terminals; GND-ring-to-magnet resistance;
   hipot 250 V net-net **and net-to-magnet**.
2. Measure V1.3 levitation height over the installed board → choose the shim.
3. **DC detent test:** one phase on → rotor snaps to one of 8 detents;
   step A→B→C → 15° mech per step. Calibrates τ_max vs V² directly.
4. Max sustainable ramp rate vs V (expect ∝V²).

## Open items

- [ ] Measure the V1.3 levitation height (0.75 mm thick, 9.89 mg — likely
      differs from SGD03's 0.41 mm); h enters the torque exponentially.
- [ ] Confirm the magnet sits flush in the plate's Ø7 hole (board flatness).
- [ ] Cross-check the coupling model with a 3-D BEM/COMSOL run (the analysis
      uses a quasi-planar exp(−m h/r) approximation).
- [ ] Verify a 3-phase, phase-locked drive chain at ±100-200 V.
