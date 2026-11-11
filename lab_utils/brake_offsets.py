#!/usr/bin/env python3
"""Gate B4: brake the rotor's swing through the electrode offsets, from the live tracker. Plan: braking gates B1-B4
(analysis/brake_b1..b3_20261110 on main; DECISIONS 2026-11-10: measured trap + push map, simulator check, live safety).

    python3 brake_offsets.py run [--level 800] [--duration 120] [--port 5005] [--outdir DIR] [--enable-outputs] [--live]
    python3 brake_offsets.py selftest          (Mac: control law + safety in the B3 plant; no EPICS)

Needs the live tracker publishing angles (one UDP datagram per frame, "k,host_time,angle_deg,ncc"):
    python3 camera_utils/tracking/live_blob_track.py --centre 117.5,165.1 --publish 127.0.0.1:5005 --show --outdir DIR

CONTROL LAW (B3, analysis/brake_b3_20261110): every 125 ms (the front end applies offset writes on an 8 Hz grid), fit
the last 8 frames (quadratic), predict angle and velocity to the middle of the 125 ms hold this write will land in
(intake wait 62.5 ms + assumed extra delay 30 ms + half a hold), and switch on the ONE phase (A, B, C = V2, V4, V3, at
--level counts) whose measured push most opposes the predicted motion, if that push exceeds --min-push; else all off.
Push map (B2, measured 2026-11-10 at 800 counts): a_q(theta) = F(theta - s_q), F = const + m=8 + m=16 terms,
s = 0, -16.0, +14.5 deg. Valid only where B2 sampled it (187-238 deg).

SAFETY (live, DECISIONS 2026-11-10):
  - observe 5 s with the field off first: the start amplitude A0 is measured, not assumed;
  - field off for good (then teardown) if: the swing (half peak-to-peak over the last 4 s) exceeds --grow x A0;
    the angle leaves --safe (default 190-236 deg, inside the mapped range); no fresh angle for --stale s; ncc below
    --ncc-min for 5 frames; --duration elapsed; Ctrl-C;
  - refuses to start (voltage_steps.preflight) if the oscillator is on, an offset is non-zero, an input/OFFSET bit is
    off, LES/MON not isolated, or --level is outside 0..12800; outputs only with --enable-outputs (sw2 | 1024, the
    pre-run SW2 restored by bit; a whole SW2 word is never written);
  - teardown: offsets to 0 (TRAMP --release if any is non-zero), wait, restore the output bit and TRAMP.
--live is required for any write; without it the run prints its plan and exits. With --live but no --enable-outputs it
writes offsets with outputs OFF (an end-to-end timing test: nothing reaches the electrodes).
Log: one row per frame (angle, ncc, estimate, choice, write times) -> OUTDIR/brake_<host>.csv.
"""
import argparse
import csv
import math
import os
import socket
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voltage_steps as vs  # noqa: E402

PREFIX, CHANS = vs.PREFIX, vs.CHANS          # CHANS = (2, 4, 3) = A, B, C
INTAKE = 0.125
# B2 push map (analysis/brake_b2_20261110/pushmap_b2.json, shared_shape; measured 2026-11-10, 800 counts)
COEF = dict(c8=0.2467, s8=-0.1472, c16=-0.4432, s16=-0.2891, const=-0.0065)
SHIFT = (0.0, -16.0, 14.5)                   # A, B, C
# B2 trap (trap_run), for the controller's short prediction only
NODES = np.arange(184.0, 243.0, 2.0)
TRAP = np.array([2.1879, 1.6126, 1.0373, 0.8831, 0.8512, 1.3766, 1.5076, 1.9284, 2.6492, 1.0745, 1.1504, 2.7405, -0.9523,
                 -0.408, -0.9681, -1.2375, 0.1625, -0.9419, 0.4954, 0.7568, -0.7872, -0.2099, -0.6922, -1.1822, -1.9378,
                 -2.4935, -2.5734, -2.4193, -1.9453, -1.4714])


def F(th):
    x = math.radians(th)
    return (COEF['const'] + COEF['c8'] * math.cos(8 * x) + COEF['s8'] * math.sin(8 * x)
            + COEF['c16'] * math.cos(16 * x) + COEF['s16'] * math.sin(16 * x))


def push(q, th):
    return F(th - SHIFT[q])


def trap(th):
    return float(np.interp(th, NODES, TRAP))


