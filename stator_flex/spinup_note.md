# Electric spin-up of the levitated rotor: mechanism and a reliable protocol

*Companion script: `spinup_estimates.py` (numbers quoted below use I = 1.88e-11 kg m^2,
SGD03 disk + pinwheel sail, levitation height 0.41 mm, posts assumed ~13 mm from center.)*

## 1. What the 4-post drive actually produces

The posts driven sin / cos / -sin / -cos make an approximately **uniform in-plane E field
rotating** at the drive frequency f_d (an l=1 azimuthal potential; with 4 posts at 90 deg
you cannot make a rotating quadrupole, only this rotating dipole field plus a standing
quadrupole residual). Important caveat: the rotor floats ~0.4 mm above the conducting
magnet surface, which forces the tangential field to zero at that plane. The in-plane
field at the rotor is therefore screened by roughly h/R_post ~ a few percent to ~10%:
free-space estimate ~6 kV/m at +/-100 V drops to plausibly **a few hundred V/m** at the
rotor. Worth one COMSOL run of the actual electrode + magnet geometry to pin this down.

## 2. Candidate torque mechanisms

A rotating **uniform** field exerts torque on the rotor only through:

1. **Induced-dipole shape anisotropy (likely dominant by design).** The SS sail is a
   conducting vane with very different polarizability along vs. across the wing span
   (dalpha ~ 4.5e-19 F m^2 for a 5.25 x 1 mm vane). Torque
   tau = (1/2) dalpha E^2 sin(2 delta), where delta is the angle between the field and
   the wing axis. This is a **synchronous (hysteresis-free) torque with 180-deg
   symmetry**: two stable lock angles per revolution. Scales as **V^2** and is
   independent of the rotor's charge state.
2. **Permanent charge dipole.** Net charge q whose centroid sits a distance d off the
   spin axis (or patch potentials) gives p = q d and tau = p E sin(delta): synchronous,
   **360-deg symmetry, scales as V^1, depends on the (uncontrolled) charge state**.
   For q ~ 1e6 e and d ~ 0.3 mm this is the same order as mechanism 1 at ~300 V/m —
   the two are genuinely competitive, which is itself a source of irreproducibility.
3. **"Induction motor" (asynchronous) torque** from ohmic lag in homogeneous graphite is
   negligible (charge relaxation time eps0/sigma ~ 1e-16 s). Only a lossy RC interface
   (SS sail contacting graphite through Kapton/adhesive) could give a weak asynchronous
   drag toward f_d. This may be what slowly spins the rotor up before it locks.
4. **Net-charge monopole:** gives a rotating *force*, not a torque — it drives orbital
   (translational) motion, and is a nuisance: if f_d sweeps through a lateral trap
   resonance it will heat the orbit. Argues for neutralizing the rotor and avoiding the
   lateral resonance frequencies during ramps.

## 3. Why the current approach is unreliable

Both usable torques are **synchronous**: the time-averaged torque is zero unless the
rotor already co-rotates with the field. Starting the drive at a fixed f_d only captures
the rotor if f_d is within the pull-in bandwidth, which is the libration frequency in
the lock potential:

    f_capture = sqrt(2 tau_max / I) / 2pi  ~  5–70 mHz  for E ~ 100–3000 V/m.

That is *tiny*. Turning on a drive at, say, 1 Hz gives essentially zero average torque;
whatever spin-up you see then relies on the weak asynchronous residuals (mechanism 3,
or stochastic capture assisted by gas damping), which depend on charge state, initial
phase, and pressure — exactly the observed "sometimes it works" behavior.

## 4. Reliable protocols

**A. Open-loop frequency ramp (synchronous-motor start) — simplest, no new hardware.**
1. Neutralize the net charge (UV/filament) so mechanism 1 dominates and the torque is
   reproducible; keeps orbital heating away too.
2. Turn on the field **static** (f_d = 0) and wait for the sail to align (gas damping at
   operating pressure, gamma ~ 1/10 min, settles the libration in ~tens of minutes; at
   lower pressure this wait grows — see protocol B).
3. Ramp f_d from 0 at alpha_ramp <= 0.5 * tau_max / I. The rotor tracks the field like a
   stepper motor with a slip angle sin(2 delta) = I alpha_ramp / tau_max; if you exceed
   tau_max it pulls out, which is also a clean *measurement* of tau_max: the maximum
   sustainable ramp rate calibrates the torque directly.
4. **Direction reversal:** ramp f_d down through zero and back up with opposite
   handedness (or equivalently swap the phase of one electrode pair). The rotor stays
   locked the whole way; there is no discontinuity at f = 0.
   With +/-100 V (E ~ 300 V/m) reaching 1 Hz takes hours; with ~1 kV on the posts (the
   HV amps exist) it is ~18 min, and reversal from 1 Hz ~18 min. Torque scales as V^2,
   so voltage is by far the strongest knob.
5. The maximum locked speed is set by gas drag: f_max = tau_max/(2 pi I gamma) — at a
   10-min damping time, ~0.1 Hz for 300 V/m but ~10 Hz at 3 kV/m. Lower pressure raises
   f_max and lowers thermal noise simultaneously.

