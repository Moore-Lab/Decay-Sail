# Voltage steps, 2026-11-10: clean 8/s field test, outputs off

Interpretations are Claude's and marked "(interpretation, not approved)". Everything else is measured or derived as labelled.

- **Question (Molly):** is 8 updates/s a real operating rate for feedback, i.e. does every update of all three electrodes land?
- **Plan and code:** `lab_utils/VOLTAGE_STEPS_HANDOFF.md` ("Next", step 5); branch `voltage-steps` at 96519e1,
  `voltage_steps.py run --preset field8`, scored with `voltage_steps_score.py` at the same commit.
- **Run:** worker2, outputs **off**, level 3200 counts. FE GPS 1478386135–1478386519 (host 1794334692.36–1794335072.00).
  All 2285 writes read back correctly; every channel connected; TRAMP found 1.0 at block 0, then 0.0 (as in S0).
- **Blocks:** dithered all3 at 2/s and 4/s (30 s each) before and after, used only to fit host → FE time; between them
  one 240 s block at exactly 8 steps/s, no dither, each step a random field direction written to all three electrodes
  (A, B, C = 1600 + 1600 cos(θ − 0, 120, 240°), θ on a 15° grid, every electrode changing by ≥ 331 counts per step).
- **Data:** Dropbox `Microspheres/TFINER/data/voltage_steps/2026-11-10/vsteps_1794334700/` (writes, blocks, OUTMON, OUT_DQ
  FE 1478386115–1478386547, console logs, GPS pairs).
- **Figures and table:** `python3 lab_utils/voltage_steps_score.py <data dir> --outdir analysis/voltage_steps_20261110/plots`
  (on the branch, adc11b3): `summary.md`, `field_timing_block02.png` (where each write fell in the intake window),
  `block02_field_8.png` (sent vs recorded; its bottom panel is OUT_DQ minus each write from when the front end should apply
  it, edges masked, so it is flat except at the failures, at 3, 105 and 207 s) and the calibration blocks (gitignored).
- OUT_DQ is upstream of the output switch: these numbers are when the front end **applies** a write, not what reaches
  the electrode.

## Measured

- **1915 of 1920 field updates landed on all three electrodes** (99.74 %); 11 of 5760 channel writes lost. Achieved
  7.99 landings/s. The calibration blocks landed 100 %.
- **Intake grid as in S0:** applied ticks every 125.0 ms (one parity of the 16 Hz tick), edge onsets at OUT_DQ samples
  61–63 of each 64-sample tick.
- **The writes covered the whole intake window.** Host spacing 124.53 / 125.00 / 125.35 ms (min / median / max), host
  lateness ≤ 0.7 ms; the clock drift (+1.220 ms/s, fitted from the 1084 calibration writes; S0 +1.212) slid them
  through the 125 ms window ~2.3 times (`field_timing_block02.png`, right panel).
- **Every failure was within ~1.1 ms of an intake** (mapped write time). 58 updates fell within 1.5 ms of an intake; 53 of
  them landed. The 5 failures, read from OUT_DQ's per-tick levels:

  | step | s into block | what OUT_DQ showed |
  |---|---|---|
  | 24 | 3.0 | V2's new value applied; V4 and V3 kept the previous step's values for one window, then step 25 replaced all three |
  | 842–843 | 105.4 | 842 never applied as a whole (its V3 only); at the next intake V2, V4 had 843's values and V3 still had 842's; 843's V3 never applied |
  | 1653 | 206.9 | not applied at all: 1652's values held for two windows, then 1654 |
  | 1657–1658 | 207.4–207.5 | V2 / V4 / V3 showed a mix of 1656, 1657 and 1658 values for two windows |

  So near an intake, two kinds of failure: **a whole update lost** (two writes in one window, last wins) and **a mixed
  update**: some electrodes take the new value at one intake and the rest at the next, so for 125 ms the three electrodes
  hold values from two different steps. In each mixed case the electrodes that made it are the ones written first
  (write order V2, V4, V3).
- **Rate of failures:** 5 in 240 s (1 per ~48 s, or 1 per ~380 updates) for writes timed without regard to the grid.
- **Write → OUTMON on the host:** median 173–197 ms, p95 241–246 ms, as in S0 (upper bound on host-side latency).
- Absolute write → field latency: not measured (as S0).

## Derived

- Mapped write positions are uncertain by ~±0.5–1 ms (e.g. step 843 maps 0.5 ms after the intake its V2, V4 made). So "within
  ~1.1 ms" is the resolution of this measurement, not a sharp edge.
- The mixed updates show that the three channels are **taken separately**, not as one snapshot: a write burst (0.4–1.7 ms)
  that straddles an intake splits. S0's "0 of 987 splits" counted only steps where all channels landed, so it could not
  see this; it was already marked as not proof of "applied together".
- Expected straddles if timing is random: mean burst length (~0.5 ms; from the table's "chance" column, 0.8 % of 62.5 ms)
  / 125 ms ≈ 0.4 % per update, ≈ 8 in 1920; measured 4 mixed (+1 lost). Same order; not tested further.

## Interpretation (not approved)

- (interpretation, not approved) 8 updates/s works as an operating rate: 99.7 % of updates land intact, and the failures
  are confined to writes within ~1 ms of an intake. For feedback, a camera-triggered write would see one bad update
  (lost, or a mixed field direction for 125 ms) every ~400 updates. Avoiding them would need writes kept ~2 ms clear of
  the intake, i.e. the sender following the front end's timing.
- (interpretation, not approved) The mixed updates come from the IOC handing each channel's record to the front end
  independently; writing the channels closer together (shorter burst) would shrink, not remove, the window.

## Open

- Absolute write → field latency (the number that matters most for feedback, F3): as in the S0 README, "Open".
- Whether ~1 bad update in ~400 matters for feedback: a physics call for Molly.
