# What we are trying to accomplish

## The measurement

Detect the **Pb-212 alpha-recoil thrust** on the levitated rotor.
**F0 = 0.81 fN** (PI's figure, 2026-10-23). Note `F0_PB = 5.1e-15` is still
hardcoded in `analysis/noise_budget_2026*.ipynb` and needs updating; every SNR
statement in their section 2 scales linearly with it.

## How

A **differential CW/CCW coast-down**. Drag opposes motion, so it flips sign with
rotation direction. A lab-fixed torque does not. Compare the two directions at
matched speed and the difference isolates the torque we want:

    direction A:  tau_meas(w) = tau_drag(w) - tau_L
    direction B:  tau_meas(w) = tau_drag(w) + tau_L
    difference    = 2 tau_L,  at every w

`tau_drag` never has to be known. What is required is that the two directions
**overlap in speed**, not that they start at the same speed.

## The protocol

1. Electrodes spin up to a set frequency, direction A
2. Electrodes OFF -> coast ~10 min   <- **this is the measurement**
3. Electrodes stop the rotor
4. Electrodes spin up to the same frequency, direction B
5. Electrodes OFF -> coast ~10 min
6. Repeat, alternating

Electrodes only prepare the state. During the coast **nothing is driving**, so no
actuator noise enters the measurement window. This is why it is preferred over
holding a steady speed with the laser and looking for deviations in it -- laser
RIN would sit directly on top of the signal.

## Why the electrodes must do the reversing

The laser's torque direction is set by **which wing of the sail the beam hits**.
The sail is a flat vane across the rotor centre, two-fold symmetric; uniformly
illuminated it gives **zero** net torque, because the two wings cancel. Net torque
requires the beam offset to one side of the spin axis.

So reversing the rotor by moving the beam flips `tau_L` at the same moment it
flips `w`, and the differential **cancels instead of doubling**.

> **Reversing with the electrodes, beam untouched, is the only way to flip w
> while holding tau_L fixed. Without it there is no differential measurement.**

This is why the stator work is not a side quest.

## The blocker

The stator cannot yet spin up, stop and reverse reliably.

Measured 2026-10-14: **the rotor is driven at f_elec/8 but not carried around by
the wave -- synchronised in frequency, not locked in the motor sense.** It sits at
its capture threshold: sometimes forward motion with sudden backward slips,
sometimes back-and-forth.

`--amp 6400` is the hardware ceiling (amp + pedestal = 12800 = `V{n}_LIMIT`, which
keeps the HV amp input inside 0-2.1 V). **No more drive torque exists in
software.** The remaining levers are geometry (gap, centring, flatness -- the
2026-10-28 rebuild) and **closing a feedback loop**.

## What is being built now

**Real-time rotor angle from the camera, to close a loop on the electrodes.**

Open-loop the drive catches whatever phase it happens to land on, which is why it
slips. Knowing the angle live means always pushing ahead of the rotor and never
braking it -- `tau_max sin(load angle)` with the load angle controlled. That is
the one large gain available without new hardware.

Needed for all three operations: spin up, stop, reverse.

## State of the vision chain (2026-10-28)

Working: white dot on the rotor, two lights, Basler acA1440-220um at 50 fps,
lossless FFV1 recording with a per-frame timestamp sidecar.

| | |
|---|---|
| good detections | 84% |
| dropped frames | 0 |
| angle compute | 0.14 ms |
| EPICS write | 0.44 ms |

The dot gives a full 360 deg angle, so **no divisor convention is needed** -- unlike
LES, where rotation and libration both land on the same line.

Open: the dot clips (74% of frames have all 60 centroid pixels railed); a 2x
harmonic in the orbit consistent with ~32 deg camera tilt, which also implies
~200-300 um of parallax between rotor and board; an unexplained 3x harmonic; and
one angular sector at 44% detection despite full brightness.

**Not yet established: the actuator.** Vision is fast enough. Whether `DRVMTRX`
can be stepped fast enough to control the field phase -- writes go through
`SETTING_*` then `LOAD_MATRIX` and ramp over `DRVMTRX_TRAMP` -- is unmeasured, and
it decides whether a phase-locked loop is possible at all.
