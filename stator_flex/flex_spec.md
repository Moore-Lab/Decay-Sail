# Stator flex — design spec (rev G, final)

Under-rotor sector-electrode board that drives the diamagnetically levitated
**Snowflake V1.3** rotor as a variable-capacitance synchronous motor. Mounts on
the PEEK plate (`mounting_plate_sketch.dxf`) with four 4-40 screws that double
as the electrical terminals.

All geometry comes from `generate_flex_revG.py`; `gerber_export.py` writes the
fab files and runs the electrical checks; `verify_gerber.py` reads the shipped
Gerbers back and rasterises them; `step_export.py` builds the CAD model.

## Why under-rotor electrodes

The old drive was **4 side posts in quadrature**, making a uniform rotating in-plane
field. That can only torque the rotor through induced-dipole shape anisotropy or a
permanent charge dipole — both synchronous, so the average torque is zero unless the
rotor already co-rotates. Capture bandwidth was only `sqrt(2τ/I)/2π ≈ 5–70 mHz`, so
switching on at an ordinary frequency almost never captured ("sometimes it works").
The field was also screened by the grounded magnet plane (~6 kV/m free-space at
±100 V → a few hundred V/m at the rotor).

Electrodes *underneath* make a parallel-plate capacitor (E ~ V/h ~ 3e5 V/m) and turn
the mechanism into a **variable-capacitance synchronous motor**, τ = ½ (dC/dθ) V²:
charge-independent and reproducible, roughly 300× the side posts' torque.

## Drive

24 sectors on a 15° pitch, 3-phase (0/120/240°), synthesising a rotating **m = 8**
potential.

**Rotor speed = f_electrical / 8. Reverse by swapping any two phases.**

**Why m = 8, not 12 (derived, not yet measured).** Fourier analysis of the rotor
drawing (`analyze_snowflake_dxf.py` on `Snowflake_disk_V1.3.dxf`) puts the underside
modulation in the m = 8 family (8, 16, 24, 32; m = 16 strongest), not the m = 12 the
drawing note ("features equally spaced 30°") implies. The drawing shows 8 forked arms;
a microscope photo of the flown rotor shows the same 8-fold pattern (2026-10-29). An
m = 12 board would have been nearly torque-less. With gap attenuation exp(−m·h/r),
m = 8 is the fab-robust optimum: m = 16 couples ~1.5× better but would need 7.5°
sectors (0.083 mm copper) and ~40 µm concentricity. More phases do not help: each
extra phase boundary inserts another ≥0.08 mm gap into ~0.35 mm sectors, ×0.84
(4-phase), ×0.44 (6-phase), ×0.14 (8-phase). The DC detent test (8 detents, 15° per
A→B→C step) would confirm m = 8 directly.

### Performance (at the 0.37 mm gap, I = 1.1e-11 kg·m²)

| Drive | τ_max | Capture (mech) | 0 → 10 Hz mech |
|---|---|---|---|
| 100 V | 1.2e-12 N·m | 0.16 Hz | 19 min |
| 200 V | 5.0e-12 N·m | 0.30 Hz | 4.6 min |

Includes the 3-phase stator amplitude (a₁² = 0.438) and the fraction of the rotor's
available coupling the electrode annulus actually sees (84.2% at h = 0.37, from
`coupling_vs_radius.py`). Ramp time scales linearly with the target speed.

- τ ∝ V², and rises steeply as h shrinks (attenuation ∝ exp(−m·h/r)).
- h = levitation height − 0.043 mm (board thickness above the plate face). There is
  no centre shim; the board lies directly on the magnet.
- Capture bandwidth = `sqrt(m·τ_max/I)/2π` with m = 8. (`sqrt(2τ/I)/2π` is the
  side-post case; that 2 is the induced dipole's 2-fold symmetry.)
- Max ramp rate = `0.5·τ_max/(2πI)` Hz mech/s (≤50% torque margin).
- I and the drive ceiling: `docs/DECISIONS.md`. The voltage actually reached at the
  ceiling depends on the HV amplifier (`hv_amp_dc_investigation.md`).

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
| GND contact ring | bottom, r 2.95-3.40, bare ENIG; designed to press on the magnet, but a 1/4" magnet barely reaches it (no contact) |
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
| — | GND | top pad wired to the base (in use); bottom magnet-contact ring (no contact with a 1/4" magnet) |

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
- Nothing may sit between the board and the magnet. The bottom GND ring
  (r 2.95–3.40) barely overlaps a 1/4" magnet and does not make contact, so the board
  is grounded through a top GND pad wired to the base (2026-10-27).

## Operating protocol

1. Neutralise rotor charge; ground A/B/C when not driving.
2. Spin-up: 3-phase ramp f_elec 0 → 8·f_target at ≤50% torque margin.
   Fixed-frequency starts below ~0.4 Hz mech capture directly.
3. Reverse: swap two phases, ramp through zero.
4. Science runs: A/B/C to GND — the board becomes a clean ground plane.

## First-article tests and open items

Tracked in `docs/STATUS.md`.
