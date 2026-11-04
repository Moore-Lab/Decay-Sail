#!/usr/bin/env python3
"""Tests for commutate.c (the y1rds cdsFunctionCall) on the Mac: no RCG, no MATLAB, no hardware.

    python3 test_commutate.py

1. RCG build check, emulated: FunctionCall.pm's own parse of the C file (signature on one line,
   literal argin[k]/argout[k] indices, function ends at a column-0 '}', no 'void ' inside) must
   find 13 inputs and 4 outputs, all used. The real check is the build on cymac1.
2. Compile commutate.c as plain C (FE_RATE 2048, sincos from libm via a shim) and call it each
   model cycle from a closed-loop simulation:
   - rotor in a trap (harmonic or pendulum), drive torque from the applied field, V^2 coupling;
   - camera 50 fps with 0.1 deg noise, worker2 line fit (feedback_drive.Controller);
   - THETA/OMEGA/SEQ reach the model only at 16 Hz ticks, after the frame delay;
   - each phase AC-coupled (tau 6 s), as the HV amp.
   Checks: pump grows a 5 deg swing; the opposite lead damps it; pendulum trap goes over the
   top and keeps turning; outputs bounded; the watchdog trips when SEQ stops, latches, and
   re-arms only on an ENABLE edge; psi moves smoothly between 16 Hz updates.
"""
import ctypes, math, os, re, subprocess, sys, tempfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from feedback_drive import Controller          # worker2-side line fit (same code that will run there)

SRC = os.path.join(HERE, 'commutate.c')
FE_RATE = 2048
NIN, NOUT = 13, 4
KAPPA = 1.23e-3          # front-end clock runs fast of worker2's (scope, 2026-11-03)
H0 = 1793750000.0        # worker2 host-clock epoch for TFRAME
ok_all = True


def check(name, cond, detail):
    global ok_all
    ok_all &= bool(cond)
    print('  %-62s %s  (%s)' % (name, 'PASS' if cond else 'FAIL', detail))


# ------------------------------------------------------------------ 1. FunctionCall.pm parse
def rcg_parse(path, func):
    start = False; inv = outv = None; ins = set(); outs = set()
    for line in open(path):
        line = line.rstrip('\n')
        if re.match(r'^\t* *//', line) or re.match(r'^ *#', line):
            continue
        if start and re.match(r'^}', line):
            break
        if start and 'void ' in line:
            break
        if start:
            ins |= {int(k) for k in re.findall(re.escape(inv) + r'\[(\d+)\]', line)}
            outs |= {int(k) for k in re.findall(re.escape(outv) + r'\[(\d+)\]', line)}
        if not start and re.search(r'void %s *\(' % func, line):
            w = re.split(r'[:*(,\s/]+', line); inv, outv = w[3], w[7]; start = True
    return ins, outs, inv, outv


ins, outs, inv, outv = rcg_parse(SRC, 'COMMUTATE')
print('commutate.c tests')
check('RCG parse: 13 inputs used, literal indices 0..12', ins == set(range(NIN)), 'vars %s/%s, in %s' % (inv, outv, sorted(ins)))
check('RCG parse: 4 outputs used, literal indices 0..3', outs == set(range(NOUT)), 'out %s' % sorted(outs))

# ------------------------------------------------------------------ 2. compile
tmp = tempfile.mkdtemp()
shim = os.path.join(tmp, 'shim.h')
open(shim, 'w').write('#include <math.h>\n#define FE_RATE %d\n#define sincos(x, s, c) (*(s) = sin(x), *(c) = cos(x))\n' % FE_RATE)
lib = os.path.join(tmp, 'libcommutate.so')
r = subprocess.run(['cc', '-O2', '-Wall', '-Wextra', '-Wno-unused-parameter', '-shared', '-fPIC', '-include', shim, SRC, '-o', lib],
                   capture_output=True, text=True)
check('compiles as plain C with -Wall -Wextra, no warnings', r.returncode == 0 and not r.stderr.strip(), r.stderr.strip()[:200] or 'clean')
if r.returncode:
    sys.exit(1)


def fresh():
    """A new library instance (static state reset)."""
    p = os.path.join(tmp, 'libc_%d.so' % fresh.n); fresh.n += 1
    subprocess.run(['cp', lib, p], check=True)
    L = ctypes.CDLL(p)
    L.COMMUTATE.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int, ctypes.POINTER(ctypes.c_double), ctypes.c_int]
    return L
fresh.n = 0


