# Decay-Sail — working context

## Operating principles

1. **Read first:** `measurement_objective.md` (the goal), `docs/STATUS.md` (what is
   open), `docs/DECISIONS.md` (what is current).
2. **One fact, one home.** Current values and decisions live in `docs/DECISIONS.md`.
   Elsewhere, link to them; don't restate them.
3. **Label claims** as measured, derived, or assumed. Never record your own
   assumption as a decision. Decisions are made by a person and dated in DECISIONS.md.
4. **Report what you observe and how big it is,** with uncertainties. Don't jump to
   causes. If something is unexplained, say so.
5. **Ask first** before: hardware actuation (drive, laser, HV, any `--live`), git
   commit or push, purchases, deleting files, or changing a recorded decision.
   Otherwise proceed.
6. **Ask open questions once, in one batch.** For the rest, proceed on stated
   assumptions.
7. **Log each session** in `apparatus_log.md`: one short entry (did / ran, with command
   and GPS start–stop / saw / link). Analysis goes in its own file.
8. Never use `--leave-running` unless asked.
9. Front-end (cymac1) GPS: read it live, do not use a stored offset.
10. **Never restart GNOME Shell** without checking X11-vs-Wayland and asking first.
11. Git is the backup. Don't make copies of files.

Diamagnetically levitated rotor ("decay sail"): a Snowflake V1.3 disk floating over a
magnet, spun by an under-rotor electrostatic stator, ultimately to measure the alpha-recoil
force from a Pb-212 source (expected force: `docs/DECISIONS.md`).

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

> ⚠ **UPDATED 2026-08-28 — the ~80 V ceiling below is superseded, but the
> optimal-split number is now genuinely open, not just outdated.** Measured
> swing is **~171-180 V** (two independent measurements, `apparatus_log.md`
> 2026-08-25 and 2026-08-28), much closer to the 200 V design target than the
> 80 V figure — see "HV amplifier" below. But **the amp is bipolar** (PI
> confirmed 2026-08-28), and its true zero-crossing count is NOT at commanded
> count 0 — it sits somewhere near 6400 counts on the `_EXC` path, unmeasured on
> `_OFFSET`. So "V_dc = V_ac = V_max/2" is still the right *formula*, but V_max
> means "excursion from the true zero," which nobody has measured yet on the
> path this script actually drives. **The 40/40 V "TODAY" row below is stale
> and should not be trusted until a dedicated zero-crossing sweep is done** (see
> "Known script issues").
>
> **There is no centre shim, and none is planned** (Molly, 2026-10-19 — earlier
> "0.1 mm shim / 0.27 mm gap" text here was an unrequested assumption). The
> configuration is the 0.37 mm gap.

| Gap h | Drive | τ_max | Capture (mech) | 0 → 10 Hz mech |
|---|---|---|---|---|
| **0.37 mm — TODAY** | **40/40 V** | **1.9e-13 N·m** | **0.059 Hz** | **2.0 hr** |
| 0.37 mm | 100 V | 1.2e-12 N·m | 0.16 Hz | 19 min |
| 0.37 mm | 200 V | 5.0e-12 N·m | 0.30 Hz | 4.6 min |

At 40/40 V capture is 0.059 Hz — *inside* the old side-post band (0.005–0.07 Hz),
so on bandwidth alone the stator looks like a lateral move. It is not: the
mechanism is different in kind (variable-capacitance, charge-independent,
**static torque from rest**, which the synchronous side posts could not produce at
any drive level). The margin is thin at that drive level.

Ramp time scales linearly with target, so modest speeds stay practical even now:
~6 min to 0.5 Hz, ~12 min to 1 Hz. Only the 10 Hz target becomes impractical.

Includes the 3-phase stator amplitude (a₁² = 0.438) and the fraction of available m=8
coupling the electrode annulus actually sees (84.2% at h=0.37).

