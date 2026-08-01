# Camera vision for rotor feedback

Camera-based readout of the graphite rotor, built toward **closed-loop phase-locked
drive**. See also `../lab_utils/` (drive/laser scripts) and the project notes.

## The problem we're solving

We want to **reliably spin the rotor above 1 Hz (target ~4 Hz), start it from a
librating state, and hold it at a set speed**. Open-loop frequency sweeps only reach
~0.4 Hz *asynchronous* rotation because the HV amplifier is already saturated — so we
need a **feedback loop that phase-locks the drive to the rotor** (always pushing
slightly ahead of the current angle, never braking).

That loop needs a live measurement of **rotor angle / phase**, its **frequency and
direction**, and whether it is **librating vs. rotating**. The lateral-effect sensor
(LES) gives some of this at high rate, but the **camera lets us actually "see" the
rotor state** — which is what this directory provides.

## Cameras (both monochrome, both run from the `ueye` conda env)

| Camera | Role | Shutter / speed | Driver |
|---|---|---|---|
| Thorlabs **DCC1545M** (uEye) | current / legacy | rolling, ~25–46 fps | `pyueye` |
| Basler **acA1440-220um** | **preferred for feedback** | **global, ~220 fps**, Mono8 | `pypylon` |

Global shutter + high frame rate make the Basler the right camera for a fast,
blur-free, alias-free tracking loop. It plugs into **worker2** (same machine as the
EPICS actuation, for low latency).

## Scripts

- **`record_ueye_video.py`** — uEye capture. Modes: `image` (view), `record`
  (view+save), `data` (headless save). `image`/`record` use `cv2.imshow`, so they need
  an X display — they fail over plain SSH.
- **`grab_basler.py`** — **headless** Basler capture (no `imshow`, no X11). Three
  readout paths, any combination:
  1. `/dev/shm` JPEG snapshot (default) — latest frame, no display needed.
  2. **MJPEG HTTP stream** (`--mjpeg`) — watch live in a browser, over SSH.
  3. GPS-timestamped `.avi` recording (`--record`).

## Setup

```bash
conda activate ueye          # has cv2 4.12, pyueye, pypylon 26.6 — drives BOTH cameras
```

**Import order matters:** in any script using both, `import cv2` **before**
`from pypylon import pylon`, or cv2 loads the system libstdc++ and throws a
`CXXABI_1.3.15` error.

**Basler USB permissions (already installed on worker2):** udev rule
`/etc/udev/rules.d/69-basler-cameras.rules` grants Basler (`idVendor==2676`) to the
`plugdev` group — no `chmod` needed. (Source staged at `~/basler.rules` +
`~/setup_basler_udev.sh`.)

**Before high frame rates:** raise the USB buffer — `usbfs_memory_mb` is 16 by default,
fine up to ~60 fps; set to 1000 (`setup-usb.sh`, or add
`usbcore.usbfs_memory_mb=1000` to the GRUB cmdline) for full-rate streaming/recording.

## Usage

```bash
# Watch live in a browser on worker3 — no X11:
python grab_basler.py --mjpeg
#   then open  http://worker2:8080/   (single frame: /snapshot.jpg)

# Watch + record, short exposure to freeze motion:
python grab_basler.py --mjpeg --record --outdir videos --exposure 2

# Headless snapshot only (for a tracker / remote inspection):
python grab_basler.py            # writes /dev/shm/basler_latest.jpg every 0.5 s
```

Key flags: `--exposure` ms, `--gain` dB, `--fps` (cap; 0 = uncapped), `--roi x,y,w,h`,
`--port`, `--snapshot PATH`, `--snapshot-every`, `--duration`. See `--help`.

## Status

- [x] Basler connected on worker2 (USB3), permanent udev access, `pypylon` installed.
- [x] `grab_basler.py` — all three readout paths validated live.
- [x] Offline tracking studied on a uEye clip; validation methodology established.
- [ ] `usbfs_memory_mb` → 1000 for >60 fps.
- [ ] Mount + focus Basler on the rotor; add illumination; suppress the fixed glint.
- [ ] Build the tracker on the **current** sample (features differ from the old clip).
- [ ] Live angle/frequency/direction + confidence → overlay and/or EPICS channel.
- [ ] Close the loop: phase-locked electrode/laser drive.

## Lessons from the offline analysis (read before writing a tracker)

- **Per-frame noise is the wrong quality metric.** A tracker can have 0.02°/frame noise
  and still be completely wrong. Validate with **loop-closure** (de-rotate by the
  tracked angle → structure should sharpen), **independent cross-method agreement**, and
  a live **match-confidence (ncc)** flag.
- **Differential/integrating trackers rectify libration into fake DC rotation** — use an
  **absolute**, non-accumulating angle referenced to a template.
- **Symmetry aliases naive trackers** (a 12-fold toothed rotor is ambiguous every 30°);
  resolve with harmonic separation, high frame rate, or a **unique fiducial**.
- **Fixed lab-frame features (glints, lighting gradients) contaminate tracking** — the
  bright "bar" in the old clip was a stationary reflection, not a rotor feature. Kill
  glints optically (reposition light / cross-polarization).
- **Tilt/whirl:** the rotor motion isn't a pure in-plane rotation (disc tilt +
  imbalance-driven whirl), so account for it — and note whirl is itself a useful
  **balance diagnostic** we can extract from video.

## Fiducial note (balance is critical)

Balance matters immensely, so avoid a single off-center dot. If a mark is needed for
absolute phase, use a **balanced pair** (180° apart, distinguishable by size). Both
cameras are mono, so **color dots don't help** — use a **white/vacuum-rated** mark
(black-on-graphite has no contrast; ~1e-6 Torr → mind outgassing).
