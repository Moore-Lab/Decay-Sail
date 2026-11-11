# Rotor model refit on S1 (2026-11-10): trap and field→torque coupling

Analysis only, Mac. `python3 refit_coupling.py` (~30 s) rewrites `refit_summary.txt` (all numbers below),
`refit_coeffs.json` and `plots/` (gitignored). `s1data.py` loads the data: the tracked angle; the OUT_DQ landings on the host
clock (inverse of the scorer's `fe_of`) + Delta, AC-coupled per channel with τ 5.57 s; and z = 2/3 Σ V e^{−j ang} / 4000.
Imports `f3_check`/`f3_step2` (wt_fb) and `voltage_steps_score` (wt_vs). Interpretations are Claude's and marked "(interpretation, not approved)".

**Method.** Integral fit on segments of ≤ 0.25 s bounded by field landings: Δω = ∫(trap + coupling) dt, with ω at the
ends from a local quadratic. Training uses the holds, all3 1/s, 8/s random, 5 s of pre-run rest and the 185 s post-run free
swing (field off). All3 2/s is held out. The trap is either (a) the 11-04 fit × TRAP_S, zero at 208.6° (fixed), or (b) refit as
a piecewise-linear acceleration vs angle (2° nodes, 176–252°). The open-loop replays use a copy of `simulate_measured`'s integrator fed
the measured z(t). It agrees with `f3_check.simulate_measured` on the hold block to 2e-12° (checked). `simulate_measured` itself
cannot replay a varying field magnitude or a non-HOLD coupling form. A tabulated trap can be patched in at runtime (see "For F3 step 2").
**Canonical trap:** `refit_coeffs.json` → `trap_acc_canonical` (the HOLD-fit nodes). The per-form node sets in `fits` differ slightly
and are kept only for reference.

## Measured / derived

- **The ~0.65 Hz swing during the holds comes from the trap, not the field.** (derived) The field-off post-run swing gives a
  stiffness of 17.9 rad/s² within ±3° of 208.6°, i.e. 0.67 Hz for a small swing. The 11-04 trap × TRAP_S gives 6.1 rad/s²
  (0.39 Hz). The tracked hold swing is 0.68 Hz. The refit trap reproduces it with the field switched off in the replay (0.68 Hz).
  The hold periods were still ~1.5 s at |z| 0.035–0.06 (23–29 s).
- **The trap has structure on a ~15° scale** (`plots/trap_and_delta.png`, left; measured): a stable well at 208.6°, a
  shoulder/second zero near 218–224° (acc ≈ +0.15 rad/s² at 221°), and steep walls at 200° and 230–235°. Every block lies on
  the field-off curve to within ~0.5 rad/s². Harmonics 1–4 (the 11-04 form) cannot represent this. (derived) It also
  explains the README's "not explained" items: the post-run ±17.5° swing at 0.38 Hz spans both wells (198–234°), so it
  is centred at 215.8°, not 208.6°. The refit trap replays it at 0.3° rms for 5 s.
- **Fit quality** (Delta +72 ms; table in `refit_summary.txt`):

  | trap | coupling | train R² (all Δω) | coupling R² (field-on, after trap) | held-out all3 2/s R² (coupling R²) |
  |---|---|---|---|---|
  | 11-04 × TRAP_S | HOLD refit | 0.02 | 0.08 | 0.24 (0.26) |
  | 11-04 × TRAP_S | V2DET | 0.13 | 0.78 | 0.76 (0.84) |
  | refit | none (trap alone) | – | – | 0.927 |
  | refit | E1 | 0.984 | 0.09 | 0.947 (0.27) |
  | refit | HOLD | 0.989 | 0.43 | 0.981 (0.75) |
  | refit | V2DET (+|z|² detent) | 0.990 | 0.46 | 0.981 (0.76) |

  With the 11-04 trap the coupling fit is poor. V2DET's E²·cos/sin(8θ, 16θ) terms then soak up the trap error (a16 = +35),
  which the field-off data rule out. Refit trap + HOLD: c1 +1.00±0.08, s1 −0.57±0.08, c2 −0.31±0.52, s2 −12.0±0.5 rad/s² (E = 1
  at 4000 counts; statistical errors only). The 11-04 HOLD was [2.42, −1.05, −1.73, 0.25].
- **The coupling is not consistent between blocks** (poor fit, stated plainly). Fitted per block on the refit-trap residual, the
  1x term is fairly stable: amplitude 1.0–2.2 at a phase of −29 to −35° (holds: 1.35 at +8°). The 11-04 HOLD 1x term, for
  comparison, was 2.6 at −23°. The 2x term is not stable: c2 ranges from −11 to +8.5 and s2 from −1 to −16.5, against
  ±0.6–1.3 within each block. Leave-one-block-out, the coupling after the trap predicts all3 2/s (+0.75) and all3 1/s (+0.44),
  but not the holds (−0.08) or 8/s random (−0.39). 8/s random has the most independent field directions, and there even the
  in-block fit reaches only R² 0.16. Per-electrode V_j V_k and V_k models (GEN) and common-mode terms do not help (GEN
  held-out −0.04 to −4.5).
- **Open-loop replays** from the tracked state at each block start (`plots/replay_blocks.png`; rms in deg, first 5 s in brackets):

  | model | holds | all3 1/s | 8/s | all3 2/s (held out) | post-run |
  |---|---|---|---|---|---|
  | 11-04 HOLD, TRAP_S (= step 2) | 3.8 (3.2) | 10.4 (6.3) | 24.0 (7.7) | 30.0 (18.2) | 18.5 (7.0) |
  | refit trap + E1 | 1.7 (2.1) | 12.8 (7.0) | 18.5 (2.6) | 5.2 (1.3) | 3.3 (0.5) |
  | refit trap + HOLD | 2.2 (2.4) | 13.4 (7.2) | 21.4 (3.9) | 8.5 (3.3) | 2.8 (0.5) |
  | refit trap + V2DET | 2.1 (2.6) | 13.4 (7.5) | 16.6 (2.7) | 8.2 (1.6) | 10.8 (0.3) |
  | refit trap (canonical), field off | 1.9 (2.2) | 13.2 (7.3) | 19.5 (2.3) | 7.3 (2.1) | 2.9 (0.5) |

  The post-run rms grows over 30 s (0.5° at 5 s) through a small frequency error, not a shape error. The V2DET row's own trap
  nodes give 0.38 Hz but drift faster (10.8°). On the held-out block, adding any coupling does not beat the trap alone in the
  open-loop replay (E1 5.2°, HOLD 8.5°, field off 7.3°).

  Swing frequency in the holds: tracked 0.68 Hz, refit models 0.67–0.68 Hz, 11-04 model 0.38 Hz. The holds' first edge: the
  tracked angle reaches −4.7°, the sims −2 to −3.5° (25–55 % low at every Delta tried). **Pumping is not reproduced.** In all3 1/s the rotor left the 208.6° well
  at ~31.5 s and grew to ±20°; every refit model stays in the well (±1–5°). In 8/s random the tracked amplitude grew from 17.5
  to ~26–29°; the refit models stay flat (E1, HOLD: ~15–18°) or collapse (V2DET → ~2°). The 11-04 model happens to grow
  (19→26°), but at the wrong frequency and with the wrong trap. Averaged over all3 1/s, the frames at 212–222° accelerate
  +0.22 ± 0.52 (std) rad/s² more than the trap gives, i.e. ~1.3 per unit E, the size of the fitted 1x term. So the escape is not
  explained by a missing steady torque of the fitted size; what is missing is in its timing or phase (interpretation, not approved).
- **Delta is not determined.** The training residual vs Delta is shallow with two minima (−30 and +72 ms). It stays within 10 %
  of its minimum over −48…+103 ms. Held-out R² varies only 0.962–0.985 across −80…+160 ms. Replaying the first hold edge does not
  constrain it either, because the sim's response is too small at any Delta. This is consistent with delay_fit.py's onset
  of 4 ± 12 ms: this fit does not constrain Delta and does not conflict with that value. The JSON's `delta_s` (+72 ms) is the
  residual minimum, not a measurement. Coefficient sensitivity: refit trap + HOLD at Delta 0 gives [1.10, −0.61, −1.12, −12.35]
  vs [1.00, −0.57, −0.31, −12.03] at +72 ms (`hold_at_delta0` in the JSON).

## For F3 step 2

- **(derived) The refit model cannot yet stand in for the rotor.** The trap part can: it reproduces the free swing and the
  hold frequency, but only over 198–234° (field-off data), or 184–246° (field-on only). Start state A (+55° from the 11-04 rest,
  0.82 of a barrier) lies outside anything measured today. The coupling part cannot: no form tested pumps the swing the way S1
  did, and the 2x term changes between blocks.
- **Quadratic coefficients do not extrapolate.** The data reach only E ≤ 0.2 (1200 counts, E² ≤ 0.04). At E = 0.4,
  s2 = −12 would give ~1.9 rad/s², against ~0.3 from the 11-04 numbers, and it comes from a term that varies from −1 to −16.5
  between blocks. Do not use the 2x/E² numbers above 1200 counts without new data. The 1x term (amplitude 1.0–2.2 at −29…−35°)
  is the only coupling number to stand behind.
- **How to use the trap in step 2 without editing tracked code:** at runtime, set `f3_check.trap_acc = lambda phi: np.interp(OFF + phi,
  nodes, acc)` with OFF = 208.6 − eq (eq from the 11-04 trap, −4.875°; as delay_fit.py does). Pass `trap_scale = 1` (no TRAP_S on
  top) and `rest = OFF`. `equilibrium()`, `free_freq()` and `start_state()` all call `F.trap_acc`, so the patch reaches them
  too. Outside 184–246° the table is held flat by `np.interp`, which is not physical. Start A needs a trap there.
- **(derived) TRAP_S rescaling is wrong in kind,** not just in size. Near rest the trap is ~3× stiffer than the rescaled 11-04
  trap (17.9 vs 6.1 rad/s²), and between 210 and 225° it is nearly flat. The controller's `w0sq = 4.94·TRAP_S` (mid-swing gate
  predictor) is therefore off by ~3× near rest, and in the wrong shape across 210–225°.