- **τ ∝ V², and rises steeply as h shrinks** (attenuation ∝ exp(−m·h/r)).
- `h = levitation height − 0.043 mm` (board thickness above the plate face).
- Capture bandwidth = `sqrt(m·τ_max/I)/2π` with **m = 8**. (The Notion page's own
  `sqrt(2τ/I)/2π` is the *side-post* case; that 2 is the induced dipole's 2-fold symmetry,
  not a universal constant.)
- Max ramp rate = `0.5·τ_max/(2πI)` Hz mech/s (the 0.5 is the ≤50% torque margin).
- **`I = 1.1e-11 kg·m²` (±10%) — measured mass + model shape** (2026-09-30).
  Capture and ramp numbers above use it (capture ∝ I^-1/2, ramp time ∝ I).
  Every torque, ramp-rate and drag number in this repo scales with it.

  | | |
  |---|---|
  | Assembly weighed 2026-09-30 | **7 mg** (0.007 g; ±0.5 mg if the balance reads to 1 mg) |
  | Sail, SAL-001 "Sail Al V1.0" (Al shim, 0.1 mm; drawing `~/Downloads/Screenshot 2026-07-09 134751.png`) | 1.156 mg (drawing: 1.16), **I_sail = 1.61e-12** by integrating the outline |
  | Disk = 7 − 1.16 | **5.8 mg** |
  | I_disk = k·M·R², R = 1.75 mm | k = 0.51 (SolidWorks shape) to 0.54 (`optimize_sail.py` slotted disk) → 9.1–9.7e-12 |
  | **Total** | **1.07–1.13e-11** (0.99–1.21e-11 over ±0.5 mg) |

  **Superseded values — do not reuse:**
  - `1.88e-11`: `optimize_sail.py` slotted disk (1.26e-11, 7.62 mg) + the
    script's *reference* sail (2×2 mm wings at r_c = 2.625 mm, 6.19e-12). That
    is an older sail, not SAL-001, and the disk is heavier than the real one.
    It lives on in `momentum-simulation/thermal_noise_spindown.py:37` (Dave's,
    left untouched), `analysis/laser_dark_vs_on.py:117`, and in the dated analysis notebooks, kept as records:
    their torque/force numbers are ×0.585 too high.
  - `1.7e-11`: SolidWorks assembly (11.05 mg). The shape is right, but the
    CAD mass is 58% heavier than the weighed rotor.

  Remaining unknowns: the balance resolution, and the disk OD (it enters as R²).
  The disk is lighter than any model (a solid 3.5 mm × 0.5 mm graphite disk
  would be 10.6 mg), so it is probably thinner or less dense than assumed.
  Its mass is measured, so that does not change I.

  **To measure it** rather than calculate it: apply a known static torque from
  rest and track the angular acceleration, α = τ/I, on LES or the camera. That
  needs the stator torque known independently, so it is not free — but a
  measured `I` would remove the largest shared uncertainty in this file.

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
| — | GND | grounded by a wire from a top GND pad (r = 10.8, az 60/240°) to a base screw. The bare bottom ring (r 2.95–3.40) barely overlaps the 1/4" magnet and does not make contact |

> ✅ **RESOLVED 2026-08-24 by continuity check at the chamber opening.** V1 IS
> the centre electrode. Clockwise viewed from the pad face the four terminals
> read V1, V3, V4, V2 (cross-checked counterclockwise too — both directions
> agree). Combined with the board's CCW-positive azimuth convention
> (`generate_flex_revG.py`), this gives **(A, B, C) = (V2, V4, V3)**, i.e.
> `PHASE_ELECTRODES = (2, 4, 3)` in `stator_epics_drive.py`. The old `(2,3,4)`
> swaps B and C — a transposition, not a cyclic rotation, so it would still spin
> the rotor but backwards and mislabelled. Full derivation:
> `apparatus_log.md`, "2026-08-24 — electrode map CONFIRMED".

- Sector electrodes span **r = 0.69 → 1.95 mm**; inner edge sits at the 0.08 mm
  minimum-copper limit.
