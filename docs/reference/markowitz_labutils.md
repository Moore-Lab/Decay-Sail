# Aaron Markowitz's `labutils`

**github.com/aaronmarkowitz/labutils** (Python; last checked 2026-08-26). Aaron (ex-LIGO
postdoc) set up the lab's CDS/rtcds DAQ, so his repo is the house template for code that
talks to the front end. His experiment is the levitated microdiamond, model `Y1:DMD`;
decay sail is `Y1:RDS` on the same cymac1. **Different models: don't assume they match.**

## Most relevant files

- `scripts/dipole/measure_actuator_gain.py`: drives electrodes via `diag` SineResponse,
  extracts a complex coupling matrix. The best template for phase-controlled excitation.
- `scripts/dipole/README.md`, `PROCEDURE.md`: the written-up method.
- `scripts/dipole/tests/`: pytest suite, incl. an opt-in live loopback test.
- `scripts/dipole/upload_actuation_matrix.py` / `upload_sense_matrix.py`: writing
  matrices to EPICS (ACTS/SENSE architecture).
- `.claude/skills/add-daq-channel/SKILL.md`: adding an EPICS channel to the DAQ
  (softIOC `.db` → `minimal_working_ioc.sh` → `edc.ini` on cymac1 → restart all four rts
  services, not just rts-edc).
- `mdl_to_adl.py`: parses rtcds `.mdl` models (incl. matrix routing) and builds MEDM screens.
- Also: `fetch_nds2_data.py`, `epics/` (softIOC, BURT, Leybold turbo), `cameras/`,
  `ndscope/*.yaml`, `moku/`.

## Infrastructure facts (from his repo, 2026-08)

- NDS2 `192.168.1.11:8088` (cymac1); EDC status page http://192.168.1.11:9000/;
  `edc.ini` dcuid 52, 16 Hz.
- Model source `/opt/rtcds/userapps/<user>/<model>.mdl`; MEDM `/opt/rtcds/yqg/y1/medm/`.
- The softIOC runs on **worker1** (`sudo systemctl restart auxioc`); the front end is cymac1.
- Filter-module switch states: read `_SWSTR` for a readable string.
- **GPS convention differs:** his scripts use `GPS = Unix − 315964818`; the correct
  offset (and this repo's) is `Unix − 315964782` (GPS epoch 315964800 minus 18 leap
  seconds). His is 36 s off; don't copy it.

## Practices worth copying

- He never uses a Python `awg` module (checked 2026-08-26 by grepping the repo); all
  excitation goes through `diag -l -f <cmdfile>`. The AWG slot limit is 9 excitation
  channels per DCU; his code checks it before any EPICS write.
- Abort cleanup: zero GAIN at once (TRAMP 0), poll NDS until every EXC channel's RMS is
  below 1 count, only then restore GAIN.
- Conventions: branch first, merge only when working and approved, never push without
  asking, `--dry-run` on every hardware script.
- The public LIGO CDS parts wiki has empty pages for `cdsOsc` and AWG/test points
  (checked 2026-08-26); don't look there for them.
