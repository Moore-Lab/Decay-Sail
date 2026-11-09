# Oscillator chirp through f₀: predictions before the run (2026-11-06)

Runbook: `lab_utils/OSC_CHIRP_RUNBOOK.md` on branch `osc-chirp`. Sim: `osc_sim.py` (here), which uses the
F3 plant model (`f3_check.py` trap and `COUPLING_HOLD`, branch `feedback-drive`; `analysis/f3_20261104/README.md`).
All numbers below are simulated (derived); the coupling is measured only at amp 4000.

## The sim against C2 (2026-11-02, all holds at amp 6400): `python3 osc_sim.py c2`

End swing amplitude over the last 20 s of each 150 s hold, over 4 start phases × 2 directions. Measured from
`analysis/c2_20261102/README.md`. Start amplitudes are those in the drive-off gap before each hold.

| hold | f_elec, Hz | measured end | sim, coupling as at amp 4000 | sim, scaled to 6400 (V², assumed) |
|---|---|---|---|---|
| 1 | 0.100 | 39 | 18–64 | 24–83, over the top 5/8 |
| 2 | 0.200 | 49 | 25–71 | 23–104, over 1/8 |
| 3 | 0.400 | 41 | 21–67 | 43–92, over 2/8 |
| 4 | 0.100 | 54 | 18–54 | 112, over 7/8 |
| 5 | 0.200 | 96 | 44–71 | 36–112, over 1/8 |
| 6 | 0.400 | 99 | 87–118 | 37–139, over 4/8 |
| 7 | 0.155 | 111 | 89–124 | 46–120 |

- No C2 hold went over the top. The amp-4000 coupling matches 6 of 7 holds (not hold 5); the 6400 scaling
  predicts over-the-top runs that didn't happen.
- (Interpretation, not approved; **not supported by R1**, see below) C2's full amplitude acted like amp 4000 in this model.
  R1's direct test favours the coupling scaled to 6400 instead, so the C2 mismatch is more likely the sim's
  sensitivity near the barrier than a weaker drive.

## Predictions for the runbook (`python3 osc_sim.py chirp`)

| run | coupling as at 4000 (matches C2) | scaled to 6400 |
|---|---|---|
| R1 chirp 0.40 → 0.15 Hz, 104 s | no over-the-top; max swing 39–115° | over the top in 3/6 at ~11 s |
| R2 hold 0.31 Hz, 120 s, from rest | no; max 33–104° | over in 4/6 at 14–17 s |
| slower chirps (to 416 s), 0.40→0.15 or 0.34→0.20 | no; max 46–140° | not run |

## Result: R1, 2026-11-06 (chirp 0.40 → 0.15 Hz, amp 6400, from rest; then 10 min free swing)

Run: `apparatus_log.md` 2026-11-06; data Dropbox `data/osc_chirp/2026-11-06/` (worker2 `report.md`). Scripts:
`plot_drive.py` → `plots/osc_chirp_r1_drive.png` (the drive from OUT_DQ); `analyze_r1.py` → `plots/osc_chirp_r1_swing.png`.

**The drive** (measured, OUT_DQ): pedestals rose together over ~10 s; AC ramped in over ~3.5 s; three phases 120°
apart, 0–12800 counts; field frequency followed the commanded glide 0.40 → 0.15 Hz to 0.001 Hz, passing 0.31 Hz
~45 s in. There is no scope record of R1; the electrode-voltage panel is derived (W2 gains, AC coupling).

**The rotor** (measured, tracker):
- **No over-the-top, and no lock.** The swing reached 137° from rest, **0.74 of the barrier** (trap model), by ~45 s,
  while the drive passed 0.36 → 0.32 Hz. After that the swing did **not** follow the drive down: its frequency stayed
  ~0.25–0.30 Hz while the drive glided to 0.15 Hz, and the energy held at 0.45–0.75 of the barrier with no net growth.