- (interpretation, not approved) The shoulder at ~221° and the steep wall near 233° matter for braking: a small push near
  rest can decide whether the rotor stays in the 208.6° well or swings out to ±20°. A brake model needs this trap first.
  The coupling at ~1200 counts (rms 0.30 rad/s² at E 0.17) is ~4× weaker than the trap's structure (rms 1.15 rad/s²).

## Caveats

- The near-rest stiffness is a frequency, so it does not depend on the tracker's angle scale. The shoulder at 221° and the
  wall at 233° rely on the tracker's angle linearity. The evidence that the shape holds at larger amplitude is the held-out
  all3 2/s frequency match: 0.32 Hz tracked and simulated at ±28°.
- The trap refit assumes the trap was the same before, during and after the run. All3 1/s points sit ~0.5 rad/s² above the
  field-off curve at 212–222°. That offset could be a field term the forms miss, or a trap change; the two cannot be told apart here.
- Acceleration in the plot is a 0.3 s savgol estimate (biased on fast features). The fits use the integral form instead.
  ~1000 `blanked` tracker frames (sail line zeroed before matching; ncc ≥ 0.95, real measurements) sit at 223–231°.
- Coefficient errors are statistical only. The block-to-block spread (above) is the real uncertainty.
- The D convention is the absolute tracked angle (template zero of 11-06; rest 208.6°). To use the HOLD numbers in
  `simulate_measured`, set `rest` so that rest + phi equals today's absolute angle.
- The 11-04 rest (229.8°) vs today's (208.6°) is still unexplained. (interpretation, not approved) 229.8 lies near today's
  outer wall, so the trap may have shifted, or the template zero may differ.

Files: `refit_coupling.py`, `s1data.py`, `refit_summary.txt`, `refit_coeffs.json`, `plots/trap_and_delta.png`, `plots/replay_blocks.png`.
