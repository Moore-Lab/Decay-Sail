# Drive lock: handoff

Does the rotor lock to the stator drive, and under what conditions? Serves the spin-up
directive (`../measurement_objective.md`). Gates agreed with Molly 2026-11-01. Owner: the
tracking/drive session (this file and `drive_coupling.py`); docs/STATUS/DECISIONS edits
go through Molly or the cleanup session.

## Done (2026-11-01, recording gps1477428272)

Data: video `output_basler_gps1477428272.avi` + `camera_utils/tracking/blob_gps1477428272.csv`
(angles), drive `Y1:RDS-OUTS_V{1..4}_OUT_DQ` front-end GPS 1477443068–1477443939 (Dropbox
`Microspheres/TFINER/data/Electrodes/`), LES in `data/LES_video/`. Front-end minus true GPS
at the recording: 15073.56 s (from the video–LES alignment, gate 6).

- **D1 drive (passed, Molly; settings to re-check at the lab):** phases 120.00° apart,
  sequence A→B→C, ±6400 counts about `dc` 6400. `stator_osc_drive.py sweep`
  0.4 → 4.0 Hz electrical in 0.2 Hz steps, ~10 s per step with 5 s glides (0.02 Hz/s on
  average); on 11.2 s, full amplitude 16–209 s, off 214 s (video time). The 12–16 s start
  is `bring_up()` gliding DRV_FREQ from the previous run's 4.0 Hz while the gains ramp in
  (a fix is proposed, not made).
- **D2 which lock (passed, Molly: "follows neither"):** rotor within 15% of ±f/8 or ±f/4
  only 2.5–11% of drive-on frames; it keeps swinging at ~0.3 Hz throughout, with bursts of
  net rotation mostly in the − image direction (−4 rev at 60–100 s, −10 at 140–180 s,
  −8 at 180–206 s) at speeds below f/8, and no net rotation at 26–60 and 100–140 s.
  "−" image = with the A→B→C field sequence (item 3 below), IF the 08-24 channel map
  still holds; the wiring was redone since and is unverified. Cause of no lock: not investigated.
  Figure `../plots/d2_drive_vs_rotor_gps1477428272.png` (gitignored).
