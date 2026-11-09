# Oscillator chirp through the natural frequency: runbook (branch `osc-chirp`)

**Run 2026-11-06** (G0 PASS, R1 done, R2 skipped): results in `analysis/osc_chirp/README.md` on `main`.
The runs used `stator_osc_drive.py` from `drive-clean-start` (e466653), whose clean start waits 0.5 s after the
frequency jump; `main` now waits 1.1 s (the jump lands at the next front-end GPS second). G0 checked the start
(0.400 Hz, no glide), so it made no difference here.

**Question (Molly, 2026-11-06):** with the fixed-rate oscillator, can a field that starts above the trap frequency
f₀ (~0.31 Hz) and glides **down** through it pump the swing in step until the rotor goes over the top? Data first,
before the y1rds model change. A clean down-glide from rest has not been run before: 10-29 run 1 stepped
0.40 → 0.14 Hz but kept no tracked angle and no front-end times (`apparatus_log.md` 2026-10-29).

`osc-chirp` is `drive-clean-start` at e466653 (the code C2 ran on 11-02) plus this file and `osc_chirp_check.py`.
It is not current `main`.

**Why down:** a bigger swing has a lower frequency (0.275 Hz at ±105° vs ~0.31 small, DECISIONS), so a drive
that glides down with it can stay in step (autoresonance). Derived; not demonstrated on this rotor.

**What the Mac sim predicts** (`analysis/osc_chirp/osc_sim.py` on `main`; measured plant from F3 11-04; derived):
- With the coupling as measured at amp 4000, the sim **matches C2's measured swing amplitudes in 6 of 7 holds**,
  even though C2 ran at 6400. With the coupling scaled up to 6400 (V² above 4000, assumed), it predicts
  over-the-top in holds that didn't go over. So C2's full amplitude acted like 4000 in the model (interpretation,
  not approved).
- With that C2-matched strength, **neither this chirp nor slower ones (to 416 s) nor the f₀ hold go over the
  top**: the swing peaks at 40–140°. Only the unvalidated 6400 scaling predicts over-the-top.
- So the expected result is a large swing, not rotation. The run tests that prediction, gives the first chirp
  data, and shows whether the swing locks to the drive.

## Settings (existing options of `stator_osc_drive.py`; no drive-code changes)

- **Chirp:** `sweep --felec 0.40 --to-felec 0.15 --step 0.01 --dwell 4 --drvtramp 3.5`: 26 steps × 4 s ≈ 104 s,
  0.0024 Hz/s. Each step glides over 3.5 s and then sits 0.5 s, so a new frequency is never written mid-glide.
  `DRV_TRAMP` is documented as phase-continuous; G0 checks it. It also sets the gain ramp-in (3.5 s).
- **Amplitude 6400** (full range; pedestal = amp), forward matrix.
- **`--pedestal-ramp 10`**: ramps the DC pedestal over 10 s so its step doesn't kick the rotor through the
  AC-coupled amp. Tested on hardware 2026-11-06 (G0 and R1: the pedestals rose together over ~10 s).
- Never `--leave-running`.

## Rules for the worker2 session

- One go from Molly, typed in the session, covers steps 0–3 (outputs off). **R1 (the chirp) and R2 (the hold)
  each need their own go.** So do the contingency runs.
- **Stop and call Molly** on: a tracker error or exit, median ncc < 0.9 over 30 s at rest, a dropped frame, a
  command that errors or returns non-zero, a G0 check that fails, or anything unexpected.
- Ask before any commit, push or delete. Never stash. If a script errors, report it; don't patch it.
- **Timestamp everything.** Run every `stator_osc_drive.py` command (dry, G0, R1, R2) through
  ```
  mkdir -p ~/osc_chirp
  python3 -u stator_osc_drive.py <args> 2>&1 | while IFS= read -r l; do printf '%s %s\n' "$(date +%s.%N)" "$l"; done | tee ~/osc_chirp/<run>.log
  ```
  and immediately before and after each one run `date +%s.%N; caget -f0 Y1:DAQ-DC0_GPS` and keep the output. The host
  time of the `DRV_FREQ readback` line pins the AC start in OUT_DQ to host time (OUT_DQ's own timestamps were
  3–4 s off on 11-04).

## Steps

