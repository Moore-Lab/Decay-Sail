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
- (Interpretation, not approved) C2's full amplitude acted like amp 4000 in this model, i.e. the drive does not
  grow above ~4000 as V² scaling assumes. Not tested directly; the R1 chirp at 6400 is the first direct check.

## Predictions for the runbook (`python3 osc_sim.py chirp`)

| run | coupling as at 4000 (matches C2) | scaled to 6400 |
|---|---|---|
| R1 chirp 0.40 → 0.15 Hz, 104 s | no over-the-top; max swing 39–115° | over the top in 3/6 at ~11 s |
| R2 hold 0.31 Hz, 120 s, from rest | no; max 33–104° | over in 4/6 at 14–17 s |
| slower chirps (to 416 s), 0.40→0.15 or 0.34→0.20 | no; max 46–140° | not run |
