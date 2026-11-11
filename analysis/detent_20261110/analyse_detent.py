"""Per-step swing analysis of the detent runs (2026-11-10) from rotor_angle_detent.csv.

    python3 analyse_detent.py DATA_DIR
DATA_DIR = .../data/detent/2026-11-10 (event CSVs are the authority for switch-on and release times).
Writes swings_detent.csv (one row per half-swing extreme), steps_detent.csv (per-step table) and plots/.
Time axis: host_time_cam (camera clock mapped to host, median offset; see track_detent.py).

Swing measures from turning points (extremes of the angle between zero crossings of the angular
velocity, after a 5-frame boxcar): centre = mean of (max+min)/2 over consecutive max/min pairs,
amplitude = mean (max-min)/2, period = median spacing of same-type extremes. Windows per step,
relative to switch-on t_on and release t_rel (from the CSV): before [-10, 0); hold [0, t_rel);
ramp [t_rel, t_rel+30); gap [t_rel+30, next t_on or +10 s).
Field model (derived): commanded offset C for the hold, then a linear ramp to 0 over 30 s, through a
first-order high-pass with tau 5.57 s (measured AC coupling) -> y' = u' - y/tau.
"""
import sys, os, glob, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); D = sys.argv[1]
TAU = 5.57; RAMP = 30.0
d = pd.read_csv(os.path.join(HERE, 'rotor_angle_detent.csv'))
t = d.host_time_cam.values; a = d.angle_deg.values
ev = pd.concat([pd.read_csv(f, comment='#') for f in sorted(glob.glob(os.path.join(D, 'detent_events_*.csv')))], ignore_index=True)
on = ev[ev.event == 'on'].reset_index(drop=True); rel = ev[ev.event == 'release'].reset_index(drop=True)
steps = pd.DataFrame(dict(phase=on.phase, electrode=on.electrode, counts=on.counts, t_on=on.host_time, t_rel=rel.host_time.values))
steps['label'] = [f'{p}{1 if c == 3200 else 2}' for p, c in zip(steps.phase, steps.counts)]
T0 = steps.t_on[0]

# turning points
s = np.convolve(a, np.ones(5) / 5, 'same'); v = np.gradient(s, t)
k = np.where(np.sign(v[1:]) != np.sign(v[:-1]))[0]
ext = []
for i in k:
    j = slice(max(i - 10, 0), i + 11)
    typ = 'max' if v[i] > 0 else 'min'
    jj = j.start + (np.argmax(a[j]) if typ == 'max' else np.argmin(a[j]))
    ext.append((t[jj], a[jj], typ))
ext = pd.DataFrame(ext, columns=['t', 'angle', 'type']).drop_duplicates('t')
# keep alternating extremes only (drop noise turning points inside the pre-run small swing is fine: they alternate)
keep = [0]
for i in range(1, len(ext)):
    if ext.type.iloc[i] != ext.type.iloc[keep[-1]]: keep.append(i)
    elif (ext.type.iloc[i] == 'max') == (ext.angle.iloc[i] > ext.angle.iloc[keep[-1]]): keep[-1] = i
ext = ext.iloc[keep].reset_index(drop=True)
ext.to_csv(os.path.join(HERE, 'swings_detent.csv'), index=False, float_format='%.4f')

def swing(t1, t2):
    e = ext[(ext.t >= t1) & (ext.t < t2)]
    if len(e) < 2: return np.nan, np.nan, np.nan, len(e)
    hi, lo = e.angle.values[:-1], e.angle.values[1:]
    pair = (hi + lo) / 2; amp = np.abs(hi - lo) / 2
    per = np.median(np.r_[np.diff(e.t[e.type == 'max']), np.diff(e.t[e.type == 'min'])]) if len(e) >= 3 else 2 * np.diff(e.t).mean()
    return pair.mean(), amp.mean(), per, len(e)