- **No ground copper inside the active area** — it would screen the drive field.
- **CTR as a charge probe:** 10 V gives E_z ≈ 1.7e4 V/m on axis → 2.7e-15 N per elementary
  charge. Driven at the vertical trap frequency with Q ~ 1e3–1e4, few-electron resolution
  by lock-in is plausible; calibrate against a UV/filament charge step.

### HV amplifier (drives V1–V4, homemade board, David Moore design)

Identified 2026-08-27 from the Fusion 360 Electronics schematic (a `.fsch` is a
zip archive containing a plain Eagle-XML `.sch` — ask Claude for the extraction
method if needed again). **U1 = Microchip HV265-I/QE**, 4-channel 205 V
high-voltage op-amp array, TSSOP24, datasheet DS20006234A. Per channel:
`VIN → Hi-V Amp → HVOUT`, `FB` tied directly to `HVOUT` (fixed closed-loop
gain, no external divider).

- **Gain: datasheet spec 75.4–88.4 V/V (typ 82).** Measured 2026-08-28:
  171 V / 2.1 V ≈ **81.4 V/V** — matches spec closely; the chip is behaving as
  designed. Independent Aug-25 measurement (`_EXC` path) got a consistent
  ~0.013 V/count amplitude.
- **VOLTS_PER_COUNT ≈ 0.0134 V/count** (171 V / 12800 counts, `_EXC` path,
  2026-08-28) — supersedes the old 0.03125 and 0.00625 guesses. **Caveat: this
  is the `_EXC`-path gain. Whether `_OFFSET` (what `stator_epics_drive.py`
  actually drives) has the same slope is UNVERIFIED.**
- **The amp is BIPOLAR** — confirmed by measurement (Aug 25 and Aug 28) *and*
  directly by David Moore, 2026-08-28: "the +/- is completely normal." This
  overturns the unipolar assumption in `stator_drive.py`/`three_phase_drive.py`
  (`dc = amp`, "keep the swing ≥ 0"). Note the HV265 datasheet's own `HVOUT`
  spec range reads as unipolar (1.85 V min to `VPP − 10 V` max) — trust the PI
  and the direct measurement over that typical-range table.
- ✅ **CORRECTED 2026-08-31 — there is NO special "zero-crossing count."** An
  earlier revision here claimed the amp's zero sat near ~6400 counts. It does
  not. Molly, definitively: *"The high voltage amp is bipolar. It takes any DC
  input and translates that to the 0 V point with a bipolar amplitude. The
  voltage I send to the HV amp must be positive and between 0–2 V."* So **any**
  DC input becomes the output's zero — 6400 was simply where the offset happened
  to be sitting during the Aug-25 and Aug-28 measurements. That, not a
  coincidental zero-crossing, is what explains the Aug-25 log's item 5 ("offset
  did not create a DC pedestal"): no commanded offset ever will.
- **The input range is a hard constraint: positive, 0–2 V.** Measured, 12800
  counts ↔ 2.1 V at `VIN`, and `V{n}_LIMIT` is 12800 — so the commanded swing
  must stay within 0 → 12800 counts. This makes **`dc >= amp` mandatory**, and
  **`dc = amp = 6400` exactly fills the input range**. The pedestal is what keeps
  the input positive; it is not spare swing to be reclaimed. More AC amplitude
  requires a larger input range or a higher `VPP`, not a rebalance of dc against
  amp. Full account: `hv_amp_dc_investigation.md`.
- `VPP` is set by a 10 kΩ trimmer off a front-panel banana-jack LV input, same
  node that powers `VDD` and the on-board HV DC-DC converter. Nobody has
  checked the applied LV voltage or trimmer position.
- **Verify scope coupling before trusting any absolute-voltage reading.** AC
  coupling silently removes the true DC level and re-centres the remainder about
  0 V, which is visually indistinguishable from a genuinely bipolar signal. This
  cost significant time on 2026-08-26/27. DC-couple both channels and perform a
  GND-coupling zero-line check first.

