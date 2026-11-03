# Problem 1: arbitrary waveforms on the three electrodes at ~10 Hz bandwidth (branch `waveform-test`)

**Why:** the PI suggested (Molly, 2026-11-03) splitting the feedback drive in two. Problem 1: can we put any
signal (sine, chirp, pulse, arbitrary) on A, B, C up to ~10 Hz, and verify it on the scope? Problem 2,
closing the loop with the camera, comes after. The y1rds model change is paused until Problem 1 passes
(Molly, 2026-11-03). 10 Hz ≈ 8 × F2's top rotor speed of 1.17 rev/s (derived).

**Route:** the front-end AWG plays sample arrays into `V{n}_EXC` at 2048 Hz. EPICS writes can't carry
10 Hz: they land only at 16 Hz (F1b, `FEEDBACK_HANDOFF.md` on `feedback-drive`).

## Current state (2026-11-03)

- **Scope:** RTB2004 on worker2 USB, as `/dev/usbtmc1`.
  - Mode is USB TMC (changed from MTP on the scope).
  - The udev rule `/etc/udev/rules.d/99-rs-scope.rules` (Molly, sudo) gives group plugdev rw.
  - `*IDN?` answered: `Rohde&Schwarz,RTB2004,1333.1005k04/102215,01.210`.
- **Channel map:** CH1 = LES YAW, CH2 = V2, CH3 = V3, CH4 = V4. 10× probes on the amplifier outputs.
- **Scope LAN:** says "no cable"; not resolved. USB is used instead.
- **Written, Mac-tested only:**
  - `waveforms.py`: the waveform set. Run `list` for names and lengths.
  - `awg_waveform_drive.py`: the player. Tested dry against a mock EPICS, including the refusals for outputs on in W1 and for an input range outside 0..12800.
  - `waveform_check.py`: the W1 scorer. `selftest` passes: it recovers lags to 0.05 ms, catches a 2.5 ms channel offset and a 5% gain error, and separates post-jump ringing.
  - `scope_rtb.py`: scope reads.
