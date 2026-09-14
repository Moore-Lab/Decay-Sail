# Dataset: 2026-09-11 → 09-14 — laser-driven rotation + laser-off spindown

Two contiguous datasets on the Moore Dropbox (`Microspheres/TFINER/data/…`), covering a
single physical episode: the 660 nm **pushing** laser driving the rotor into steady-state
rotation, then being turned off (lab issue) and the rotor coasting down into libration.

**Filenames are stamped in cymac/front-end GPS** (the DAQ frame clock), which runs *ahead*
of true GPS by a drifting offset (~9876 s on 09-11, ~10155 s on 09-14 — it wanders). So the
UTC times below are approximate to ±~5 min. **For slicing the data, use the DAQ-GPS values
or the "seconds-into-file" offsets — those are exact.** The cleanest internal time marker is
the PD itself: laser-on ≈ 400 counts, dark ≈ 1.5 counts.

Channel facts (from `apparatus_log.md` / `CLAUDE.md`, do not re-derive):
- All channels are 1024 Hz `_IN1_DQ` / `_OUT_DQ`.
- **`LES_YAW` = x position, `LES_PIT` = y position** (NOT pitch/yaw angle). The motion is a
  line; post-09-11 (ND05A added) it projects onto both axes.
- **While ROTATING**, the 2-fold sail makes the **2× line dominant** in LES → `rotation
  frequency = dominant LES line / 2`.
- **While LIBRATING**, `LES_YAW` *rectifies* and reports **2× the mechanical** libration
  frequency → halve it. This is a different regime; do not apply the rotation rule there.

---

## 1. Laser-DRIVEN (steady-state rotation), 09-11 20:30 → 09-13 20:25 UTC (~48 h)

The rotor held a **laser-driven steady state at ≈ 0.79 Hz rotation** (LES line ≈ 1.58 Hz,
÷2). `LASER_OFFSET = 1300` → 5.8 mW at the chamber (660 nm pushing laser).

Window (DAQ-GPS): **`1473204000` → `1473376497`**

| channel | Dropbox file | notes |
|---|---|---|
| PD    | `data/PD/Y1_RDS-PD_IN1_DQ_1473204000_1473376497.h5` | 572 MB; laser monitor (~400 cts on) |
| LES x | `data/LES_pit/Y1_RDS-LES_PIT_IN1_DQ_1473204000_1473376497.h5` | 590 MB (PIT = y) |
| LES x | `data/LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_1473204000_1473376497.h5` | 652 MB (YAW = x, strongest signal) |

Events inside this file (seconds from file start `1473204000`):
- **+0 s** — file start, ~a few min before the laser was set to 1300.
- **+600 s** (DAQ `1473204600`, ~20:40 UTC) — `LASER_OFFSET` set to **1300**; steady drive begins.
- **+172497 s** (end) — laser turned OFF (see dataset 2 for the precise transition).

**Electrodes: only a ~13.5 min drive burst at the very start.** The electrode outputs were
ON (recording) the whole 48 h but sat at flat zero except **20:29:25 → 20:42:55 UTC**
(DAQ `1473203940`–`1473204750`), during setup, overlapping the laser being set to 1300.
Only that burst was pulled (pulling 48 h of zeros was pointless):

| channel | Dropbox file |
|---|---|
| V1–V4 OUT | `data/Electrodes/Y1_RDS-OUTS_V{1,2,3,4}_OUT_DQ_1473203700_1473204900.h5` |

Burst window DAQ `1473203700` → `1473204900` (~20 min, 20:25–20:45 UTC). V2/V3/V4 carry the
drive (~3 MB each); V1 is the centre disk (only ~0.3% crosstalk, 0.12 MB).

---

## 2. Laser-OFF SPINDOWN (coast-down), 09-13 20:15 → 09-14 12:48 UTC (~16.6 h)

Starts 10 min before the turn-off so the steady state is captured, then the free coast-down.
Electrodes intentionally omitted here — their **outputs were switched OFF** for this window,
so `V*_OUT_DQ` is all NaN (no data = outputs disabled = definitively no drive).

Window (DAQ-GPS): **`1473375897`** → **`1473435502`**

| channel | Dropbox file |
|---|---|
| PD    | `data/PD/Y1_RDS-PD_IN1_DQ_1473375897_1473435502.h5` (228 MB) |
| LES y | `data/LES_pit/Y1_RDS-LES_PIT_IN1_DQ_1473375897_1473435502.h5` (190 MB) |
| LES x | `data/LES_yaw/Y1_RDS-LES_YAW_IN1_DQ_1473375897_1473435502.h5` (222 MB) |

Events (seconds from file start `1473375897`):
- **+0 s** — file start; laser still ON, steady ~0.79 Hz rotation.
- **+600 s** (DAQ `1473376497`, **09-13 20:25:26 UTC**) — **LASER OFF.** PD drops 404 → 3 in
  one second. `LASER_OFFSET` was left at 1300 (hardware/shutter off, not a setpoint change),
  so PD light level is the true marker, not the EPICS setpoint.
- **+600 s onward** — free coast-down.

### Spindown behaviour (first-look, `spindown_track.py`)
- **First ~2 h after laser-off: clean rotation decay, 0.79 Hz → ~0.1 Hz.** Trustworthy.
- **~11.5 h: LES amplitude collapses (~1500 → ~400)** — likely the rotation→libration
  transition (rotor can no longer make full turns).
- **After the transition the naive `line/2` tracker is WRONG** (LES rectifies libration), so
  the apparent "rising frequency" late in the file is an artifact, not the rotor speeding up.
  A rotation-vs-libration-aware tracker is needed for the full 16 h (TODO).

---

## Loading (personal computer)
Point at the synced Dropbox folder, e.g.:
```python
DATA = '/Users/<you>/…/Dropbox/…/Microspheres/TFINER/data'
```
See `analysis/laser_dark_vs_on.py`'s `load_h5()` for the segment-aware reader (the `.h5`
holds `data` + a `segments` group + `sample_rate` attr). The two datasets overlap ~10 min at
the turn-off, so they can be concatenated into one continuous drive-on → rest record.
