# lab_utils — drive, tracking and front-end notes

Which script is current: see the drive-script table in `CLAUDE.md`.
Hardware rules every session needs are in `CLAUDE.md` ("Hardware traps"); this file
holds the details behind them.

## Filter-module switch bits (measured 2026-09-09)

Probed on `OUTS_V1` (output off, no signal) by writing `SW2S` and reading which
`SWSTAT` bit lit:

| `SW2` bit | `SWSTAT` bit | meaning |
|---|---|---|
| 256 | 13 | **LIMIT** — clamps at `V{n}_LIMIT` |
| 512 | 15 | **DECIMATION** — output anti-alias for the 16 Hz monitors |
| 1024 | 12 | **OUTPUT** — connects the module to the DAC |

`SW1` bit 4 = INPUT (`SWSTAT` 10), bit 8 = OFFSET (`SWSTAT` 11).

Resting states: `V1..V4` = 768 (LIMIT + DECIMATION, output off), 1792 while driving,
and `LES_*`/`MON` = 512 (DECIMATION only; their `LIMIT` is 1, not 12800).

Writing a whole `SW2` word of 0 silently disengages the limiter. `V{n}_LIMIT = 12800`
is the hardware backstop that keeps the amp input inside 0–2.1 V; a software amplitude
check in one script is not a substitute. `stator_osc_drive.py stop` did this wrong
until 2026-09-09.

## Live channel facts (2026-08-21)

- `V{n}_TRAMP` was found at 1.0 s on all four electrodes, and it resets between runs.
  `_OFFSET` writes ramp over TRAMP, so a nonzero value low-passes a software sinusoid
  into a smaller, lagged, distorted waveform. `stator_epics_drive.py` zeroes it for a
  run and restores it after; `three_phase_drive.py` never did.
- `V{n}_OUT` is a fast test point (NDS only). Use `_OUTMON` / `_INMON` over EPICS.
- `_GAIN` reads 1.0, `SW1R` 12. `SW2R` was seen at 768 and later 1792 — check the
  output bit (1024) before concluding the drive is dead.

## LES sensor: x/y balance (measured 2026-09-10)

`LES_YAW` = x position, `LES_PIT` = y position (lateral-effect sensor; neither is an
angle). From an hour of quiet undriven data (front-end GPS 1473050000–1473053600):

| | x (`YAW`) | y (`PIT`) |
|---|---|---|
| broadband rms | 915.6 | 0.357 |
| per-bin noise floor | 7.38 (rotor motion) | **0.00174** (instrumental) |
| line SNR, 0.185–0.45 Hz | 3–15 | **25–76** |

Coherence between the axes was 0.88–0.99 at every line, so y saw the same motion,
projected ~1000× weaker: a geometry/alignment imbalance, not a light problem
(`LES_SUM` ~800 counts, no dropouts). y was limited by instrument noise, x by the
rotor's own broadband motion. Balanced x and y would give the 2-D trajectory directly
(line = libration, ellipse = whirl, circle = orbiting centre). The 2026-10-09 beam move
flipped which axis is strong; see `docs/DECISIONS.md`.

## `stator_epics_drive.py` (older EPICS `_OFFSET` drive)

`status / calibrate / detent / hold / spinup / stop`. Dry-run by default, `--live` to
touch hardware. EPICS only (`_OFFSET`, `_TRAMP`, `DRVON`), which avoids the AWG slot
limit and the front-end clock frame. The cost is bandwidth: software-timed writes
reach a few Hz electrical, and synthesising AC through `_OFFSET` fails somewhere
between 0.16 and 4 Hz electrical (`hv_amp_dc_investigation.md`). Its `calibrate`
subcommand (DC staircase on one electrode) is the way to measure `VOLTS_PER_COUNT`
on the `_OFFSET` path. It refuses to print torque limits until `--volts-per-count`
is passed.

## AWG route (superseded by DRVMTRX, kept for reference)

- The API is a bare `import awg` (not `cdsutils.awg`): `Sine(chan, ampl, freq, phase,
  offset, start, duration, restart)`, phase in radians, start in GPS seconds.
- Three Sines on `V{n}_EXC` sharing one explicit `start` are a coherent three-phase
  drive. `start` must come from `Y1:DAQ-DC0_GPS`; `awgbase.GPSnow()` is true GPS and
  lands in the front end's past, so the excitation silently never plays.
- `MAX_NUM_AWG = 9` channels. Slots leak unless stopped with `wait=True`
  (`stator_awg_drive.py reclaim_slots`).
- To drive `_EXC`: `GAIN = 1`, module input OFF (`SW1` 4), output ON (`SW2` 1024).
- `diag` SineResponse is the other route; template in
  github.com/aaronmarkowitz/labutils (`scripts/dipole/measure_actuator_gain.py`).
  y1rds is not y1dmd.

## Model history

The original `y1rds` fan-out was a hardwired (sin, cos, −sin, −cos), which could not
give per-electrode phases. It was replaced on 2026-09-08 by `DRVMTRX`; see
`y1rds_model_change_muxmatrix.md`.