- **awg API (read from worker2's python-awg 4.2.3, 2026-11-03; dump on Dropbox `data/feedback/waveform/awg_api.txt`):**
  - `ArbitraryLoop(chan, data, scale, rate, start)` streams the array through libSIStr in 1 s chunks and loops it until `stop()`.
  - `start` is an integer GPS second.
  - The player pads each waveform with 12 s of zeros and stops inside them, uses `ramptime=0` and arms with `wait=False`.
- **Not yet checked: which clock the stream's start time needs.**
  - The old Excitation route needed the front-end clock (`Y1:DAQ-DC0_GPS`, hours ahead of true GPS on 2026-08-28).
  - libSIStr paces on worker2's own clock. So with a large offset, one of the two frames may silently not play.
  - W0 below settles it. The player prints the offset every run.
- **Not yet checked: the RTB SCPI spellings.** The first query attempt timed out on every bulk write after the `*IDN?` that worked. A scope power-cycle is pending.
- **Not written yet:** the W2 scorer (scope ÷ command: gain, delay and the chirp's amplitude/phase vs frequency, including the AC coupling).

## W0 result (2026-11-03, worker2 agent, outputs off; data Dropbox `data/feedback/waveform/w0_pulse_1793738075/`)

Measured:
- **Clocks:** the front-end clock (`Y1:DAQ-DC0_GPS`) minus worker2's clock was **+15496.6 s**. For comparison, it was +8376 s on 2026-08-28.
- **Playback:** with the start time in the front-end frame, the stream started on time, but **only the first 3.0 s played**.
  - V2's pulse at 1 s and V3's at 2 s came through whole.
  - V4's pulse straddles 3.0 s, so it was cut at 3.0 s.
  - Every later pulse is missing.
- **Timing of what played:** `waveform_check.py` lag for V2 and V3 is 1.05 ms, with the two within 0.01 ms of each other. The gains it reports (0.25) only reflect the missing pulses.
- **The cut V4 pulse:** after the abrupt drop at 3.0 s, `OUT_DQ` undershot the pedestal by ~900 counts (5499) on a drop of ~5000 counts. A sharp drop rings in the recording, as in F1/F2.
- **The stop hung:** "awgsendwaveform RPC error = 5" ×3, then killed by worker2's 300 s timeout. The pedestal was left at 6400 with outputs off, then cleaned up (Molly OK). `awg_reclaim.py` found 4 distinct leaked slots.

(Interpretation, not approved.) libSIStr sends its 1 s chunks paced by worker2's clock. A start time 4.3 h ahead in that clock lets the first buffered chunks out and then holds the rest. With `--clock local`, the front end would probably see the data as 4.3 h late. So streaming arbitrary waveforms needs the front-end clock fixed, or a route that doesn't stream.

Fix made after W0 (8ca0199): each stream's stop has a 10 s limit, and the pedestal drops only after EXCMON reads 0 for 3 s (tested on the Mac with a simulated hang and with live AC).

## W2 grounded `bburst_1793746069` (22:47Z; all three grounded after the DAQ output since ~22:36Z)

The scope was triggered by the pedestal step, after the pre-trigger wait. Full 120 s record, no spikes. `scope_check.py`: **PASS.** Measured, with today's earlier runs for comparison:

| | burst gain, V/count | earlier runs | τ, s (whole-record residual) | earlier runs |
|---|---|---|---|---|
| V2 (was floated) | 0.01243 | 0.01241 | 5.69 (1.8%) | 5.69 (2.2%) |
| V3 (was floated) | 0.01268 | 0.01250 | 5.56 (1.7%) | 4.83 (6.6%), poor fit |
| V4 (grounded throughout, apart from the ~22:05–22:20 float) | 0.01275 | 0.01276 | 5.43 (1.9%) | 5.57 (2.1%) |

- **Joint burst:** V3 and V4 within +0.00 and −0.01 ms of V2.
- **V3 now fits the one-pole AC-coupling model like the others.** Its odd slow response appeared only while it was floated (one run each way, so not yet repeated).
- **The FE/scope clock-rate difference** came out at +1.230 ms/s again.

## Next (as of 2026-11-03 evening)

- **Problem 1, status:**
  - The front-end side passes: built-in sine, chirp and bursts are exact on V2–V4 and aligned to well under 1 ms (W1).
  - At the electrodes (W2, amp 500 on 1000): V2 and V3 are flat 0.3–10 Hz with timing < 0.13 ms. V4 is checked only on bursts and the 2 Hz sine, before the ground change.
  - Streamed arbitrary waveforms wait for the front-end clock fix (W0; question for Alma).
- **V4 grounding:** Molly floated V4's DAQ-output ground at ~22:05Z to match the other channels. V4 then showed no signal at the scope, so she reverted it (by ~22:20Z). She'll retry with a different BNC cable on 2026-11-04, then repeat W2 `bburst` and `bchirp` and check CH4.
- **Scope capture:**
  - `--scope` arms a single acquisition (SING) and waits for COMP before reading.
  - The trigger (CH2 rising, 5 V) fires on the first crossing, which may be during the chirp. The record is still complete with the trigger at the screen centre at 10 s/div (±60 s).
  - The scope-only `scope_rtb.py diag` is written, but not run.
- **Unexplained, open:**
  - The two 14 ms ±25 V all-channel scope spikes.
  - V3's slow response doesn't fit a one-pole decay.
  - The FE clock is 0.12% fast.

## Built-in route (Molly OK 2026-11-03, after W0)

The AWG server makes these waveforms itself, so there's no streaming and no dependence on worker2's clock. The start time is in the front-end frame, as for the August sines. They're added to `awg_waveform_drive.py` as `--wave bsine|bchirp|bburst` and scored by `builtin_check.py`, whose `selftest` passes.
- **`bsine`:** three-phase 2 Hz, 10 s, with a 0.5 s amplitude phase-in.
- **`bchirp`:** three-phase log sweep from 0.1 to 12 Hz over 60 s, so 10 Hz is inside the sweep. It's scored in bands from 0.3 to 10 Hz.
- **`bburst`:** one-cycle 10 Hz bursts, V2 alone at 1 s, V3 at 2 s, V4 at 3 s, then all three at 4 s.

The scorer is model-free where the AWG's conventions are undocumented:
- **sin or cos:** `bburst` reports the shape.
- **sign of `phase`:** reported as "forward" or "reversed".
- **the log-sweep law:** the chirp is fitted against V2's own measured phase.

**Python library time units:** with python-awg 4.2.3 (worker2, 2026-11-03), `Excitation` takes `start` in GPS **seconds** and multiplies it by 1e9. `stator_awg_drive.py` passes nanoseconds, so with this library version its excitations would be scheduled absurdly far in the future (not run; derived from the source).

## W1 results (2026-11-03, worker2 agent, outputs off, Molly's go each; Dropbox `data/feedback/waveform/`)

Re-scored on the Mac from the Dropbox files; the numbers match worker2's.
- **`bburst_1793739733`: PASS.**
  - Every burst at its commanded second, amplitude 5001.4 for 5000 (+0.03%), residual 0.10%.
  - 0 counts where none was commanded.
  - At the joint burst, V2, V3 and V4 are sample-for-sample identical (0.000 ms).
  - All arrive 1.06 ms after the commanded time.
  - The AWG's periodic waveform is a **sine** (measured from the burst shape).
- **`bchirp_1793739965`: PASS.**
  - Amplitudes 99.8–100.2% at 0.3, 0.5, 1, 2, 5 and 10 Hz.
  - Lag of V3 and V4 against V2: within ±0.03 ms at 5 and 10 Hz and ±0.3 ms at 1–2 Hz. The ±0.4 ms at 0.3–0.5 Hz is the estimator's scatter at low frequency.
  - Field direction **reversed**: V4 leads V2 by 120°. The AWG's `phase` enters with the opposite sign to the 08-24 convention, as `stator_awg_drive.py` found on 2026-08-28. Negate the phases for a forward field.
- **`bchirp` range:**
  - The recording left 1400..11400 by at most ~110 counts (V3 1287, V4 11511), only at the first sample after the start.
  - The sweep starts at full amplitude, so V3 and V4 step by ~4300 counts at t = 0. That is ~2.5% overshoot in the recording after a sharp step.
  - After 60 s the sweep restarts (restart = sweeptime) until the stop at ~61 s.
- **`bsine_1793740354`: PASS.** Amplitude 5000.1 on all three, phases exactly ±120.00° (reversed), residual 0.00%, clean stop.
- **Before W2 (proposed):** a 0.5 s amplitude phase-in on `bchirp`, and built-in stops with a 0.5 s gain ramp, so there are no full-amplitude steps at the electrodes.

## W2 attempts (2026-11-03, outputs on, bburst amp 500 on pedestal 1000, Molly's go each)

- **`bburst_1793741789_w2_no_scope`:** the scope was stopped during the run, so there's no capture. OUT_DQ is exact, as in W1.
- **`bburst_1793742033`:** OUT_DQ is exact. The scope read came ~90 s after the run, so the bursts had scrolled off the 60 s screen. The floats were also parsed with the wrong byte order (the RTB sends REAL,32 MSB-first). Both are fixed in 53e1224: `--scope` reads right after the stop.
- **Unexplained event (measured, not interpreted):**
  - At 21:42:49Z (FE ≈ 1477792886, ~75 s after the run, nothing commanded), CH2–4 show a 14 ms event on all three at once: CH2 −23.5..+25.7 V, CH3 −15.0..+34.2 V, CH4 −25.0..+23.9 V. The baseline is the same before and after.
  - Over FE 1477792860–910, `OUT_DQ` V2–V4 are exactly 0, and LES YAW, PIT and SUM show no step beyond their normal sample-to-sample range.
  - worker2 made no writes then. Data: Dropbox `waveform/bburst_1793742033/event_2142/`.

## W2 result: `bburst_1793742522` (2026-11-03 21:48Z, outputs on, amp 500 on pedestal 1000, `--scope`)

Scored on the Mac with `scope_check.py` (scope vs `out_dq_long.npz`, FE 1477793220–300). Measured:
- **Bursts reach the electrodes in order and on time.** V2, V3, V4, then all three, as commanded. That confirms the scope channel map (CH2–4 = V2–V4).
- **Alignment:** at the joint burst, V3 and V4 are within −0.07 and +0.02 ms of V2. **W2 bursts: PASS** by the proposed mark (1 ms; residual ≤ 5%).
- **Gain at the electrode (per-burst fits; the AC-coupling decay is removed by a local slope):**
  - V2 0.01241, V3 0.01251, V4 0.01277 V/count.
  - That's ~13 V peak-to-peak for 1000 counts peak-to-peak.
  - The fit residual is 2.5%, the size of the scope's baseline noise.
  - For comparison, 0.0134 V/count was measured on the `_EXC` path on 2026-08-25. Different amplitude and method, so not directly comparable.
- **AC-coupling decay after the pedestal step (one-pole fit to the whole record):**
  - V2: τ = 5.69 s, residual 2.2%.
  - V4: τ = 5.57 s, residual 2.1%.
  - V3: the one-pole model fits poorly (τ 4.83 s, residual 6.6%, gain 0.0096, which disagrees with its burst gain). Not explained.
- **Clock rate:** the front-end clock runs **+1.233 ms per second fast** relative to the scope (derived from the burst delays drifting across 3 s).
  - This matches the FE−worker2 offset growing from +8376 s on 2026-08-28 to +15497 s on 2026-11-03: 7121 s over ~5.8e6 s = 0.12%.
  - So front-end "seconds" are ~0.12% short of real seconds (derived). A 10 Hz front-end signal is ~10.012 Hz in real time, and frequencies of real signals read in FE time come out ~0.12% low.
- **A second 14 ms all-channel spike,** at 21:48:32Z, 9 s before the run started. It appears on CH1 (LES) too, at −0.09..+3.3 V, so it isn't only on the electrode lines. Not explained.

## W2 `bsine_1793742986` (21:56Z, outputs on, amp 500 on pedestal 1000, `--scope`)

- **OUT_DQ:** exact (W1 PASS).
- **The scope record ended before the STOP:** it holds only t 25.3–29.8 s, ~4.5 s of the 10 s sine.
  - The record is the last *completed* 60 s acquisition, not the 60 s up to the STOP (interpretation: at 5 s/div the scope is not in roll mode).
  - Fix: trigger the scope on the pedestal step (Normal/Single, CH2 rising edge), with the trigger position near the left edge.
- **2 Hz fit on the captured 3.7 s (sine + offset + slope):**
  - Gain: V2 0.01238, V3 0.01250, V4 0.01276 V/count, the same as the `bburst` gains to 0.3%.
  - Phase vs V2: V3 −119.43°, V4 +120.15°, i.e. 0.57° and 0.15° from ±120° (0.8 and 0.2 ms at 2 Hz).
- **No spikes in this record.** The whole-record τ fit failed on the partial record (not meaningful).

## W2 `bchirp_1793743924` (22:12Z, outputs on, amp 500 on pedestal 1000; after the V4 ground change at ~22:05Z)

- **OUT_DQ:** W1 PASS on all three.
- **Scope:** the first read came too early (my wait took STOP for "complete") and is garbage; kept as `scope_1793744012_w2.npz`. The completed 120 s record was read afterwards without touching the scope: `scope_1793744239_w2_complete.npz`.
- **Response 0.3–10 Hz at the electrodes (`chirp_tf.py`, measured):**
  - V2 gain: 0.01238–0.01241 V/count at every band, 0.3, 0.5, 0.7, 1, 1.5, 2, 3, 5, 7, 10 Hz. **Flat within ±0.15%.**
  - V3 gain: 0.01256–0.01266 V/count, flat within ±0.4%. It is ~2% above V2.
  - V3 vs V2 timing: within ±0.13 ms from 1 to 10 Hz (−0.009 ms at 10 Hz). At 0.3–0.7 Hz the estimate scatters by up to ~1.7 ms.
  - Absolute phase is not reported: it depends on the arbitrary scope-clock alignment.
- **V4: no signal at the scope.** CH4 shows 0.3–0.8 V peak-to-peak noise for the whole record, a fitted gain of 0.00008 V/count, although OUT_DQ V4 is exact.
  - In `bsine` at 21:57Z, before the ground change, CH4 carried 14.3 V peak-to-peak.
  - So since the change, V4's signal doesn't reach the scope, and possibly not the electrode. To check (Molly).
- **The trigger** fired ~45 s into the chirp, not at the pedestal step (CH2 crosses 5 V repeatedly). The record still covers the whole run because the trigger sat at the screen centre.

## Gates (pass marks agreed with Molly 2026-11-03; numbers proposed by Claude)

| gate | where | what | pass |
|---|---|---|---|
| W1 | worker2, **outputs off** | each waveform via the AWG; `OUT_DQ` vs the samples sent | `waveform_check.py`: gain within 1%, residual rms ≤ 1% of amp (for `step`, away from the jumps), every electrode within 1 ms of V2 |
| W2 | worker2, **outputs on, low amplitude, electrodes connected** | same waveforms; scope CH2–4 vs command | scope trace = command × gain through the amplifier's measured response; chirp gives the response 0.1–10 Hz; three channels within 1 ms (scorer to be written) |

W1's `step` run also answers the open F2 question. If `OUT_DQ` rings after a clean 2048 Hz step with
outputs off, the out-of-range transients are in the recording. W2's scope shows the real output.

**W2 amplitude (derived, Molly to confirm):** amp 500 on pedestal 1000.
- F2's linear coupling, 1.52 rad/s² at amp 5000, scales to ~0.15 rad/s². That is ~3% of the trap's 4.94 rad/s² peak.
- The chirp passes the 0.35 Hz swing resonance. That could leave a swing of order 10° (rough estimate) that rings down slowly (Q ~ 10⁴).

## Runbook (worker2)

0. Get the branch: `cd ~/rds-code/Decay-Sail && git fetch && git worktree add ~/wt_wave waveform-test`,
   then `cd ~/wt_wave/lab_utils`. Use the env that imports `awg`, `nds2` and `epics`, as for `stator_awg_drive.py`.
1. Checks, no hardware:
   - `python3 waveforms.py list`
   - `python3 waveform_check.py selftest`, which takes ~40 s
   - `python3 scope_rtb.py settings`: every line should have a value, and `errors` should be empty
2. **W0, outputs off: which clock.** Run `pulse` once at F2's level with the default `--clock fe`. The player prints the clock offset.
   - **If `OUT_DQ` shows the pulses,** the front-end frame works.
   - **If it's flat, or the stream seems to hang** (Ctrl-C runs the stop sequence), repeat with `--clock local`.
   - Record which one worked here.
3. **W1, outputs off.** Molly approves each `--live`.
   - Start state: `stator_osc_drive.py status` should show DRVON 0, gains 0, outputs off, offsets 0.
   - Built-ins first, in the order `bburst`, `bsine`, `bchirp`, scored with `builtin_check.py`. The streamed waveforms (`pulse`, `sine`, `step`, `spinup`, `chirp`) wait for the clock fix. For each:
     - dry run: `python3 awg_waveform_drive.py --wave bburst --amp 5000 --pedestal 6400`
     - then the same with `--live`
     - then: `python3 builtin_check.py ~/waveform_runs/bburst_<time>`
   - Amp 5000 on 6400 is F2's level. The outputs are off, so nothing reaches the chamber, and the `step` ringing can be compared with F2.
   - If `OUT_DQ` is flat, run `python3 awg_reclaim.py` as its own process and try again.
   - rclone `~/waveform_runs/` to Dropbox `Microspheres/TFINER/data/feedback/waveform/`.
4. **W2, outputs on, after W1 passes.** Molly approves each.
   - **Scope:** set the timebase so the screen holds the waveform plus a few seconds. Run, then press Run/Stop once the script prints "waveform done".
   - **Command:** `python3 awg_waveform_drive.py --wave pulse --amp 500 --pedestal 1000 --outputs-on --live`
   - **Read the scope:** `python3 scope_rtb.py read ~/waveform_runs/pulse_<time> --label w2`
   - **First check:** in `pulse`, the pulses come V2 alone, V3 alone, V4 alone, then all three. That confirms the scope channel map.
