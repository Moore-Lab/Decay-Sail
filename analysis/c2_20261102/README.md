# C2 drive holds, 2026-11-02: analysis

The measured numbers here come from the listed commands. Statements of cause or meaning are Claude's interpretations, marked "(interpretation, not approved)".

Run: `apparatus_log.md` 2026-11-02. The plan and pass marks are in `lab_utils/DRIVE_LOCK_HANDOFF.md` ("C2 hold schedule").
Data (Dropbox `Microspheres/TFINER/`):
- `videos/output_basler_gps1477668186.{avi,csv}` and `videos/blob_live_gps1477668186.csv`
- `data/Electrodes/Y1_RDS-OUTS_V{2,3,4}_OUT_DQ_1477683254_1477685619.h5`

Those channels end at FE 1477685383–389, not 619, because they were fetched seconds after the data was written. All seven holds are covered.
FE − true GPS = 15368.7 s, read live on worker2.

## Gate 7 (tracker): PASS

Reproduced exactly by an independent reviewer, 2026-11-02, as was "no lock" (max mean speed 0.0016 rev/s).

Command: `camera_utils/tracking/gate7_check.py` (branch `live-blob-tracker`).
- **Dropped frames:** 0 BlockID gaps and 0 late frames. Video, timestamps and live CSV agree at 88173 frames, 49.999 fps.
- **Live vs offline:** 99.966% of frames agree within 0.1°; max 0.47°. The largest differences all fall at the 0/360° wrap.
- **NCC:** median 0.964; 0.919 over the last 30 s; 1st percentile 0.882.
- **Circled-frame sheet:** regenerate with the command above. Plots are gitignored. Red and green sit on the blob in all 16 frames.

So the live angles are usable for C2.

## Step 0 no-glide check: PASS

`V2..V4_OUT_DQ` during the outputs-off test shows the drive above half amplitude from FE 1477683382.7 to 409.8. The field frequency is 0.1000 Hz from the first second: the instantaneous value stays at 0.100 throughout, and fits over the first 2, 5 and 10 s also give 0.1000. There is no glide from the previous run's 4 Hz.

## drive_coupling.py

Command:
```
python3 lab_utils/drive_coupling.py blob_live_gps1477668186.csv output_basler_gps1477668186.csv V2.h5 V4.h5 V3.h5 --tau 15368.7
```

- **No lock in any hold (measured).** The mean rotor speed was ≤ 0.002 rev/s in every hold. The slowest candidate lock, f/8 at 0.1 Hz, would be 0.0125 rev/s. The net rotation per hold was < 0.25 rev.
- **The swing frequency was lower when the swing was larger (measured). This is CONFOUNDED with time:** the later free-swing recording showed the frequency drifting 10% in 39 min at a nearly fixed amplitude (`../ringdown_20261102/README.md`). Drive-off segments:

  | swing amplitude | frequency |
  |---|---|
  | 46° | 0.341 Hz |
  | 51° | 0.335 Hz |
  | 57° | 0.326 Hz |
  | 97° | 0.287 Hz |
  | 100° | 0.276 Hz |
  | 105° | 0.272 Hz |

  That is a 20% drop from 46° to 105°, but amplitude and elapsed time grew together, so this does not show that the trap is anharmonic. The script's single "0.306 Hz" is a median over this trend. The small-amplitude f₀ was not measured today: the one quiet segment, at 4°, gives a false peak at 0.696 Hz. Two consequences:
  - The `kd/kt` column is meaningless here: the frequency drifts by more than any drive stiffness would shift it.
  - A fixed f₀/2 drive (hold 7) cannot follow a drifting frequency.
- **The wobble columns (A1, A2, tau1, tau2) are NOT measurements of drive torque.** An independent reviewer (2026-11-02) agreed, and added: the cos(k·φ) regression ignores the rotor's own m·θ phase, so with a 40–100° swing even a real torque would not give a phase-stable wobble. `c2_checks.py` part 1 shows why:
  - The 1× and 2× amplitudes are 4–25° in the thirds of a hold.
  - Their phase relative to the drive wanders by more than 90° between thirds in most holds. The exception is hold 2 at 2×: phases −169/−160/−121° (48° spread), 12.1° amplitude at 0.400 Hz, the largest within ±0.05 Hz (next 9.5°). That is suggestive at ~2σ, not established (independent review 2026-11-02, coherence p ≈ 0.07), and 2f = 0.4 Hz sits near the broad swing band.
  - Detuning the reference by ±0.02 Hz gives similar amplitudes, 0.3–31°.
  - The off-line amplitude spectrum's 95th percentile is 5–12°.

  (Interpretation, not approved.) With a 40–100° free swing present, a wobble below ~10° can't be separated from the swing by this method, so the table's 2–6 × 10⁻¹² N·m bounds nothing either way.