- Per half-swing with the field on, the energy change was +0.11 ± 0.87 rad²/s² (mean ± std, 60 half-swings): after
  ~45 s the drive added and removed energy in roughly equal measure.
- After the drive: a steady swing −104/+130°, period ~3.6–4.0 s.
- Tracker: no 180° flips (largest frame-to-frame step 4.7°). Worker2's "±0.5 turn" bins came from the absolute angle
  crossing 360° → 0° (229.6 + 137 > 360). Two ~2.5 s recording stalls (137 s and 380 s after the drive start, drive
  off): `host_time` is processing time, so after each stall the frames arrive in a 0.03 s burst. The gaps are
  bridged in the plot; `trap_today.py` drops 3 s after each; the camera CSV has the true frame times.

**Trap today vs 11-04** (`trap_today.py`; derived): fitting U(φ) to today's 10-min free swing (energy conserved
apart from a linear decay; residual 0.06 rad²/s² rms), over −95..+105° it agrees with the 11-04 joint fit to
**0.15 rad²/s² rms** (max 0.43 at the +105° edge), on a curve spanning 0–6.1. So the trap has not changed
measurably since 11-04 over that range, and the energies here stand. The barrier itself (−160°) was not reached
today, so "0.74 of the barrier" uses the 11-04 barrier.

**Coupling at amp 6400** (derived; per half-swing, measured ΔE against the work the F3 coupling predicts with the
measured field, `ΔE = a·W_linear + b·W_2x`; a = b = 1 if it scales as V and V², a = 0.63 and b = 0.39 if 6400 pushes
like 4000). The field is put on host time by the DRVON write; the gains start at the next 16 Hz tick (0–0.06 s
later) and the camera adds ~0.02 s, so the physical shift is about +0.00 to +0.08 s:

| shift, s | a | b | R² (free) | R² scaled (1, 1) | R² as at 4000 |
|---|---|---|---|---|---|
| +0.00 | 1.02 ± 0.19 | 0.53 ± 0.27 | 0.37 | 0.34 | 0.31 |
| +0.05 | 0.97 ± 0.17 | 0.96 ± 0.25 | 0.47 | 0.47 | 0.38 |
| +0.10 | 0.85 ± 0.15 | 1.22 ± 0.22 | 0.57 | 0.55 | 0.42 |
| +0.15 | 0.69 ± 0.15 | 1.29 ± 0.20 | 0.61 | 0.58 | 0.45 |

- **Robust over the physical range:** the linear term scales with V (a ≈ 1.0 ± 0.2, about 2σ above 4000-like 0.63).
- **Not determined:** the 2× term (b from 0.5 to 1.0 ± 0.25 over the same range).
- (Interpretation, not approved) So the full amplitude does push harder than 4000, at least through the linear term.
  The earlier reading of C2 ("6400 acts like 4000") is not supported.
- R1's outcome itself discriminates nothing: the scaled-coupling sim gave over-the-top in 3 of 6 cases, and one run
  coming out "no" is consistent with that.
- (Interpretation, not approved) Why the chirp stalls below the barrier: once the swing is large, the arms pass
  several field crests per swing (8 × 100° = 800° electrical), so a fixed-rate field's pushes alternate in sign.

**Free swing, drive off, 10 min** (measured; derived where marked):
- Period 3.64–3.68 s at 97–108° amplitude, falling to 3.33 s at 89°. The trap model gives 3.76 → 3.52 s over the same
  range. The trap frequency is also known to drift with time (DECISIONS), so amplitude and drift aren't separable here.
- **Damping time τ = I/γ ≈ 32–35 min** (derived: energy decay over ⟨ω²⟩, through the trap model, assuming linear
  drag; 32 min from turning points, 35 min from the `trap_today.py` fit). A drifting trap would also look like an
  energy change, so this carries that caveat. DECISIONS' 88 min predates the October changes and the larger paint
  blob; the live-2 coast (11-04) also gave ~33 min. To be recorded by Molly if she wants it; not entered here.