def run(T=120.0, A0=5.0, lead=45.0, trap='harmonic', acc=0.14, f0=0.33, Q=1e4, lat_frame=0.03, latency_param=0.06,
        stop_seq_at=None, reenable_at=None, true_sign=-1, m=8, seed=0, use_acc=True, amp_cmd=6400.0, tframe=True,
        log_err=None, clock_step_at=None, clock_step=0.0):
    rng = np.random.default_rng(seed)
    L = fresh()
    ain = (ctypes.c_double * NIN)(); aout = (ctypes.c_double * NOUT)()
    ain[3], ain[4], ain[5], ain[6], ain[7], ain[8], ain[9], ain[11] = m, -1, lead, latency_param, 1.0, 0.5, 6.0, amp_cmd
    w0 = 2 * math.pi * f0; dt = 1.0 / FE_RATE
    th, om = math.radians(A0), 0.0
    ang = [0.0, -2 * math.pi / 3, -4 * math.pi / 3]
    hp_in = [0.0] * 3; hp_out = [0.0] * 3; a_hp = 6.0 / (6.0 + dt)
    ctrl = Controller(lead=lead, sign=-1, m=m)
    frames = []; seq = 0; pending = None
    out_t, out_th, psis, gains, outmax = [], [], [], [], 0.0
    n = int(T * FE_RATE); fr = FE_RATE // 50; tick = FE_RATE // 16
    for i in range(n):
        t = i * dt
        if i % fr == 0:                                       # camera frame
            meas = math.degrees(th) + rng.normal(0, 0.1)
            ctrl.update(t, meas)
            hstep = clock_step if (clock_step_at is not None and t >= clock_step_at) else 0.0
            frames.append((t + lat_frame, ctrl.th, ctrl.w, ctrl.a, H0 + t / (1 + KAPPA) + hstep))   # ready after the frame delay; TFRAME in worker2's clock
            out_t.append(t); out_th.append(math.degrees(th))
        if i % tick == 0:                                     # EPICS 16 Hz tick: latest ready frame lands
            ready = [f for f in frames if f[0] <= t]
            if ready and (stop_seq_at is None or t < stop_seq_at):
                _, th_f, w_f, a_f, tf_f = ready[-1]; frames = [f for f in frames if f[0] > t]
                seq += 1; ain[0], ain[1], ain[2], ain[10] = th_f, w_f, seq, (a_f if use_acc else 0.0)
                ain[12] = tf_f if tframe else 0.0
        if reenable_at is not None and abs(t - reenable_at) < dt / 2:
            ain[7] = 0.0
        if reenable_at is not None and abs(t - reenable_at - 0.01) < dt / 2:
            ain[7] = 1.0
        L.COMMUTATE(ain, NIN, aout, NOUT)
        s, c, psi, g = aout[0] / 6400.0, aout[1] / 6400.0, aout[2], aout[3]   # field in units of full amplitude
        outmax = max(outmax, abs(aout[0]), abs(aout[1]))
        psis.append(psi); gains.append(g)
        if log_err is not None and abs(om) > math.radians(6):
            want = (true_sign * m * math.degrees(th) + (lead if om * true_sign * -1 > 0 else -lead))
            log_err.append(abs((psi - want + 180) % 360 - 180))
        # phases: cos(psi + phi_n) = c cos(phi) - s sin(phi), AC-coupled
        z = 0j
        for k in range(3):
            v = c * math.cos(ang[k]) - s * math.sin(ang[k])
            hp_out[k] = a_hp * (hp_out[k] + v - hp_in[k]); hp_in[k] = v
            z += hp_out[k] * complex(math.cos(-ang[k]), math.sin(-ang[k]))
        z *= 2 / 3
        psi_e = math.atan2(z.imag, z.real); E = abs(z)
        psi_r = true_sign * m * th
        tq = acc * E * E * math.sin(2 * (psi_e - psi_r))
        restore = -w0 * w0 * (math.sin(th) if trap == 'pendulum' else th)
        om += (restore - w0 / Q * om + tq) * dt
        th += om * dt
    return np.array(out_t), np.array(out_th), np.array(psis), np.array(gains), outmax


def amp(t, th, a, b):
    m = (t >= a) & (t < b); y = th[m] - th[m].mean(); return math.sqrt(2) * y.std()


t, th, psi, g, om = run(T=120, A0=5, lead=45)
check('pump (lead +45, V^2): 5 deg swing grows', amp(t, th, 100, 120) > 4 * amp(t, th, 0, 10),
      '%.1f -> %.1f deg' % (amp(t, th, 0, 10), amp(t, th, 100, 120)))
