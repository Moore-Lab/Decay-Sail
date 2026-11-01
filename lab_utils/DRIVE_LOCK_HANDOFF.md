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
  Not established: which board direction "−" is. Cause of no lock: not investigated.
  Figure `../plots/d2_drive_vs_rotor_gps1477428272.png` (gitignored).
- **C1 lock scorer (passed on the data; awaiting Molly's look at the plot):**
  `drive_coupling.py` (usage in its docstring). LOCKED = mean speed within 5% of s·f/k
  AND drift of θ − s·φ/k under one pattern step (360/k deg). `selftest` passes (clean
  lock → −f8, swinging → none, lock with a slip → none). On gps1477428272: none on all
  19 steps (`--min-seg 4`). The swing-frequency / stiffness column (`kd/kt`) is noise on
  4–6 s steps; it needs the 2-min holds below.

## C2 hold schedule (DRAFT, for Molly to approve)

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
`git fetch && git checkout live-blob-tracker && git pull && claude` (the branch includes
main up to this file). Stop `grab_basler.py` first: the camera is held exclusively.

Rules: **one approval from Molly for the whole C2 schedule** (she approved the schedule
2026-11-01; confirm once at the start of the session), then run all six holds without
further asks. **Stop the schedule and call Molly on any failed check:** tracker error or
exit, median `ncc` < 0.9 over the last 30 s, any dropped frame, a hold command that errors
or returns non-zero, or anything unexpected. Still ask before any commit/push/delete;
never `--leave-running`; if `live_blob_track.py` errors, report it, don't patch the code
(it is fixed on the branch from the Mac).

1. Start the live tracker in its own terminal (or in the background, logged):
   `cd camera_utils/tracking && python3 live_blob_track.py --outdir ~/stator_detent --show`
   Report the registered centre and board-shift response; after ~30 s, the median `ncc`
   in `blob_live_gps*.csv` (want ≥ 0.9) and dropped frames (want 0). Molly checks the
   window: the red circle stays on the blob. If not, stop before any hold.
2. Run the six C2 holds in order, ≥ 60 s drive-off between, checking the tracker (ncc,
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
