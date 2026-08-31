# Apparatus change log

Dated record of physical changes to the rotor / optics / vacuum system, and what each
one invalidates. Analysis notebooks assume constants (γ, counts/mW, the thermal floor)
that are only valid for a particular apparatus state — this file is the record of which
state each dataset was taken in.

**Add an entry whenever anything in the beam path, the chamber, or the readout chain
changes**, even if it seems minor at the time. A change that is obvious in the lab is
invisible in an HDF5 file six months later.

Entries are newest-last. Dates are UTC unless noted.

---

## Changes

### 2026-08-28, afternoon — ROTOR SPUN. Drive moved to AWG; `_OFFSET` AC path found unusable

**The rotor did full rotations**, driven three-phase from the stator. First time.
It happened on a plain fixed-frequency drive, not on any of the pumping or
sweeping machinery built that day.

> ⚠ **The drive frequency it caught at was not recorded.** That is the single
> most valuable number from the session and it is lost — the run was started by
> hand and the log window has rolled. **Next session: record the exact command
> and the front-end GPS at the start of every drive**, so the archive can be
> re-fetched. The frequencies tried across the afternoon were `f_elec` = 0.32,
> 0.56, 0.64, 1.0 and 2.0 Hz.

#### 1. The `_OFFSET` write path CANNOT carry AC above ~0.1 Hz rotor

Driving `f_elec` = 4 Hz by writing `V{n}_OFFSET` from Python at 320 Hz produced a
**square wave**, not a sine. From `V{n}_OUT_DQ`:

| line | measured | ideal square |
|---|---|---|
| 4 Hz fundamental | 1.000 | 1.000 |
| 12 Hz (3rd) | 0.333 | 0.333 |
| 20 Hz (5th) | 0.199 | 0.200 |
| 28 Hz (7th) | 0.141 | 0.143 |

THD 38.8%; phases came out 0/180/180 instead of 0/−120/−240; amplitudes
2324/1039/1272 against 2000 commanded. **The DC pedestal was perfect**
(2002/2001/1997) — that is the tell: static settings get through, time-varying
ones do not. Matches what Molly saw on the scope (`Downloads/IMG_1018`,
`IMG_1019`: a blocky staircase).

Cause: **the front end samples EPICS settings on its slow cycle (~16 Hz)**, so at
4 Hz there are only ~4 samples per cycle however fast we write. Measured client
throughput was 500 Hz / 1500 `caput`/s — not the bottleneck. The 2026-08-24 run
looked perfect only because 0.16 Hz gave ~100 samples/cycle. **No write rate and
no `TRAMP` value fixes this.** The AC must be generated in the front end.

#### 2. AWG works — and why it never did before

> ### `start` must be in the FRONT END's clock frame:
> ### `Y1:DAQ-DC0_GPS + lead`, **not** `awgbase.GPSnow()`.

`awg.py:128` defaults `start` to `GPSnow() + 4*_EPOCH`. The front end runs **fast**
of true GPS — **+8376 s on 2026-08-28** (drifting: 5836 s on 06-03, 7630 s on
08-21) — so the default lands ~2.3 hours in its past, the excitation is already
expired, and **it silently never plays with no error raised.** Verified both ways:
true-GPS frame → nothing at `OUTMON`; front-end frame → 800 counts commanded,
742.8 measured. This explains every previous failed AWG attempt here, including
`electrode_noise_generator.py`.

With that fixed the three-phase drive is excellent: amplitudes matched to 5
significant figures, spacing **120.00°**, **THD 0.00%** — at the same frequency
where `_OFFSET` gave a square wave.

Also: `awg`'s `phase` argument enters with the **opposite sign** to the `_OFFSET`
path (commanding 0/−120/−240 produced 0/+120/+240), so the field rotates the
other way. `stator_awg_drive.py` negates internally to match the verified 08-24
direction. A transposition still makes a clean travelling wave, so this would
have spun fine and only shown up as a sign error once the video loop closed.

#### 3. ⚠ ARMING IS INTERMITTENT — unresolved, and the main open problem

Sometimes the excitation simply does not start. Symptom: **`OUT_DQ` carries the
DC pedestal with rms 0.00 and no error anywhere.** Retrying works — one test
armed on attempt 4.

**Ruled out:**

- **Not slot exhaustion.** `lab_utils/awg_reclaim.py` prints the slot per
  channel: *distinct* numbers (13005/13006/13007/13008) mean real leaked
  allocations; *the same number for all four* means nothing is allocated. It has
  been reporting the same number.
- **Reclaiming in-process made it WORSE.** The script worked reliably before a
  reclaim was added, and afterwards failed its first attempt right after it.
  `--reclaim` is now off by default; run `awg_reclaim.py` as a separate process
  if the AWG is genuinely stuck.

**Best remaining hypothesis, untested:** `start = Y1:DAQ-DC0_GPS + lead`, and that
PV ticks only once per second. A read landing late in its tick shortens the
effective lead by up to a second; if it goes negative the excitation is expired
before it is armed. **Test:** run the same drive ~5× each at `--lead 4`, `8`, `20`
and see whether the failure rate falls with longer lead. If it does, round the
start up to a `awgbase._EPOCH` (1/16 s) boundary with a couple of seconds margin.

**Workaround in place:** `stator_awg_drive.py` now checks `OUT_DQ` after arming
and retries up to 8 times, so it can no longer silently drive DC-only.

#### 4. ⚠ NEVER background a drive

When the AWG client process exits, **the excitation dies with it, while the
`_OFFSET` pedestal persists in EPICS.** DC present, AC absent — indistinguishable
from a broken drive. Several "no AC" results that afternoon were self-inflicted:
drives launched with `nohup ... &` and reaped, or killed by a `pkill` aimed at
something else. Run drives in the foreground.

#### 5. Corrections to earlier entries in this log

- **There is no "true zero-crossing near ~6400 counts."** The amp is bipolar and
  maps *any* input DC to its 0 V output point (Molly, 08-31); 6400 was simply
  where the offset was sitting during the 08-25 and 08-28 measurements. The
  "bipolar" finding in the entry below is correct; the zero-crossing number is
  not. Full account in `hv_amp_dc_investigation.md`.
