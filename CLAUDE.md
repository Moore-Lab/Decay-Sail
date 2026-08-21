# Decay-Sail — working context

Diamagnetically levitated rotor ("decay sail"): a Snowflake V1.3 disk floating over a
magnet, spun by an under-rotor electrostatic stator, ultimately to measure the alpha-recoil
thrust from a Pb-212 source (~40 kBq → ~1–5 fN).

This file travels with the repo, so a session on **any** machine gets the same context.
Deeper detail lives in `apparatus_log.md`, `stator_flex/flex_spec.md`,
`stator_flex/spinup_note.md`.

---

## Machines

| Host | Role |
|---|---|
| Mac (`~/Desktop/VSCode/decay_sail`) | development, analysis notebooks |
| `worker2` = 192.168.1.13 | lab workstation, EPICS client, NTP-synced |
| `cymac1` = 192.168.1.11 | rtcds front end, NDS2 server on :8088 |

- Front-end model prefix is **`Y1:RDS`** (cf. Aaron Markowitz's microdiamond experiment
  on the same cymac1, which is `Y1:DMD` — *different model, do not assume they match*).
- **cymac1's GPS clock runs +5836 s fast** of true GPS (measured 2026-06-03).
  true GPS = cymac GPS − 5836. Scripts here use `GPS = Unix − 315964782`
  (= 315964800 − 18 leap seconds).
- **Never restart GNOME Shell / the compositor on a live worker2 session** without
  checking X11-vs-Wayland and asking first — it caused a login-loop lockout on 2026-07-10.

---

## THE STATOR (rev G under-rotor drive)

Full design writeup: `stator_flex/flex_spec.md` + the "Stator for underneath drive"
Notion page. Everything below is the operating summary.

### Why it exists

The old drive was **4 side posts in quadrature**, making a uniform rotating in-plane
field. That can only torque the rotor through induced-dipole shape anisotropy or a
permanent charge dipole — **both synchronous, so average torque is zero unless the rotor
already co-rotates.** Capture bandwidth was only `sqrt(2τ/I)/2π ≈ 5–70 mHz`, so switching
on at any ordinary frequency essentially never captured; what spin-up did happen rode on
weak charge-dependent residuals. Hence "sometimes it works". The field was also screened
by the grounded magnet plane (~6 kV/m free-space at ±100 V → a few hundred V/m at the rotor).

**The fix:** electrodes *underneath*. That makes a parallel-plate capacitor
(E ~ V/h ~ 3e5 V/m) and turns the mechanism into a **variable-capacitance synchronous
motor**, τ = ½ (dC/dθ) V² — charge-independent and reproducible. Roughly **300× the
torque** of the side posts.

### Drive harmonic: m = 8, NOT m = 12

Fourier analysis of the real `Snowflake_disk_V1.3.dxf` (`stator_flex/analyze_snowflake_dxf.py`)
shows the underside modulation lives in the **m = 8 family** (8, 16, 24, 32 — with m=16
strongest), *not* the m = 12 the drawing note ("features equally spaced 30°") implies.
**An m=12 board would have been nearly torque-less.** Folding in gap attenuation
exp(−m·h/r), m=8 is the fab-robust optimum: m=16 couples ~1.5× better but would need
7.5° sectors (0.083 mm copper) and ~40 µm concentricity.

24 sectors on a 15° pitch, driven 3-phase, synthesise the rotating m=8 potential.
More phases do not help — each extra phase boundary inserts another ≥0.08 mm gap into
sectors only ~0.35 mm wide: ×0.84 (4-phase), ×0.44 (6-phase), ×0.14 (8-phase).

### The two numbers that govern everything

> **Rotor speed = f_electrical / 8.  Reverse by swapping any two phases.**

Reversal is *structural*, not a sign flip. (`sweep_oscillator_reverse.py` tried to reverse
the OLD drive by negating COS, but the forward script already ran `COS = -GAIN`, so the
negation cancelled and it drove the same direction. **That script does not work.**)

### Performance

| Gap h | Drive | τ_max | Capture (mech) | 0 → 10 Hz mech |
|---|---|---|---|---|
| 0.37 mm (no shim) | 100 V | 1.2e-12 N·m | 0.12 Hz | 32 min |
| 0.37 mm (no shim) | 200 V | 5.0e-12 N·m | 0.23 Hz | 7.9 min |
| 0.27 mm (0.1 mm shim) | 100 V | 3.8e-12 N·m | 0.20 Hz | 10 min |
| **0.27 mm (0.1 mm shim)** | **200 V** | **1.5e-11 N·m** | **0.41 Hz** | **2.6 min** |

