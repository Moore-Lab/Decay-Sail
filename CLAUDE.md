# Decay-Sail — working context

Diamagnetically levitated rotor ("decay sail"): a Snowflake V1.3 disk floating over a
magnet, spun by an under-rotor electrostatic stator, ultimately to measure the
femtonewton-scale alpha-recoil force from a Pb-212 source.

## Operating principles

1. **Read first:** `measurement_objective.md` (the goal), `docs/STATUS.md` (what is
   open), `docs/DECISIONS.md` (what is current).
2. **One fact, one home.** Current values and decisions live in `docs/DECISIONS.md`.
   Elsewhere, link to them; don't restate them. Before adding a line to this file, ask
   what would go wrong without it.
3. **Label claims** as measured, derived, or assumed. Never record your own
   assumption as a decision. Decisions are made by a person and dated in DECISIONS.md.
   State which checks ran and which were skipped.
4. **Report what you observe and how big it is,** with uncertainties. Don't jump to
   causes. If something is unexplained, say so.
5. **Ask first** before: hardware actuation (drive, laser, HV, any `--live`), any
   `ssh cymac1` (even read-only), git commit or push, purchases, deleting files or
   scripts, or changing a recorded decision. Otherwise proceed.
   **Git:** doc edits go straight to `main`. Code that touches hardware (drive scripts,
   capture, anything that commands an instrument) goes on a branch, is tested on worker2,
   then merged. Read-only data fetches (NDS, caget) go to `main` (Molly, 2026-10-30).
   With several agents, one branch each.
6. **Ask about intent, decide implementation.** Ask when the answer changes what "done"
   means: physics interpretation, scope, or lab state you can't observe. Decide
   implementation yourself and say what you chose and why. Ask once, in one batch.
7. **Don't re-ask settled decisions.** At checkpoints, show evidence (plots, output)
   with file paths.
8. **Handback:** every question or completion says where we are (done and verified,
   with paths), what you need from Molly and why, the exact steps for her, and what
   continues meanwhile. Recommended option first.
9. **Log each session** in `apparatus_log.md`: one short entry (did / ran, with command
   and GPS start–stop / saw / link). Analysis goes in its own file.
10. Never use `--leave-running` unless asked.
11. Front-end (cymac1) GPS: read it live, do not use a stored offset.
12. **Never restart GNOME Shell** without checking X11-vs-Wayland and asking first.
13. Git is the backup. Don't make copies of files.

## Delegation (agents)

Agents are in `.claude/agents/`; brief templates in `docs/templates/`.

- **Delegate the reading, never the deciding.** Send a `scout` for long reading where you
  only need an extract (a long log, a notebook, a web page, a file over ~8 KB). Do short
  lookups yourself. Many similar lookups become one script, not many agents.
- **Route:** `scout` (Haiku) read-only extraction; `worker` (Sonnet) execution and
  token-heavy work; `reviewer` (Fable) an independent re-check where a wrong result is
  expensive (a number going into a talk, paper or recorded decision, a stage pass/fail, a
  hardware order); `sub-orchestrator` (Opus) only when a sub-project passes all five
  tests: too big for one context, splits into 3+ independent parts, needs its own
  planning, has a checkable result, needs little from Molly mid-way. Anything else, do it
  yourself or with workers: delegation costs a plan, a handoff and a merge.
- **Every dispatch states** objective, files to read, write allowlist, output format and
  path, and turn budget (`docs/templates/worker-brief.md`). One writer per file.
- **Agents never actuate hardware**, `ssh cymac1`, push or delete; they hand back the
  command. Check their results yourself before using them; judge from files, not summaries.
- **Longer than one sitting:** keep a `HANDOFF.md` in the task folder whose top section
  (≤150 lines) holds current state, verified results and the exact next commands. Prefer a
  fresh session from HANDOFF over a degraded long one.