rows = []
for n, r in steps.iterrows():
    nxt = steps.t_on[n + 1] if n + 1 < len(steps) else r.t_rel + RAMP + 60
    gap_end = min(nxt, r.t_rel + RAMP + 10)
    i0 = np.searchsorted(t, r.t_on)
    m = (t >= r.t_on - 0.1) & (t < r.t_on)
    vel = np.polyfit(t[m] - r.t_on, a[m], 1)[0]
    first = ext[ext.t > r.t_on + 0.04].iloc[0]
    hm = (t >= r.t_on) & (t < r.t_rel); ip = np.argmax(np.abs(a[hm] - a[i0 - 1]))
    out = dict(step=r.label, phase=r.phase, electrode='V%d' % r.electrode, counts=r.counts,
               angle_at_on=a[i0 - 1], vel_at_on_dps=vel,
               first_extreme=first.angle, first_extreme_dt=first.t - r.t_on,
               hold_peak_disp=a[hm][ip] - a[i0 - 1], hold_peak_angle=a[hm][ip], hold_peak_dt=t[hm][ip] - r.t_on)
    for nm, (t1, t2) in dict(before=(r.t_on - 10, r.t_on), hold=(r.t_on, r.t_rel), ramp=(r.t_rel, r.t_rel + RAMP),
                             gap=(r.t_rel + RAMP, gap_end)).items():
        c, A, P, ne = swing(t1, t2)
        out.update({f'{nm}_centre': c, f'{nm}_amp': A, f'{nm}_period': P, f'{nm}_next': ne})
    rows.append(out)
tab = pd.DataFrame(rows)
# free swing after the last ramp (field off): centre/amp/period
c, A, P, ne = swing(steps.t_rel.iloc[-1] + RAMP, t[-1]); post = dict(centre=c, amp=A, period=P, n=ne)
c0, A0, P0, _ = swing(t[0], T0)
tab.to_csv(os.path.join(HERE, 'steps_detent.csv'), index=False, float_format='%.3f')
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
print(tab.round(2).T)
print('pre-run: centre %.2f amp %.2f period %.2f' % (c0, A0, P0))
print('post-run free swing (%d extremes): centre %.2f amp %.2f period %.2f' % (ne, *post.values())[:4] if False else post)
# amplitude decay over the final free swing
e = ext[ext.t > steps.t_rel.iloc[-1] + RAMP]
print('final free swing amp first/last 4 extremes:', np.abs(np.diff(e.angle.values[:5])).mean() / 2, np.abs(np.diff(e.angle.values[-5:])).mean() / 2,
      'over %.0f s' % (e.t.iloc[-1] - e.t.iloc[0]))

# derived field (fraction of the step) through the AC coupling
def field(tt, r):
    u = np.where(tt < r.t_on, 0, np.where(tt < r.t_rel, 1, np.clip(1 - (tt - r.t_rel) / RAMP, 0, 1)))
    y = np.zeros_like(tt); dt = np.diff(tt, prepend=tt[0])
    du = np.diff(u, prepend=0.)
    for i in range(1, len(tt)): y[i] = y[i - 1] * np.exp(-dt[i] / TAU) + du[i]
    return y

# ---- plots
INK, MUTED, GRID = '#1f1f1e', '#6b6a63', '#e4e3dd'
COL = {'A': '#2a78d6', 'B': '#eb6834', 'C': '#1baf7a'}
def style(ax):
    ax.grid(color=GRID, lw=0.6); ax.set_axisbelow(True)
    for sp in ('top', 'right'): ax.spines[sp].set_visible(False)

f, ax = plt.subplots(2, 1, figsize=(15, 8), sharex=True, gridspec_kw=dict(height_ratios=[3, 1.3], hspace=0.08))
ax[0].plot(t - T0, a, color=INK, lw=0.6)
emx, emn = ext[ext.type == 'max'], ext[ext.type == 'min']
ax[1].plot(emx.t - T0, emx.angle, '.', color=INK, ms=3, label='swing max')
ax[1].plot(emn.t - T0, emn.angle, '.', color=MUTED, ms=3, label='swing min')
cen = (ext.angle.values[1:] + ext.angle.values[:-1]) / 2
ax[1].plot(ext.t.values[1:] - T0, cen, '-', color='#a33ea1', lw=1, label='(max+min)/2 per half-swing')
for x in ax:
    style(x)
    for _, r in steps.iterrows():
        c = COL[r.phase]
        x.axvline(r.t_on - T0, color=c, lw=1.2); x.axvline(r.t_rel - T0, color=c, lw=0.8, ls='--')
        x.axvline(r.t_rel + RAMP - T0, color=c, lw=0.8, ls=':')