- **`dc = amp = 6400` is already optimal and must not be reduced.** The amp input
  must stay positive within 0–2 V, and 12800 counts ↔ 2.1 V, so `dc = amp = 6400`
  puts the input at 0 → 2.1 V, exactly filling the range. `dc >= amp` is an
  input-range constraint, not a torque choice. `check_amplitude()`'s rejection of
  negative counts was right all along.
- **A commanded `V_dc` does not appear as a DC offset at the electrode.** That
  much is measured. What it implies for the m=8 torque channel (∝ `V_dc·V_ac`)
  is **NOT resolved** — an earlier draft of this entry asserted the channel has
  never been on and that `CLAUDE.md`'s m=8 torque/capture/ramp tables therefore
  do not apply. **Do not treat that as established**; Molly is not persuaded, and
  it rests on a chain of reasoning rather than a measurement. What is certain:
  the drive spins the rotor, and `dc = amp = 6400` is the maximum commandable AC.
- **The 2026-08-21 "DC detent" claim does not survive.** It held DC for 180 s but
  a DC step decays in ~20 s, so there was no field for most of it. *"A static
  torque from rest, which the synchronous side posts could not produce at any
  drive level"* does not follow from that measurement, and the "capture threshold
  between 3200 and 6400 counts" bracket is the response to a decaying transient.
  The variable-capacitance physics is untouched; only this evidence for it is.

#### 6. Measurements from that day that are NOT trustworthy

Recorded so they are not mistaken for results:

- **The "stator is ~6× weaker than an intrinsic trap" ratio**, and the
  **"intrinsic trap weakening 0.33 → 0.20 Hz over the afternoon"** trend. Both
  came from a peak-finder that jumped between the libration fundamental and its
  subharmonic. `measure_stator_stiffness.py` carries the same flaw and needs a
  constrained search band before reuse. The *method* is sound and `I`-independent
  — `k_int/k_stator = f_off²/(f_on² − f_off²)` — only the frequencies were bad.
- **Any rms or frequency quoted from a 1-second NDS buffer.** `conn.iterate()`
  returns 1 s blocks, which is a third of a cycle at 0.3 Hz: frequency resolution
  is 1 Hz and rms is badly under-read. This produced a false "the drive heated the
  rotor 5×". Always `fetch()` a window of ≥100 s for anything spectral.
- **LES rms as an amplitude measure once it saturates.** Peak-to-peak sat pinned
  near 4600 counts for an hour while the frequency moved 30%. The *frequency* is
  still good; the amplitude is not. The camera is the better instrument there.

#### 7. New scripts

`lab_utils/stator_awg_drive.py` (the drive — `--felec` states the electrical
frequency directly, since `f_elec = 8 × f_rotor` is an easy factor to get
backwards), `stator_chirp.py` (phase-continuous stepped sweep — `awg.SweptSine`
passes `restart=sweeptime` and therefore **loops**, snapping back to the start
frequency, so it is unusable for a spin-up; **not yet run live**),
`awg_reclaim.py`, `measure_stator_stiffness.py`, `test_exc_phase_coherence.py`.

Also traced and previously unrecorded: **each electrode has a signal summed in
ahead of its filter module** — `V1←LES_PIT`, `V2←LES_YAW`, `V3←LES_SUM`,
`V4←MON` (top level of `y1rds.mdl`). `LES_PIT`/`LES_YAW` are live; only the
input switches being off on V1/V2 keeps them off the drive, and V3/V4 are quiet
solely because `LES_SUM` and `MON` have `GAIN = 0`. `check_inputs()` guards this.
**Do not infer "nothing is arriving" from `INMON = 0`** — it is a slow monitor and
a zero-mean AC signal reads ~0 through it.

The electrode filter banks are **flat**: `Y1RDS.txt` defines zero filter sections
on `OUTS_V1..V4` (the only filter in the file is a PID on `PD`).

---

### 2026-08-28 — HV amp identified (HV265), calibration confirmed, PI confirms bipolar is normal

Follow-up to the 2026-08-25 entry below, from a from-scratch electrical
characterization session (different machine/session than the 08-25 one).

**1. Amplifier identified.** Pulled the Fusion 360 Electronics schematic apart
(the `.fsch` is a zip archive containing a plain Eagle-XML `.sch` — readable
without the app). `U1 = Microchip HV265-I/QE`, 4-channel 205 V high-voltage
op-amp array, TSSOP24, datasheet DS20006234A. One channel per V-line, `VIN ->
Hi-V Amp -> HVOUT`, `FB` tied directly to `HVOUT` (fixed gain config). Only one
HV supply net in the design (`VPP`, from an on-board DC-DC module set by a
10 kOhm trimmer off a front-panel banana-jack LV input, same node as `VDD`).

**2. Calibration confirmed, cross-validated three ways.** Careful DC-coupled,
GND-referenced measurement (BNC tee at the amp output, one leg to the chamber,
one to the scope, so this is the real electrode drive, not a monitor proxy):
12800 counts (`_EXC`, offset=amplitude=6400) = 2.1 V swing at `VIN` = 171 V
swing at `HVOUT`.
  - Gain = 171/2.1 = **81.4 V/V**. HV265 datasheet spec: 75.4-88.4 V/V (typ 82)
    for this FB-tied-direct config. Matches closely -- the chip is behaving
    exactly as designed, not out of spec.
  - VOLTS_PER_COUNT = 171/12800 = **0.0134 V/count**, consistent with the
    2026-08-25 entry below's ~0.013 V/count. Two independent measurements
    agree. Supersedes `stator_drive.py`'s old 0.03125 placeholder.
  - Still open: this is the `_EXC`-path gain. `_OFFSET` (what
    `stator_epics_drive.py` actually drives) is unverified to have the same
    slope.

