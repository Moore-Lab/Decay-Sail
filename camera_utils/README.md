# camera_utils — Basler / uEye capture and rotor-angle tracking

Camera setup and the capture scripts. The tracking problem (what the rotor looks like,
what has been tried, what is open) is in `TRACKING_NOTES.md`. Why tracking matters: the
spin-up directive in `../measurement_objective.md`.

## Cameras (both monochrome, both run from the `ueye` conda env on worker2)

| Camera | Role | Shutter / speed | Driver |
|---|---|---|---|
| Basler **acA1440-220um** | **the one in use** | global, up to ~220 fps, Mono8, 3.45 µm pixels, 1440×1080 | `pypylon` |
| Thorlabs DCC1545M (uEye) | legacy | rolling, ~25–46 fps | `pyueye` |

**Basler optics (2026-10-29):** Navitar 16 mm F1.4, C-mount. At the current working
distance the magnification is **~0.09×**, so the rotor (Ø ~3.4 mm) is **~95 px** across
and the white mark only ~10–15 px. Magnification ≈ (lens extension) / f: more needs
the lens further from the sensor (a C-mount spacer, or the lens unscrewed 2–4 turns at
0.79 mm per turn, ~0.2–0.3×, held with an O-ring or tape) and the camera closer to the
rotor. A 35–50 mm lens would give the same magnification at a larger working distance.
The 6–12 mm varifocal lens does not help.

## Scripts

| script | what |
|---|---|
| `grab_basler.py` | Headless Basler capture: `/dev/shm` JPEG snapshot (default), MJPEG stream to a browser (`--mjpeg`), GPS-named recording (`--record`), live window (`--show`, needs a display). |
| `rotor_angle_loop.py` | Rotor angle at frame rate from the white mark, in-process (pypylon → numpy). Measures only, commands nothing. Holds the camera exclusively, so it cannot run alongside `grab_basler.py`. |
| `analyze_detent_video.py` | Scores a `--phase` sweep video by capture. |
| `darkline_tracker.py` | Tracker for the **old** rotor's dark diametric line (see `TRACKING_NOTES.md`, history). |
| `record_ueye_video.py` | uEye capture (`image` / `record` / `data`); `image`/`record` need an X display. |

**Recording format (`grab_basler.py --record`, since 2026-10-28):**
`output_basler_gps<true GPS>.avi`, **FFV1 lossless Mono8** by default (falls back to
MJPG q=100 if the OpenCV build can't open FFV1; the codec used is printed at start),
plus a per-frame sidecar `output_basler_gps<GPS>.csv` with
`frame_index,block_id,cam_timestamp_ns,host_time`. The GPS in the filename is true GPS
(worker2 clock), not the front-end clock.

## Setup

```bash
conda activate ueye          # cv2 4.12, pyueye, pypylon 26.6
```

- **Import `cv2` before `pypylon`**, or cv2 loads the system libstdc++ and throws
  `CXXABI_1.3.15`.
- **Orientation** is saved in the camera (`UserSet1`, the default). Don't add flip flags;
  a single flip reverses the apparent sense of rotation.
- USB permissions: udev rule `/etc/udev/rules.d/69-basler-cameras.rules` (installed).
- Above ~60 fps, raise `usbfs_memory_mb` from 16 to 1000 (`setup-usb.sh` on worker2, not in the repo, or
  `usbcore.usbfs_memory_mb=1000` on the GRUB cmdline). Not done yet.

## Usage

```bash
# Watch live in a browser from any lab machine (no X11):
python grab_basler.py --mjpeg            # then open http://worker2:8080/

# Watch + record lossless, short exposure to freeze motion:
python grab_basler.py --mjpeg --record --outdir videos --exposure 2

# Live angle (stop grab_basler.py first):
python rotor_angle_loop.py --csv angles.csv
```

Key flags: `--exposure` ms, `--gain` dB, `--fps`, `--roi x,y,w,h`, `--codec`,
`--duration`. See `--help`. `--roi` only crops; it does not change magnification.