for _, r in steps.iterrows():
    ax[0].text(r.t_on - T0, 302, ' %s %s %d' % (r.label, 'V%d' % r.electrode, r.counts), color=COL[r.phase], fontsize=9, va='bottom')
ax[0].set_ylim(135, 315); ax[0].set_ylabel('rotor angle (deg)\nimage coords, template zero')
ax[0].set_title('Detent runs 2026-11-10: rotor angle (solid = switch-on, dashed = release/ramp start, dotted = ramp end)', loc='left', fontsize=11, color=INK)
ax[1].set_ylabel('turning points (deg)'); ax[1].legend(fontsize=8, frameon=False, ncol=3, loc='upper left')
ax[1].set_xlabel('host time − %.3f s (A1 switch-on)' % T0)
f.savefig(os.path.join(HERE, 'plots', 'detent_overview.png'), dpi=130, bbox_inches='tight'); plt.close(f)

for n, r in steps.iterrows():
    f, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True, gridspec_kw=dict(height_ratios=[3, 1], hspace=0.08))
    m = (t >= r.t_on - 5) & (t <= r.t_on + 40)
    ax[0].plot(t[m] - r.t_on, a[m], color=INK, lw=1)
    tr = tab.iloc[n]
    for nm, (t1, t2) in dict(before=(-5, 0), hold=(0, r.t_rel - r.t_on), ramp=(r.t_rel - r.t_on, 40)).items():
        cc = tr[f'{nm}_centre']
        if np.isfinite(cc): ax[0].plot([t1, t2], [cc, cc], color=COL[r.phase], lw=1.5, ls='--')
    ax[0].text(0.01, 0.97, 'dashed: swing centre (max+min)/2\nbefore %.1f°, hold %.1f°, ramp %.1f°\namp before %.1f°, hold %.1f°, ramp %.1f°' % (
        tr.before_centre, tr.hold_centre, tr.ramp_centre, tr.before_amp, tr.hold_amp, tr.ramp_amp), transform=ax[0].transAxes, va='top', fontsize=9, color=MUTED)
    ax[0].set_ylabel('rotor angle (deg)'); ax[0].set_title('%s: phase %s (V%d), %d counts' % (r.label, r.phase, r.electrode, r.counts), loc='left', fontsize=11, color=INK)
    y = field(t[m], r); ax[1].plot(t[m] - r.t_on, y, color=COL[r.phase], lw=1.5)
    ax[1].set_ylabel('output / step\n(derived, τ 5.57 s)'); ax[1].axhline(0, color=MUTED, lw=0.6)
    ax[1].set_xlabel('time from switch-on (s)'); ax[1].set_xlim(-5, 40)
    for x in ax:
        style(x); x.axvline(0, color=COL[r.phase], lw=1); x.axvline(r.t_rel - r.t_on, color=COL[r.phase], lw=0.8, ls='--')
        x.axvline(r.t_rel - r.t_on + RAMP, color=COL[r.phase], lw=0.8, ls=':')
    f.savefig(os.path.join(HERE, 'plots', 'detent_zoom_%s.png' % r.label), dpi=120, bbox_inches='tight'); plt.close(f)

# period vs amplitude (field-off-ish windows: gaps and pre/post) - trap shape beyond the fitted range
f, ax = plt.subplots(figsize=(6, 4)); style(ax)
for nm in ['before', 'hold', 'ramp', 'gap']:
    ax.plot(tab[f'{nm}_amp'], tab[f'{nm}_period'], 'o', label=nm, ms=6)
ax.plot([A0, post['amp']], [P0, post['period']], 'k^', label='pre-run / post-run free')
ax.set_xlabel('swing amplitude (deg)'); ax.set_ylabel('period (s)'); ax.legend(fontsize=8, frameon=False)
f.savefig(os.path.join(HERE, 'plots', 'detent_period_vs_amp.png'), dpi=120, bbox_inches='tight'); plt.close(f)
