# `y1rds` model change: ±1 fan-out replaced with a mux matrix

> ## ✅ DONE AND VERIFIED — 2026-09-08
>
> Built on cymac1 at 17:31, installed and restarted the same evening. Verified
> from `V{n}_OUT_DQ` with the oscillator at `DRV_FREQ = 0.32 Hz`, gains 2000,
> **output switches still disabled** so nothing reached the chamber:
>
> | | amplitude | phase | relative |
> |---|---|---|---|
> | V2 (A) | **2000.0** | −43.07° | 0.00° |
> | V4 (B) | **2000.0** | −163.07° | **−120.00°** |
> | V3 (C) | **2000.0** | +76.93° | **+120.00°** |
> | V1 (CTR) | 0.0 | — | silent, as specified |
>
> Amplitudes identical to five significant figures and equal to the commanded
> oscillator gain; relative phases exact to the hundredth of a degree; DC zero
> throughout. That clears the same bar as the verified 2026-08-24 and 08-28
> runs, **from the oscillator with no AWG involved**. Step sense is V2 → V4 → V3
> at −120° each, matching the 08-24 convention, so no sign flip was needed.
>
> ### Commissioning finding: the electrode input switch gates the matrix
>
> The matrix output is summed into `Sum*[2]`, upstream of each electrode filter
> module, so `V{n}` receives the matrix drive and the LES/MON signal as a single
> summed input. The module's SW1 input bit therefore gates both together. On the
> first test V3 and V4 responded (`SW1R = 12`) while V1 and V2 were silent
> (`SW1R = 8`, input bit clear); setting `V1_SW1S` and `V2_SW1S` to 12 restored
> them.
>
> The consequence for LES decoupling is that the electrode input switch is the
> wrong place to separate the two signals, since by that point they have already
> been added. Separation must occur at the source, upstream of the Sum.
>
> ### Isolating LES/MON: source output switch, not source gain
>
> Each source is isolated at its own **output switch**, with its gain left at the
> nominal value. Configuration verified 2026-09-09:
>
> | module | GAIN | SW2R | output |
> |---|---|---|---|
> | `LES_PIT` | 1.000 | 512 | off |
> | `LES_YAW` | 1.000 | 512 | off |
> | `LES_SUM` | 0.000 | 512 | off |
> | `MON` | 0.000 | 512 | off |
>
> The output switch is preferred to zeroing the gain for three reasons. Its state
> is a boolean and is unambiguous in `SW2R`. The gain is a calibration value
> worth preserving rather than overwriting and later having to restore. And gain
> changes are ramped over `TRAMP`, so they pass through intermediate values,
> whereas the switch acts cleanly within one sample.
>
> Sensing is unaffected by either method: `LES_*_IN1_DQ` records upstream of both
> the gain and the output switch.
>
> ### Record names — NOT what was predicted
>
> A ramp matrix does **not** use a `_GAIN` suffix (that was extrapolated from
> Aaron's `ACTS`, which is a *filter* matrix). The real interface:
>
> ```
> Y1:RDS-OUTS_DRVMTRX_SETTING_{r}_{c}    write the value here
> Y1:RDS-OUTS_DRVMTRX_LOAD_MATRIX        then trigger this -- all elements ramp in TOGETHER
> Y1:RDS-OUTS_DRVMTRX_{r}_{c}            readback of what is actually applied
> Y1:RDS-OUTS_DRVMTRX_RAMPING_{r}_{c}    1 while ramping
> Y1:RDS-OUTS_DRVMTRX_TRAMP              ramp time, seconds
> ```
>
> **Writing `_{r}_{c}` directly does nothing** — measured. Values only take
> effect via `SETTING_*` + `LOAD_MATRIX`, which is better than per-element
> writes: the phasing never passes through an inconsistent intermediate state.
> `TRAMP` came up at 0 after the build; set it (2 s works) or changes are steps.

**Original proposal follows, drafted 2026-09-08 before the work.**

One change — swap two hardwired `×(−1)` blocks for a 2×4 gain matrix — and the
stator can be driven entirely from the front-end oscillator over plain EPICS,
making the whole AWG stack (`stator_awg_drive.py`, `stator_chirp.py`,
`awg_reclaim.py`, the arming retry loop) unnecessary.

---

## Why: the fan-out was built for different hardware

Traced from `y1rds.mdl`, inside the `OUTS` subsystem:

```
DRV[2] ──→ Choice  ──┬──────────────→ Sum [2] → V1        (+s)
                     └─→ Product ───→ Sum2[2] → V3        (−s)
DRV[3] ──→ Choice1 ──┬──────────────→ Sum1[2] → V2        (+c)
                     └─→ Product1 ──→ Sum3[2] → V4        (−c)
DRVON ──→ Choice[2], Choice1[2]      Constant(0) → Choice[3], Choice1[3]
Constant1(−1) ──→ Product[2], Product1[2]
In1..In4 ──→ Sum..Sum3[1]            Ground ──→ DRV[1]
```

So `V1 = In1 + s`, `V2 = In2 + c`, `V3 = In3 − s`, `V4 = In4 − c` — the four
electrodes are locked to phases **0 / 90 / 180 / 270**.

That is correct for **four side posts in quadrature**, which is what this
apparatus used to have. The rev G stator is **three-phase**, needing 0 / −120 /
−240. The model was never updated when the stator was redesigned, and that
mismatch is the root cause of everything the AWG work has been routing around.

**It is not a shortage of degrees of freedom.** Two quadratures at one frequency
span every phase at that frequency — `cos(θ+φ) = cosφ·cosθ − sinφ·sinθ`. What is
missing is only the ability to *mix* them per electrode. `CLAUDE.md` currently
says the fan-out "cannot make 120-degree phases"; that is wrong as stated, and
this document supersedes it.

---

## The change

```
DELETE   Constant1  (the −1)
DELETE   Product, Product1        ← the two ×(−1) blocks
ADD      Mux                       2 lines → 1 bus
ADD      cdsRampMuxMatrix          2 inputs × 4 outputs
ADD      Demux                     1 bus → 4 lines
```

New signal path, everything downstream untouched:

```
DRV[2] (s) ─┐                                              ┌→ Sum [2] → V1
            ├→ Mux → [2] → MATRIX → [4] → Demux ───────────┼→ Sum1[2] → V2
DRV[3] (c) ─┘        (gated by DRVON via Choice/Choice1)    ├→ Sum2[2] → V3
                                                            └→ Sum3[2] → V4
```

`DRV`, `DRVON`, `Choice`, `Choice1`, the four `Sum` blocks, the `V1..V4` filter
modules and the DAC wiring (`OUTS[1..4]` → `DAC_0[12,14,15,16]`) all stay as they
are.

### Precedent — this pattern already runs on this front end

`y1dmd` (Aaron's microdiamond model, same `cymac1`) does exactly this shape:

```
Mux2 → ACTS (cdsFiltMuxMatrix) → Demux2 → POLES[1..4] (cdsFilt) → DAC_0[1..4]
```

Their `POLES` are the direct analogue of our `V1..V4`. So this is copying a
working local pattern, not inventing one.

### Which matrix part

**Use `cdsRampMuxMatrix`**, not `cdsFiltMuxMatrix`.

| part | element is | verdict |
|---|---|---|
| `cdsMuxMatrix` | plain gain | works, but gain changes are steps |
| **`cdsRampMuxMatrix`** | **ramped gain** | **use this** — changes glide, so phasing can be altered on a running drive without kicking the rotor |
| `cdsFiltMuxMatrix` | full filter module per element | overkill here |

`cdsFiltMuxMatrix` is what Aaron uses because they inject a separate excitation
into each electrode–DOF path to measure actuator gains. We need six constant
numbers. And **per-electrode filtering is already available downstream** —
`V1..V4` are `cdsFilt` blocks with ten biquad slots each, currently *empty*
(`Y1RDS.txt` defines zero filter sections on them), so any future shaping can be
loaded with foton without touching the model.

---

## The gain values

For an electrode whose waveform should be `cos(ωt + φ)`:

```
cos(ωt + φ) = cos φ · cos(ωt)  −  sin φ · sin(ωt)
```

so the coefficient on the **cos** input is `cos φ`, and on the **sin** input is
`−sin φ`. (This is the inverse Clarke transform; the name adds nothing beyond
that identity.)

With `(A, B, C) = (V2, V4, V3)` — confirmed 2026-08-24 by continuity check — and
matrix inputs ordered **(s, c)** = `(DRV[2], DRV[3])`:

| output | electrode | phase | s coeff | c coeff |
|---|---|---|---|---|
| row 1 | V1 (CTR) | — off | `0` | `0` |
| row 2 | V2 (A) | 0° | `0` | `1` |
| row 3 | V3 (C) | −240° | `−0.8660` | `−0.5` |
| row 4 | V4 (B) | −120° | `+0.8660` | `−0.5` |

`0.8660 = √3/2`. Note rows 3 and 4 are **not** in electrode-number order — V3
carries phase C and V4 carries phase B. Getting this backwards swaps B and C,
which still produces a clean travelling wave but **runs the field the other way**
— the exact error that was in `stator_drive.py` until 08-24.

Naming will follow the RCG convention seen on `Y1:DMD-ACTS_{r}_{c}_GAIN`, so
expect `Y1:RDS-OUTS_{NAME}_{row}_{col}_GAIN` — eight records.

---

## What it buys

**Every failure mode from the AWG work disappears**, because AWG is no longer
involved:

- no arming failures (intermittent, still unexplained as of 09-08)
- no leaked AWG slots, no `MAX_NUM_AWG = 9` ceiling
- no front-end-vs-true-GPS clock frame trap
- no streaming underruns
- no drive dying when its client process exits

**Frequency sweeps become trivial and phase-continuous.** `DRV_FREQ` moved with
`DRV_TRAMP` gives a smooth, phase-matched frequency change — the mechanism
`sweep_oscillator.py` already uses successfully. (`DRV_TRAMP` currently reads
100 s.) That removes the need for `stator_chirp.py` entirely, and sidesteps
`awg.SweptSine`'s `restart=sweeptime` looping bug.

**Direction reversal becomes a sign flip** in two matrix elements rather than a
cable swap.

**Control is plain EPICS**: `DRV_FREQ`, `DRV_SINGAIN`/`DRV_COSGAIN` for
amplitude, eight matrix gains for phasing. All archived alongside the response.

Note this is setting *parameters*, not synthesising a waveform — so the slow
EPICS path is entirely appropriate, unlike the `_OFFSET` write loop which failed
because it tried to trace out a sine through a channel sampled at ~16 Hz.

---

## Verification after the change

Do not assume the phasing came out right — the sign conventions here have bitten
repeatedly (the `_OFFSET` path and `awg` differ from each other in the sign of
`phase`, measured 08-28).

1. `DRVON = 1`, `SINGAIN = COSGAIN =` small, `DRV_FREQ` = 0.32 Hz.
2. Capture `V{2,4,3}_OUT_DQ` at 1024 Hz over ≥100 s from NDS.
3. Fit each at the drive frequency. **Pass = relative phases −120.0° and
   −120.0°, amplitudes equal to ~4 significant figures.** That is exactly the
   check that validated the 08-24 run and the 08-28 AWG drive, so there is a
   known-good reference to compare against.
4. Confirm V1 stays flat at 0.
5. Phase should *decrease* with increasing azimuth (V2 15° → V4 105° → V3 195°),
   i.e. `φ = −8θ`, giving CCW rotation in board coordinates.

If the sequence comes out reversed, swap the two rows for B and C — do not
rewire anything.

---

## Risks

- **A failed build takes down the front end**, which is shared with Aaron's
  `y1dmd` experiment. Coordinate before rebuilding.
- **Simulink library availability**: MATLAB R2019a with Simulink is installed on
  worker2 and `y1rds.mdl` is NFS-mounted read-write, but the RCG parts library
  is not visible from worker2 — opening the model here would show unresolved
  library links. Edit on cymac1, or make the parts path available first.
- **Build tooling is on cymac1**, not worker2 (`rtcds` is not on worker2's path).
- `/opt/rtcds/yqg/y1/target_archive` exists, so there appears to be a rollback
  path — confirm before starting.
- **Do not hand-edit the `.mdl` as text.** It carries layout, port indices and
  library metadata that are easy to corrupt in ways that only surface at build
  time.

## What becomes obsolete

Once this is verified working, these exist only to work around the missing
matrix and should be retired rather than maintained:

- `lab_utils/stator_chirp.py` — never run live; re-arms every 8 s, which is the
  unreliable operation
- `lab_utils/awg_reclaim.py` — AWG slot recovery
- the arming retry loop and `ac_present()` in `stator_awg_drive.py`

Keep `stator_awg_drive.py` itself until the matrix is verified, and keep
`stator_epics_drive.py` for DC work (`detent`, `calibrate`) regardless — that
path is unaffected and correct for static values.