def choose(hist, t_now, level, c_assumed=0.030, min_push=0.15):
    """hist: [(t, angle_deg)] last frames. Returns (offsets (V2, V4, V3), est dict)."""
    tt = np.array([h[0] for h in hist]) - t_now; yy = np.array([h[1] for h in hist])
    p2 = np.polyfit(tt, yy, 2)
    th_e, w_e = p2[2], math.radians(p2[1])
    h = c_assumed + INTAKE
    acc = trap(th_e)
    th_p = th_e + math.degrees(w_e * h + 0.5 * acc * h * h); w_p = w_e + acc * h
    best, bq = 0.0, None
    for q in range(3):
        pw = w_p * push(q, th_p)
        if pw < best:
            best, bq = pw, q
    out = [0.0, 0.0, 0.0]
    if bq is not None and abs(push(bq, th_p)) > min_push:
        out[bq] = level
    return tuple(out), dict(th=th_e, w_dps=math.degrees(w_e), th_p=th_p, q=-1 if out == [0.0] * 3 else bq)


class Safety:
    def __init__(self, grow, safe, fps=50.0, win=4.0):
        self.grow, self.safe, self.n = grow, safe, int(win * fps)
        self.buf = []; self.A0 = None

    def add(self, th):
        self.buf.append(th); self.buf = self.buf[-self.n:]

    def amp(self):
        return (max(self.buf) - min(self.buf)) / 2 if self.buf else 0.0

    def check(self, th):
        if not (self.safe[0] <= th <= self.safe[1]):
            return f'angle {th:.1f} outside {self.safe}'
        if self.A0 is not None and len(self.buf) >= self.n and self.amp() > self.grow * self.A0:
            return f'swing {self.amp():.1f} > {self.grow} x start {self.A0:.1f}'
        return None


