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
- **`bsine`:** not run (Molly skipped it; the chirp covers 2 Hz).
- **Before W2 (proposed):** a 0.5 s amplitude phase-in on `bchirp`, and built-in stops with a 0.5 s gain ramp, so there are no full-amplitude steps at the electrodes.

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