0. **Start.** On worker2 the repo is `~/rds-code/Decay-Sail` (its main checkout may be on another branch with local
   changes: don't touch it). Use a worktree: `cd ~/rds-code/Decay-Sail && git fetch && git worktree add ~/wt_chirp osc-chirp`
   (or `cd ~/wt_chirp && git pull` if it exists). Never stash. Stop `grab_basler.py` if running. `python3 lab_utils/stator_osc_drive.py status`:
   gains 0, DRVON 0, outputs off.
1. **Tracker** (both lights on, as F3 live 2):
   `cd camera_utils/tracking && /home/controls/.conda/envs/ueye/bin/python live_blob_track.py --exposure 15 --centre 122.8,179.6 --outdir ~/stator_detent --show`
   Leave it recording through all runs. Check the rotor is **at rest**: angle span < 2° over 60 s, ncc ≥ 0.9.
   Note the rest angle (229.8 on 11-04). If the spot or centre looks moved, stop and call Molly.
2. **Dry run** (`cd lab_utils`, run label `dry`): `python3 stator_osc_drive.py sweep --felec 0.40 --to-felec 0.15 --step 0.01 --dwell 4 --drvtramp 3.5 --amp 6400 --pedestal-ramp 10`
   It must print 26 steps, 4 s dwell, 3.5 s glide, total ~104 s.
3. **G0, outputs OFF** (nothing reaches the chamber; label `g0`): the same command plus `--live`, **no**
   `--enable-outputs`. Fetch `Y1:RDS-OUTS_V2_OUT_DQ`, `_V3_`, `_V4_` from the front-end start − 20 s to end + 20 s
   (`batch_fetch.fetch_channel`), then `python3 osc_chirp_check.py <V2.h5> <V3.h5> <V4.h5>`.
   It prints five checks (pedestal together, AC ramps in, no phase jumps, frequency glides 0.40 → 0.15 without
   flat spots or rises, AC out before pedestal) and `G0 PASS/FAIL`. **If it fails, stop**: the chirp isn't what we
   think it is.
4. **Wait for Molly's go for R1.**
5. **R1, the chirp, outputs ON**, from rest (this is the run that matters; label `r1`):
   `python3 stator_osc_drive.py sweep --felec 0.40 --to-felec 0.15 --step 0.01 --dwell 4 --drvtramp 3.5 --amp 6400 --pedestal-ramp 10 --enable-outputs --live`
   Ctrl-C stops it with a full teardown. Molly watches the window. Afterwards note the rotor's state: swinging
   (roughly how far) or rotating (which way).
   - **If it is rotating: skip R2.** Keep the tracker running and let it coast ≥ 10 min with the drive off (that
     gives a damping-time estimate at a known speed). Then go to step 7.
6. **Wait for Molly's go for R2.** Wait ≥ 60 s with the drive off. **R2, hold at f₀** (label `r2`), from whatever
   state the rotor is in (write it down):
   `python3 stator_osc_drive.py hold --felec 0.31 --amp 6400 --duration 120 --pedestal-ramp 10 --enable-outputs --live`
   **Contingencies, each only with Molly's go, from whatever state the rotor is in (log it):**
   - R1 pumped but lost step (the swing grew then shrank): the same chirp at half the rate, `--dwell 8 --drvtramp 7`.
   - R1 showed almost nothing: the same chirp with `--reverse`.
7. **Fetch and copy.** Stop the tracker. Fetch over the whole session (first start − 60 s to last end + 60 s):
   `Y1:RDS-OUTS_V1..V4_OUT_DQ`, `Y1:RDS-LES_PIT_IN1_DQ`, `Y1:RDS-LES_YAW_IN1_DQ`, `Y1:RDS-LES_SUM_IN1_DQ`.
   rclone the video, its `.csv`, `blob_live_gps*.csv`, the h5 files, `~/osc_chirp/*.log` and the
   `date`/`caget` pairs to `dropbox:Microspheres/TFINER/data/osc_chirp/<YYYY-MM-DD>/`.
8. **Raw report** (in the session, and as `report.md` in that Dropbox folder): each command, its host and
   front-end times before/after, the rotor state before and after, the G0 output, anything odd. No interpretation.
9. `python3 stator_osc_drive.py status` (gains 0, outputs off), then `git checkout main`.

## Afterwards (Mac)

Score R1 and R2 from the tracker angle against the drive phase reconstructed from OUT_DQ (aligned by the
`DRV_FREQ readback` host time): swing amplitude and frequency over time, the drive-minus-swing phase (steady = in
step), and whether it went over the top. Compare with `osc_sim.py` at both strengths. That is also the first
direct amp-6400 point for the coupling.