**3. PI confirms the amp is genuinely bipolar.** Spoke to David Moore (designed
this board): the +/- output is completely normal, expected behaviour. This
settles the question the 08-25 entry below left open, and corrects a wrong
turn taken mid-session here: the swing was initially found to look centred on
~0 V, which was first mistaken for a scope AC-coupling artifact (a real bug,
worth the general lesson below) and "fixed" by switching to DC coupling --
which appeared to confirm a real DC offset and seemed to vindicate the
opposite (unipolar) reading. That was a false resolution. Re-measuring
carefully with DC coupling confirmed via a GND-coupling zero-line check still
showed VIN's midpoint (~1 V) landing on HVOUT's zero-crossing, with a real
bipolar swing around it -- and the PI confirmed by hand that this is correct,
not an artifact.
  - **This explains the 08-25 entry's item 5 ("offset did not create a DC
    pedestal -- unresolved").** Riding the command at ~6400 counts happens to
    land almost exactly on the amp's own natural zero-crossing point. That
    count value doesn't produce a pedestal, not because pedestals don't work.
    **To get a real V_dc for the m=8 torque channel, the commanded offset must
    be biased AWAY from ~6400 counts, not centred on it.**
  - The HV265 datasheet's own `HVOUT` spec table reads as unipolar (1.85 V min
    to VPP-10V max) -- doesn't match what's measured here. Either that's a
    characterized/recommended range rather than a hard floor, or this board's
    implementation differs from the datasheet's typical config in some way not
    visible in the schematic. Deferring to the PI and the direct measurement.

**4. General lesson, cost real time here: always check AC vs DC coupling (and
do a GND-coupling zero-line check) before trusting an absolute-voltage or
offset reading on any scope.** AC coupling silently removes the true DC
component and re-centres whatever's left around the display's 0 V line,
regardless of the real DC level -- visually indistinguishable from a genuine
bipolar-about-zero signal.

**5. Bug found in `stator_epics_drive.py`.** `banner()`'s DC-pedestal warning
only checks `dc == 0` in commanded-count space. Given the true zero-crossing is
near 6400 counts, not 0, a commanded `dc` near that value would ALSO silently
zero the real m=8 channel without triggering any warning. Needs a measured
`_OFFSET`-path zero-crossing (fine DC sweep, not yet done) before the check can
be fixed properly.

**Next:** a fine DC sweep on the `_OFFSET` path (same idea as `calibrate`, but
aimed at finding where the pedestal goes to zero, not where the amp
saturates) -- needed before the 2026-08-21 "capture threshold bracketed
between 3200 and 6400 counts" result or the 2026-08-24 live-drive `--amp 4800`
choice can be properly re-interpreted in light of the true zero-crossing.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>

### 2026-08-25 — electrode voltage measured on a scope: amp is BIPOLAR, VOLTS_PER_COUNT, _EXC path works

Drove **V2 alone** via a diaggui excitation on `V2_EXC` (front-end-generated sinusoid) with
`DRVON` off, and read the amplifier output on a scope. Electrode/voltage/counts findings only
(rotation behaviour deliberately excluded here — pending video review):

**1. The HV amplifier is BIPOLAR — it swings ±, symmetric about ~0 V, NOT unipolar.**
Setting a positive count "offset" did **not** shift the waveform to all-positive; it stayed
centred near 0 and went both + and −. This overturns the unipolar assumption baked into the
drive scripts (`three_phase_drive.py` and the `stator_epics_drive.py` default `dc = amp`,
chosen to "keep the swing ≥ 0"). With a bipolar amp that pedestal is not required for polarity
— though a DC pedestal is still wanted for torque (m=8 channel ∝ V_dc·V_ac).

**2. VOLTS_PER_COUNT — measured (on the `_EXC` path, 660-drive amplifier output):**

| counts | Vpp | − / + peak |
|---|---|---|
| 1000 | 33.4 | −15 / +18 |
| 2000 | 58   | −28 / +30 |
| 3000 | 83.2 | −40 / +43 |
| 4000 | ~110 | −52 / +58 |
| 5000 | 128  | −64 / +70 |
| 6000 | 159  | −75 / +84 |
| 6400 | 169  | −80 / +89 |

- Roughly linear at **~0.026 V/count peak-to-peak (≈0.013 V/count amplitude)** over 3000–6400;
  apparent slope is a bit higher below 3000 (likely small-signal offset). Slightly
  **sub-linear** at the top and slightly **asymmetric** (the + peak runs a few V above the −).
- **Working point 6400 counts ≈ ±85 V (169 Vpp).** So `VOLTS_PER_COUNT ≈ 0.013 V/count` at the
  operating point — use this for τ ∝ V² instead of the placeholder `0.03125` in
  `stator_drive.py`, which is provably wrong. **Better yet, work in volts directly.**
- **The real ceiling is ≥ ±85 V, higher than the "~80 V" quoted in CLAUDE.md** — and 6400 counts
  did not obviously clip, so the amp may go higher still. Was **not** driven past 6400.
- **Caveat:** this is the `_EXC`-path gain. Whether the slow `_OFFSET` path has the same
  counts→volts slope is **unverified** — do not assume they match.

**3. The `_EXC` / diaggui excitation route WORKS** (previously untested — CLAUDE.md flagged the
`awg` import as broken and a possible test-point grant needed). A single-electrode excitation on
`V2_EXC` produced a clean output, so diaggui SineResponse is a viable drive backend for at least
one channel. **It is also SMOOTH** — front-end-generated, unlike the coarse ~5–8-level staircase
that Python `caput`-to-`_OFFSET` at 200 Hz produces (confirmed by capturing `V2_OUTMON` during a
software drive). Correction to an earlier wrong claim: smooth AC *is* achievable — via the DRV
oscillator (`sweep_oscillator`) or `_EXC`/diaggui; only the Python-offset-write path is coarse.

**4. Capacitive crosstalk onto V1 (centre disk) ≈ 500 mV.** While V2 swung ±85 V (169 Vpp), the
scope saw **~500 mV** on V1 even though V1 was **not commanded** (`V1_OFFSET/OUTMON/INMON` all 0,
`DRVON` off). That is a coupling of **~0.3% of V2's peak-to-peak** (~0.5 / 170), physical
capacitive coupling to the adjacent electrode — expected, and V1 (centre, in the middle of the
sectors) is the most exposed. Benign at this level, but a real sector drive will put a small
parasitic AC on the centre electrode; if the CTR-as-charge-probe scheme is ever used, this
crosstalk sets a floor to watch.