### ⚠ Assembly / safety

- **The plated barrels make all four screws live, up to 200 V.** They thread into tapped
  PEEK so they are isolated from the plate — use stainless or silver-plated hardware and
  check screw length so no tip protrudes toward ground.
- **Max screw head / washer OD is 9.5 mm** before it reaches another net.
- Clock the ring-terminal tongues radially outward.
- Nothing may sit between the board centre and the magnet.
- **Board height:** shims go under the PEEK plate, and the flex lies flat (2026-10-27).
  No metal under the pads: the bottom coverlay opening exposes bare GND around each
  live pad, so a metal shim shorts that phase to GND.
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

1. Continuity at the four terminals; GND pad to base continuity; hipot 250 V
   net-net **and** net-to-magnet.
2. Measure V1.3 levitation height over the installed board → confirm the gap h.
3. **DC detent test:** energise one phase → rotor snaps to one of 8 detents; stepping
   A→B→C walks it 15° mech per step. Directly calibrates τ_max vs V².
4. Max sustainable ramp rate vs V (expect ∝ V²) — confirms the capacitance-motor mechanism.

**All four are fixed-frequency or DC — none needs a frequency ramp.** That matters for
choosing a drive backend (below).

### Known hardware issues

- There is a **bright deposit near the centre of the rotor's underside**. That face flies
  ~0.37 mm off the board and τ ∝ exp(−m·h/r), so anything standing proud there costs real
  torque.
- Open from the design: measure the V1.3 levitation height; confirm the magnet sits flush
  in the plate's Ø7 hole; cross-check the quasi-planar exp(−m h/r) coupling model against
  3-D BEM/COMSOL.

---

## Driving it

**Status (2026-08-28): the stator has driven a real 3-phase field.** First live
3-phase run 2026-08-24 (`stator_epics_drive.py --amp 4800 hold -f 0.02`, ~158 s):
**electrically verified correct** — relative phases −120.0°/−120.0° to the
decimal, amplitudes matched to 4 sig figs, f_elec matched commanded, V1 (CTR)
flat at 0 throughout, CCW rotation in board coordinates confirmed straight from
the phase-vs-azimuth data (independently re-confirms m=8). **The rotor did not
hold lock** — slipped/unlocked, attributed to being outside capture bandwidth
or camera handedness, explicitly NOT a wiring or phasing fault (both are
measured and confirmed). Earlier single-electrode result (2026-08-21): DC on V2
at 6400 counts collapsed the rotor's libration 2.6× (rms 22.5 → 8.6) and held it
180 s; 3200 counts did nothing — a detent capturing a moving rotor, a static
torque from rest the old side posts could never produce. **That bracket's
interpretation is genuinely open again** given the bipolar/zero-crossing finding
above (see "HV amplifier") — re-derive it once the true `_OFFSET` zero-crossing
is known, don't take "6400 > 3200 so bigger pedestal wins" at face value either
way. Full record in `apparatus_log.md`.

| script | status |
|---|---|
| **`lab_utils/stator_epics_drive.py`** | **THE drive. EPICS-only. Use this.** |
| `lab_utils/stator_drive.py` | Physics reference only — its backend cannot run (see below) |
| `lab_utils/three_phase_drive.py` | Superseded; never zeroes `TRAMP`, so its run was low-passed |
| `lab_utils/sweep_oscillator_reverse.py` | Broken — the reversal cancels itself (see above) |

### `stator_epics_drive.py` — the working drive

`status / calibrate / detent / hold / spinup / stop`. Dry-run by default, `--live` to
touch hardware; a dry run advances a *virtual* clock, so a 65-minute spin-up rehearses
in under a second.

**EPICS only** — `_OFFSET`, `_TRAMP`, `DRVON`, nothing else. That was a deliberate call
and it is the right one:

