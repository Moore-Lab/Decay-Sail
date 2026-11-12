# Spin-up handoff (state 2026-11-12 morning; for a fresh session)

Directive and pass marks: `measurement_objective.md`. Plan and next steps: `lab_utils/SPINUP_PLAN.md`. Current values and
decisions: `docs/DECISIONS.md` (2026-11-10 feedback rule; 2026-11-11 DC coupling and the spin-up amendment). Log:
`apparatus_log.md` 2026-11-11/12. Start by reading those, then this.

## Where we are

- **Spin-up through the electrode offsets works, in both directions** (measured, 2026-11-11/12).
  - **Method:** a feedback governor on worker2 pumps the swing over the trap barrier along a chosen direction, then adds
    energy near the top of each turn until the mean rate over the last full turn hits a target.
  - **Results at 0.5 Hz** (level 800, push limit 120°/s): U1 (+) and U2 (−) passed, each holding every turn for 300 s
    within ±5 % (means 0.501 and 0.510 Hz).
  - **Spin-down** with the same tool (target ~0, push limit 120) stops 0.5 Hz in ~20 s.
  - **The attempt series is complete:** 8 attempts, 4 per direction. 6/8 pass at frame-resolution timing and 7/8 with
    interpolated crossings. Details in `SERIES` below.
- **Ceiling at 8 updates/s ≈ 0.5 Hz** (sim with the measured trap; derived).
  - Pushing usefully needs the rotor slower than ~15° of motion per update. That caps the speed, and it makes ±1 % holds
    rare (14–41 % of turns), because the governor can only brake where the rotor is slow.
  - **0.75 Hz** (Molly: consistent 0.75 Hz would be fine) needs a faster update rate. Update-rate sim:
    `analysis/spinup_spin_20261111/spin_rate_summary.md` (8/16/25/50 updates per second).
- **Rate routes** (Alma, 2026-11-11; DECISIONS 8 Hz row):
  - set the RCG EPICS helper back to 16 Hz. That needs a recompile of the two models on cymac1, Molly's and Alma's.
  - or a USB/Ethernet DAC driving the amp input directly, with the loop on worker2 at up to the 50 fps camera rate.
  - Not decided.

## Verified results (each README labels measured / derived / assumed)

| what | where |
|---|---|
| HV amp DC-coupled; DC path 0.0124–0.0128 V/count, flat, ≤12 mV crosstalk, ~0 V at 0 counts | DECISIONS 2026-11-11; `apparatus_log.md` 11-11 (DC check) |
| G2 brake from ±35–40°: 3/3 below ±10° in 3–9 s (plot, clips) | `analysis/brake_g2_20261111/README.md` |
| Full-circle trap from S1's free coast: barrier at 60°, 6.5 rad²/s² per I, minimum 220° | `analysis/spinup_spin_20261111/README.md`, `coast_trap.json` |
| Damping c = 3.8e−4 /s (τ 44 min), B1 3.5e−4; September τ_mech 79.8 min (~1.8× lower damping then; cause not identified) | same README |
| Trap at 0.40 vs 0.31 Hz: same barrier; shape differs ~5 % (0.19 rad/s² rms; noise 0.04) | same README (`coast_speed_check.py`) |
| Spin sim with the measured trap reproduces the live 0.44–0.47 Hz plateau at a 90°/s push limit | same README (`spin_sim_coast.py`) |
| Spin-ups S1 (+, 0.45 Hz), S3 (−, 0.47 Hz); video timing 0.459 / 0.469 Hz | `apparatus_log.md` 11-11/12 |

## Assumptions still in use

| assumption | status | where used |
|---|---|---|
| push map (G1+B2 shape, 45°-periodic) holds outside 167–267° | A; spin-up works, so it is not badly wrong | `brake_offsets.py` (`--map g1`), sims |
| push above 1600 counts; V² share f (0–0.2) | A (extrapolated); scanned in sims | carry and spin sims |
| AC-path push map valid on DC | checked 11-11 (gain within a few %, pump rate, brake works) | all live runs |
| trap at very low speed (swinging) the same as when rotating | open; the coast only covers 0.27–0.43 Hz | spin sim |
| landing delay ~15 ms on the 8 Hz grid | M (S0, G1) | controller, sims |

## Code (branch `voltage-steps`, worker2 `~/wt_vs`; tracker from `feedback-drive`, worker2 `~/wt_fb`)