**5. Offset field on the `_EXC` path did not create a DC pedestal** — the user set a 6400 offset
but the waveform stayed ± about ~0. So the diaggui stimulus offset did not translate to an
electrode DC bias. Unresolved; matters because the strong m=8 torque channel needs `V_dc·V_ac`.

**6. PCB is fine at this drive.** 6400 counts = ±85 V is ~⅓ of the board's 250 V hipot rating; no
damage risk driving this hard.

### 2026-07-27 — PD realigned, low-noise amplifier removed

The photodiode was poorly aligned through the step-down run, and a low-noise amplifier
in the PD chain was contributing significant noise. Both fixed on this day, before the
3 mW noise run started at 20:51 UTC.

- **Invalidates:** all PD-derived quantities from the 07-05 → 07-09 step-down run. A
  misaligned diode converts beam-pointing drift into apparent power drift, and the amp
  added noise that never reached the sail.
- **Consequence for correlation work:** PD noise not common with the rotor inflates
  `S_PP` and biases coherence `γ²(f)` **downward** (errors-in-variables), so any
  PD↔rotor coherence from the step-down run understates how much of the rotor's wander
  the laser explains. Use post-07-27 data for that analysis.
- The YAW channel is unaffected — rotor-frequency stability comparisons across this
  boundary remain valid.
- PD gain changed with the amp removal: ~16.2 counts/mW before, ~281–285 after.
  **Never reuse a κ quoted in N·m per PD count across this boundary**; convert to
  physical power first and use torque per mW, which is gain-independent.
- Measured PD linearity after the change: 280.6 vs 284.6 counts/mW over 3.03 → 10.40 mW,
  i.e. **+1.4%** — the chain is linear across the operating range.

### 2026-07-27, later the same day — tilt stage removed from the chamber

The chamber no longer has the tilt stage. The damping constant is **worse** as a result.

- **Invalidates:** τ_free = 67.65 min (measured 2026-07-02, tilt stage present) for
  everything after this point.
- **Propagates to:** the thermal torque floor `S_N = √(4k_BTγI)` scales as √γ, so the
  power-noise requirement `δP_req = S_N/(∂N/∂P)` moves with it — **0.735 µW/√Hz at
  τ = 67.65 min becomes ~1.86 µW/√Hz at the measured τ = 10.5 min**. The rotor response
  corner γ/2π moves 0.039 → 0.25 mHz.
- **Measured post-change value: τ = 10.5 ± 0.1 min** (`spindown_20260803.ipynb`). The
  electrodes drove the rotor at 3.9000 Hz phase-locked and switched off at t = 31.94 min;
  the laser stayed on, so the decay is fitted as a driven relaxation
  `f_ss + (f₀−f_ss)e^(−γt)`. The free-decay formula `γ = −(df/dt)/f` reads `γ − A/f` when
  a drive is present and returns ~11.1 min. Curve fit and model-independent regression
  agree to 0.1% (10.54 / 10.55 min). **Damping is 6.4× worse than with the tilt stage**,
  giving a thermal floor 2.53× higher and a requirement of ~1.86 µW/√Hz in that
  configuration.
- **Harmonic caution for all YAW work.** The dominant YAW line is the sail's **second**
  harmonic — two wings pass the sensor per revolution — so the Hilbert locks to 2× the
  rotation rate. Confirmed against the known electrode drive: the 3.898 Hz line equals
  the 3.9000 Hz drive to 0.05%, and 7.797 Hz is 2×. γ is immune (all harmonics decay at
  the same rate) but every *rate* must be divided by 2. Getting this wrong pushed the two
  γ methods 3% apart and doubled the fit residual; fixing it brought them to 0.1%.
- Still worth a deliberate **laser-off** spindown once the new stage is in, so the simple
  free-decay model applies and no drive term has to be fitted alongside γ.
- Note on timing: this happened the same day the 3 mW DARK record began (20:51 UTC), so
  that record may straddle it. It does not matter for the dataset itself — that run
  measures *laser* noise, with no rotor involved. It matters only for which γ the
  requirement is computed against.
- **A replacement tilt stage is on order**, to be installed and aligned to best tilt.
  The no-tilt period is therefore a temporary excursion, not the end state. τ after
  realignment will need re-measuring — it will not necessarily return to exactly
  67.65 min, since that value belongs to the *old* stage at its own alignment.

### Before 2026-08-03 — power meter moved onto a pickoff (Thorlabs PBS251)

The Ophir head no longer samples the full beam. It sits on the **rejected port of a
PBS251 polarizing beamsplitter cube** ("not in the main direction"), reading roughly
5–10% of the beam (~540 µW against a PD implying ~5–7 mW at the chamber). Ratio
inferred, **not measured**.

- ⚠️ **This pickoff amplifies polarization noise.** The sampled fraction is sin²θ, so
  its fractional sensitivity to a polarization drift is `sin(2θ)/sin²θ` ≈ 6 per radian
  at θ ≈ 18°, versus `sin(2θ)/cos²θ` ≈ 0.67 per radian for the transmitted beam the
  rotor sees — roughly **9× amplified**. A 1 mrad polarization wobble reads as 0.6% on
  the meter but only 0.07% on the beam. Any polarization drift (thermal, fiber stress)
  therefore appears on this channel as power noise that the rotor never experiences.
- **Consequence:** for `260803-12_*.txt` the meter is **not** a clean independent power
  witness. Its excess over the PD should be assumed to be polarization until shown
  otherwise. This defeats the PD↔meter cross-check that worked on the earlier logs.
- **Invalidates:** absolute mW from those logs, until the pickoff ratio is measured.
- **Recommended fix:** replace with a non-polarizing pickoff — an uncoated **wedged**
  window (~4% Fresnel), largely polarization-blind near normal incidence, and wedged so
  the two surface reflections cannot form an etalon.
- Earlier logs (`260728_laser_power.txt`, `260731_laser_power_10mW.txt`) predate this and
  do read chamber power directly, head-on.

### Not done — ND filter tilt