- **Advisor (Fable):** consult it before a costly or hard-to-reverse call (a plan, a
  stage pass/fail, a result you can't explain), not for routine steps. If a consult fails
  or times out, say so; never continue as if it answered.

## Machines

| Host | Role |
|---|---|
| Mac (`~/Desktop/VSCode/decay_sail`) | development, analysis notebooks |
| `worker2` = 192.168.1.13 | lab workstation, EPICS client, NTP-synced |
| `cymac1` = 192.168.1.11 | rtcds front end, NDS2 server on :8088 |

- Front-end model prefix is **`Y1:RDS`** (cf. Aaron Markowitz's microdiamond experiment
  on the same cymac1, which is `Y1:DMD` — *different model, do not assume they match*).

## Where things live

| Path | What |
|---|---|
| `docs/DECISIONS.md`, `docs/STATUS.md` | current values; open items |
| `apparatus_log.md` | dated session log (pre-October 2026: `logs/2026-q3.md`) |
| `analysis/calibration_history.md` | which constants applied to which datasets |
| `stator_flex/` | stator design (`flex_spec.md`), generators, fab files |
| `hv_amp_dc_investigation.md` | HV amplifier behaviour and the DC-pedestal question |
| `y1rds_model_change_muxmatrix.md` | the 2026-09-08 front-end model change (DRVMTRX) |
| `lab_utils/` | drive, tracking and monitoring scripts (`README.md`) |
| `camera_utils/` | Basler / uEye capture and rotor-angle tracking |
| `analysis/` | notebooks and analysis write-ups |

## The stator (rev G under-rotor drive)

Electrodes under the rotor make a variable-capacitance synchronous motor,
τ = ½ (dC/dθ) V²: charge-independent, ~300× the torque of the old side posts.
Design, rationale and performance: `stator_flex/flex_spec.md`.

> **Rotor speed = f_electrical / 8. Reverse by swapping any two phases.**

Drive harmonic m = 8 (derived from the rotor drawing; see DECISIONS).

### Board (rev G)

Ø25.4 mm, 2-layer polyimide flex, 0.1 mm thick, 18 µm Cu, ENIG, coverlay both sides
with openings. Mounts on the PEEK plate with four 4-40 screws at r = 9 mm; **the screws
double as the electrical terminals** (ring terminals on top pads, plated barrels tie top
to bottom).

| Terminal | Net | Function |
|---|---|---|
| 15° | A | phase 0° |
| 105° | B | phase 120° |
| 195° | C | phase 240° |
| 285° | CTR | centre disk r = 0.58 mm — charge drive / DC height trim |
| — | GND | grounded by a wire from a top GND pad (r = 10.8, az 60/240°) to a base screw. The bare bottom ring (r 2.95–3.40) barely overlaps the 1/4" magnet and does not make contact |

Electrode-to-channel map (V1 = CTR; A, B, C = V2, V4, V3): `docs/DECISIONS.md`.

### ⚠ Assembly / safety

- **The plated barrels make all four screws live, up to 200 V.** They thread into tapped
  PEEK so they are isolated from the plate — use stainless or silver-plated hardware and
  check screw length so no tip protrudes toward ground.
- **Max screw head / washer OD is 9.5 mm** before it reaches another net.
- Clock the ring-terminal tongues radially outward.
- Nothing may sit between the board centre and the magnet.
- **Board height:** shims go under the PEEK plate, and the flex lies flat (2026-10-27).
  No metal under the pads: the bottom coverlay opening exposes bare GND around each
  live pad, so a metal shim shorts that phase to GND.
- The board was hipot tested to **250 V** net-net and net-to-magnet.

### Operating protocol

1. Neutralise rotor charge; ground A/B/C when not driving.
2. Spin-up: 3-phase ramp f_elec 0 → 8·f_target at ≤50% torque margin. Fixed-frequency
   starts below ~0.4 Hz mech capture directly.
3. Reverse: swap two phases, ramp through zero.
4. Science runs: A/B/C to GND — the board becomes a clean ground plane, no drive
   systematic. CTR optionally on DC bias.

## Drive scripts

| script | status |
|---|---|
| **`lab_utils/stator_osc_drive.py`** | **THE drive** (since 2026-09-08): front-end oscillator + `DRVMTRX` |
| `lab_utils/track_drive.py` | LES frequency tracking during a drive |
| `camera_utils/rotor_angle_loop.py` | rotor angle from the white dot (Basler) |
| `lab_utils/stator_epics_drive.py` | Older EPICS `_OFFSET` drive; software-timed, a few Hz electrical at most |
| `lab_utils/stator_awg_drive.py` | AWG route; superseded by DRVMTRX |
| `lab_utils/stator_drive.py` | Physics reference only (torque/capture/ramp formulas); its backend cannot run |
| `lab_utils/three_phase_drive.py` | Superseded; never zeroes `TRAMP` |
| `lab_utils/sweep_oscillator_reverse.py` | Broken — its reversal cancels itself |

Don't delete non-functional scripts unilaterally; Molly prunes them.

## Hardware traps (read before driving)

**HV amplifier** (homemade, HV265 op-amp; details in `hv_amp_dc_investigation.md`):
- It is **bipolar** and maps *any* DC input to 0 V out.
- The input must be **positive, 0–2 V**. 12800 counts ↔ 2.1 V and `V{n}_LIMIT` = 12800,
  so **`dc >= amp` is mandatory** and `dc = amp = 6400` exactly fills the range.
- ~0.0134 V/count, measured on the `_EXC` path only; `_OFFSET` is unverified.
- DC-couple the scope and do a GND zero-line check before trusting any absolute voltage.

**Front-end channels:**
- Anything writing `_OFFSET` must zero `V{n}_TRAMP` first; a nonzero TRAMP low-passes the
  waveform while the commanded values still look perfect.
- `V{n}_OUT` is not an EPICS record. Use `_OUTMON` (output) and `_INMON` (input).
- **Never write a whole `SW2` word.** It also carries the LIMIT and DECIMATION bits.
  Clear the output with `sw2 & ~1024`. Resting `V1..V4` = 768, 1792 while driving.
  Bit table: `lab_utils/README.md`.
- AWG start times must be in the front end's clock (`Y1:DAQ-DC0_GPS`), not true GPS.

**LES sensor:**
- `LES_YAW` = **x position**, `LES_PIT` = **y position**, `LES_SUM` = total light.
  Neither is an angle; there is no channel that isolates tilt.
- **LES is the frequency readout, but the true rotor frequency is often half the LES
  line**, whether librating or rotating, and libration vs rotation is hard to tell
  apart on LES. Say which divisor you used and why. (History: `logs/2026-q3.md`, 2026-09-09
  and 2026-09-14.)
- Isolate LES/MON at their own output switches (`SW2R 512`), leaving gains at 1.0.

## Conventions

- Generated figures are gitignored (`plots/`, `analysis/*.png`); notebooks and notes are tracked.
- `analysis/ringdown_analysis_executed.ipynb` is misnamed — it is a *variant* with the
  window shifted 3 min earlier, not a re-execution.