check('outputs bounded |SIN|,|COS| <= AMP = 6400', om <= 6400 * (1 + 1e-12), 'max %.3f' % om)
_, _, _, _, om2 = run(T=2, A0=5, amp_cmd=99999.0)
check('AMP clamped to 6400 even if set to 99999', om2 <= 6400 * (1 + 1e-12), 'max %.3f' % om2)
dpsi = np.abs((np.diff(psi) + 180) % 360 - 180)
tick = FE_RATE // 16
upd = np.zeros(len(dpsi), bool); upd[tick - 1::tick] = True        # cycle steps where a 16 Hz update lands
big = dpsi > 60                                                       # direction flips (2 x lead = 90 deg)
between = dpsi[~upd & ~big]
check('between 16 Hz updates psi turns smoothly (all cycle steps < 2 deg)', between.max() < 2,
      'max %.2f deg per cycle' % between.max())
jumps = dpsi[upd & ~big]
check('correction at each update: 95% < 30 elec deg (inside the 45 deg lead margin)', np.percentile(jumps, 95) < 30,
      'median %.1f, 95%% %.1f, max %.1f deg' % (np.median(jumps), np.percentile(jumps, 95), jumps.max()))
t, th, psi, g, om = run(T=120, A0=30, lead=-45)
check('damp (lead -45): 30 deg swing shrinks', amp(t, th, 100, 120) < 0.5 * amp(t, th, 0, 10),
      '%.1f -> %.1f deg' % (amp(t, th, 0, 10), amp(t, th, 100, 120)))
t, th, psi, g, om = run(T=300, A0=10, lead=45, trap='pendulum')
turns = (th[-1] - th[0]) / 360
check('pendulum trap: over the top, >= 10 turns in 300 s', abs(turns) >= 10, '%.1f turns' % turns)
t, th, psi, g, om = run(T=10, A0=10, lead=45, stop_seq_at=4.0)
gi = lambda tt: g[int(tt * FE_RATE)]
check('watchdog: SEQ stops at 4 s -> gain 0 by 4 s + WDOG 0.5 + ramp 0.5', gi(3.9) == 1.0 and gi(5.05) == 0.0 and gi(9.9) == 0.0,
      'gain %.2f at 3.9 s, %.2f at 5.05 s, %.2f at 9.9 s' % (gi(3.9), gi(5.05), gi(9.9)))
t, th, psi, g, om = run(T=12, A0=10, lead=45, stop_seq_at=4.0, reenable_at=8.0)
check('watchdog latches; ENABLE edge re-arms (but SEQ still stale -> trips again)', gi(7.9) == 0.0 and gi(9.9) == 0.0,
      'gain %.2f at 7.9 s, %.2f at 9.9 s' % (gi(7.9), gi(9.9)))
# Prediction from the frame's true age (TFRAME, added 2026-11-03) vs from the arrival time (TFRAME = 0, the
# 2026-11-02 behaviour), on a rotor spinning over the top in the pendulum trap. Field angle vs the ideal
# -8*theta +- lead at the same instant; frame delay 30 ms; LATENCY = that delay (TFRAME) or 60 ms (old).
e_new, e_old = [], []
run(T=200, A0=10, lead=45, trap='pendulum', latency_param=0.03, tframe=True, log_err=e_new)
run(T=200, A0=10, lead=45, trap='pendulum', latency_param=0.06, tframe=False, log_err=e_old)
e_new, e_old = np.array(e_new[len(e_new) // 2:]), np.array(e_old[len(e_old) // 2:])
check('TFRAME: field-angle error while turning, 95% < 30 deg', np.percentile(e_new, 95) < 30,
      'with TFRAME median %.1f, 95%% %.1f; without %.1f, %.1f deg' % (np.median(e_new), np.percentile(e_new, 95),
                                                                     np.median(e_old), np.percentile(e_old, 95)))
check('TFRAME = 0 keeps the 2026-11-02 behaviour (bounded, runs)', len(e_old) > 0, '%d samples' % len(e_old))
# worker2's clock steps (NTP) by +1 s and by -0.3 s mid-run: the learned offset must restart, not extrapolate seconds ahead
for step in (1.0, -0.3):
    e_s = []
    run(T=200, A0=10, lead=45, trap='pendulum', latency_param=0.03, tframe=True, log_err=e_s, clock_step_at=120.0, clock_step=step)
    e_s = np.array(e_s); n = len(e_s); after = e_s[int(n * 0.65):]      # from ~130 s on (10 s after the step)
    check('worker2 clock step %+.1f s at 120 s: recovered (95%% < 30 deg after 130 s)' % step, np.percentile(after, 95) < 30,
          'median %.1f, 95%% %.1f deg' % (np.median(after), np.percentile(after, 95)))
print('TESTS %s' % ('PASSED' if ok_all else 'FAILED'))
sys.exit(0 if ok_all else 1)
