# Side camera: brief for a fresh session (2026-11-17)

**Read first:** `CLAUDE.md`, then this file. Work on worker2, which the camera plugs into. Labels: M measured,
D derived, A assumed; "Molly" = Molly said.

## Goal (Molly)

A new **side-view camera** to see exactly where the 660 nm push laser lands on the sail. Its first output is a
picture of the spot on the sail. Later, the spot's height and its distance from the rotor axis in mm (the lever
arm), with the beam position recorded for each filter. Setup first: driver, capture, focus, exposure.

## The camera

- Thorlabs/IDS, USB3 (Molly, 2026-11-17: "I believe"). Confirm the model from its label or from
  `lsusb` / `idscameramanager` and write it here.
- Old code that worked before (Molly): `camera_utils/record_ueye_video.py` (pyueye; modes `image`, `record`,
  `data`; GPS-stamped file names). It ran from the `ueye` conda env on worker2 (`conda activate ueye`: cv2 4.12,
  pyueye, pypylon). The README marks it "no longer used", but it is the starting point.
- If it's a Thorlabs **TSI**-line camera (Zelux/Kiralux, not IDS-made), the other old script is
  `lab_utils/run_thorcam.py` (thorlabs_tsi_sdk, PyQt5, copied from Alma's labutils).

## What is known about the spot (D, from the top camera, analysis by the Mac session)

- Top-camera frames from 2026-11-16 (ND1 and no filter, minus laser-blocked frames): the light lands on the
  left/lower-left of the hub, ~25–30 px from the rotor axis in the Basler image (axis at 128.6, 176.5 px; the
  white dot runs at r ≈ 23 px). Much of it is glare and scatter, so there is no sharp edge, and no px→mm scale.
- Assumed lever arm for the recoil comparison: 1.38 mm (mid-wing). The side view should tell whether the
  beam lands near that.

## Laser levels (`analysis/calibration_history.md`, 2026-11-16)

PD `Y1:RDS-PD_INMON` (after the ND, before the chamber): 222 counts/mW. No filter ≈ 3.08 mW at the window;
ND1 ≈ 0.30 mW; ND2 ≈ 31 µW; ND3 ≈ 3 µW; ND4 ≈ 0.29 µW (measured from the 16–17 Nov night). For imaging use
ND1 or no filter briefly; at ND3/ND4 the spot is too faint for the top camera.

## Don't disturb (check with Molly or the Mac session for today's schedule)

- **Interleaved laser runs at night** (`coast_series.py`, run from the other worker2 session). The top Basler
  tracker runs at 50 fps on worker2 and has had **0 dropped frames**. Before any run, confirm the side camera
  (streaming or just plugged in) does not cause tracker frame gaps or CPU load.
- **Beam position.** Mounting near the chamber or the laser path must not nudge the beam, the lens holder or
  the filter holder. A change in where the beam lands changes the torque calibration.
- **Stray light.** Lighting for the side camera must not reach the top camera (the tracker needs ncc ≥ 0.62)
  or the pickoff PD (it already picks up room light, ~1 count).

## Rules (from CLAUDE.md)

- Ask Molly first before any hardware actuation (drive, laser, HV, `--live`). Camera capture itself is
  hardware-touching code.
- **Code on a branch in its own worktree** on worker2 (`git worktree add ~/wt_sidecam -b side-camera
  origin/main`); test there; merge after Molly OKs. Doc edits and notes can go to main via the Mac session.
- No `--leave-running`. Don't restart GNOME Shell. Videos: upload to Dropbox and verify before deleting local
  copies, never during runs.
- Keep a `HANDOFF.md` in your task folder if it runs past one sitting; log the session in `apparatus_log.md`.

## Suggested first steps

1. Identify the camera (model, serial, USB3 link speed) and the right SDK. Try `record_ueye_video.py image` in
   the `ueye` env.
2. Get a live view. Set exposure and gain with the room lights as they are during runs.
3. Focus on the sail edge. Photograph a known dimension (e.g. a sail feature or a screw head) for a px→mm scale.
4. With Molly: ND1 or no filter for 1–2 min, rotor at rest or swinging. Take laser-on and laser-blocked frames, and
   send them, or their Dropbox path, to the Mac session.
5. Check that the top tracker still runs with 0 dropped frames while the side camera streams.
