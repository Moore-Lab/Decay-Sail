# F2, 2026-11-03: first outputs-on feedback run (EPICS matrix route)

Interpretations are Claude's and marked "(interpretation, not approved)". Everything else is measured or
derived as labelled.
- **Run:** `apparatus_log.md` 2026-11-03. Runbook: `lab_utils/FEEDBACK_HANDOFF.md` (branch `feedback-drive`).
- **Data:** Dropbox `Microspheres/TFINER/data/feedback/f2/`: video and angles gps1477756297, scan log
  `feedback_1477757064.csv`, `OUT_DQ` FE 1477771945–2664, and the worker2 report.
- **Reproduce:** `python3 f2_coupling.py <f2 dir>`.

## What happened (measured)

- **Start and prep hold:** the rotor was still (0.2° span over 30 s). The prep hold (0.1 Hz, 30 s) left a ±25.5° swing.
- **Scan 1:** `--scan default --dwell 10 --amp 5000 --pedestal 6400 --rate 10`. From the −90 step on, the
  rotor went over the top and made full turns. The fastest it turned was **1.17 rev/s**; the most net
  rotation in one 10 s step was −5.5 turns.

| lead | net turns | mean rev/s | max \|rev/s\| |
|---|---|---|---|
| +45 | +0.1 | +0.013 | 0.47 |
| −45 | −0.0 | −0.004 | 0.26 |
| +90 | −0.4 | −0.037 | 0.55 |
| −90 | +3.6 | +0.366 | 0.74 |
| +135 | −5.5 | −0.553 | 1.17 |
| −135 | −2.0 | −0.202 | 0.77 |
| 0 | +3.0 | +0.304 | 0.84 |
| 180 | −1.6 | −0.165 | 0.87 |

- **Scan 2 was not run** (Molly): the swing was ±155°, outside the runbook's window. The free swing was then
  recorded for ~13 min: it decayed from ±160° to ±116°.
- **Molly saw** (11:04–11:05 local): CCW full rotations, then a slip and rotation the other way.
- **Out-of-range recorded outputs.** `OUT_DQ` during the scan left 0–12800: V2 −246..13165, V3 −382..13198,
  V4 −389..13155 (13–20 samples per channel). The nominal command range was 1400–11400. So the transients
  after steps reached ~1800 counts, more than in F1 (~1000). Whether they are in the real output or only in
  the DQ decimation filter is **still unresolved**. Until it is, do not rerun the staircase route at this
  amplitude.

## Trap torque vs angle (measured, free swing after the scan, field off)

Acceleration vs angle over −996..−678° unwrapped, i.e. 318° of the circle. Fit R² 0.946:
- **1× harmonic: 4.94 rad/s².** That is a once-per-turn restoring torque, peak ≈ I·4.94 = 5.4 × 10⁻¹¹ N·m
  (I = 1.1e-11 kg m², DECISIONS).
- **2×, 3×, 4×:** 1.00, 0.86 and 0.73 rad/s².
- **Damping:** 5.2 × 10⁻⁴ /s.

This is measured directly against angle, so it does not have the time confound of the 2026-11-02 swing-frequency
reading. 4.94 rad/s² corresponds to f₀ ≈ 0.354 Hz (derived).

## Drive torque vs field–rotor angle (derived from a fit; R² 0.165)

The residual acceleration during the scan (after the trap model) was regressed on the angle between the
applied field ψ and the rotor's pattern s·m·θ:
- **Pattern −8θ fits best:** R² 0.165. The null, with the command sequence shifted in time, gives R² ≤ 0.008.
  That supports m = 8 with sign −1 (the 2026-11-01 board reading and the 08-24 channel map), now from the
  rotor's own response.
- **Pattern +16θ also fits:** R² 0.140. Not interpreted; it may alias with the commanded law.
- **Effective delay:** 0.07 s from the logged write to the field acting (0.05–0.10 s within 10% of the best fit).
- **Coupling:** at 1× (linear in V) **1.52 rad/s² ≈ 1.7 × 10⁻¹¹ N·m**; at 2× (V²) **1.79 rad/s² ≈ 2.0 × 10⁻¹¹ N·m**,
  at amp 5000 counts.
  - (Interpretation, not approved.) Both terms are present, so the push is not symmetric in lead. That would
    explain why leads 0 and 180 turned the rotor opposite ways, which a pure V² coupling would not.
  - The size is ~30× the design-derived estimate scaled to 67 V. Not explained.
- **Best field–rotor angle:** max + acceleration at **−88°** (2.9 rad/s²), max − acceleration at **+167°** (3.0 rad/s²).
  For the controller law ψ = −8θ + dir·lead, that means lead ≈ −88° when moving + and ≈ −167° when moving −,
  before correcting for the 0.07 s delay (derived).

## Open

- Whether the out-of-range transients are real. Read the 2048 Hz output, or use a scope.
- The +16θ fit.
- The torque size vs design.
- A second scan.