- **`lab_utils/brake_offsets.py`** (latest c5a2afe: adds reversal, brakes first if rotating against --dir):
  - `run --map g1` gives the brake (`--level 800`) or the pump (`--pump-to DEG`).
  - `--spin-to HZ --dir ±1 --w-push-max DEG/S --level N` gives the spin-up governor; `--spin-to 0.001` is the spin-down.
  - **Safety:**
    - `--duration`;
    - `--w-cap` (500°/s, from an 8-frame fit, tripping after 3 frames running);
    - `--stale`;
    - `--ncc-min` (use 0.70 for spins: the tracker match dips to ~0.78 at 320–330°; a false lock scores ≤ 0.71);
    - in brake/pump mode, the `--safe` range.
  - `selftest` must pass before any live use.
- **Live tracker** (centre (131.03, 178.79) since the camera move of 2026-11-12 15:00; was (117.5, 165.1); STATUS): `camera_utils/tracking/live_blob_track.py --centre 131.03,178.79 --publish 127.0.0.1:5005 --show
  --duration 2700 --outdir DIR`. It records video too, at 15 ms exposure and 50 fps.
- **Series settings:**
  - spin-up: `--map g1 --level 800 --w-push-max 120 --spin-to 0.5 --dir D --duration 540 --ncc-min 0.70 --enable-outputs --live`;
  - spin-down: `--map g1 --level 1600 --w-push-max 120 --spin-to 0.001 --dir D --duration 300 --ncc-min 0.70 ...`.

## Working conventions (worker2)

- **The worker2 Claude** is the Remote Control session (named "Stair shape option" on 11-11/12; find it by kind).
  Messages to it must be self-contained.
- **Live writes need Molly's go,** typed in that session. One go may cover a stated sequence. A stop condition or a code
  change uses it up.
- **Stop rules used:** any stop other than the expected one, a wrong-direction first turn, no turn by 360 s, a spin-down
  leaving the rotor turning, or a dirty end state (OFFSET 0, SW2R 768, TRAMP restored, OUTMON 0).
