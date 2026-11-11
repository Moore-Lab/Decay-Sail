#!/usr/bin/env python3
"""Static carry capacity (derived, Mac only): at each angle, the largest forward / backward push the three phases can
give with the amp input in 0..12800 counts on a pedestal P (electrode level x 800 in [-P, 12800 - P] counts), push
a_q = F_q [(1-f) x + f x^2] (x = level/800, V^2 part unsigned, A), G1+B2 shape. Compared with the trap: measured over
180-254, assumed k-sinusoid (x OUT) outside. Prints the largest OUT that a slow carry could pass statically, per case."""
import numpy as np
import carry_sim as C

F = C.push_tables('G1B2')
trap_in = C.trap_table(1.0, 0.0)          # measured part only (outside zeroed)
w_in = np.clip(np.minimum(C.TH - 172.0, 262.0 - C.TH) / 8.0, 0, 1)
sin_out = C.trap_table(0.0, 1.0)          # outside part only, OUT = 1


def cap(P, f, amp=1.0, lim=12800.0):
    xs = np.linspace(-P / 800, (lim - P) / 800, 401)
    g = (1 - f) * xs + f * xs * xs
    gmax, gmin = g.max(), g.min()
    fw = np.where(F > 0, F * gmax, F * gmin).sum(0) * amp     # most forward push per angle
    bw = np.where(F > 0, F * gmin, F * gmax).sum(0) * amp     # most backward push (negative)
    return fw, bw


print('trap outside model: k %.2f rad/s^2, zero %.1f deg' % (C.K_SIN, C.TH0_SIN))
print('| pedestal | f | amp | min fwd capacity (rad/s^2) | worst angle | largest OUT, forward | largest OUT, backward |')
print('|---|---|---|---|---|---|---|')
for P in (3200, 6400, 9600, 12800):
    for f in (0.0, 0.1, 0.2):
        for amp in (1.0,):
            fw, bw = cap(P, f, amp)
            # forward carry passes angle th if fw + trap > 0; trap = trap_in + OUT * sin_out
            def ok(o, sign):
                tr = trap_in + o * sin_out
                return np.all(fw + tr > 0) if sign > 0 else np.all(bw + tr < 0)
            def largest(sign):
                if not ok(0.0, sign):
                    return 'fails inside measured range'
                lo, hi = 0.0, 10.0
                for _ in range(40):
                    mid = 0.5 * (lo + hi); lo, hi = (mid, hi) if ok(mid, sign) else (lo, mid)
                return f'{lo:.2f}'
            i = np.argmin(fw)
            print(f'| {P} | {f} | {amp} | {fw.min():.2f} | {C.TH[i]:.0f} | {largest(1)} | {largest(-1)} |')


def plot():
    import os
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs('plots', exist_ok=True)
    fig, ax = plt.subplots(1, 2, figsize=(15, 4.5), sharey=True)
    for k, (sign, name) in enumerate(((1, 'forward (increasing theta)'), (-1, 'backward'))):
        for o, ls in ((0.5, ':'), (1.0, '-'), (1.5, '--')):
            tr = trap_in + o * sin_out
            ax[k].plot(C.TH, -sign * tr, 'k', ls=ls, lw=0.8, label=f'trap to beat (outside x{o}, A)')
        for (P, f), col in (((6400, 0.0), 'C0'), ((6400, 0.1), 'C1'), ((3200, 0.1), 'C2'), ((6400, 0.2), 'C3')):
            fw, bw = cap(P, f)
            ax[k].plot(C.TH, fw if sign > 0 else -bw, color=col, lw=1, label=f'capacity, pedestal {P}, f {f}')
        ax[k].axvspan(180, 254, color='grey', alpha=0.12, label='trap measured (G1)')
        ax[k].set_title(name, fontsize=10); ax[k].set_xlabel('theta (deg)'); ax[k].set_xlim(0, 360)
    ax[0].set_ylabel('rad/s^2 (push in the carry direction)'); ax[1].legend(fontsize=7, loc='upper right')
    fig.suptitle('Slow carry needs capacity > trap at every angle (0-12800 counts in; push extrapolated from <= 1600)', fontsize=10)
    fig.tight_layout(); fig.savefig('plots/carry_capacity.png', dpi=90)


plot()