- the commanded values are themselves archived EPICS records, so the stimulus sits next
  to the `V{n}_OUT_DQ` response in the same NDS fetch;
- it sidesteps the AWG slot limit, the test-point grant, and — decisively — **the cymac
  GPS clock offset**. An AWG excitation needs an absolute GPS start time to make three
  phases coherent, and that start time must be in the **front end's** clock
  (`Y1:DAQ-DC0_GPS`), not true GPS. Use the wrong clock frame and the phases are
  silently randomised. Writing offsets from Python has no
  absolute-time dependence at all.

**The cost is bandwidth.** Software-timed writes are good to a few Hz electrical.
Since `f_elec = 8 × f_mech`, at a 200 Hz update rate:

| f_mech | f_elec | samples/cycle | verdict |
|---|---|---|---|
| detent | DC | — | ideal, pure `caput` |
| 0.05 Hz | 0.4 Hz | 500 | comfortable |
| 0.5 Hz | 4 Hz | 50 | fine |
| 2 Hz | 16 Hz | 12 | coarse |
| 10 Hz | 80 Hz | 2.5 | not possible |

**Every first-article test is DC or a fixed frequency below capture, so this covers the
whole near-term programme.** AWG only becomes necessary for real speed.

### ⚠ Live channel facts (2026-08-21)

- **`V{n}_TRAMP` was found set to 1.0 s on all four electrodes, and it resets between
  runs.** `_OFFSET` writes are *ramped* over TRAMP, so a nonzero value low-passes a
  software-generated sinusoid into a smaller, phase-lagged, distorted waveform — while
  the commanded values, and anything the writing script logs, still look perfect.
  **Anything writing offsets must zero TRAMP first.** `stator_epics_drive.py` zeroes it
  for the duration of a run and restores it after; `three_phase_drive.py` never did,
  which is a prime suspect for why its run produced movement but not rotation.
- **`V{n}_OUT` does not exist as an EPICS record** (fast test point, NDS-only). Use
  **`_OUTMON`** for the slow output readback, `_INMON` for the input.
- `_GAIN` reads 1.0. `SW1R` reads 12. **`SW2R` was observed at 768, then 1792 a few
  minutes later** — 1792 contains the 1024 output-enable bit and 768 does not, so
  **check the output switch is on before concluding the drive is dead.**

### Filter-module switch bits — MEASURED 2026-09-09

Probed on `OUTS_V1` (output off, no signal) by writing `SW2S` and reading which
`SWSTAT` bit lit:

| `SW2` bit | `SWSTAT` bit | meaning |
|---|---|---|
| 256 | 13 | **LIMIT** — clamps at `V{n}_LIMIT` |
| 512 | 15 | **DECIMATION** — output anti-alias for the 16 Hz monitors |
| 1024 | 12 | **OUTPUT** — connects the module to the DAC |

`SW1` bit 4 = INPUT (`SWSTAT` 10), bit 8 = OFFSET (`SWSTAT` 11).

**Resting states: `V1..V4` = 768** (LIMIT + DECIMATION, output off), **1792 while
driving**, and **`LES_*`/`MON` = 512** (DECIMATION only — their `LIMIT` is 1, not
12800, so the limiter is deliberately not engaged there).

⚠ **Never write a whole SW2 word to clear the output.** `SW2` carries the
limiter and decimation bits alongside it, and writing 0 silently disengages
both. `V{n}_LIMIT = 12800` is the hardware backstop that keeps the amp input
inside 0–2.1 V no matter what commands it — a software amplitude check in one
script is not a substitute. Clear the output with `sw2 & ~1024`, preserving the
rest. `stator_osc_drive.py stop` did exactly this wrong until 2026-09-09 and
left all four electrodes with the limiter disengaged.

### ⚠ `LES_PIT` and `LES_YAW` are X AND Y POSITION, not pitch and yaw angle

**The names are misleading and have caused real reasoning errors.** The sensor is
a **lateral-effect sensor**: it reports where the beam centroid lands, in two
orthogonal position axes. Neither channel is an angle.

