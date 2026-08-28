# HV amplifier: does it pass DC? — open investigation

**Status: OPEN. Started 2026-08-28 on worker2.** This file exists so an agent with
access to the Fusion 360 Electronics schematic (on Molly's laptop; the `.fsch` is a
zip containing a plain Eagle-XML `.sch`, readable without the app) can answer
questions that cannot be answered from the lab machine.

Context lives in `CLAUDE.md` ("HV amplifier") and `apparatus_log.md` (2026-08-25,
2026-08-28). **U1 = Microchip HV265-I/QE**, 4-channel 205 V HV op-amp array,
TSSOP24, datasheet DS20006234A. It drives electrodes V1–V4 of the rev G stator.

---

## Why this matters

The stator's torque has two channels (`CLAUDE.md`, "The DC pedestal is not cosmetic"):

| channel | couples to | amplitude |
|---|---|---|
| ch1 | rotor m=8 | **V_dc · V_ac** |
| ch2 | rotor m=16 | V_ac² |

and **at V_dc = 0 the m=8 channel vanishes identically.** So if the amplifier
cannot deliver a DC bias at the electrode, the m=8 channel — a central part of why
this stator was designed — is unavailable, and every drive ever run here has been
m=16 only. That would also change the torque, capture-bandwidth and ramp-rate
numbers throughout `CLAUDE.md`, which are all tabulated for the m=8 channel.

---

## What was observed (2026-08-28, worker2)

Measurement point: **BNC tee at the amp output** — one leg to the chamber
electrode, one to the scope. Scope **DC-coupled, 1X probe**. This is the real
electrode drive, not a monitor proxy.

1. **Static DC produces nothing.** Commanded a stationary m=8 detent:
   `V2/V4/V3_OFFSET = 12800 / 3200 / 3200` counts. The front end was verified to be
   outputting it, three independent ways:

   | | OFFSET (setpoint) | OUTMON (slow) | OUT_DQ (1024 Hz DAQ) |
   |---|---|---|---|
   | V2 | 12800.0 | +12800.00 | 12800.00, rms 0.00 |
   | V4 | 3200.0 | +3200.00 | 3200.00, rms 0.00 |
   | V3 | 3200.0 | +3200.00 | 3200.00, rms 0.00 |

   MEDM showed the offsets. The scope showed **0 V**.

2. **A DC step decays.** `V4_OFFSET` stepped to 6000 counts with `TRAMP = 0`:
   the voltage **rose, then returned to 0 over roughly 20 s.**

3. **AC is completely healthy at the same amplitudes.** Driving the three phases
   from AWG on `V{n}_EXC` at f_elec = 0.32 Hz, 6400 counts: amplitudes 2000.1 /
   2000.1 / 2000.1 against 2000 commanded (5 significant figures), relative phases
   120.00° apart, **THD 0.00%**, and the user confirmed on the scope that 6400
   counts of AC does not clip. Earlier: 6400 counts ≈ ±85 V, gain 81.4 V/V,
   matching the HV265 datasheet spec of 75.4–88.4 V/V.

So: **AC passes perfectly, DC decays away with τ of order 5–20 s.**

---

## Competing explanations — NOT yet resolved

Both fit the data above equally well, and they have different fixes:

- **(A) The signal path is AC-coupled** (series capacitor at the amp input, or on
  HVOUT), so DC never reaches the electrode at all.
- **(B) The amplifier can drive DC, but the node discharges** — a bleed resistor,
  a leakage path, or the scope's own 1 MΩ input loading a series-coupled output.
  Molly's instinct: *"I think I have a discharge time of 20 seconds"* and
  *"I don't recall the amp behaving like this previously."*

A third possibility worth keeping open: something in the DAC→amp path between the
front end and `VIN` blocks DC, in which case the amp is blameless.

---

## Questions for the schematic

Please answer against the actual `.fsch`, quoting component designators and values.

**Signal path, per channel (V1–V4):**

1. Is there a **series capacitor** anywhere between the input connector and the
   HV265 `VIN` pin? Value?
2. Is there a **bias network** setting `VIN`'s DC operating point (e.g. a divider
   to mid-rail)? Values, and what DC level does it set? *(Measured at the bench:
   VIN swings 0–2.1 V, which would be consistent with ~1.05 V of bias plus
   ±1.05 V of signal.)*
3. Is there a **series capacitor on `HVOUT`** before the output connector? Value?
4. Is there a **bleed / load resistor** from `HVOUT` (or the output connector) to
   ground? Value? *(This is the prime suspect for a ~20 s decay — with the
   electrode's small capacitance it would need to be very large, so the value
   matters.)*
5. What is the **feedback network**? `CLAUDE.md` currently records "`FB` tied
   directly to `HVOUT`, no external divider" — but the measured gain is 81.4 V/V,
   not unity, so please confirm what FB actually connects to.

**Supply:**

6. What sets **`VPP`**? There is a 10 kΩ trimmer off a front-panel banana-jack LV
   input feeding an on-board HV DC-DC converter. What is the converter part
   number, and what `VPP` range does the trimmer span?