Includes the 3-phase stator amplitude (a₁² = 0.438) and the fraction of available m=8
coupling the electrode annulus actually sees (89.4% at h=0.27, 84.2% at h=0.37).

- **τ ∝ V², and rises steeply as h shrinks — the shim is the main tuning knob (2–3×).**
- `h = levitation height − 0.043 mm` (board thickness above the plate face).
- Capture bandwidth = `sqrt(m·τ_max/I)/2π` with **m = 8**. (The Notion page's own
  `sqrt(2τ/I)/2π` is the *side-post* case; that 2 is the induced dipole's 2-fold symmetry,
  not a universal constant.)
- Max ramp rate = `0.5·τ_max/(2πI)` Hz mech/s (the 0.5 is the ≤50% torque margin).
- **`I = 1.88e-11 kg·m²` is ASSUMED, never measured.** Both formulas above inherit it.

### Board (rev G)

Ø25.4 mm, 2-layer polyimide flex, 0.1 mm thick, 18 µm Cu, ENIG, coverlay both sides
with openings. Mounts on the PEEK plate with four 4-40 screws at r = 9 mm; **the screws
double as the electrical terminals** (ring terminals on top pads, plated barrels tie top
to bottom).

| Terminal | Net | Function |
|---|---|---|
| 15° | A | phase 0° |
| 105° | B | phase 120° |
| 195° | C | phase 240° |
| 285° | CTR | centre disk r = 0.58 mm — charge drive / DC height trim |
| — | GND | bare bottom ring r 2.95–3.40 pressed on the grounded magnet; 2 optional top pads at r = 10.8, az 60/240° |

- Sector electrodes span **r = 0.69 → 1.95 mm**; inner edge sits at the 0.08 mm
  minimum-copper limit.
- **No ground copper inside the active area** — it would screen the drive field.
- **CTR as a charge probe:** 10 V gives E_z ≈ 1.7e4 V/m on axis → 2.7e-15 N per elementary
  charge. Driven at the vertical trap frequency with Q ~ 1e3–1e4, few-electron resolution
  by lock-in is plausible; calibrate against a UV/filament charge step.

### ⚠ Assembly / safety

- **The plated barrels make all four screws live, up to 200 V.** They thread into tapped
  PEEK so they are isolated from the plate — use stainless or silver-plated hardware and
  check screw length so no tip protrudes toward ground.
- **Max screw head / washer OD is 9.5 mm** before it reaches another net.
- Clock the ring-terminal tongues radially outward.
- A centre shim must be **≤ Ø5.8 mm** so it does not lift the GND contact ring off the magnet.
- Screw-in-hole fit centres the pattern to ~±0.1 mm, which meets the m=8 concentricity
  requirement without separate fiducials.
- The board was hipot tested to **250 V** net-net and net-to-magnet.

### Operating protocol

1. Neutralise rotor charge; ground A/B/C when not driving.
2. Spin-up: 3-phase ramp f_elec 0 → 8·f_target at ≤50% torque margin. Fixed-frequency
   starts below ~0.4 Hz mech capture directly.
3. Reverse: swap two phases, ramp through zero.
4. Science runs: A/B/C to GND — the board becomes a clean ground plane, no drive
   systematic. CTR optionally on DC bias.

### First-article tests (the near-term experimental programme)

1. Continuity at the four terminals; GND-ring-to-magnet resistance; hipot 250 V
   net-net **and** net-to-magnet.
2. Measure V1.3 levitation height over the installed board → choose the shim.
3. **DC detent test:** energise one phase → rotor snaps to one of 8 detents; stepping
   A→B→C walks it 15° mech per step. Directly calibrates τ_max vs V².
4. Max sustainable ramp rate vs V (expect ∝ V²) — confirms the capacitance-motor mechanism.

**All four are fixed-frequency or DC — none needs a frequency ramp.** That matters for
choosing a drive backend (below).

### Known hardware issues

- **The board is currently wired through the old electrode stands.** Those are tall
  conductors at r ≈ 9 mm carrying up to 200 V, which recreates the rotating in-plane
  dipole field the stator redesign existed to escape. Its synchronous torque averages to
  zero (the post field rotates 8× faster than the rotor), but any net rotor charge sees a
  **rotating force at 8× rotor speed** — orbital heating, hunting for the lateral trap
  resonance. Plan is to swap the stands for short screws at the next chamber opening.
- There is a **bright deposit near the centre of the rotor's underside**. That face flies
  0.27 mm off the board and τ ∝ exp(−m·h/r), so anything standing proud there costs real
  torque.