Recommended 2026-07-20 to break the air-gap etalon around the reflective ND in the PD
filter stack (notch → reflective ND → PD), which produces a ±12 count wiggle and makes
the PD non-monotonic vs true power in the 1500–1800 commanded-count range.

**Never done.** The etalon is still present in all data to date. Note that the PD and
the head-on meter nonetheless agreed to 0.2% at 0.3–1 mHz on the 07-28 run, so the
etalon is not dominating at those frequencies — but it remains a candidate for
anomalies at the count levels above.

### 2026-08-21 — first stator drive that measurably moved the rotor

First runs of `lab_utils/stator_epics_drive.py` (EPICS-only, offsets on the electrode
filter modules). Two DC detent runs, `--cycles 1 --dwell 180`, laser OFF, no shim
(gap 0.37 mm), rotor already librating from earlier activity. Video via
`grab_basler.py --record --fps 10`, analysed with `camera_utils/analyze_detent_video.py`.

| electrode | 6400 counts | 3200 counts |
|---|---|---|
| pre-drive | rms 22.5 | rms 19.9 |
| **A (V2)** | **rms 8.6 — captured, 2.6x quieter** | rms 19.8 — no effect |
| B (V3) | rms 24.0 | rms 21.2 |
| C (V4) | rms 23.0 | rms 23.7 |
| post-drive | rms 21.1 | rms 23.8 |

**The result: at 6400 counts, energising V2 collapsed the rotor's motion 2.6x and held
it quiet for the full 180 s. That is a detent capturing a moving rotor — a static
torque the four side posts could not produce at any drive level.** At 3200 counts the
same electrode did nothing.

**Only V2 is demonstrated; V3 and V4 are untested, not shown broken.** The rms returning
to ~24 when the detent moved to V3 is *not* evidence V3 did anything — switching from V2
to V3 releases V2's detent and applies V3 in the same instant, and a return to the
pre-drive amplitude (22.5) is fully explained by release alone. More generally an
A→B→C walk cannot compare electrodes: capture depends on where the rotor is and how fast
it is moving when the field switches on, so the first electrode meets a settled rotor and
the rest meet one the earlier steps just stirred up. Use `detent --phase` (added
2026-08-21) to give each electrode the same test.

**So the capture threshold for the rotor's libration energy that day lies between 3200
and 6400 counts.** Since tau ~ V^2 that is a factual bracket on the drive torque, and
the first quantitative statement this apparatus has made about the stator. It does not
yet give tau in N*m, because `VOLTS_PER_COUNT` is still unmeasured.

**What did NOT work.** Extracting a libration frequency to get tau from
`tau = (2 pi f)^2 I / m`. PC1 explains only ~30% of the masked variance and the peak
frequencies scatter (0.25, 0.38, 0.77, 1.2, 1.3 Hz) with no consistent scaling between
the two drive levels — the motion is multi-mode, not one clean oscillator. Treat the
capture bracket as the result and the frequencies as not yet interpretable.

**Two analysis traps, both hit for real before being caught** (guards now built into
`analyze_detent_video.py`, which prints both on every run):

1. Selecting the highest-variance pixels finds steep spoke edges, where the ~0.14%
   lamp ripple looks like large motion. This produced a confident and entirely wrong
   "the rotor oscillates at 0.78 Hz" from a clip in which nothing moved.
2. Coherence with frame brightness does **not** prove artefact: the rotor is a few
   percent of the frame, so real motion modulates the frame mean too. The correct
   discriminator is **localisation** — on-rotor vs off-rotor change ratio, 9.4x and
   19.0x on these two runs. Illumination lights the static mounts as well; motion does
   not.

Rotor motion persisted well after the drive was grounded, as expected with no laser
and hence no optical damping. `V{n}_TRAMP` was found at 1.0 s on all four electrodes,
which silently distorts any software-generated sinusoid; the drive script now zeroes it
for the duration of a run and restores it after.

### 2026-08-21, 16:12 — five-electrode `--phase` sweep (RESULTS PENDING)

Follow-up designed to fix the flaw in the morning runs: an A→B→C walk cannot compare
electrodes, because capture depends on where the rotor is and how fast it is moving when
the field switches on, so the first electrode meets a settled rotor and the rest meet one
the earlier steps stirred up. `detent --phase` gives each electrode the same test.

Sequence, 6400 counts, 3 attempts of 60 s with 30 s grounded between, 4:00 per electrode:

| electrode | start | role |
|---|---|---|
| V2 | 16:12:01 | control — the one that captured in the morning |
| V3 | 16:16:02 | first fair trial |
| V4 | 16:20:02 | first fair trial |
| V1 | 16:24 | **centre-disk test** — symmetric, so must show NO capture from any rotor state |
| V2 | 16:28 | control again — brackets the session against drift in rotor energy |

Laser off, no shim, gap 0.37 mm. Camera recording started 16:10:37 (so video t=0 is
16:10:37; the drive begins at t≈84 s), one continuous clip at 10 fps.

Artifacts, both on Dropbox at `Microspheres/TFINER/videos/`:
`output_basler_gps*.avi` (the sweep) and `phase_sweep.log` (the exact electrode start
times, which is what the analyser reads so no window boundary is guessed).

To score it:

```
python camera_utils/analyze_detent_video.py <video> \
       --sweep-log phase_sweep.log --dwell 60 --release 30 --attempts 3
```

Reports rms(ON)/rms(OFF) per electrode. Below 0.6 = capture, above 0.85 = nothing.
**Read the two V2 control blocks first:** if they disagree with each other, the rotor's
energy drifted across the 20 minutes and the electrodes in between are not comparable.

`V{n}_TRAMP` was again found at 1.0 s on all four at the start of the sweep — it resets
between runs, so anything writing offsets to these channels must zero it first or it is
fighting a 1-second ramp.

---

### 2026-08-22 — rotor librates ~20 h with drive AND laser off: floating/domed board suspected

Left the rotor after the 08-21 stator tests; it was still librating the next morning with,
as far as the records show, **no drive of any kind**:
- **Electrodes off.** Last real drive was the 16:33 08-21 sweep. `V{1-4}_OUT_DQ` is flat 0
  across the ~23:09 amp power-off window (±20 min) — no command or transient there. (The GUI
  power-off is an HV-amp state, not in `_OUT_DQ`.)