def cmd_run(a, ep=None, src=None):
    lv = a.level
    rows = [dict(block=0, pattern='brake', rate=8.0, step=0, t=0.0, V2=lv, V4=lv, V3=lv)]
    print('=' * 72)
    print(f'  brake_offsets: level {lv:g} counts (~{lv * 0.0124:.0f} V), {a.duration:g} s after {a.observe:g} s observing; '
          f'safe {a.safe[0]:g}-{a.safe[1]:g} deg, grow limit {a.grow}x; outputs '
          f'{"ON" if a.enable_outputs else "OFF (timing test)"}; {"LIVE" if a.live else "DRY"}')
    print('=' * 72)
    err = vs.check_plan(rows)
    if err:
        print('! ' + err); return 1
    if not a.live:
        print('  dry: nothing written. Start the tracker (--publish 127.0.0.1:%d), then add --live.' % a.port); return 0
    ep = ep or vs.Epics()
    no = vs.preflight(ep, rows)
    if no:
        print('! refusing:\n    ' + '\n    '.join(no)); return 1
    if src is None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(('127.0.0.1', a.port)); sock.settimeout(0.05)
        def src():
            try:
                k, ht, ang, ncc = sock.recv(256).decode().split(',')
                return int(k), float(ht), float(ang), float(ncc)
            except socket.timeout:
                return None
    os.makedirs(a.outdir, exist_ok=True)
    fn = os.path.join(a.outdir, f'brake_{int(ep.now())}.csv')
    log = open(fn, 'w', buffering=1)
    log.write('# brake_offsets.py ' + ' '.join(sys.argv[1:]) + '\n')
    log.write('host_t,frame,frame_t,angle,ncc,phase,th_est,w_dps,th_pred,choice,V2,V4,V3,write_t0,write_t1,note\n')
    sw2_before = {n: int(ep.get(f'{PREFIX}_V{n}_SW2R') or 0) for n in (1, 2, 3, 4)}
    tramp_before = {n: float(ep.get(f'{PREFIX}_V{n}_TRAMP') or 0.0) for n in CHANS}
    cur = {n: 0.0 for n in CHANS}
    S = Safety(a.grow, a.safe)
    hist, low_ncc, reason = [], 0, 'duration'
    try:
        for n in CHANS:
            ep.put(f'{PREFIX}_V{n}_TRAMP', 0)
        ep.sleep(vs.TRAMP_SETTLE)
        if any(abs(float(ep.get(f'{PREFIX}_V{n}_TRAMP') or 0)) > 1e-9 for n in CHANS):
            raise RuntimeError('TRAMP did not read back 0')
        if a.enable_outputs:
            for n in CHANS:
                if not sw2_before[n] & vs.SW2_OUTPUT_ON:
                    ep.put(f'{PREFIX}_V{n}_SW2S', sw2_before[n] | vs.SW2_OUTPUT_ON)
        for _ in range(1000):                # drop angles queued during preflight (stage 1: up to 1.2 s old)
            m0 = src()
            if m0 is None or ep.now() - m0[1] < 0.1:
                break
        t_start = ep.now(); last_frame = t_start; last_write = -1.0; phase = 'observe'
        print(f'  observing {a.observe:g} s (field off) ...')
        while True:
            m = src()
            now = ep.now()
            if m is None:
                if now - last_frame > a.stale:
                    reason = f'no fresh angle for {a.stale} s'; break
                continue
            k, ht, ang, ncc = m
            if now - ht > a.stale:                 # an old frame is no better than none
                if now - last_frame > a.stale:
                    reason = f'frames older than {a.stale} s'; break
                continue
            last_frame = now
            low_ncc = low_ncc + 1 if ncc < a.ncc_min else 0
            if low_ncc >= 5:
                reason = f'ncc < {a.ncc_min} for 5 frames'; break
            hist.append((ht, ang)); hist = hist[-8:]
            S.add(ang)
            note = ''
            if phase == 'observe' and now - t_start >= a.observe:
                S.A0 = max(S.amp(), 1.0); phase = 'brake'; t_brake = now
                print(f'  start swing +-{S.A0:.1f} deg; braking for up to {a.duration:g} s')
            if phase == 'brake':
                bad = S.check(ang)
                if bad:
                    reason = bad; break
                if now - t_brake >= a.duration:
                    reason = 'duration'; break
            choice = ''; w0 = w1 = ''
            est = dict(th='', w_dps='', th_p='')
            if phase == 'brake' and len(hist) >= 5 and now - last_write >= INTAKE - 0.020:
                last_write = now
                out, est = choose(hist, ht, a.level, a.c_assumed, a.min_push)
                ch = [n for n, v in zip(CHANS, out) if v != cur[n]]
                w0 = ep.now()
                for n in ch:
                    ep.put(f'{PREFIX}_V{n}_OFFSET', out[CHANS.index(n)], wait=False)
                ep.flush(); w1 = ep.now()
                for n, v in zip(CHANS, out):
                    cur[n] = v
                choice = 'off' if est['q'] < 0 else 'ABC'[est['q']]
                est = {k2: (f'{v:.3f}' if isinstance(v, float) else v) for k2, v in est.items()}
            log.write(f'{now:.6f},{k},{ht:.6f},{ang:.3f},{ncc:.3f},{phase},{est["th"]},{est["w_dps"]},{est["th_p"]},{choice},'
                      f'{cur[2]:g},{cur[4]:g},{cur[3]:g},{w0 if w0 == "" else f"{w0:.6f}"},{w1 if w1 == "" else f"{w1:.6f}"},{note}\n')
    except KeyboardInterrupt:
        reason = 'Ctrl-C'
    except Exception as e:
        reason = f'error: {e}'
    finally:
        print(f'\n  stop: {reason}; final swing +-{S.amp():.1f} deg (start {S.A0 if S.A0 is None else round(S.A0, 1)})')
        for n in CHANS:                      # field off now: steps to 0 (small, <= level); AC tail decays with tau
            ep.put(f'{PREFIX}_V{n}_OFFSET', 0, wait=False)
        ep.flush(); ep.sleep(0.5)
        if a.enable_outputs:
            for n in CHANS:
                sw2 = int(ep.get(f'{PREFIX}_V{n}_SW2R') or 0)
                want = (sw2 & ~vs.SW2_OUTPUT_ON) | (sw2_before[n] & vs.SW2_OUTPUT_ON)
                if want != sw2:
                    ep.put(f'{PREFIX}_V{n}_SW2S', want)
        for n, t in tramp_before.items():
            ep.put(f'{PREFIX}_V{n}_TRAMP', t)
        log.write(f'# stop: {reason}; start swing {S.A0}; final swing {S.amp():.2f}\n'); log.close()
        left = {n: ep.get(f'{PREFIX}_V{n}_OFFSET') for n in (1, 2, 3, 4)}
        print(f'  offsets {left}; log -> {fn}')
    return 0 if reason in ('duration', 'Ctrl-C') else 2


