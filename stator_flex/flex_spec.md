# Under-rotor sector-drive flex circuit — design spec (rev G)

**Rev G = rev F + center charge-drive electrode (CTR) on the 4th post, fully
compliant with the PCBWay flex rules in `design_rules.pdf`** (min track/space
0.08/0.08 mm, via drill/pad ≥0.15/0.35, 0.1 mm 2-layer PI, 18 µm Cu, ENIG,
coverlay with openings, 100% e-test). Files: `generate_flex_revG.py` →
`flexG_top_copper.dxf`, `flexG_bottom_copper.dxf`, `flexG_outline.dxf`,
`flexG_preview.png/pdf`. The script prints a DRC self-check — all clearances
≥0.08 mm as generated.

## Nets and posts (4-40 ring terminals, tapped PEEK plate, r = 9.0)

| Post az | Net | Function |
|---|---|---|
| 15° | A | phase 0° |
| 105° | B | phase 120° |
| 195° | C | phase 240° |
| 285° | CTR | center disk r = 0.60: charge-measurement drive / DC height trim |
| — | GND | exposed bottom ENIG ring (r 2.95–3.40, coverlay opening) pressed on the grounded magnet; 8 stitching vias at r = 3.2 |
| (optional) | GND | 2× bare-ENIG Ø3.4 pads on the top pour at r = 10.8, az 60°/240° — solder a ground wire here if the magnet contact ring proves unreliable |

**CTR routing:** top-layer trace at az 285° (a sector boundary): 0.08 wide with
0.08 clearances through the annulus (flanking sectors 18/19 clipped to
r ≥ 0.98 so no copper is narrower than 0.08), widening to 0.25 outside, straight
to the pad. **GND note:** the magnet contact ring is the only ground path —
verify low resistance at assembly; a center shim must be ≤ Ø5.8 so it doesn't
lift the ring off the magnet.

**Charge measurement:** drive CTR at the vertical trap frequency;
E_z ≈ 1.8×10⁴ V/m per 10 V on axis → F = 2.8×10⁻¹⁵ N per elementary charge;
off-resonance z ≈ 0.03 pm/e (×Q on resonance — with Q ~ 10³–10⁴ in vacuum,
single-to-few-electron resolution via lock-in is plausible). Also serves as DC
height trim.

## Bottom routing (the rule-driven rework)

Straight concentric bus rings with a single via radius would force taps to
cross inner rings — fixed with **staggered per-phase via radii**: top tabs run
to r = 4.27 (A) / 4.90 (B) / 5.585 (C), then drop to bus rings at
r = 4.55 / 5.24 / 5.93 (0.18 wide, 0.69 pitch so via pads fit between rings
with 0.08 clearance). Escapes at az 7.5/36.5/352.5 through the aligned ring
windows; lanes at r = 7.0 thread between pad footprints; radial rises at pad
azimuths to 3-via clusters. Live bottom copper keep-out r < 4.0 unchanged
(A via pad clears it by 0.095).

## Phase-count trade (evaluated, decided: keep 3-phase)

More phases give at most +18% rotating-wave amplitude (stepped-wave limit) but
every extra phase boundary inserts another ≥0.08 mm gap into sectors only
~0.35 mm wide, so torque vs 3-phase at m=8, 0.10 gaps: 4-phase ×0.84,
6-phase ×0.44, 8-phase ×0.14. m=16 with 48 sectors also loses under the 0.08
rule. **3-phase, 24 sectors is the optimum for this rotor + fab process.**
Extra posts, if ever added (plate has 4 more 4-40 tap-size holes at r = 14.37,
az 45/135/225/315, reachable with small board ears), are better spent on a
dedicated GND post and/or outer m=1 lateral-control arcs — not more phases.

## Performance (from rotor-DXF coupling, 3-phase amplitude included)

| Configuration | 200 V: τ_max | 0→10 Hz mech |
|---|---|---|
| No shim (h ≈ 0.37 mm) | 5.9e-12 N·m | ~7 min |
| Ø5.8 × 0.1 mm shim (h ≈ 0.27 mm) | 1.7e-11 N·m | ~2.3 min |

Electrical frequency = 8 × mechanical; reversal = swap two phases.

## Fab order parameters (PCBWay flex)

2 layers, polyimide, FPC thickness 0.1 mm, 0.5 oz (18 µm) finished copper,
ENIG 1U", yellow coverlay both sides **with openings**: top opening over the
active area (r < ~6, boundary in the pour), bottom opening over the GND
contact ring; 100% e-test; no stiffener (the PEEK plate is the stiffener).

## First-article tests

1. Continuity at ring terminals incl. CTR; GND-ring-to-magnet resistance;
   hipot 250 V net-net and net-magnet.
2. Levitation height of V1.3 over the board → shim choice.
3. DC detent test (8 detents; A→B→C steps of 15° mech) → τ_max vs V².
4. CTR charge check: drive at f_z, lock-in on vertical motion; calibrate
   against a known charge change (UV/filament step).

## Open items

- [ ] Verify magnet-flushness in the plate hole; measure levitation height.
- [ ] Confirm GND pressure-contact reliability (else add a GND ear to a
      r = 14.37 plate hole).
- [ ] BEM/COMSOL cross-check of coupling (grounded plane under electrodes).
- [ ] Final EDA pass: pours, teardrops, coverlay opening boundaries.