- `LES_YAW` = **x** position
- `LES_PIT` = **y** position
- `LES_SUM` = **total light** (the denominator; also the dropout detector)

**Do not reason "tilt will show up in PIT".** Both axes see a mixture of
everything that moves the centroid: the sail sweeping through the beam, the
rotor translating, and tilt changing the silhouette. There is no channel that
isolates tilt. On 2026-09-10 an entire argument about the drive exciting
out-of-plane motion was built on the wrong reading of these names, and was wrong.

**The y axis is ~1000x attenuated, but NOT blind — MEASURED 2026-09-10.** From
an hour of quiet undriven data (front-end GPS 1473050000–1473053600):

| | x (`YAW`) | y (`PIT`) |
|---|---|---|
| broadband rms | 915.6 | 0.357 |
| per-bin noise floor | 7.38 (rotor motion) | **0.00174** (instrumental) |
| line SNR, 0.185–0.45 Hz | 3–15 | **25–76** |

**Coherence between the axes is 0.88–0.99 at every line**, so y is measuring the
same physical motion, merely projected badly. That makes the imbalance a
**geometry/alignment problem, not a light problem** — `LES_SUM` sits at ~800
counts with no dropouts.

Note the two axes are limited by *different* things: y by instrument noise, x by
the rotor's own broadband motion. So **x is not light-limited at all**, and y has
SNR 25–76 of headroom — roughly 4x less light is safe under any assumption, 10x
is the edge depending on whether the sensor is shot- or electronics-limited
(untested).

**What balanced x and y would buy**, and why it is worth the alignment work:
plotting x against y gives the actual 2D trajectory — a line means pure
libration, an ellipse means whirl, a circle means the rotor centre is orbiting.
That distinguishes wobble from in-plane motion directly, which no single axis
can. It would also settle the rotation fold number geometrically, without a
stopwatch.

### ⚠ Reading libration off LES: halve the frequency (2026-09-09)

**While the rotor is librating, `LES_YAW` reports 2× the mechanical frequency.**
The channel responds to `|θ|`, so it completes a cycle on every one-way swing.
Confirmed two ways: the swing timed by eye (1.6 s each way, ~3.2 s round trip)
and the waveform shape (skew −0.748, kurtosis +0.915, broad maxima with sharp
cusps at the centre crossings, even harmonics dominant). Full entry in
`apparatus_log.md`.

- **Divide any LES libration line by 2** to get the mechanical frequency.
- **Do not apply this to rotation.** A rotor going all the way round gives a
  genuine 1×/2×/3× series, fundamental confirmed against the camera on 09-08.
  Rectification is a turning-point phenomenon and does not arise there.
- Amplitude inferences from `f/f₀ = π / (2 K(sin(θ₀/2)))` are unaffected — the
  factor of 2 cancels in the ratio when both come from this channel.
- **Isolate LES/MON at their own output switches (`SW2R 512`), leaving gains at
  1.0** — not by zeroing the gains. The electrode input switch cannot separate
  them, since the matrix sums into `Sum*[2]` upstream of `V{n}`. Sensing is
  unaffected either way: `LES_*_IN1_DQ` taps upstream of both.

### RESOLVED (2026-08-21): the model routing, traced from `y1rds.mdl`

Every signal line in `/opt/rtcds/userapps/mastqg/y1rds.mdl` was parsed. `DRV` is a
single `cdsOsc`; its quadrature pair `s`,`c` passes through two `Switch` blocks gated
by `DRVON` (passing `Constant = 0` when off), then fans out through two `×(−1)` gains:

```
V1 = In1 + s    V2 = In2 + c    V3 = In3 − s    V4 = In4 − c      (all Sums are ++)
```