- **No Dropbox uploads or other heavy jobs during a live run.** A 4.7 GB upload starved the tracker (D2 stale stop, 11-12).
- **Videos (Molly's standing OK, 11-12):** after each run, worker2 uploads the folder (`rclone copy`), runs `rclone check`, and
  deletes the local .avi files only when that folder shows 0 differences. CSVs and logs stay local. Never during a run
  or a coast.
- **Data:** worker2 `~/spinup/<date>/...`, mirrored to Dropbox `Microspheres/TFINER/data/spinup/<date>/...`; Mac path
  `~/Library/CloudStorage/Dropbox/...`.

## SERIES (2026-11-12, complete; worker2 `series_score_table.txt`, Dropbox `spinup/2026-11-12/series/`)

Each spin-up: `--level 800 --w-push-max 120 --spin-to 0.5`. Score window: the 300 s after the first turn within ±5 %.
Timing methods: (a) frame-resolution crossings; (b) crossings interpolated between frames. Molly to rule which method
counts; it was fixed only after U6.

| attempt | dir | first turn (s) | target (s) | mean (Hz) | min–max (b) | ±5 % (a / b) | ±1 % (b) | verdict (a / b) | spin-down: rotation stopped |
|---|---|---|---|---|---|---|---|---|---|
| U1 | + | 67 | 99 | 0.501 | 0.479–0.512 | 100 / 100 | 39 % | pass / pass | D1 failed (limit 90); D1b swing damp |
| U2 | − | 94 | 117 | 0.510 | 0.478–0.522 | 100 / 100 | 18 % | pass / pass | 19 s (stall stop later, upload) |
| U3 | + | 58 | 100 | 0.510 | 0.483–0.520 | 100 / 100 | 16 % | pass / pass | 29 s |
| U4 | − | 89 | 115 | 0.508 | 0.476–0.521 | 100 / 100 | 8 % | pass / pass | 10 s |
| U5 | + | 54 | 71–73 | 0.508 | 0.481–0.518 | 100 / 100 | 11 % | pass / pass | 32 s |
| U6 | − | 73 | 102 | 0.511 | 0.482–0.523 | 99.3 / 100 | 3 % | **fail / pass** | 31 s |
| U7 | + | 51 | 77 | 0.504 | 0.471–0.522 | 98.7 / 98.7 | 25 % | **fail / fail** (2 slow turns, 0.471 and 0.474) | 17 s |
| U8 | − | 79 | 106–108 | 0.507 | 0.487–0.515 | 100 / 100 | 32 % | pass / pass | 33 s |

- **Score:** 6/8 by (a), 7/8 by (b).
  - Per direction by (b): + 3/4, − 4/4.
  - The directive needs 8 of 10 per direction, so 6 more attempts per direction are still to run.
- **All first turns went the right way.**
  - Time to first turn: 51–67 s (+) and 73–94 s (−).
  - Time to target: 71–100 s (+) and 102–117 s (−).
- **Peaks:** speed 254–286°/s; tracker ncc min 0.777–0.781 (always at 326–328°).
- **Bias** (all turns): + mean 0.5059 Hz (sd 0.0084), − mean 0.5092 (sd 0.0078). Both run high, − slightly more.
- **Video timing** (10 turns, independent of the tracker): U1 0.492 Hz (log 0.489), U2 0.514 Hz (log 0.513).

## REVERSAL SERIES (2026-11-12 afternoon; worker2 `reversal_score_table.txt`, Dropbox `spinup/2026-11-12/reversal/`)

Code: c5a2afe, plus the cap fix c1a86f5 from U19. Settings: level 800, push limit 120°/s, 0.5 Hz, 480 s. Each attempt
started as soon as the previous ended (a reversal), except U9 and U19 (from a swing). Scored with interpolated timing.

| attempt | dir | start | brake-first (s) | first turn (s) | target (s) | mean (Hz) | min | ±5 % | ±1 % | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| U9 | + | swing | – | 60 | 100 | 0.506 | 0.474 | 99.3 | 12 | fail (one dip) |
| U10 | − | rev | 79 | 102 | 118 | 0.509 | 0.479 | 100 | 7 | pass |
| U11 | + | rev | 30 | 52 | 74 | 0.507 | 0.479 | 100 | 21 | pass |
| U12 | − | rev | 108 | 130 | 142 | 0.510 | 0.481 | 100 | 17 | pass |
| U13 | + | rev | 80 | 125 | 178 | 0.507 | 0.473 | 98.7 | 11 | fail (two dips) |
| U14 | − | rev | 121 | 142 | 155 | 0.508 | 0.489 | 100 | 21 | pass |
| U15 | + | rev | 59 | 96 | 120 | 0.510 | 0.478 | 100 | 24 | pass |
| U16 | − | rev | 70 | 116 | 139 | 0.509 | 0.478 | 100 | 18 | pass |
| U17 | + | rev | 25 | 64 | 91 | 0.508 | 0.472 | 99.3 | 9 | fail (one dip) |
| U18 | − | rev | 77 | 125 | 143 | 0.511 | 0.491 | 100 (222 s) | 5 | incomplete (spurious cap trip at 365 s; fixed c1a86f5) |
| U19 | + | swing | – | 37 | 76 | 0.501 | 0.482 | 100 | 46 | pass |
| U20 | − | rev | 88 | 140 | 159 | 0.508 | 0.481 | 100 | 6 | pass |

- **Both series together (20 attempts):** − **9/10** (U18 incomplete), + **6/10**.
  - Every + failure is a single dip to 0.47 within ~15 s of the first in-band turn (U7, U9, U13, U17).
  - So − meets 8 of 10 at the interim 0.5 Hz target; + does not yet.
- **Reversals:** all 9 turned along D within the 240 s limit (latest first turn 142 s).
  - Braking the old rotation took longer into − (70–121 s) than into + (25–80 s). The sim had predicted 16–26 s.
  - Observed, not explained. The same +/− asymmetry shows in the settling dips.
- **Video timing** (tracker-independent): U9 0.512 Hz, U10 0.517 Hz, matching the log windows.

## Next commands

1. Molly rules on the timing method. Then run 6 more attempts per direction for 8 of 10, ideally with the target centred
   (e.g. `--spin-to 0.495`: the means run 1–2 % high).
2. Read `spin_rate_summary.md`, then decide with Molly and Alma between the 16 Hz helper and the DAC route for 0.75 Hz.
3. Open items: a tracker template that fixes the 320–330° dip (frames in Dropbox `spinup/2026-11-12/tracker_dip/`); a
   spindown at September's speed (damping); the DECISIONS drag-row wording (board installed but not grounded in
   September; Molly to OK the edit).