- Open from the design: measure the V1.3 levitation height; confirm the magnet sits flush
  in the plate's Ø7 hole; cross-check the quasi-planar exp(−m h/r) coupling model against
  3-D BEM/COMSOL.

---

## Driving it: `lab_utils/stator_drive.py`

**This is the one drive script.** Subcommands: `status / spinup / spindown / hold /
reverse / sweep / detent / stop`. **Dry-run by default; `--live` to touch hardware.**
`lab_utils/three_phase_drive.py` is superseded and will be deleted once its backend is
folded in. `lab_utils/sweep_oscillator_reverse.py` is broken (see above).

Its physics core is validated — it reproduces all four rows of the performance table.

### ⚠ The DC pedestal is not cosmetic

Expanding τ = ½ (dC/dθ)V² for `V_k = V_dc + V_ac·cos(φ + δ_k)` over the 24-sector/3-phase
pattern gives **two** torque channels, both locking the rotor at the same speed f_elec/8:

| channel | couples to | amplitude | winds |
|---|---|---|---|
| ch1 | rotor m=8 | **V_dc · V_ac** | 1× per elec cycle |
| ch2 | rotor m=16 | V_ac² | 2× per elec cycle |

**At V_dc = 0 the m=8 channel vanishes identically**, leaving only m=16 — the stronger
rotor harmonic, but it suffers twice the gap attenuation. Maximising V_dc·V_ac subject to
V_dc + V_ac ≤ V_max gives **V_dc = V_ac = V_max/2**, hence `DRIVE_DC = DRIVE_COUNTS = 6400`
— the same 6400/6400 split `sweep_oscillator.py` used on the old posts. `--dc` exists only
as a diagnostic: **m=8 scales with V_dc, m=16 does not**, so varying it separates them.

### Unresolved: how the three phases actually get generated

`PHASE_GAIN_PVS` at the top of the script (`Y1:RDS-OUTS_V{1,2,3}_{SIN,COS}GAIN`) is a
**placeholder guess** — those strings appear nowhere else in the repo. The real model has
*one* oscillator with one quadrature pair (`Y1:RDS-OUTS_DRV_{SIN,COS}GAIN`) fanned out to
four posts as sin/cos/−sin/−cos, which cannot make 120° phases.

**Fast vs slow channels (from Aaron's CLAUDE.md — verify on y1rds, do not assume):**
slow filter-module records (`_GAIN`, `_OFFSET`, `_TRAMP`, `_SW1R`) answer `caget`/`caput`;
**fast channels (`_EXC`, `_IN1`, `_OUT16`) are test points** reachable only via
`diag`/`awg`/`nds2`. So writing AC sinusoids to `V{n}_OFFSET` (what `three_phase_drive.py`
does) is the wrong access method — OFFSET is for the DC pedestal only.

**Most promising route: `diag` SineResponse** (headless diaggui, `diag -l -f <cmdfile>`).
Its XML takes index-aligned per-tone `Stimulus{Frequency,Amplitude,Offset,Phase}[i]` +
`StimulusChannel[i]`, **phase in radians** — i.e. three rows at one frequency with phases
0 / −2π/3 / −4π/3 on `V{1,2,3}_EXC` is a three-phase drive, applied coherently by the front
end, with no model rebuild. Template: `scripts/dipole/measure_actuator_gain.py` in
github.com/aaronmarkowitz/labutils.

**Caveat: y1rds is NOT y1dmd.** All of that is proven on Aaron's front end. Verify before
building against it — read the y1rds `.mdl` under `/opt/rtcds/userapps/`, and confirm
V1–V4 are standard filter modules (which is what the `_EXC` inference rests on).

### `VOLTS_PER_COUNT = 0.03125` is UNMEASURED

Torque goes as V², so an error here is **squared** in every limit the script prints.
The DAC is 16-bit signed (32768 counts full scale → 6400 counts ≈ 1.95 V); the HV amp gain
after it is unknown. Note `sweep_oscillator.py` drives 0 → 12800 counts — if 6400 really is
200 V, that swing is 400 V, above the 250 V hipot.

---

## Conventions

- **Ask before pushing.** Commit messages explain *why*, not just what.
- Hardware scripts default to dry-run; prefer it when testing.
- Don't delete "non-functional" scripts unilaterally — Molly wants to prune them together.
- Generated figures are gitignored (`plots/`, `analysis/*.png`); notebooks and notes are tracked.
- `analysis/ringdown_analysis_executed.ipynb` is misnamed — it is a *variant* with the
  window shifted 3 min earlier, not a re-execution.