> ⚠ **SUPERSEDED 2026-09-08 — the model was changed.** The `×(−1)` blocks were
> replaced with `Mux → DRVMTRX (cdsRampMuxMatrix 2×4) → Demux`, and the stator
> now drives a verified three-phase field from the oscillator (−120.00° spacing,
> amplitudes matched to 5 significant figures). See
> `y1rds_model_change_muxmatrix.md`.
>
> The claim below that two quadratures "cannot make 120° phases" was **wrong**:
> `cos(θ+φ) = cosφ·cosθ − sinφ·sinθ`, so two quadratures span every phase at that
> frequency. What was missing was only the ability to mix them per electrode.
> That error is why the oscillator route was abandoned in August.

So the fan-out WAS (sin, cos, −sin, −cos): **2 degrees of freedom across 4
electrodes.** It could not make 120° phases whichever three you picked (V2/V3/V4 carry
cos/−sin/−cos = 0°/90°/180°), and V4 is rigidly locked anti-phase to V2 — there is no
way through `DRV` to give the centre electrode an independent drive. **`DRVON = 0`
removes the fan-out entirely**, after which each `V{n}` is driven only by what you
write to it. (`INMON` reads 0 on all four, so nothing else is arriving at `In{n}`.)

This is why `stator_drive.py`'s `PHASE_GAIN_PVS`
(`Y1:RDS-OUTS_V{1,2,3}_{SIN,COS}GAIN`) was always fiction — those records do not exist,
and no per-electrode gain pair does. Keep that script for its torque/capture/ramp
formulas, which are validated; do not try to run its backend.

### ✅ `VOLTS_PER_COUNT` — MEASURED 2026-08-28, ≈0.0134 V/count on the `_EXC` path

