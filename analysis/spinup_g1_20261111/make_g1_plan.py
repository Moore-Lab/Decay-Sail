#!/usr/bin/env python3
"""Spin-up gate G1 (Molly OK 2026-11-11): push map over a larger swing, and its scaling with voltage.

    python3 make_g1_plan.py            # -> g1_plan.csv, for voltage_steps.py run --plan (offset route, open loop)

Run on a swing first pumped to ~+-35 deg (brake_offsets.py --pump-to 35), so the pulses land over ~180-250 deg.
50 single-electrode pulses, 0.25 s each, random phase and order: 25 at 800 counts (B2's level) and 25 at 1600.
If the push is linear in V the 1600 pulses change the rotor speed 2x as much as the 800 ones; if ~V^2, 4x
(detent runs looked ~linear; STATUS's harmonic question turns on this). Gaps uniform 3-6 s (swing period ~3-4 s).
Energy (derived, rough): a 1600 pulse changes the swing energy by up to ~10-20 %, random sign; 50 pulses walk the swing
by roughly +-15 deg about its start.
"""
import csv
import numpy as np

LEVELS, PULSE, N, GAP, LEAD, SEED = (800.0, 1600.0), 0.25, 25, (3.0, 6.0), 2.0, 20261111
rng = np.random.default_rng(SEED)
items = [(ch, lv) for lv in LEVELS for ch in np.resize([2, 4, 3], N)]
order = rng.permutation(len(items))
rows, t, k = [], LEAD, 0
for i in order:
    ch, lv = items[i]
    on = {2: 0.0, 4: 0.0, 3: 0.0}; on[int(ch)] = lv
    rows.append(dict(block=0, pattern='pulse', rate=0.2, step=k, t=round(t, 6), V2=on[2], V4=on[4], V3=on[3])); k += 1
    rows.append(dict(block=0, pattern='pulse', rate=0.2, step=k, t=round(t + PULSE, 6), V2=0.0, V4=0.0, V3=0.0)); k += 1
    t += PULSE + rng.uniform(*GAP)
with open('g1_plan.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(f'{len(items)} pulses ({N} at each of {LEVELS}, {PULSE} s), {rows[-1]["t"]:.0f} s -> g1_plan.csv')
