# C2 drive holds, 2026-11-02: analysis

Run: `apparatus_log.md` 2026-11-02. The plan and pass marks are in `lab_utils/DRIVE_LOCK_HANDOFF.md` ("C2 hold schedule").
Data (Dropbox `Microspheres/TFINER/`):
- `videos/output_basler_gps1477668186.{avi,csv}` and `videos/blob_live_gps1477668186.csv`
- `data/Electrodes/Y1_RDS-OUTS_V{2,3,4}_OUT_DQ_1477683254_1477685619.h5`

Those channels end at FE 1477685383–389, not 619, because they were fetched seconds after the data was written. All seven holds are covered.
FE − true GPS = 15368.7 s, read live on worker2.

## Gate 7 (tracker): PASS

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
- **The swing frequency falls as the swing grows (measured).** Drive-off segments:

  | swing amplitude | frequency |
  |---|---|
  | 46° | 0.341 Hz |
  | 51° | 0.335 Hz |
  | 57° | 0.326 Hz |
  | 97° | 0.287 Hz |
  | 100° | 0.276 Hz |
  | 105° | 0.272 Hz |

  That is a 20% drop from 46° to 105°, so the trap is not harmonic at these amplitudes. The script's single "0.306 Hz" is a median over this trend. The small-amplitude f₀ was not measured today: the one quiet segment, at 4°, gives a false peak at 0.696 Hz. Two consequences:
  - The `kd/kt` column is meaningless here, because amplitude softening shifts the frequency more than any drive stiffness.
  - A fixed f₀/2 drive (hold 7) detunes itself as the swing grows.
- **The wobble columns (A1, A2, tau1, tau2) are NOT measurements of drive torque.** `c2_checks.py` part 1 shows why:
  - The 1× and 2× amplitudes are 4–25° in the thirds of a hold.
  - Their phase relative to the drive wanders by more than 90° between thirds in almost every hold.
  - Detuning the reference by ±0.02 Hz gives similar amplitudes, 0.3–31°.
  - The off-line amplitude spectrum's 95th percentile is 5–12°.

  With a 40–100° free swing present, a wobble below ~10° can't be separated from the swing by this method. The table's 2–6 × 10⁻¹² N·m therefore bounds nothing either way.

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

- **Between holds the amplitude holds steady:** it changes by ≤ 4° across each ~80 s drive-off gap. The changes inside holds, by contrast, are 10–50°, and the hold 3 switch-off dropped the swing from 26° to 4°. So the swing changes while the drive is on or switching, and not while it is off (measured). What does it is not established: the drive torque at f or 2f, the amplifier's DC step at switch-on and switch-off (AC-coupled, τ ≈ 5–7 s estimated), or both.
- **Switch-on growth.** In holds 1 and 4, starting near rest, the swing reached 28° (7°) by 15 s and 42° (41°) by 30 s. A sustained drive torque would build it over that time, and so would the pedestal's DC step, which decays over ~20 s. So the timing does not tell the two apart.
- **Unexplained:** a 40° swing from rest, against the ~1° static detent estimated from the design torque and trap stiffness (`lab_utils/DRIVE_LOCK_HANDOFF.md`, Detent test).
- **Hold 7 (resonance test) is not a clean test.** It started at a ~93° swing, where the swing frequency is ~0.28–0.29 Hz rather than 0.31, so 2f = 0.31 Hz was off resonance.

## Not done / open

- Telling drive torque from the DC kick. One option is a hold with the pedestal ramped slowly (`--pedestal-ramp`), compared with an abrupt one, starting from rest.

`c2_checks.py DATA_DIR` reproduces parts 1–4, the no-glide check included.