See "HV amplifier" above for the full derivation (171 V / 12800 counts, gain
81.4 V/V, matches the HV265 datasheet's 75.4–88.4 V/V spec). Cross-validated
against an independent 2026-08-25 measurement (~0.013 V/count). Both supersede
`stator_drive.py`'s old `0.03125` placeholder.

**Still open: whether `_OFFSET` (the slow path `stator_epics_drive.py` actually
drives) has the same slope as `_EXC` (what was measured) is unverified.** Do not
assume they match without checking — this is exactly the kind of thing
`calibrate` exists to settle on the real drive path, not just the diagnostic one.

`stator_epics_drive.py` still sets `VOLTS_PER_COUNT = None` by default and
**refuses to print torque, capture or ramp limits until `--volts-per-count` is
passed explicitly** — kept that way deliberately even though a number now
exists, until it's confirmed on the `_OFFSET` path specifically. Its
`calibrate` subcommand is a DC staircase on one electrode for exactly this.

### ⚠ The DC pedestal is not cosmetic (applies to AC drive, not the DC detent)

Expanding τ = ½ (dC/dθ)V² for `V_k = V_dc + V_ac·cos(φ + δ_k)` over the 24-sector/3-phase
pattern gives **two** torque channels, both locking the rotor at the same speed f_elec/8:

| channel | couples to | amplitude | winds |
|---|---|---|---|
| ch1 | rotor m=8 | **V_dc · V_ac** | 1× per elec cycle |
| ch2 | rotor m=16 | V_ac² | 2× per elec cycle |

**At V_dc = 0 the m=8 channel vanishes identically**, leaving only m=16 — the stronger
rotor harmonic, but it suffers twice the gap attenuation. Maximising V_dc·V_ac subject to
V_dc + V_ac ≤ V_max gives **V_dc = V_ac = V_max/2**. A `--dc` override is worth having as
a diagnostic — **m=8 scales with V_dc, m=16 does not**, so varying it at fixed amplitude
separates the two channels.

> ⚠ **CORRECTED 2026-08-31.** A previous revision of this box claimed the amp
> had a "true zero-crossing near ~6400 counts" that `dc=amp` might land on by
> coincidence. **That is wrong** — the amp maps *any* input DC to its 0 V output
> point, so there is no special count to avoid (see "HV amplifier" above).
>
> **What this means for the pedestal is now an open question, not a settled
> one.** The commanded `V_dc` does not appear as a DC offset at the electrode.
> Whether that means the m=8 channel is genuinely off, or whether the analysis
> in this section needs restating in terms of what the amplifier actually
> delivers, has **not been resolved** — do not treat either reading as
> established. The measured facts are: `dc = amp = 6400` exactly fills the amp's
> 0–2 V input range and is the maximum commandable AC amplitude, and the drive
> demonstrably spins the rotor (2026-08-28).

### If AWG is ever needed (for speed only)

Not needed for any first-article test. If the programme ever wants ≳2 Hz mechanical:

`electrode_noise_generator.py` **cannot run** — it does `from cdsutils import awg` and
there is no `cdsutils.awg` module. The real API is a bare `import awg` (top-level
`site-packages/awg.py`), providing `Sine(chan, ampl, freq, phase, offset, start,
duration, restart)` with **phase in radians and start in GPS seconds**. Three Sines on
`V{n}_EXC` sharing one explicit `start` are a coherent three-phase drive — but with
`start=0` each excitation independently picks `GPSnow() + 4*EPOCH` at `.start()` time,
so the phases would be randomised per run. **And `awgbase.GPSnow()` returns *true* GPS,
not the front end's clock**, so `start` must come from `Y1:DAQ-DC0_GPS`. Limit is `MAX_NUM_AWG = 9` simultaneous channels.

To drive `_EXC` you must, per Aaron's verified recipe: set `GAIN = 1`, turn the module
**input OFF** (blocks the `Sum`, i.e. the DRV fan-out — a cleaner per-electrode kill
than `DRVON = 0`), and turn the **output ON** (`_EXC` does not reach the DAC otherwise).
Bits: `SW1` input = 4, `SW2` output = 1024.

`diag` SineResponse (headless diaggui, `diag -l -f <cmdfile>`) is the other route: its
XML takes index-aligned per-tone `Stimulus{Frequency,Amplitude,Offset,Phase}[i]` +
`StimulusChannel[i]`, phase in radians. Template:
`scripts/dipole/measure_actuator_gain.py` in github.com/aaronmarkowitz/labutils.
**Caveat: y1rds is NOT y1dmd** — that is proven on Aaron's front end, not this one, and
it inherits the same GPS-clock-frame question.

## Known script issues (`stator_epics_drive.py`, found 2026-08-28)

- **`banner()`'s DC-pedestal warning (`if dc == 0: ... m=8 channel is OFF`) only
  catches commanded count 0.** An earlier revision said this mattered because the
  amp's zero sat near ~6400 counts; **that was wrong** (2026-08-31 — the amp maps
  any input DC to 0 V out, so there is no special count). The `dc == 0` check is
  therefore not the trap it was described as. Whether a pedestal warning is
  wanted at all depends on the open pedestal question above.
- ✅ **`check_amplitude()`'s rejection of negative counts is CORRECT** —
  resolved 2026-08-31, and an earlier revision here wrongly called its
  justification obsolete. **The amp input must be positive and within 0–2 V**, so
  a negative commanded count is genuinely out of range. Keep this check.
- ✅ **`--dc` default (`= --amp`) is CORRECT and should not be lowered.** With
  12800 counts ↔ 2.1 V and `V{n}_LIMIT = 12800`, `dc = amp = 6400` puts the amp
  input at 0 → 2.1 V, exactly filling its range. `dc >= amp` is required to keep
  the input positive. Reducing the pedestal to "recover swing" would command the
  input negative — do not do it.

## Conventions

- **Ask before pushing.** Commit messages explain *why*, not just what.
- Hardware scripts default to dry-run; prefer it when testing.
- Don't delete "non-functional" scripts unilaterally — Molly wants to prune them together.
- Generated figures are gitignored (`plots/`, `analysis/*.png`); notebooks and notes are tracked.
- `analysis/ringdown_analysis_executed.ipynb` is misnamed — it is a *variant* with the
  window shifted 3 min earlier, not a re-execution.