- **Laser off.** `RDS-PD_IN1_DQ` sat at the dark level (−1 ct, median=min=max) for the whole
  17 h overnight; commanded laser offset 0. So the optical libration spring is NOT involved.

LES is unaligned (to be fixed ~Mon 08-24), so the camera is the only readout. Two clips
scored with `analyze_detent_video.py` — both pass the localisation guard (ratio 30.6× and
16.3×; frame-flicker ~0.1%), so this is real motion, not the lamp-ripple trap:

| clip | time | motion rms | dominant f | PC1 |
|------|------|-----------:|-----------:|----:|
| `output_basler_gps1471403607` | 23:13 Fri | ~25.3 | 0.37 Hz | 38% |
| `output_basler_gps1471438107` | 08:48 Sat | ~25.9 | 0.61 Hz | 79% |

Over 9.6 h the amplitude did **not** decay — it slightly ROSE (25.14→25.41 within the first
clip; 25.3→25.9 between clips). Free decay can only shrink amplitude, so the growth argues
for a weak *sustaining drive*, not merely a high-Q ringdown. Either way a lower bound:
**libration τ ≳ 90 h** (≳100× the 67-min spin ringdown). The 0.37→0.61 Hz shift with PC1
38→79% is energy consolidating into one librational mode.

Initial hypothesis was board doming (GND ring lifted); the actual cause turned out simpler —
see CONFIRMED below. Board facts that hold either way: **board-on-metal does NOT ground the
sector electrodes** (separate insulated nets — coverlay, no ground copper under the active
area by design; only the bare GND ring grounds, by pressing on the magnet), and **"amp on,
offsets 0" grounds the sectors only if the amp output is low-Z at 0 V.**

**CONFIRMED (2026-08-23): the amp WAS the variable — floating sector electrodes pumped it.**
Turning the amp back on with all offsets 0 (16:59 UTC 08-22) holds A/B/C at 0 V low-Z,
grounding the sectors *through the amp* (independent of the GND ring). The libration then
decayed: 25.9 → 14.2 in ~95 min (amplitude τ ≈ 2.6 h), and by 08:49 UTC 08-23 (~16 h
grounded) the rotor was at **rest**.
- The overnight persistence was the amp being **powered OFF**, which floats the sectors (amp
  output high-Z); a floating charge-carrying sector beside the charged rotor pumps the
  libration. (The earlier belief that it "librated in the amp-on config too" was wrong — that
  period was amp-off/floating.)
- **OPERATIONAL FIX (procedural, no chamber opening): keep the amp ON with A/B/C held at 0 V
  whenever idle. Do NOT power the amp off with the board installed — it floats the sectors
  and drives the rotor.** This also confirms the amp is low-Z at 0 V.
- Because grounding worked *through the amp*, the **GND-ring/doming question is now a SEPARATE
  open item** (board ground plane / CTR / field shielding), still worth the continuity check
  at the opening, but NOT the cause of this libration.
- Continuous decay-to-rest recorded in `stator_detent/output_basler_gps1471453183_grounded_decay.mp4`
  (H.264 slim of the 5.58 h clip that started at grounding).

