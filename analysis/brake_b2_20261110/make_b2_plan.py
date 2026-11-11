#!/usr/bin/env python3
"""Gate B2 (Molly OK 2026-11-10): push-map pulse plan for voltage_steps.py run --plan (offset route, open loop).

    python3 make_b2_plan.py            # -> b2_plan.csv

One electrode at a time: OFFSET 0 -> LEVEL for PULSE s, then 0. Phases in shuffled order, N per phase, gaps uniform in
GAP s (not a multiple of the ~4.17 s swing period, so the pulses land at all angles of the swing). Each pulse's change
in rotor angular velocity (tracked video), against the angle it hit, maps that phase's push vs angle.
Size (derived): at 3200 counts phase A gave ~1.2 rad/s^2 (detent runs, first 0.6 s), ~linear in V, so 800 counts for
0.25 s changes the swing velocity by ~0.075 rad/s (~4 deg/s, measurable to ~0.2 deg/s) and the swing energy by at most
~5 %; 45 random-sign pulses walk the +-72 deg swing by ~+-8 deg typically (derived, rough).
"""
import csv
import numpy as np

LEVEL, PULSE, N, GAP, LEAD, SEED = 800.0, 0.25, 15, (3.0, 6.0), 2.0, 2026
rng = np.random.default_rng(SEED)
order = rng.permutation(np.repeat([2, 4, 3], N))
rows, t, k = [], LEAD, 0
for ch in order:
    on = {2: 0.0, 4: 0.0, 3: 0.0}; on[int(ch)] = LEVEL
    rows.append(dict(block=0, pattern='pulse', rate=0.2, step=k, t=round(t, 6), V2=on[2], V4=on[4], V3=on[3])); k += 1
    rows.append(dict(block=0, pattern='pulse', rate=0.2, step=k, t=round(t + PULSE, 6), V2=0.0, V4=0.0, V3=0.0)); k += 1
    t += PULSE + rng.uniform(*GAP)
with open('b2_plan.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(f'{len(order)} pulses ({N} per phase, {LEVEL:.0f} counts, {PULSE} s), {rows[-1]["t"]:.0f} s -> b2_plan.csv')