# ------------------------------------------------------------------------------------------- selftest
def selftest():
    """The control law and safety in the B3 plant (measured trap + push map), driven through cmd_run's code path with a
    fake tracker and a fake front end (MockFE timing: 8 Hz intake)."""
    import argparse as ap
    ok = True
    sys.path.insert(0, os.path.expanduser('~/Desktop/VSCode/decay_sail/analysis/brake_b3_20261110'))
    try:
        import b3_sim as B
    except ImportError:
        print('b3_sim.py not found (Mac path); skipping the plant test'); B = None

    class Plant:
        """Rotor in the B3 plant; offsets applied on the MockFE intake grid; frames at 50 fps; virtual time."""
        def __init__(self, fe, amp0=22.0, c=0.03, gain=1.0, seed=0):
            self.fe, self.th, self.w, self.c, self.gain = fe, 212.5 + amp0, 0.0, c, gain
            self.rng = np.random.default_rng(seed); self.k = 0; self.t_frame = fe.now()
            self.hp_in = np.zeros(3); self.hp_out = np.zeros(3); self.t_sim = fe.now()

        def applied(self, t):
            v = []
            for n in CHANS:
                ws = [(h, val) for h, ch, val in self.fe.writes if ch == n and
                      self.fe._tick_after(self.fe.fe(h) + self.c, n) <= self.fe.fe(t)]
                v.append(ws[-1][1] if ws else 0.0)
            return np.array(v)

        def step_to(self, t):
            dt = 0.002
            while self.t_sim < t:
                cmd = self.applied(self.t_sim) if int(self.t_sim / dt) % 10 == 0 else getattr(self, '_cmd', np.zeros(3))
                self._cmd = cmd
                a_hp = B.TAU_AC / (B.TAU_AC + dt)
                self.hp_out = a_hp * (self.hp_out + cmd - self.hp_in); self.hp_in = cmd.copy()
                a_f = sum(self.gain * B.push(q, self.th) * (self.hp_out[q] / 800.0) * abs(self.hp_out[q] / 800.0) for q in range(3))
                self.w += (B.trap(B.TRAPS['run'], self.th) + a_f) * dt
                self.th += math.degrees(self.w * dt); self.t_sim += dt

        def __call__(self):
            t = self.fe.now()
            if t < self.t_frame + 0.02:
                self.fe.t = self.t_frame + 0.02; t = self.fe.t
            self.step_to(t); self.t_frame = t; self.k += 1
            return self.k, t, self.th + self.rng.normal(0, 0.05), 0.95

    for label, gain, want in (('brake (measured push)', 1.0, 'duration'), ('wrong-sign push: must stop on growth', -1.0, 'grow')):
        if B is None:
            break
        fe = vs.MockFE('every2', seed=1)
        fe.jit = 0.0
        for n in (1, 2, 3, 4):
            fe.pv[f'{PREFIX}_V{n}_SW2R'] = 768        # outputs off at rest, so the run must switch them on and back
        pl = Plant(fe, gain=gain)
        a = ap.Namespace(level=800.0, duration=40.0, observe=5.0, safe=(190.0, 236.0), grow=1.2, stale=0.5, ncc_min=0.8,
                         port=0, outdir=os.path.join('/tmp', 'brake_selftest'), enable_outputs=True, live=True,
                         c_assumed=0.03, min_push=0.15)
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = cmd_run(a, ep=fe, src=pl)
        txt = buf.getvalue()
        line = [l for l in txt.splitlines() if 'stop:' in l]
        print(f'  {label}: {line[0].strip() if line else txt[-300:]}; offsets at end {[fe.pv[f"{PREFIX}_V{n}_OFFSET"] for n in CHANS]}, '
              f'SW2 {[fe.pv[f"{PREFIX}_V{n}_SW2R"] for n in CHANS]}')
        fin = float(line[0].split('final swing +-')[1].split(' ')[0]) if line else 99
        good = (want == 'duration' and 'stop: duration' in txt and fin < 10) or (want == 'grow' and ('swing' in txt.split('stop:')[1].split(';')[0] or 'outside' in txt.split('stop:')[1].split(';')[0]))
        good &= all(fe.pv[f'{PREFIX}_V{n}_OFFSET'] == 0 for n in CHANS)
        ok &= good
        if not good:
            print('   CHECK FAILED')
    print('SELFTEST', 'PASSED' if ok else 'FAILED')
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sp = p.add_subparsers(dest='cmd', required=True)
    r = sp.add_parser('run')
    r.add_argument('--level', type=float, default=800.0, help='counts (B2/B3: 800; 1600 failed in B3)')
    r.add_argument('--duration', type=float, default=120.0)
    r.add_argument('--observe', type=float, default=5.0, help='s of field-off observation to measure the start swing')
    r.add_argument('--safe', type=lambda s: tuple(float(x) for x in s.split(',')), default=(190.0, 236.0))
    r.add_argument('--grow', type=float, default=1.2)
    r.add_argument('--stale', type=float, default=0.25)
    r.add_argument('--ncc-min', type=float, default=0.8)
    r.add_argument('--c-assumed', type=float, default=0.030, help='s of delay beyond the intake wait (B3 nominal)')
    r.add_argument('--min-push', type=float, default=0.15)
    r.add_argument('--port', type=int, default=5005)
    r.add_argument('--outdir', default=os.path.expanduser('~/brake_runs'))
    r.add_argument('--enable-outputs', action='store_true')
    r.add_argument('--live', action='store_true')
    sp.add_parser('selftest')
    a = p.parse_args()
    return selftest() if a.cmd == 'selftest' else cmd_run(a)


if __name__ == '__main__':
    sys.exit(main())