**B. Closed-loop commutation (brushless-DC mode) — recommended endpoint.**
Use the camera sail-angle readout (machine_vision already extracts it) to command the
field angle: phi_E = theta_rotor + delta_lead, with delta_lead = +45 deg for the
2-theta induced torque (-45 deg to reverse). This gives maximum torque at every speed,
is **self-starting from any orientation**, never pulls out, and reverses direction at
full torque instantly on sign flip — no waiting for alignment or slow ramps, and it
doubles as an active damper for the libration. Latency budget (20-deg phase error):
~50 ms at 1 Hz, ~5 ms at 10 Hz — a 100 fps camera with linear phase extrapolation, or
the CDS front end fed by the photodiode, is enough. Practical hybrid: closed-loop for
start/stop/reverse, hand off to open-loop synchronous drive (protocol A) for long
constant-speed runs so the drive is spectrally clean.

## 5. Quick experiments to pin down the mechanism

1. **Voltage scaling:** measure max sustainable ramp rate (= tau_max/I) vs. drive
   voltage. Quadratic -> induced anisotropy; linear -> charge dipole.
2. **Charge dependence:** repeat after adding/removing charge with UV/filament. No
   change -> induced anisotropy (good news: reproducible forever).
3. **Lock symmetry:** while locked, step the drive phase by 180 deg. Nothing happens ->
   2-theta (induced); rotor swings half a turn -> 1-theta (dipole). A 90-deg step
   disambiguates further (2-theta: rotor swings 90 deg; 1-theta: swings 90 deg too, but
   transient amplitude differs; the 180-deg test is the clean one).
4. **Slip-angle measurement:** camera angle of sail minus known field phase while locked
   gives tau(delta) directly — the full torque curve for free.

## 6. Numbers (from `spinup_estimates.py`)

| E at rotor | tau_ind | f_capture | ramp 0->1 Hz | f_max @ 10-min damping | reversal from 1 Hz |
|---|---|---|---|---|---|
| 300 V/m (~+/-100 V now) | 2e-14 N m | 7 mHz | 3.3 hr | 0.1 Hz | 3.3 hr |
| 1 kV/m | 2.2e-13 | 24 mHz | 18 min | 1.1 Hz | 18 min |
| 3 kV/m (~+/-1 kV, HV amp) | 2e-12 | 73 mHz | 2 min | 10 Hz | 2 min |

(Charge-dipole torque for q ~ 1e6 e, d ~ 0.3 mm is comparable at the low end; all
E-at-rotor values carry the screening uncertainty of Sec. 1.)

## 7. Outcome: the planar stator (built)

Sections 1-6 diagnosed the side-post drive; the conclusion was to move the
electrodes underneath the rotor. That design is now complete and documented in
`flex_design/flex_spec.md`, with the code and fab package in the
[Decay-Sail repo](https://github.com/Moore-Lab/Decay-Sail/tree/main/stator_flex).
Summary of what changed relative to the analysis above:

- **Mechanism:** electrodes under the rotor form a parallel-plate capacitor
  (E ~ V/h ~ 3e5 V/m instead of a few hundred V/m at the rotor), and the torque
  becomes variable-capacitance, `tau = 1/2 (dC/dtheta) V^2` — charge-independent
  and reproducible, unlike either synchronous mechanism of Sec. 2.
- **Drive harmonic:** Fourier analysis of the real rotor DXF
  (`flex_design/analyze_snowflake_dxf.py`) shows the Snowflake V1.3 underside
  modulation is in the **m = 8 family**, not the m = 12 the drawing note
  implies. Folding in gap attenuation exp(-m h / r), m = 8 is the fab-robust
  optimum. Implemented as 24 sectors, 15 deg pitch, 3-phase.
- **Torque:** ~1.5e-11 N m at 200 V with a 0.1 mm shim (h ~ 0.27 mm) —
  about 300x the side posts. Capture bandwidth 0.41 Hz mechanical (vs 5-70 mHz),
  so fixed-frequency starts below ~0.4 Hz simply work and a ramp to 10 Hz takes
  ~2.6 min. Reverse by swapping two phases.
- **The gap is the dominant knob:** h = 0.37 -> 0.27 mm is worth 3x. A shim disk
  under the board centre sets it.

The lossy-dielectric induction-motor variant (old Sec. 8) was not pursued: it
needs surface resistivity ~1e9-1e10 ohm m, which is unstable in vacuum, and a
charge-trapping layer on the rotor conflicts with the charge control needed for
the Pb-212 measurement. The capacitance motor gives deterministic starts without
modifying the rotor at all.

## 8. Still-valid diagnostics from the post era

These remain the right measurements to confirm the mechanism once the stator is
installed (they now apply to the stator drive):

1. **Voltage scaling:** max sustainable ramp rate vs drive voltage. Quadratic
   confirms the capacitance/induced-dipole mechanism.
2. **Charge dependence:** repeat after adding/removing charge with UV/filament.
   No change -> capacitance motor, i.e. reproducible indefinitely.
3. **Detent structure:** with the stator, energising one phase should snap the
   rotor into one of 8 detents, and stepping A->B->C should walk it 15 deg per
   step. This directly calibrates tau_max.
4. **Slip angle:** camera angle minus known drive phase while locked gives the
   full torque curve tau(delta) for free.
