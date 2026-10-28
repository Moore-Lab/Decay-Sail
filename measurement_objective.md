# Directive

**Reliably spin up the rotor with the electrodes.**

Spin up to a set frequency, on demand, repeatably. Nothing else.

---

## Where it stands

Measured 2026-10-14, two runs, `hold --felec 0.08 --amp 6400`:

- Drive on → LES rms 15.6 → 304.9 counts, with a line within one FFT bin of the
  0.0200 Hz that f_elec/8 predicts. Reproduced.
- Video phase coherence 0.670 during drive; four full turns would give ~0.04.

**The rotor is driven at f_elec/8 but not carried around by the wave.**

Observed directly: sometimes forward motion with sudden backward slips,
sometimes back-and-forth.

## The constraint

`--amp 6400` is the ceiling. amp + pedestal = 12800 = `V{n}_LIMIT`, which keeps
the HV amp input inside 0–2.1 V. **There is no more drive torque available in
software.**

## Tools

| | |
|---|---|
| drive | `lab_utils/stator_osc_drive.py` (oscillator + DRVMTRX) |
| rotor angle | white dot on the rotor, Basler acA1440-220um, `camera_utils/grab_basler.py` |
| LES frequency | `lab_utils/track_drive.py` |

Camera, measured 2026-10-28 at 50 fps: 84% good detections, 0 dropped frames,
0.14 ms to compute an angle, 0.44 ms for an EPICS write. The dot gives a full
360° angle, so no divisor convention is involved.

## Unmeasured

Whether `DRVMTRX` can be stepped fast enough to control the field phase. Writes
go through `SETTING_*` then `LOAD_MATRIX` and ramp over `DRVMTRX_TRAMP`.

This decides whether a feedback loop is possible. Nothing else is blocking.
