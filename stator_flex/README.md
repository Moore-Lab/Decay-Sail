# Stator flex: electrostatic drive for the levitated rotor

Under-rotor sector-electrode flex circuit ("stator") that spins the
diamagnetically levitated Snowflake V1.3 rotor up and down reproducibly, and
reverses its direction, by applying a rotating electric potential from below.
Replaces the four side posts, which gave a synchronous torque with a capture
bandwidth of only a few mHz — hence the unreliable, hard-to-explain spin-ups.

**Everything here is generated from one parametric source.** Change a number in
`generate_flex_revG.py`, re-run the scripts, and the Gerbers, the STEP model and
all the checks follow. Nothing is hand-drawn.

## Physics summary

- The drive works as a **variable-capacitance synchronous motor**: the rotor's
  patterned underside makes the rotor-electrode capacitance angle dependent, so
  `tau = 1/2 (dC/dtheta) V^2`. It is charge independent and reproducible.
- Fourier analysis of the rotor DXF (`analyze_snowflake_dxf.py`) shows the
  bottom-surface modulation is in the **m = 8 family** (8, 16, 24, 32) — *not*
  m = 12 as the "features every 30 deg" drawing note suggests.
- Gap attenuation goes as `exp(-m h / r)`, so m = 8 is the fab-robust optimum:
  m = 16 couples ~1.5x better but needs 7.5 deg sectors and ~40 um concentricity.
- 24 sectors on a 15 deg pitch, driven 3-phase, synthesise the rotating m = 8
  potential. **Rotor speed = f_electrical / 8.** Reverse by swapping two phases.

| Configuration (200 V) | tau_max | capture | 0 -> 10 Hz mech |
|---|---|---|---|
| no shim, h ~ 0.37 mm | ~6e-12 N m | 0.25 Hz | ~7 min |
| 0.1 mm shim, h ~ 0.27 mm | ~1.7e-11 N m | 0.43 Hz | ~2.3 min |

Torque scales as V^2 and rises steeply as the rotor-electrode gap `h` shrinks:
**the shim under the board centre is the main tuning knob**, worth 2-3x.

## Board (rev G)

Circular 2-layer polyimide flex, 25.4 mm diameter, 0.1 mm thick, ENIG, mounting
directly on the PEEK plate with four 4-40 screws at r = 9 mm
(15/105/195/285 deg). The screws double as the electrical terminals: ring
terminals clamp onto top pads, and the plated barrels tie top to bottom.

| Terminal | Net | Function |
|---|---|---|
| 15 deg | A | phase 0 |
| 105 deg | B | phase 120 |
| 195 deg | C | phase 240 |
| 285 deg | CTR | centre disk (r = 0.58): charge-measurement drive / DC height trim |
| - | GND | exposed bottom ENIG ring (r 2.95-3.40) pressed on the grounded magnet, plus two optional bare pads on top at r = 10.8, az 60/240 |

Key geometry: electrodes span **r = 0.69 -> 1.95 mm** (captures ~89% of the
available m = 8 coupling; inner edge is at the 0.08 mm minimum-copper limit),
0.10 mm gaps, no ground copper inside the active area (it would screen the drive
field), bottom copper kept clear of the grounded magnet except the contact ring.

## Files

| File | What it does |
|---|---|
| `generate_flex_revG.py` | parametric source of the board geometry; writes DXFs and a DRC self-check |
| `gerber_export.py` | Gerber + Excellon export with boolean ground pours, per-net clearance and floating-copper checks |
| `verify_gerber.py` | reads the *shipped* Gerbers back and rasterises them (painter's-algorithm polarity) — verifies what actually gets fabricated |
| `step_export.py` | 3D solid model (CadQuery) -> STEP for the CAD assembly |
| `analyze_snowflake_dxf.py` | rotor DXF -> angular harmonics, torque vs drive harmonic and gap |
| `coupling_vs_radius.py` | how much of the available torque a given electrode annulus captures |
| `emit_fusion_scr.py` | optional: Fusion Electronics build script |
| `flex_spec.md` | full design spec, operating protocol, first-article tests |
| `spinup_note.md` | why the side posts were unreliable; mechanism analysis |
| `fab/` | Gerbers, drill file, PCBWay design rules, fab notes — ready to order |
| `inputs/` | rotor and mounting-plate DXFs the design is derived from |

## Reproducing

```
python analyze_snowflake_dxf.py   # rotor harmonics (m=8 family)
python coupling_vs_radius.py      # electrode annulus optimisation
python gerber_export.py           # fab files + all electrical checks
python verify_gerber.py           # independent read-back and render
python step_export.py             # STEP model for CAD
```

Requires `numpy`, `matplotlib`, `ezdxf`, `shapely`, and `cadquery` (STEP only).

## Checks that run on every export

- per-net clearances on both layers (worst case 0.100 mm vs 0.08 mm rule)
- floating-copper detection: union-find over all copper islands through vias and
  plated holes; every island must reach a screw terminal or the magnet ring.
  Currently 48 islands -> exactly 5 groups, one per net. **Unconnectable ground
  fragments are deleted, not left floating.**
- ground copper inside the active area must be zero
- every mount hole must have same-net copper on both layers (plating safety)
- largest screw head / washer that fits without touching another net (9.5 mm)

## Coordinate frame

Origin on the trap/magnet axis, matching `inputs/mounting_plate_sketch.dxf`.
In the STEP model **z = 0 is the board's bottom face** (against the PEEK plate);
the electrode surface sits at z = +0.043 mm, so the rotor gap is
`h = levitation_height - 0.043 mm` with no shim.

## Open items before ordering

- Measure the V1.3 rotor's levitation height over the installed board; pick the
  shim thickness (must be <= 5.8 mm diameter so it does not lift the GND ring).
- Confirm the magnet sits flush in the plate's 7 mm hole.
- Cross-check the coupling model with a 3-D BEM/COMSOL run (the analysis uses a
  quasi-planar `exp(-m h / r)` approximation).
