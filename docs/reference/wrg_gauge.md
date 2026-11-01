# Edwards WRG-S gauge (T-Station 85)

Setup: Edwards T-Station 85 (nEXT85 turbo) with an Edwards **WRG-S D14703000** DN40CF
wide-range gauge, on the chamber that holds the rev G stator. Established Aug 2026
from two faults (2026-08-20, 2026-08-24); see `logs/2026-q3.md`.

## The trap: a plausible pressure with no error code

The WRG blends a Pirani (atmosphere → 1e-3 mbar) with an inverted magnetron
(1e-2 → 1e-9), blending between 1e-2 and 1e-3. If the magnetron isn't lit, the reading
sits at the Pirani floor and **displays a plausible pressure with no error code**. The
automatic Pirani vacuum-set only fires below 1e-4, so a drifted-high floor never
recovers on its own.

2026-08-20: a steady 8.6–8.8e-3 mbar was not the vacuum; the true pressure was
~2–3.5e-7 (baseline ~1e-7, confirmed 2026-08-21). Cause: a marginal gauge cable
browning out the head.

**Rate of rise** falsified the reading: `P_true = V·(dP/dt)/S_eff`. Isolate the chamber,
measure dP/dt, compare with the indicated pressure (it disagreed by ~7000×). It uses a
difference, so a mis-zeroed gauge doesn't matter.

**After any gauge power cycle, wait a minute or more** (striker heats, HT ramps) before
judging it. ~1e-3 right after reconnecting is normal.

## Raw voltage readout

T-Station Units screen: mbar / Torr / Pa / **voltage**. `P(mbar) = 10^(1.5 V − 12)`;
1 mV ≈ 0.35% in P, far finer than the 2-digit mbar display. Anchors: 6.00 V = 1e-3,
5.33 V = 1e-4 (auto vacuum-set), 4.00 V = 1e-6, 3.33 V = 1e-7.

Error voltages: 1.000 Pirani fail (Err21) · 1.100 magnetron short (Err22) · 1.200
striker fail (Err23) · 1.300 not struck (Err24) · < 0.95 under-range (Err12). Err21 has
the highest priority and masks the others: Err22 then Err21 within the hour is one
cause getting worse, not two faults. Read the voltage, not the panel code; if they
disagree, the fault is between head and controller.

## Cable

FCC68/RJ45 8-way. Proper part **D400-01-010** (1 m) / **D400-01-030** (3 m): screened,
solid-colour conductors, not twisted pairs. A Cat5e patch lead works as a stopgap but is
unshielded and splits signal (pin 3) and signal common (pin 5) across different pairs.
Never tie pin 2 to pin 5. Shielded Cat5e/6 adds a screen bonded to both shells; check the
TIC manual's screen termination first (ground-loop risk).

2026-08-24: Err22 then Err21 cleared by **reseating the same lead**: contact resistance
at the plug, not the cable type. Reseating only catches the loud failures; a marginal
contact can also brown out into a plausible wrong reading (the 08-20 fault). Cheap
mitigations: strain-relieve the lead, check the RJ45 latch tab.

## Manuals and spares

Gauge D147-01-880 Issue L · TIC D397-22-880 (has the crossover/blend spec) · T-Station 85
D395-94-880 (voltage display, CAL screen). Spares: D147-01-803 Pirani tube kit ·
D147-01-802 electrode/striker kit (no Pirani tube) · D147-01-804 full body tube kit.
