# Stator HV amp: design files

The homemade HV amp that drives the stator electrodes. Design: David Moore's Fusion 360
Electronics project ("High Voltage Amp Schematic", Fusion Team hub project
`diamagnetic_trap_alpha_decay`). Behaviour rules for operating it are in `CLAUDE.md`
("HV amplifier"); the open lab check is in `docs/STATUS.md`.

## Reading the files without Fusion

Fusion keeps a local cache under `~/Library/Application Support/Autodesk/Autodesk Fusion
360/<hub-id>/W.login/F/` (macOS). `_<Design>.<uuid>.fsch` (schematic) and `.fbrd`
(board) are **zip files**; inside, `…/electron.BlobParts/ExtFile.<uuid>.sch|.brd` is
plain **Eagle XML**, readable with `xml.etree.ElementTree`: `<part>` / `<element>` for
components, `<net><pinref part= pin=>` for connectivity. The `._xx` siblings are small
metadata files with no circuit content. A fresh File > Export gives the same structure.

**Resistor values are not stored** (R1–R5 have no value in either file). The 20
capacitors are AVX 2220PC105KAT1A (1 µF, 2220).

## What the netlist shows (read 2026-10-31; not yet confirmed on the board)

- `U1` = HV265-I/QE quad high-voltage op-amp; each channel's `FBn` is tied to `HVOUTn`.
  One HV supply (`VPP`, from DC-DC module `U$10`, `-VOUT` to GND); `VPP` is set by trimmer
  `RV1` + `R5` on the module's `VCONT` pin, fed from the front-panel LV banana jack.
- Per channel (channel 1 shown; 2–4 the same): `HVOUT1` → header J1 pins 1 and 3.
  - **Path A (direct):** J1-2 → J5-1; J5-2 and J5-4 → output BNC.
  - **Path B (through capacitors):** J1-4 → 5 × 1 µF in parallel → node = J5-3, and
    → R1 → GND.
- This looks like **jumper-selectable output coupling**: direct (DC-coupled, output
  0…VPP) or a high-pass (τ = R1 × 5 µF) that centres the output on 0 V. The 2026-08 bench
  test (DC step on `V4_OFFSET`, `TRAMP = 0`) saw the step "return to 0 over roughly 20 s",
  so τ ≈ 5–7 s (estimate). Ceramic capacitors lose capacitance at high DC bias, so
  R1 × 5 µF is an upper bound.
- To confirm: read R1's code, see which pins the J1/J5 jumpers join (STATUS); ask David
  whether J1/J5 are meant as a coupling choice.