## Swing amplitude per hold (measured)

Amplitude is √2 × rms of the detrended angle, in degrees. Start and end are the first and last 20 s of the hold (`drive_coupling.py`); the gap column is from `c2_checks.py` part 3.

| hold | f_elec (Hz) | start | end | change | next drive-off gap (before → after) |
|---|---|---|---|---|---|
| 1 | +0.100 | 39 (from rest: 0 → 28 → 42 over the first 30 s) | 39 | grew from 0 | 46.8 → 46.1 |
| 2 | +0.200 | 37 | 49 | +12 | 51.1 → 51.4 |
| 3 | +0.400 | 74 | 41 (26 just before off) | −33 | 3.9 → 3.7, after a drop from 26 at switch-off |
| 4 | −0.100 | 30 (from 4: 7 → 41 over the first 30 s) | 54 | grew | 56.7 → 56.4 |
| 5 | −0.200 | 50 | 96 | +46 | 97.5 → 94.4 |
| 6 | −0.400 | 89 | 99 | +10 | 102.7 → 98.9 |
| 7 | +0.155 | 93 | 111 | +18 | 105 (end of recording) |

- **Measured:** the amplitude changes by ≤ 4° across each ~80 s drive-off gap. Inside holds it changes by 10–50°, and the hold 3 switch-off dropped it from 26° to 4°.
- **(Interpretation, not approved.)** The swing changes while the drive is on or switching, and not while it is off. What does it is not established: the drive torque at f or 2f, the amplifier's DC step at switch-on and switch-off (AC-coupled, τ ≈ 5–7 s estimated), or both.
- **Switch-on growth.** In holds 1 and 4, starting near rest, the swing reached 28° (7°) by 15 s and 42° (41°) by 30 s. A sustained drive torque would build it over that time, and so would the pedestal's DC step, which decays over ~20 s. So the timing does not tell the two apart.
- **Unexplained (interpretation, not approved):** a 40° swing from rest, against the ~1° static detent estimated from the design torque and trap stiffness (`lab_utils/DRIVE_LOCK_HANDOFF.md`, Detent test).
- **Hold 7 (resonance test) is not a clean test (interpretation, not approved).** It started at a ~93° swing, where the free-swing frequency nearby in time was ~0.28 Hz rather than 0.31, so 2f = 0.31 Hz was off resonance.

## Drive starts: pedestal stagger and AC rise (measured, `c2_checks.py` parts 5–6)

These were measured from `OUT_DQ` at each of the 8 drive starts (start 0 is the step-0 outputs-off test):
- **Pedestal stagger.** At starts 1, 2, 3 and 6, one phase's pedestal reached half height 125 ms
  before or after the other two. That made a differential (rotating-field) signal of up to
  728 counts, 11% of full amplitude, while the pedestal ramped. At starts 0, 4, 5 and 7 the three
  phases crossed within 1 ms, with no differential signal.
- **AC rise.** The AC rose from 10% to 90% in 3.0 s at 7 of 8 starts, which is the DRV_TRAMP 5 s
  spline. At start 1 (hold 1) it rose in one step. Cause not investigated.
- **Rotor at hold 1 (from rest).** The angle stayed within 227.75–227.92° until 103.75 s. It moved
  to 232.5° by 104.5 s, about 0.5 s after the staggered pedestal (half at 103.32 s, differential
  peak during the ramp), and before any AC. The AC then stepped on at 105.5 s.
- **Rotor at hold 4 (±3.8° swing).** No visible change when the pedestals ramped together; the
  swing grew once the AC ramped in.
- (Interpretation, not approved.) A common-mode pedestal step does nothing visible; a staggered
  one kicks, through its differential part. There is one clean example of each. If it holds,
  writing the three offsets so they ramp together, or ramping more slowly (`--pedestal-ramp`),
  would remove the kick.

## Not done / open

- Telling drive torque from the DC kick. One option is a hold with the pedestal ramped slowly (`--pedestal-ramp`), compared with an abrupt one, starting from rest. See "Drive starts" above: the visible kick at hold 1 coincided with a staggered pedestal and an AC step, not with a clean common-mode step.
- Why the AC stepped on at hold 1 instead of ramping.

`c2_checks.py DATA_DIR` reproduces parts 1–4, the no-glide check included.
