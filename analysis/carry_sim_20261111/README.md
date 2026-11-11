# Stage-1 carry in simulation (2026-11-11, Mac only, nothing live)

Molly OK 2026-11-11 ("yes" to the carry simulation). Directive: `measurement_objective.md` stage 1 (0.01–0.05 Hz for
5 min, both directions). Spin-up order: `lab_utils/SPINUP_PLAN.md`. Inputs: G1 push map and trap
(`analysis/spinup_g1_20261111/pushmap_g1.json`), B2 shape (`analysis/brake_b2_20261110/pushmap_b2.json`).

**Status:** the sim is built, and one constraint found while building it decides most of the outcome. The robustness scan
in `carry_sim.py main()` was **not run**, because the nominal cells already fail (see 3). Interpretations are **not approved**.

## 1. Constraint found while building it

- **The amp input must be 0–12800 counts** (CLAUDE.md, hardware traps; V_LIMIT 12800). The electrodes go negative only
  through the AC coupling (level = command − its 5.57 s low-pass, S1, measured).
  - A carry therefore needs a pedestal P set slowly beforehand. It is assumed here and its setting is not simulated.
  - With the pedestal, each electrode swings about −P..12800−P.
  - This corrects my earlier message's "6.6 rad/s² at 12800 counts", which assumed ±12800 counts at the input.
- **The V² share f matters a lot at these levels** (derived).
  - Push per phase ∝ (1−f)x + f·x², x = level/800. f = 0.1 reproduces G1's 1600/800 ratio of 2.19; f = 0 gives 2.0 and
    f = 0.2 gives 2.4, both inside the 68 % range.
  - Assumed: the V² part keeps the shape F and does not reverse with sign.
  - Then a negative level pushes at most −(1−f)²/(4f) × F per phase (−2.0 F at f = 0.1, reached at −3600 counts).
  - Push at negative levels has **never been measured**, and nothing has been measured above 1600 counts (one kick at 2400).
- **The trap is measured over 180–254° only** (G1 frames on both sides of each node; the table's edge nodes have none).
  - Outside that range: assumed a = −k sin(θ − θ0), with k = 4.25 rad/s² and zero at 216.8°, fitted to 176–256°.
  - The barrier lies outside 145–295° (B1). The sinusoid is scanned ×0.5, ×1, ×1.5 (`OUT`).

## 2. Static capacity (derived; `capacity.py`, `capacity_table.md`, `plots/carry_capacity.png`)

The capacity at each angle is the largest push in the carry direction from all three phases within the input range,
using the G1+B2 shape.

- **Over most of the turn the capacity is 2–3× the trap:** ~5–20 rad/s² against ≤ 4.3 at OUT = 1.
- **Narrow dips, one per 45°,** sit near 30, 75, 120, 165, 210, 255, 300 and 345°. There all three shifted copies of F
  are weak at once (capacity ~2 rad/s²), and the trap wins in most cases. The same dips appeared in G1's single-phase
  carry check at 210° and 256°.
- **Strict criterion** (capacity > trap at every angle, i.e. a carry at constant, near-zero speed): fails for f = 0.1 at
  every pedestal tried, even inside the measured range. f = 0 passes only if OUT ≤ 0.76.
- **Coasting through the dips:** the energy deficit across the worst dip, with full effort elsewhere, sets the entry
  speed needed:

  | pedestal | f | OUT 1.0, fwd / bwd (Hz) | OUT 1.5, fwd / bwd (Hz) |
  |---|---|---|---|
  | 6400 | 0 | 0.027 / 0.027 | 0.073 / 0.073 |
  | 6400 | 0.1 | 0.059 / 0.036 | 0.107 / 0.088 |
  | 3200 | 0.1 | 0.034 / 0 | 0.068 / 0.029 |
  | 6400 | 0.2 | 0.053 / 0.016 | 0.094 / 0.065 |

  Interpretation, not approved: a carry whose mean speed is in the directive's range but which surges to ~0.03–0.1 Hz at
  each dip looks statically possible in most cases. A carry at constant speed does not.
- Plot caveat: the capacity curves assume each low-pass state sits at the pedestal. In closed loop it drifts (τ 5.57 s
  is about one 45° push period at 0.02 Hz), so the real capacity is lower and history-dependent.

## 3. Closed loop (`carry_sim.py`; derived)

The controller is a constant-speed reference with PID and feedforward through the nominal trap. Every 125 ms it predicts
to the middle of the next hold, then allocates the three commands nearest the pedestal, by Newton on the push model.
It knows the 8 Hz grid. The plant adds:

- ±10 % amplitude per phase;
- a 0.6 rad/s² ripple outside the measured region;
- 0.05° camera noise;
- 1 in 400 updates lost;
- a landing constant C (15 ms, or 60 ms = one tick late).

**Checks run:**

| case | 0.02 Hz fwd / bwd | 0.05 Hz fwd / bwd | 0.2 Hz |
|---|---|---|---|
| ideal: model exact, no noise, unlimited input (ω_n 2.5–4) | pass, worst error 0.9 / 2.2° | pass, 2.1–2.6 / 5.3–7.6° | fails (slips after 18–186 s) |
| nominal: 0–12800, P 6400, f 0.1, OUT 1 (ω_n 2.5, 4) | slips at 18–19 s | slips at 12–13 s | – |
| f 0, P 6400, OUT 0.5 (passes the strict static criterion) | slip at 77 s / slip at 18 s | pass (15 turns) / slip at 16 s | – |
| f 0, P 6400, OUT 1 | slip / slip | slip / slip | – |

- "Slip" here means the error passed 30°, so the field went off.
- The first slips come just outside the measured region (~280° forward, ~145° backward), with 20–75 % of updates saturated.
- Bug found and fixed on the way: the prediction from landing to mid-hold used the trap alone. That biased the speed by
  trap × 62 ms and left a ±2° trap-shaped tracking error even with an exact model.
- **Not diagnosed:** why the closed loop does worse than the strict static criterion (third row). Suspects (untested):
  low-pass drift reducing headroom, the ±10 % amplitude scatter, and the outside ripple.
- 0.2 Hz fails even ideally at 8 updates/s (9° per update against a 22.5° m = 16 period), as the plan expected.

## 4. What would decide it (suggested, not approved)

Measured inputs the result hinges on, cheapest first:

1. Push at **negative electrode levels** (B2-style pulses stepped down from a pedestal): the sign and size give f
   directly.
2. Push at **3200 and 6400 counts**: whether the V² part grows as assumed.
3. **The trap beyond 172–262°**: pump to larger swings, as in G3, with the brake as backup.

On the sim side, a dip-aware controller that plans the speed profile from the capacity map (surging before each dip)
instead of holding constant speed.

## Files

- `carry_sim.py`: plant and controller. Its `main()` (gain scan and robustness scan) was not run. Test switches at
  module level: `CTRL_F`, `AMP_NOISE`, `RIPPLE`, `NOISE_DEG`.
- `capacity.py`: the static capacity, `capacity_table.md` and `plots/carry_capacity.png`.