Tests at the next chamber opening (some already on the first-article list):
- **GND-ring-to-magnet continuity/resistance** — open/high ⇒ doming (now decoupled from the
  libration, but still worth confirming the board's ground plane / CTR).
- Board flatness / does the centre sit proud when mounted.
- (HV-amp-at-0 V impedance — ANSWERED 08-23: low-Z; grounding via amp-on-0 V damped the rotor.)
- Interim mitigation *without* opening, if available: **neutralise the rotor charge**
  (protocol step 1) — the stray coupling needs rotor charge.
- Opening safety: amp OFF → verify 0 V → discharge electrodes/board to ground before
  handling (barrels live to ~80 V when driven); ground yourself for ESD on the de-energised
  board.

---

### 2026-08-24 — electrode map CONFIRMED at the chamber opening

Continuity check at the terminals during the vent-to-atmosphere. **V1 is the centre
electrode**, conclusive. This closes a question open since 08-21 that three scripts
disagreed about.

**Measured**, all four terminals, clockwise viewed from above (the face the pads are on):
**V1, V3, V4, V2**.

**The board's convention, from `generate_flex_revG.py` — not the spec prose, which never
states a sign:** `pol()` returns `(cos, sin)`, so azimuth is **CCW-positive**;
`SEC_CTR = [7.5 + 15k]` with `NET = PHASE[k % 3]` puts sectors A,B,C,A,B,C… at
**increasing** azimuth; and `PAD_AZ = {A 15, B 105, C 195, CTR 285}` agrees. So
**A→B→C advances counterclockwise**, and going *clockwise* the four terminals are, by net,
CTR, C, B, A.

Lining that up: **V1 = CTR, V3 = C, V4 = B, V2 = A**, i.e. **(A,B,C) = (V2, V4, V3)**.

**This is a transposition of (2,3,4), not a cyclic rotation** — B and C are swapped.
`PHASE_ELECTRODES` has been corrected to **(2, 4, 3)**. The old value would still have
produced a clean travelling wave (a transposition is exactly what flex_spec.md means by
*"Reverse by swapping any two phases"*), so the drive would have *worked* — but it would
have run **backwards** relative to the board's A→B→C sense and mislabelled every phase,
commanding "B" while energising net C. That is the sign error that bites when the video
loop closes, not something that shows up as a failure to spin.

**The cables were still left alone** — the fix is one tuple. Recabling would have retired
a measured mapping for an assumed one, on a board whose flatness is still open.

Consequences recorded in code:
- `stator_epics_drive.py` — map marked CONFIRMED; `CTR_ELECTRODE = 1` was already correct.
- `stator_drive.py` — map CORRECTED. It had CTR = V4 with phases on V1/V2/V3, i.e. it
  would have driven the centre electrode as a phase. Still not runnable (placeholder
  SINGAIN/COSGAIN PVs), now flagged as such in the file.

**Rotation direction, as derived above:** with `(2,4,3)`, A→B→C advances
**counterclockwise seen from the rotor side**. This is now derived rather than unknown —
the generator pins the azimuth sign that flex_spec.md left open. One empirical check is
still worth doing, because the chain rests on "clockwise" having been read off the board
viewed from above. **Cross-check CONFIRMED 2026-08-24: counterclockwise the terminals read
V1, V2, V4, V3**, as the derivation requires — so the viewing-side assumption holds and the
map is settled in both directions. Remaining: drive slowly at low counts and confirm the
rotor turns CCW as seen from the camera, which validates the derivation end-to-end
against the hardware.

**The CTR feed arm.** flex_spec.md: *"CTR electrode | disk r = 0.58; 0.08 trace out
through the sector boundary at az 285°, widening to 0.25 beyond r = 2.50"*. So V1 is a
disk **plus an in-plane radial arm**, and the arm is the only part of V1 with angular
authority. Sizing it against the active annulus (r = 0.69 → 1.95, area 10.45 mm², 24
sectors ⇒ 0.436 mm²/sector, 3.48 mm²/phase), the arm contributes 1.26 × 0.08 =
**0.101 mm², ≈ 2.9% of one phase**. Two consequences:
- The 08-21 16:24 V1 block was designed as a null test (*"symmetric, so must show NO
  capture"*). That is now a **magnitude** argument, not a symmetry guarantee — 3% of a
  phase against a capture threshold that needed 3200–6400 counts on a full phase. If V1
  shows *weak* capture when the sweep is scored, read it as the arm, not as a mis-mapping.
- A floating V1 reaches the rim, so it is a better stray-coupling antenna than a small
  central disk. Include V1 in the amp-on/grounded idle rule, not just A/B/C.

**Geometry correction worth stating once:** the board is **not** three sectors at 120°.
It is **24 sectors on a 15° pitch, interleaved 3-phase, 8 sectors per phase, synthesising
a rotating m = 8 potential** (flex_spec.md), which is where `rotor speed = f_elec / 8`
comes from. 15° × m=8 = exactly 120° electrical per sector, so ABCABC… around the ring is
a uniform travelling wave by construction. Reasoning from the three-sector picture gives
wrong torque and wrong direction arguments.

---

### 2026-08-24, ~16:45 EDT — first live 3-phase drive; ELECTRICALLY VERIFIED, rotor slipped

First `--live` run of `stator_epics_drive.py` after the pump-down, with the corrected
`PHASE_ELECTRODES = (2,4,3)`. `--amp 4800 hold -f 0.02`, ~158 s (ended by `stop`).
Amp on at 0 V beforehand, so the sectors had only been grounded a short time and the
rotor still carried libration energy.

**The electrical drive is exactly right.** From `V{n}_OUT_DQ` (1024 Hz, NDS), burst at
DAQ GPS 1471647404 → 1471647563, 142.5 s of steady-state analysed after trimming the
ramps:

| chan | net | az | f (Hz) | amplitude | phase |
|---|---|---|---|---|---|
| V2 | A | 15° | 0.1614 | 1.692e8 | +61.7° |
| V4 | B | 105° | 0.1614 | 1.693e8 | −58.3° |
| V3 | C | 195° | 0.1614 | 1.693e8 | −178.3° |

Relative phases **−120.0° and −120.0°**, amplitudes equal to 4 significant figures,
f_elec 0.1614 Hz vs 0.160 commanded (f_mech 0.02017, 50 s/rev), swing [−9, 9609] counts
on a 4800 DC pedestal exactly as commanded, and **V1 (CTR) flat at 0.0 throughout**.
There is nothing wrong with the waveform: phase, amplitude balance, frequency and the
centre electrode all check out.

**This also settles field direction electrically, without the camera.** Phase *decreases*
by 120° as azimuth *increases*, i.e. φ = −8θ, giving sin(ωt − 8θ) — constant-phase fronts
at θ = ωt/8, so **the field rotates counterclockwise in board coordinates**, as derived.
The `/8` falling straight out of the measured numbers independently confirms m = 8.

**The rotor did not hold lock.** Observed on camera: it tends clockwise, then unlocks and
swings back. Since the drive is verified correct and CCW, an apparent CW rotor is *not* a
wiring or phasing fault — it is either slip (the rotor was never captured, so its motion
is libration plus intermittent drag, which has no reliable sense) or a camera-handedness
question. **Do not "fix" the electrode map or the phase order on the basis of this
observation.** Both are measured and both are confirmed.

Next, in order: drop the frequency hard (`-f 0.005`, 200 s/rev) to get well inside capture
before adding torque; then `--amp 6400`; and give the libration longer to damp
(τ ≈ 2.6 h, and the amp had only just gone on). If it locks at 0.005 and slips at 0.02
that brackets the true capture bandwidth, which is a number we do not have — the 0.045 Hz
figure is an estimate assuming a full 80 V at 0.37 mm, and the screws were just retightened
so the gap may have moved. Also worth noting a scope trace of this drive looks unusual for
a benign reason: it is **unipolar**, a 0.16 Hz sine on a DC pedestal, not a bipolar swing.

Raw data: `Y1:RDS-OUTS_V{1,2,3,4}_OUT_DQ`, 6 h window (DAQ GPS 1471626014 → 1471647614),
uploaded to `Microspheres/TFINER/data/Electrodes/`.

**End-of-session state:** electrodes all 0, amp ON at 0 V (sectors grounded — do not power
it off), TRAMP restored to 1.0 s on all four, DRVON 0, SW1R 12 / SW2R 1792.

---

## Vacuum

Pressure ~**2.9e-7 mbar**, consistent across this period. No logger yet
(`lab_utils/log_pressure.py` written, gauge not recording).

Because pressure was steady, it is **not** the explanation for the elevated damping from
07-27 onward — that is the tilt-stage removal.

---

## Dataset → apparatus state

| dataset | window (UTC) | tilt stage | PD | meter |
|---|---|---|---|---|
| laser step-down | 07-05 → 07-09 | **yes** | misaligned + LN amp | none |
| 3 mW dark / ON | 07-27 → 07-29 | removed same day | good | at chamber, head-on |
| 10 mW noise run | 07-31 → 08-02 | no | good | at chamber, head-on |
| spindown (electrode drive-off) | 08-03 → 08-04 | no | good | PBS251 pickoff |
| stability run (1600 cts) | 08-04 → 08-05 | no | good | PBS251 pickoff |

τ_free = 67.65 min applies **only to the first row**.

---

## Known-stale constants

| constant | value | valid for | note |
|---|---|---|---|
| commanded→power | 11.87 µW/count above 735 | **still good** | verified to 3.6% by direct measurement 08-03 |
| PD counts/mW | 283 | 07-28 → 07-31 only | **203 on 08-03** (−28%); use measured chamber power |
| `TAU_FREE_S` | 67.65 min | ≤ 07-27 only | tilt stage present |
| `REQ_UW` | 0.735 µW/√Hz | ≤ 07-27 only | derived from the above; **1.86 µW/√Hz** post-tilt |
| `I_KGM2` | 1.88e-11 | assumed | from `momentum-simulation/thermal_noise_spindown.py`, never measured |
| `KAPPA_PD_OLD` | 7.35e-16 N·m/count | step-down gain only | do not reuse post-amp-removal |

### Decision: which γ goes in which notebook

The two uses of γ are different questions and take different values.

- **`laser_dark_vs_on.ipynb` keeps τ = 67.65 min** (tilt stage present). Its measurements
  are laser properties, unaffected by the chamber; the requirement line is a *design
  target* for the configuration the experiment is meant to run in. With a replacement
  tilt stage on order, that is the tilt-present state — so the 0.735 µW/√Hz line stands,
  and the 89× / 361× margins quoted against it are the honest ones. Re-drawing it ~2×
  looser to match a temporary no-tilt excursion would flatter the result.
- **`spindown_20260803` / `rotor_stability_20260804` need the measured post-tilt γ**,
  because they describe how the rotor actually behaved, not what it should achieve.

Revisit both once the new stage is installed and τ re-measured.

---

## PD scale shift — the PD, not the commanded calibration

On the 2026-08-03 run the laser was commanded to **1400 counts** and the chamber power
was **measured at 7.62 mW**. The 2026-07-20 commanded-count calibration
(11.87 µW/count above a 735-count threshold) predicts 7.89 mW — **agreement to 3.6%**,
inside its own repeatability. **That calibration is sound.**

What moved is the PD. It read 1550 counts for that 7.62 mW, i.e. **203 counts/mW**,
against **280.6** (07-28) and **284.6** (07-31) measured head-on against the Ophir. The
PD has lost **~28% of its response relative to chamber power**, between 07-31 and 08-03
— which is when the PBS pickoff was installed.

- **Use measured chamber power** for post-08-03 datasets, not the 283 counts/mW scale.
- The PD remains fine as a *relative* monitor (its 1.4% linearity was measured across
  3–10 mW); it is the absolute scale that has shifted.
- Worth finding out *why* — a 28% change in the PD's share of the beam suggests its tap
  was disturbed when the PBS went in.

### Consequence: the laser torque has dropped too

The 08-03 fit gives a drive torque of 2.03e-14 N·m at 7.62 mW, i.e. **2.66e-15 N·m/mW**
against the July calibration of **1.19e-14 N·m/mW** — **4.5× lower** (4.5–5.4× across the
f_ss method spread).

Combined with damping 6.4× worse, the sustainable rotation rate
`f_ss = κP/(2πIγ)` is **~29× lower than in July**. That is why the laser could not hold
the rotor at a power that would have worked before the tilt stage came out, and it is a
torque-coupling change as well as a damping change — worth separating once the new stage
is in.

---

## Open items

- [ ] Clean post-tilt γ measurement — driven-relaxation fit to the 08-03 decay, or a
      deliberate spindown. Needed by the spindown and stability notebooks.
- [ ] Install the replacement tilt stage, align to best tilt, and **re-measure τ** with a
      deliberate free spindown (laser off, so the free-decay formula applies). This
      becomes the new design-target γ for the requirement.
- [ ] Measure the pickoff ratio (meter at chamber vs meter at pickoff, one reading).
- [ ] Replace the PBS251 pickoff with a wedged uncoated window, or characterise the
      polarization drift so the amplification can be corrected for.
- [ ] Tilt the ND filter to break the air-gap etalon.
- [ ] Commanded laser counts before and after the 08-03 step (PD went 2359 → 1545).
- [ ] Get the pressure gauge logging.
- [ ] Find out why the PD lost ~28% of its response relative to chamber power when the
      PBS pickoff was installed — was its tap disturbed? Re-anchor counts/mW against the
      Ophir head-on.
- [ ] Separate the 4.5× torque-per-mW drop into beam-geometry vs sail-alignment causes
      once the new tilt stage is in.
- [ ] Measure `I` directly rather than inheriting it — the electrode drive gives it from
      the high-frequency asymptote of χ(f).
- [ ] Measure `VOLTS_PER_COUNT` (`stator_epics_drive.py calibrate` + a meter on the
      amplifier output). Until then the 3200–6400 count capture bracket cannot be turned
      into a torque in N·m. The old placeholder 0.03125 is provably wrong — it implies
      200 V at 6400 counts on an amplifier that stops at ~80 V.
- [ ] Narrow the capture bracket: detent runs at 4000 / 4800 / 5600 counts against a
      comparable starting libration amplitude. Note the threshold depends on the rotor's
      energy at the time, so record the pre-drive rms for each.
- [x] Settle which `V{n}` is the centre electrode by continuity check at the next chamber
      opening. **DONE 2026-08-24 — V1 IS the centre electrode, conclusive.** Clockwise the
      sector phases read V3, V4, V2, which is a *cyclic rotation* of (2,3,4), so
      `stator_epics_drive.py`'s `PHASE_ELECTRODES = (2,3,4)` was already correct and no
      recabling was needed. See the 08-24 entry. Rotation **direction** is still open.
- [ ] Swap the ½" electrode stands for 4-40 vented screws and fit a ≤Ø5.8 mm, 0.1 mm
      shim. The stands are a live confound (tall conductors at r ≈ 9 mm) and the shim is
      worth 3.2× torque, which at the ~80 V ceiling is no longer optional.