- **C1 lock scorer (passed on the data; awaiting Molly's look at the plot):**
  `drive_coupling.py` (usage in its docstring). LOCKED = mean speed within 5% of s·f/k
  AND drift of θ − s·φ/k under one pattern step (360/k deg). `selftest` passes (clean
  lock → −f8, swinging → none, lock with a slip → none). On gps1477428272: none on all
  19 steps (`--min-seg 4`). The swing-frequency / stiffness column (`kd/kt`) is noise on
  4–6 s steps; it needs the 2-min holds below.

## Before lab day (Mac work for the supervisor; Molly agreed 2026-11-01)

In this order; gates first for anything large; ask Molly only for physics calls, gate
passes, hardware and commits.
1. **Clean drive start** in `stator_osc_drive.py` `bring_up()`: jump DRV_FREQ at zero gain
   (DRV_TRAMP 0, guard that the gains read 0, restore DRV_TRAMP before the gains ramp).
   Optional slow pedestal ramp via `V{n}_TRAMP` (~60 s) behind a flag, default off.
   Branch (hardware code); outputs-off test on worker2 on lab day, before the holds.
   **Written 2026-11-01** on branch `drive-clean-start` (from `live-blob-tracker`):
   refuses to start if the oscillator gains are nonzero (before touching anything);
   jumps DRV_FREQ at DRV_TRAMP 0, restores DRV_TRAMP in a `finally`; AC waits out the
   live `V{n}_TRAMP` pedestal ramp; `ramp_down()` waits it out again before any SW2
   write. Flag `--pedestal-ramp S` (default 0), restores pre-run `V{n}_TRAMP`.
   Checked on the Mac only, with a stub `epics` that records every caput (38/38
   checks pass: ordering for hold and sweep at ramp 0 and 60 s, plus Ctrl-C during a
   hold and mid-jump). Hold now prints its front-end GPS start/end. Not run on hardware.
2. **Gate 7 analysis script:** one command after the lab run: dropped frames, live vs
   offline `blob_track.py` angles (pass: >= 99.9% within 0.1 deg), median NCC, circled-frame
   sheet.
   **Written 2026-11-01:** `camera_utils/tracking/gate7_check.py` on `live-blob-tracker`
   (tests and a header-precision fix to `live_blob_track.py` in that branch's HANDOFF).
3. **A->B->C direction vs the camera's angle sign:** from the `stator_flex/` sector layout
   and the camera orientation (UserSet1 = 180 deg rotation, top view); add "with / against
   the drive" to `drive_coupling.py`'s report.
   **Done 2026-11-01 (measured; reviewer AGREE):** the sector tabs end at three via radii,
   one per phase; in increasing image angle they read A, C, B (ratios 1 : 1.17 : 1.32 vs
   design 1 : 1.16 : 1.33; CTR trace between A and B as designed). So + image angle
   (clockwise on screen) = C→B→A on the board, and a rotor turning with the field
   sequence is `−f8` (m=16 V², or charge on m=8) / against at f/4 is `+f4` (m=8 V²).
   `drive_coupling.py` now prints `net_vs_field` (with/against; blank under 0.5 rev) and
   its selftest has forward and reverse sign controls. **Only unverified link:** the
   channel map A, B, C = V2, V4, V3 is from the 2026-08-24 continuity check, before rev G;
   if two terminals are wired differently now, every with/against label flips.
4. **DEFERRED (Molly, 2026-11-01):** not needed for the spin-up directive; build it when
   stage 3 gives a free spindown from 1 Hz (tilt stage in). Was: **Spindown analysis ready** for the next free spindown (camera absolute angle + LES).
5. **Delegate to a worker:** `lab_utils` stale-script candidates, each with what references
   it and when last used, for Molly to decide (flag, never delete).
   **Done 2026-11-01:** `STALE_SCRIPT_CANDIDATES.md` (text-match evidence only; shell-only
   use on worker2 not checked).
6. ~~Re-examine the 09-08 LES file for the trap frequency~~ **Dropped (Molly, 2026-11-01):**
   pre-changes data; f₀ is measured on the current setup (DECISIONS) and the C2 drive-off
   stretches re-measure it.

## Detent test (written 2026-11-01, branch `detent-test`; Molly approved writing it)

`lab_utils/stator_detent.py`: one phase stepped on (TRAMP 0), ramped off over 60 s, A, B,
C in turn; `analyze` fits the tracked angle for each step's torque. **Measures torque per
phase and whether each phase is connected. Cannot tell the wiring order** (small motion:
any three per-phase torques fit either order). **Expected ~1° (derived), nothing visible
by eye.** Replaces `stator_epics_drive.py` (deleted, Molly). Mac checks: selftest 25/25
(stub EPICS ordering incl. two Ctrl-C cases; synthetic torque recovered within 1%).
Not run on hardware. **Later, not lab day, and only with both lights on** (Molly,
2026-11-01: the second light is off; a ~1° effect needs the good tracking). Lab day does
not depend on it. Kept on its own branch; before running, merge `detent-test` into the
branch that has the live tracker. Worker2 sequence (Molly runs the `--live` steps):
1. Stop `grab_basler.py`. Check out the merged branch and pull.
2. `cd lab_utils && python3 stator_detent.py selftest`, then dry `run --cycles 1`.
3. Outputs-off: `python3 stator_detent.py run --cycles 1 --live` (no `--enable-outputs`).
   On the Mac, fetch `V2,V4,V3_OUT_DQ` for the `fe_gps` span in the events CSV. **Pass:** a
   step at each `on`, a ~60 s linear ramp at each `release` (OFFSET ramping via TRAMP is
   otherwise untested). Fail: stop.
4. Rotor quiet, lighting as for gps1477428272: `cd camera_utils/tracking && python3
   live_blob_track.py --outdir ~/stator_detent --show --snapshot-every 0.05`.
5. `cd lab_utils && python3 stator_detent.py run --live --enable-outputs` (4 cycles,
   ~17 min; events to `~/stator_detent`). Then stop the tracker.
6. rclone the `.avi`, timestamps `.csv`, `blob_live_gps*.csv`, `detent_events_*.csv` to
   `dropbox:Microspheres/TFINER/videos/`. On the Mac: `stator_detent.py analyze EVENTS
   ANGLES`, and `gate7_check.py` on the same recording (first live tracker run).
For Molly's STATUS edit: the detent item still expects "15° mech per step"; with the trap
as stiff as f₀ = 0.31 Hz implies, the estimate is ~1°.

## C2 hold schedule (approved by Molly 2026-11-01)

Fixed-frequency holds, not sweeps, so the rotor has time to settle. Rotor 0.0125–0.05
rev/s at f/8 = the stage 1 carry range.

| # | Command (run from `lab_utils/` on worker2; Molly runs it) | f_elec | rotor at f/8 |
|---|---|---|---|
| 1 | `python3 stator_osc_drive.py hold --felec 0.1 --amp 6400 --duration 150 --enable-outputs --live` | 0.1 | 0.0125 |
| 2 | same, `--felec 0.2` | 0.2 | 0.025 |
| 3 | same, `--felec 0.4` | 0.4 | 0.05 |
| 4–6 | 1–3 again with `--reverse` | 0.1, 0.2, 0.4 | reversed |

- Drive OFF (script exits) for **≥ 60 s between holds**, so the DC kick decays (~20 s) and
  the swing settles; the scorer uses each hold after its first 30 s.
- **Before:** fix the light; start `camera_utils/tracking/live_blob_track.py --outdir <dir>`
  (branch `live-blob-tracker`) and leave it recording through all six holds (~25 min).
  Note the start time of each hold.
- **After:** stop the tracker; fetch LES with `fetch_les_for_video.py <video GPS>
  --duration <s>` (reads the offset live) and V1–V4 for the same front-end window
  (`batch_fetch.py` functions, as on 2026-11-01); copy the video, timestamps and angle
  CSV to Dropbox.
- Each command still has the start-up glide (DRV_FREQ from the previous value) until the
  `bring_up()` fix is made; between these holds the jump is small (≤ 0.3 Hz).

## Lab-day runbook (C3 + tracking gate 7 / L4), for a Claude session on worker2

Approved by Molly 2026-11-01. Start in the repo on worker2:
`git fetch && git checkout drive-clean-start && git pull && claude` (= `live-blob-tracker`
plus the clean-start fix; includes main up to this file). Stop `grab_basler.py` first: the camera is held exclusively.

Rules: **one approval from Molly for the whole C2 schedule** (she approved the schedule
2026-11-01; confirm once at the start of the session), then run all six holds without
further asks. **Stop the schedule and call Molly on any failed check:** tracker error or
exit, median `ncc` < 0.9 over the last 30 s, any dropped frame, a hold command that errors
or returns non-zero, or anything unexpected. Still ask before any commit/push/delete;
never `--leave-running`; if `live_blob_track.py` errors, report it, don't patch the code
(it is fixed on the branch from the Mac).

0a. **Wiring (no lab step).** The channel-to-terminal wiring was redone after the
   2026-08-24 continuity check, and the terminals are inside the pumped-down chamber, so
   it is not metered. The holds don't need it: lock SPEED (f/8 vs f/4) does not depend on
   the wiring, and both signs are scored. Only the with/against label does. If a hold
   locks, its speed plus the predicted direction for that speed (f/8 with, f/4 against)
   tells the wiring, at the cost of no longer testing that prediction; the detent test
   (STATUS) would check the wiring independently.
0. **Outputs-off test of the clean start** (nothing reaches the chamber):
   `cd lab_utils && python3 stator_osc_drive.py status`, then
   `python3 stator_osc_drive.py hold --felec 0.1 --amp 6400 --duration 20 --live`
   (no `--enable-outputs`). Pass: the echoed writes show `DRV_TRAMP <- 0`,
   `DRV_FREQ <- 0.1`, `DRV_TRAMP <- 5`, all before `DRV_SINGAIN <- 6400`; ramp-down ends
   with offsets 0 and outputs off; `status` afterwards shows gains 0, DRVON 0. Also
   re-check the D1 settings in `status`: matrix V2 (0, 1), V3 (−0.866, −0.5),
   V4 (+0.866, −0.5), V1 (0, 0) = A→B→C 120° apart. Note the `hold start/end, front-end
   GPS` lines it prints; on the Mac, confirm in `V2..V4_OUT_DQ` (records with outputs
   disabled: measured 2026-09-08, `y1rds_model_change_muxmatrix.md`) that the 0.1 Hz
   starts with no glide. Any failure: stop and call Molly.
   Then tracker speed (gate L3, read-only, no camera):
   `cd camera_utils/tracking && python3 live_blob_track.py --replay
   /home/controls/stator_detent/output_basler_gps1477428272.avi --centre 132.3,180.6
   --outdir /tmp/l3 --snapshot ""`. Pass: the `Stopped.` line shows p99 < 10 ms and
   0 dropped. If p99 >= 10 ms: stop and call Molly (live tracking would drop frames).
1. Start the live tracker in its own terminal (or in the background, logged):
   `cd camera_utils/tracking && python3 live_blob_track.py --outdir ~/stator_detent --show`
   Report the registered centre and board-shift response; after ~30 s, the median `ncc`
   in `blob_live_gps*.csv` (want ≥ 0.9) and dropped frames (want 0). Molly checks the
   window: the red circle stays on the blob. If not, stop before any hold.
2. Before hold 1: Molly confirms the rotor is quiet (no swing; quiet it first if it is
   swinging); note the swing amplitude the tracker shows. Later holds start after the
   60 s gap whatever the rotor is doing (the gap lets the DC kick fade; it does not
   settle a swing).
   Run the six C2 holds in order, ≥ 60 s drive-off between, checking the tracker (ncc,
   dropped frames) before each hold; log each hold's start and stop time. On any failed
   check: stop (no further holds) and report.
3. Stop the tracker (Ctrl-C). `python3 lab_utils/fetch_les_for_video.py <video GPS>
   --duration <recording length, s>`; note the offset it prints. Fetch
   `Y1:RDS-OUTS_V1..V4_OUT_DQ` for the same front-end window with `batch_fetch.py`'s
   `fetch_channel`/`upload` (dest `Microspheres/TFINER/data/Electrodes`).
4. `rclone copyto` the `.avi`, its timestamps `.csv` and `blob_live_gps*.csv` to
   `dropbox:Microspheres/TFINER/videos/`. Report paths, hold times, anything odd.
5. `git checkout main` when done.

Then on the Mac: `drive_coupling.py` on the recording (one row per hold) and the gate 7
check (live angles vs `blob_track.py` on the saved video).

## C3 / C4

- C3 (lab): run C2 → `drive_coupling.py` on the recording, one row per hold.
- C4 (only if nothing locks): choose one variable with Molly: DC coupling via J1/J5
  (David), slow pedestal ramp, rotor-charge neutralisation, or CTR bias.