7. Is the supply **single-ended (0 → VPP)** or **split (±VPP/2)**? What is the
   output referenced to? *(The measured output is bipolar, ±85 V about ground,
   while the HV265 datasheet's own `HVOUT` spec table reads unipolar — 1.85 V min
   to VPP−10 V max. Resolving this would explain the discrepancy.)*

**Escape hatches:**

8. Are there any **jumpers, links, or DNP (do-not-populate) positions** that would
   provide a DC path, or bypass a coupling capacitor?
9. Is the DC block (if any) **per channel or common** to all four?

---

## Bench tests that would settle it (worker2 + scope)

In rough order of value:

1. **Probe `VIN` and `HVOUT` simultaneously during a DC step.** *This is the
   decisive one.* If `VIN` holds its DC level while `HVOUT` decays → the block is
   inside or after the amp. If `VIN` decays too → it is the input coupling, and
   the amp is innocent.
2. **Disconnect the electrode**, leaving only the scope on the tee, and repeat the
   DC step. If DC now holds → the decay is a discharge into the chamber side, not
   an amplifier property.
3. **Swap 1X for a 10X probe** and repeat. If τ scales by ~10, the scope's input
   impedance is the discharge path and the amplifier is fine.
4. **Measure the corner frequency directly.** Drive a fixed-amplitude sine and step
   the frequency down: 0.5, 0.2, 0.1, 0.05, 0.02, 0.01 Hz electrical, recording the
   scope amplitude at each. The −3 dB point gives `f_c`, and `τ = 1/(2π f_c)`
   independently of the step test. *(Predicted from the step: f_c ≈ 0.02–0.03 Hz.
   Note the drives used so far, at 0.32 Hz electrical, are far above this and so
   are unaffected — consistent with the clean AC results.)*

Commands for the step test, run from `/home/controls/rds-code/Decay-Sail` on
worker2:

```bash
python -c "
from epics import caput; import time
caput('Y1:RDS-OUTS_V4_TRAMP', 0.0, wait=True)
caput('Y1:RDS-OUTS_V4_OFFSET', 6000.0, wait=True)
print('stepped to 6000 - watch VIN and HVOUT'); time.sleep(90)
caput('Y1:RDS-OUTS_V4_OFFSET', 0.0, wait=True)"
```

---

## If DC really is unavailable

Not fatal, but it changes the programme:

- The drive is **m=16 only** (`∝ V_ac²`). Rotor speed is still `f_elec / 8` —
  `CLAUDE.md` notes both channels lock at the same speed.
- `V_ac` is already at the amplifier ceiling (±85 V at 6400 counts), so the
  remaining torque lever is **the gap**. Extrapolating the m=8 rows in `CLAUDE.md`
  (0.37 → 0.27 mm gives 3.17×, implying a characteristic radius r ≈ 0.69 mm, which
  matches the electrode inner radius), the same shim is worth roughly **10× on
  m=16** because the exponent in `exp(−m·h/r)` doubles. That makes the 0.1 mm shim
  the single largest available gain anywhere in the system. **Treat ~10× as an
  estimate**: it extrapolates a model that `CLAUDE.md` lists as never cross-checked
  against 3-D BEM/COMSOL.
- The **2026-08-21 "DC detent"** result needs re-interpretation. It held DC for
  180 s, but if the field decays in ~20 s then there was no drive for 160 of those
  seconds. The claim that it demonstrated *"a static torque from rest, which the
  synchronous side posts could not produce at any drive level"* does not follow
  from that measurement — it was a decaying transient. The underlying
  variable-capacitance physics is unaffected; only this evidence for it is.
  The "capture threshold between 3200 and 6400 counts" bracket is likewise a
  response to a transient, not a clean V² measurement.
- **`--park` in `lab_utils/stator_awg_drive.py` cannot work** and should not be
  used: a stationary detent decays by construction.

---

## Also worth knowing (found 2026-08-28, unrelated to the DC question)

- **AWG works on this front end, but `start` must be in the FRONT END's clock
  frame** — `Y1:DAQ-DC0_GPS + lead`, *not* `awgbase.GPSnow()`. `awg.py:128`
  defaults `start` to `GPSnow() + 250 ms`; the front end runs **+8376 s** fast
  (drifting: 5836 s on 06-03, 7630 s on 08-21), so the default lands ~2.3 hours in
  its past and the excitation silently never plays, with no error raised. This is
  why every previous AWG attempt here "didn't work."
- **The `_OFFSET` write path cannot carry AC above ~0.1 Hz rotor.** The front end
  samples EPICS settings on its slow cycle (~16 Hz), so at 4 Hz electrical it sees
  ~4 samples/cycle and emits a **square wave** — measured harmonics at 1/3, 1/5,
  1/7 of the fundamental, THD 38.8%, phases 0/180/180 instead of 0/−120/−240. No
  write rate fixes this. The AC must be generated in the front end (AWG).
- `awg.SweptSine` passes `restart=sweeptime` internally, so it **loops** the sweep
  — it would snap back to the start frequency mid-spin-up. Not usable as-is.
- The electrode filter banks are **flat**: `Y1RDS.txt` defines zero filter sections
  on `OUTS_V1..V4` (the only filter in the file is a PID on `PD`). No foton work is
  needed for phase or amplitude control, and nothing in the bank can distort the
  drive.
