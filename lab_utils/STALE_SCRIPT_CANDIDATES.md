# lab_utils stale-script candidates (W5, 2026-11-01)

Flag only; nothing deleted or edited. Molly prunes.

**Method (measured):** `ls lab_utils/*.py` (35 files); last change from `git log --format='%ad %h' --name-only -- lab_utils` (first hit per file); first docstring line via `ast`; references via a word-boundary regex over all .py/.md/.ipynb in the worktree (excluding self and .git; "refs" = count of other files:lines, first few shown; refs inside other lab_utils scripts count); log date = latest dated heading containing the name in `apparatus_log.md` / `logs/2026-q3.md`. Verdicts are **inferred** from those. Last-change dates are commit dates of the latest touching commit and may reflect bulk commits (e.g. 2026-08-21, 2026-09-08).
Caveat: reference counts are text matches, not proof of use; scripts run only from a shell leave no reference.

## Candidates first

| Script | Purpose | CLAUDE.md status | Refs (non-self) | Last change | Last log | Verdict |
|---|---|---|---|---|---|---|
| sweep_oscillator_reverse | reverse-direction oscillator sweep | "Broken, reversal cancels itself" | CLAUDE.md:163, stator_drive.py:18,365 | 2026-07-10 | - | candidate: superseded by stator_osc_drive (swap two phases); known broken |
| three_phase_drive | 3-phase sinusoid on V1-V3 | "Superseded; never zeroes TRAMP" | CLAUDE.md:162, stator_epics_drive.py:165, README.md:33, q3:884 | 2026-08-14 | 2026-08-25 | candidate: superseded by stator_osc_drive |
| stator_awg_drive | 3-phase drive, waveform in front end (AWG) | "superseded by DRVMTRX" | 15 refs (muxmatrix doc, CLAUDE.md:160) | 2026-09-08 | 2026-09-08 | candidate: superseded by stator_osc_drive |
| stator_chirp | phase-continuous sweep via stepped AWG | not listed | muxmatrix doc:78,212,268; stator_osc_drive.py:23 | 2026-08-28 | 2026-09-08 | candidate: superseded by stator_osc_drive (AWG route); osc_drive docstring references it |
| awg_reclaim | release leaked AWG slots | not listed | muxmatrix doc:79,270; stator_osc_drive.py:21 | 2026-08-28 | 2026-09-08 | unclear: only needed if AWG route is used; osc_drive docstring mentions it |
| sweep_oscillator | oscillator sweep (no docstring) | not listed | muxmatrix:211, stator_osc_drive.py:24, stator_drive.py:5,54 | 2026-06-01 | 2026-08-25 | candidate: superseded by stator_osc_drive (older oscillator sweep) |
| stator_epics_drive | DC-only EPICS tool for stator | "Older _OFFSET drive, a few Hz at most" | 18 refs, 9 log mentions to 2026-09-30 | 2026-10-29 | 2026-09-30 | **DELETED 2026-11-01 (Molly)**; replacement `stator_detent.py` on branch `detent-test` |
| stator_drive | torque/capture/ramp formulas | "Physics reference only; backend cannot run" | CLAUDE.md:161, 8 refs | 2026-10-29 | 2026-09-30 | keep (reference, per CLAUDE.md) |
| test_exc_phase_coherence | one-off _EXC relative-phase test | not listed | q3:784 only | 2026-08-28 | 2026-08-28 | candidate: unused (one-off test, 2026-08) |
| measure_stator_stiffness | stator angular stiffness measurement | not listed | q3:766,784 only | 2026-10-29 | 2026-08-28 | unclear: only old log refs but edited 2026-10-29 (rev G?) |
| electrode_noise_generator | (no docstring) | not listed | q3:686 only | 2026-08-21 | 2026-08-28 | candidate: unused (one mention, Aug) |
| laser_power_sweep | configurable laser sweep for optical sensitivity | not listed | 0 | 2026-07-10 | - | candidate: unused (no refs, no log) |
| damping_monitor_gui | real-time tau vs laser power GUI | not listed | laser_power_sweep.py:6 only | 2026-09-08 | - | candidate: unused (only ref is another candidate) |
| spindown_gui | real-time spindown GUI | not listed | analyze_freq_timeline.py:153, q3:435 | 2026-09-08 | 2026-09-08 | candidate: superseded by track_spindown / track_drive (inferred) |
| analyze_freq_timeline | frequency timeline from LES PIT HDF5 | not listed | 0 | 2026-09-08 | - | candidate: unused (no refs) |
| export_data | (no docstring) | not listed | 0 | 2026-05-29 | - | candidate: unused (no refs, oldest commit) |
| run_thorcam | (no docstring) | not listed | 0 | 2026-05-29 | - | candidate: unused (no refs; camera_utils may hold capture now, not checked) |
| ReadPressure | (no docstring) | not listed | log_pressure.py:3,62; original_files/* | 2026-05-29 | - | unclear: used by log_pressure; gauge hardware status unchecked |
| visausb | pyvisa USB base class | not listed | log_pressure.py:6; original_files/functiongenerator.py | 2026-05-29 | - | unclear: dependency of log_pressure |
| log_pressure | vacuum-gauge logger | not listed | calibration_history.md:10, STATUS.md:86 | 2026-07-19 | - | keep (STATUS.md references it) |
| fetch_data_to_h5 | fetch to HDF5 | not listed | spindown_20260702.ipynb:504 | 2026-07-31 | - | unclear: one notebook ref, superseded by batch_fetch? (not checked) |
| laser_power_calibration | PD to mW calibration | not listed | analysis/laser_calibration/pd_calibration.ipynb:9,467 | 2026-07-20 | - | keep (notebook uses it) |
| build_background | median background for angle detection | not listed | detection_notes.md:32 | 2026-08-21 | - | unclear: one doc ref; camera_utils tracking may have replaced it |

## Keep (in use)

| Script | Purpose | Status | Refs | Last change | Last log | Verdict |
|---|---|---|---|---|---|---|
| stator_osc_drive | front-end oscillator + DRVMTRX drive | THE drive | 10 (CLAUDE.md:156, HANDOFF) | 2026-09-09 | 2026-10-14 | keep (in use) |
| track_drive | LES frequency tracker during drive | listed | apparatus_log:326,334,335; CLAUDE.md:157 | 2026-10-09 | 2026-10-09 | keep (in use) |
| drive_coupling | video angle vs drive phase (D1-D2, C1) | not listed | DRIVE_LOCK_HANDOFF | 2026-11-01 | - | keep (in use, new) |
| fetch_les_for_video | LES for a Basler video span | not listed | apparatus_log:40, DECISIONS:11 | 2026-10-30 | 2026-10-30 | keep (in use) |
| batch_fetch | fetch channels over GPS range to Dropbox | not listed | 12 refs, HANDOFF:72,101 | 2026-09-09 | - | keep (in use) |
| laser_step_down | step-down with settled check | not listed | notebook, q3:107 | 2026-10-31 | 2026-09-14 | keep (in use) |
| settled_check | check_settled() | not listed | laser_step_down.py imports; apparatus_log:299 | 2026-09-14 | 2026-10-09 | keep (in use) |
| laser_on / laser_off | laser switching | not listed | apparatus_log:274 | 2026-08-21 | 2026-10-09 | keep (in use) |
| monitor_libration | live libration monitor | not listed | apparatus_log:300, 3 notebooks | 2026-09-08 | 2026-10-09 | keep (in use) |
| track_spindown | rotation frequency after drive stop | not listed | apparatus_log:300, STATUS.md:18 | 2026-09-08 | 2026-10-09 | keep (in use) |
| watch_capture | catch capture into libration | not listed | track_drive.py:130, spindown_20260909 nb | 2026-09-09 | - | keep (referenced by track_drive) |

## Skipped
No import-graph analysis (text match only); no check of camera_utils or Dropbox/other machines for shell-only usage; no check of worker2's copies.
