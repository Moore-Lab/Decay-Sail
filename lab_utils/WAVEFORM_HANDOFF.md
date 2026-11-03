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
   - With the clock found in W0, for each waveform in the order `pulse`, `sine`, `step`, `spinup`, `chirp`:
     - dry run: `python3 awg_waveform_drive.py --wave pulse --amp 5000 --pedestal 6400`
     - then: `python3 awg_waveform_drive.py --wave pulse --amp 5000 --pedestal 6400 --live`
     - then: `python3 waveform_check.py ~/waveform_runs/pulse_<time>`
   - Amp 5000 on 6400 is F2's level. The outputs are off, so nothing reaches the chamber, and the `step` ringing can be compared with F2.
   - If `OUT_DQ` is flat, run `python3 awg_reclaim.py` as its own process and try again.
   - rclone `~/waveform_runs/` to Dropbox `Microspheres/TFINER/data/feedback/waveform/`.
4. **W2, outputs on, after W1 passes.** Molly approves each.
   - **Scope:** set the timebase so the screen holds the waveform plus a few seconds. Run, then press Run/Stop once the script prints "waveform done".
   - **Command:** `python3 awg_waveform_drive.py --wave pulse --amp 500 --pedestal 1000 --outputs-on --live`
   - **Read the scope:** `python3 scope_rtb.py read ~/waveform_runs/pulse_<time> --label w2`
   - **First check:** in `pulse`, the pulses come V2 alone, V3 alone, V4 alone, then all three. That confirms the scope channel map.
