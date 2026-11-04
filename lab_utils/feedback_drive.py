#!/usr/bin/env python3
"""Camera-feedback stator drive (gates F0-F3, lab_utils/FEEDBACK_HANDOFF.md). Branch feedback-drive.

    python3 feedback_drive.py selftest
    python3 feedback_drive.py run --lead 45 --duration 60 [--amp 6400] [--sign -1] [--m 8]
                                  [--latency 0.04] [--scan 0,45,...,315 --dwell 30]
                                  [--port 5005] [--live] [--enable-outputs]

Default is DRY: prints the writes it would make. --live writes EPICS; --enable-outputs also
switches the electrode outputs on (without it nothing reaches the chamber: the F1 test).

HOW IT POINTS THE FIELD (no model change; F0 design, Molly 2026-11-02)
The front-end oscillator cannot take a phase, and a FREQ change waits for the next GPS second
and restarts at phase 0 (RCG cdsOsc, LIGO-T080135 sec 7.6.3). So the oscillator is FROZEN:
FREQ 0, so SIN = 0 and COS = COSGAIN, a constant. The DRVMTRX matrix (rows V1..V4, columns
(sin, cos)) then sets each electrode's drive from column 2 alone. For field angle psi
(electrical degrees, + = A->B->C, the convention of stator_osc_drive.py and drive_coupling.py)
    SETTING_n_2 = cos(psi + phi_n),  phi = 0 (V2, A), -120 (V4, B), -240 (V3, C);  SETTING_n_1 = 0
which is the state the running oscillator drive passes through at phase psi. Matrix TRAMP is
set to 0 so each LOAD_MATRIX is a step. One update = 3 SETTING writes + LOAD_MATRIX, sent
without waiting, once per camera frame. The waveform itself is not streamed: each update is a
field DIRECTION, held by the front end until the next one.

CONTROL LAW (pump = push along the motion)
The live tracker (camera_utils/tracking/live_blob_track.py --publish HOST:PORT) sends each
frame's angle theta (image degrees). The controller predicts theta ahead by --latency using the
measured angular velocity w, then
    psi = sign * m * theta_pred + dir(w) * lead
w and the current angle come from a line fit to the last 5 frames; dir(w) = sign of w,
changed only when |w| > --vmin deg/s. sign maps rotor image angle to field
angle: -1 if a rotor turning with the A->B->C sequence has decreasing image angle (measured on
the board 2026-11-01, assumes the 08-24 channel map; drive_coupling.py WITH_FIELD_SIGN). lead
is in ELECTRICAL degrees. Which lead pumps is unknown: for a torque from V^2 on an m=16 rotor
pattern it goes as sin(2*lead), for the term linear in V on m=8 as sin(lead). The F2 scan
(--scan default) steps lead in +/- pairs (45,-45,90,-90,...; 10 s each, so the swing stays
bounded) and the swing growth per step says which. The same law keeps pushing once the
rotor goes over the top (dir stays constant), so it also commutates.

SAFETY
- Refuses to start if the oscillator gains are nonzero or any phase offset is nonzero.
- Pedestal = --pedestal (default 6400) on the phase electrodes; refuses unless amp <= pedestal and
  pedestal + amp <= 12800 = V{n}_LIMIT (amp input 0-2.1 V). |matrix| <= 1, so the command stays in
  pedestal - amp .. pedestal + amp; amp 5000 on pedestal 6400 leaves 1400 counts of margin each side.
- Watchdog: no fresh angle for --stale s, or ncc < --ncc-min for 5 frames in a row: stop.
- Stop (Ctrl-C, watchdog, end): gains ramp to 0 over --gain-ramp s, DRVON 0, matrix restored to
  the forward drive matrix with TRAMP 2, DRV/matrix TRAMPs restored, pedestal dropped over the
  live V{n}_TRAMP, and only then the output switches restored.
Writes a log (one line per update) to --log (default ~/stator_detent/feedback_<gps>.csv).
"""
import argparse, math, os, socket, sys, time

import numpy as np

PREFIX = 'Y1:RDS-OUTS'
MTRX = f'{PREFIX}_DRVMTRX'
PHI = {2: 0.0, 4: -120.0, 3: -240.0}          # electrode -> phase offset (A, B, C = V2, V4, V3)
S3 = math.sqrt(3) / 2
MATRIX_FWD = {1: (0.0, 0.0), 2: (0.0, 1.0), 3: (-S3, -0.5), 4: (S3, -0.5)}   # = stator_osc_drive
SW2_OUTPUT_ON = 1024
SCAN_DEFAULT = [45, -45, 90, -90, 135, -135, 0, 180]   # +/- pairs keep the swing bounded
LIMIT = 12800
GPS_UNIX_OFF = 315964800 - 18


# ---------------------------------------------------------------------------------- pure logic
def field_column(psi_deg):
    """Matrix column 2 (rows V1..V4) that points the field at psi (electrical deg)."""
    col = {1: 0.0}
    for n, ph in PHI.items():
        col[n] = math.cos(math.radians(psi_deg + ph))
    return col


class Controller:
    """theta in, psi out. Pure: no I/O, so the selftest drives it with a simulated rotor."""

    def __init__(self, lead=45.0, sign=-1, m=8, latency=0.04, vmin=6.0, nfit=5, nacc=9):
        self.lead, self.sign, self.m, self.latency, self.vmin, self.nfit, self.nacc = lead, sign, m, latency, vmin, nfit, nacc
        self.th = None; self.hist = []; self.w = 0.0; self.a = 0.0; self.dir = 1

    def update(self, t, theta_deg):
        """Unwrap, fit a line to the last nfit frames (angle and velocity at t, less noise than
        a two-point difference), predict ahead by latency, return psi (deg, 0..360)."""
        if self.th is None:
            self.th = theta_deg
        else:
            self.th += (theta_deg - self.th + 180.0) % 360.0 - 180.0
        self.hist.append((t, self.th)); self.hist = self.hist[-max(self.nfit, self.nacc):]
        th_now = self.th
        if len(self.hist) >= 3:
            h = self.hist[-self.nfit:]
            tt = np.array([x[0] for x in h]) - t; yy = np.array([x[1] for x in h])
            self.w, th_now = np.polyfit(tt, yy, 1)
        if len(self.hist) >= self.nacc:              # acceleration (for the front-end prediction) from a longer quadratic fit
            tt = np.array([x[0] for x in self.hist]) - t; yy = np.array([x[1] for x in self.hist])
            self.a = 2 * np.polyfit(tt, yy, 2)[0]
        if abs(self.w) > self.vmin:
            self.dir = 1 if self.w > 0 else -1
        th_p = th_now + self.w * self.latency
        psi = self.sign * self.m * th_p + self.dir * self.lead
        return psi % 360.0


# ---------------------------------------------------------------------------------- selftest
def simulate(ctrl, T=120.0, A0=5.0, f0=0.33, Q=1e4, acc=0.14, kind='v2', true_sign=-1, m=8,
             true_offset=0.0, lat=0.04, frame=0.02, tau_ac=6.0, trap='harmonic', noise=0.1,
             lead_sched=None, rng=None):
    """Rotor angle theta (rad) in a trap, driven by the field the controller commands.
    acc = peak drive angular acceleration (rad/s^2) = torque / I (design ~1.5e-12/1.1e-11 = 0.14).
    The applied field is the command delayed by lat and AC-coupled (each phase high-passed with
    tau_ac), so a static field fades. Torque: kind 'v2' ~ |E|^2 sin(2 (psi_e - psi_r)),
    'lin' ~ |E| sin(psi_e - psi_r), psi_r = true_sign * m * theta + true_offset."""
    rng = rng or np.random.default_rng(0)
    w0 = 2 * np.pi * f0; dt = 1e-3
    th, om = np.radians(A0), 0.0
    n = int(T / dt); fr = int(round(frame / dt)); dl = int(round(lat / dt))
    cmd = [(0.0, 0.0)] * (dl + 1)                    # (x, y) of the commanded field, queue
    hp_prev_in = np.zeros(3); hp_out = np.zeros(3)
    ang = np.radians([0.0, -120.0, -240.0])
    out_t, out_th = [], []
    cur = (0.0, 0.0)
    for i in range(n):
        t = i * dt
        if lead_sched is not None:
            ctrl.lead = lead_sched(t)
        if i % fr == 0:
            meas = np.degrees(th) + rng.normal(0, noise)
            psi = math.radians(ctrl.update(t, meas))
            cur = (math.cos(psi), math.sin(psi))
            out_t.append(t); out_th.append(np.degrees(th))
        cmd.append(cur); x, y = cmd.pop(0)
        # three phase commands for field (x, y), then AC coupling per phase
        v_in = x * np.cos(ang) - y * np.sin(ang)       # cos(psi + phi_n)
        a = tau_ac / (tau_ac + dt)
        hp_out = a * (hp_out + v_in - hp_prev_in); hp_prev_in = v_in
        z = np.sum(hp_out * np.exp(-1j * ang)) * 2 / 3     # applied field phasor
        psi_e = np.angle(z); E = abs(z)
        psi_r = true_sign * m * th + np.radians(true_offset)
        tq = acc * (E ** 2 * np.sin(2 * (psi_e - psi_r)) if kind == 'v2' else E * np.sin(psi_e - psi_r))
        restore = -w0 ** 2 * (np.sin(th) if trap == 'pendulum' else th)
        om += (restore - w0 / Q * om + tq) * dt
        th += om * dt
    return np.array(out_t), np.array(out_th)


def amp_of(t, th, t0, t1):
    m = (t >= t0) & (t < t1); y = th[m] - th[m].mean()
    return np.sqrt(2) * y.std()


def selftest():
    ok = True
    def check(name, cond, detail):
        nonlocal ok; ok &= bool(cond)
        print('  %-58s %s  (%s)' % (name, 'PASS' if cond else 'FAIL', detail))
    print('feedback_drive selftest (simulated rotor, no EPICS)')
    # 1. matrix column: unit field, limits
    for psi in (0, 37, 120, 271):
        col = field_column(psi)
        z = sum(col[n] * np.exp(-1j * np.radians(PHI[n])) for n in PHI) * 2 / 3
        if abs(np.degrees(np.angle(z)) % 360 - psi) > 1e-6 and abs(abs(np.degrees(np.angle(z)) % 360 - psi) - 360) > 1e-6 or abs(abs(z) - 1) > 1e-9:
            check('field column points at psi with unit amplitude', False, 'psi %g -> %.3f deg, |z| %.4f' % (psi, np.degrees(np.angle(z)), abs(z))); break
    else:
        check('field column points at psi with unit amplitude', True, '4 angles')
    col0 = field_column(0)
    check('psi = 0 reproduces the forward drive matrix column 2', all(abs(col0[n] - MATRIX_FWD[n][1]) < 1e-9 for n in (1, 2, 3, 4)),
          'col %s' % {n: round(v, 3) for n, v in col0.items()})
    check('electrode command within 0..LIMIT at amp = pedestal = 6400', all(0 <= 6400 + 6400 * v <= LIMIT for p in range(0, 360, 5) for v in field_column(p).values()), '72 angles')
    check('amp 5000 on pedestal 6400: command within 1400..11400', all(1400 - 1e-9 <= 6400 + 5000 * v <= 11400 + 1e-9 for p in range(0, 360, 5) for v in field_column(p).values()), '72 angles')
    # 2. pumping: V^2 coupling, right sign, lead 45 grows a 5 deg swing
    t, th = simulate(Controller(lead=45), T=120)
    a0, a1 = amp_of(t, th, 0, 10), amp_of(t, th, 100, 120)
    check('V2 coupling, lead +45: 5 deg swing grows', a1 > 4 * a0, '%.1f -> %.1f deg' % (a0, a1))
    t, th = simulate(Controller(lead=-45), T=120, A0=30)
    a0, a1 = amp_of(t, th, 0, 10), amp_of(t, th, 100, 120)
    check('V2 coupling, lead -45: 30 deg swing damps', a1 < 0.5 * a0, '%.1f -> %.1f deg' % (a0, a1))
    t, th = simulate(Controller(lead=90), T=120, kind='lin')
    a0, a1 = amp_of(t, th, 0, 10), amp_of(t, th, 100, 120)
    check('linear coupling, lead +90: swing grows', a1 > 4 * a0, '%.1f -> %.1f deg' % (a0, a1))
    # 3. scan finds the pumping lead. Leads come in +/- pairs (both couplings are odd in lead), so
    #    the swing stays bounded and no step starts from rest. Start from a 20 deg swing.
    for kind, want in (('v2', (45, -135)), ('lin', (90,))):
        leads = SCAN_DEFAULT; dwell = 10.0
        t, th = simulate(Controller(lead=0), T=dwell * len(leads), A0=20, kind=kind,
                         lead_sched=lambda tt: leads[min(int(tt // dwell), len(leads) - 1)])
        growth = [amp_of(t, th, k * dwell + dwell - 3.03, k * dwell + dwell) - amp_of(t, th, k * dwell, k * dwell + 3.03) for k in range(len(leads))]
        best = leads[int(np.argmax(growth))]
        check('scan (%s coupling): largest growth at lead %s' % (kind, '/'.join(map(str, want))), best in want,
              'dA per 10 s step %s; best %d' % (' '.join('%d:%+.0f' % (l, g) for l, g in zip(leads, growth)), best))
    # 4. over the top and commutation, pendulum trap
    t, th = simulate(Controller(lead=45), T=300, A0=10, trap='pendulum')
    turns = (th[-1] - th[0]) / 360.0
    check('pendulum trap, lead 45: goes over the top, >= 10 turns in 300 s', abs(turns) >= 10, '%.1f turns' % turns)
    # 5. latency compensation matters at speed: same run with latency not compensated
    t2, th2 = simulate(Controller(lead=45, latency=0.0), T=300, A0=10, trap='pendulum')
    check('latency compensation needed to get over the top', abs((th2[-1] - th2[0]) / 360.0) < abs(turns),
          '%.1f turns compensated vs %.1f uncompensated' % (turns, (th2[-1] - th2[0]) / 360.0))
    # 6. dir hysteresis: a stationary noisy rotor does not chatter the field by 2*lead
    c = Controller(lead=45); rng = np.random.default_rng(1); psis = []
    for k in range(200):
        psis.append(c.update(k * 0.02, 10 + rng.normal(0, 0.1)))
    flips = np.sum(np.abs(np.diff(np.unwrap(np.radians(psis)))) > np.radians(60))
    check('no field flips on a still rotor with 0.1 deg noise', flips == 0, '%d flips in 200 frames' % flips)
    print('SELFTEST %s' % ('PASSED' if ok else 'FAILED'))
    return 0 if ok else 1


# ---------------------------------------------------------------------------------- hardware
def run(args):
    dry = not args.live
    if not dry:
        from epics import caget, caput
    else:
        caget = lambda pv, **k: 0.0
        caput = None

    def put(pv, val, wait=True, echo=True):
        if echo:
            print(f'    {"[dry] " if dry else ""}{pv:<34} <- {val:g}')
        if not dry:
            caput(pv, float(val), wait=wait, timeout=3.0)

    def fe_gps():
        return caget('Y1:DAQ-DC0_GPS') if not dry else float('nan')

    phases = (2, 3, 4)
    # The amp input must stay in 0..LIMIT: pedestal - amp >= 0 and pedestal + amp <= LIMIT.
    if args.amp <= 0 or args.pedestal < args.amp or args.pedestal + args.amp > LIMIT:
        sys.exit('! need 0 < amp <= pedestal and pedestal + amp <= %d (got amp %g, pedestal %g)' % (LIMIT, args.amp, args.pedestal))
    # ---- preflight
    g = [caget(f'{PREFIX}_DRV_SINGAIN'), caget(f'{PREFIX}_DRV_COSGAIN')]
    off = [caget(f'{PREFIX}_V{n}_OFFSET') for n in (1, 2, 3, 4)]
    if not dry and (any(abs(v or 0) > 1e-6 for v in g) or any(abs(v or 0) > 1e-6 for v in off)):
        sys.exit(f'! refusing: oscillator gains {g} / offsets {off} not all 0 (another drive running?)')
    before = {k: caget(f'{PREFIX}_{k}') for k in ('DRV_TRAMP', 'DRV_FREQ', 'DRVMTRX_TRAMP')}
    sw2_before = {n: int(caget(f'{PREFIX}_V{n}_SW2R') or 0) for n in (1, 2, 3, 4)}
    vtramp = {n: float(caget(f'{PREFIX}_V{n}_TRAMP') or 0) for n in (1, 2, 3, 4)}
    print('=' * 70)
    print(f'  feedback drive: lead {args.lead} elec deg, sign {args.sign}, m {args.m}, latency {args.latency} s')
    print(f'  amp {args.amp:g}, pedestal {args.pedestal:g} (range {args.pedestal - args.amp:g}..{args.pedestal + args.amp:g}); outputs {"ON" if args.enable_outputs else "OFF -- nothing reaches the chamber"}'
          f'; {"DRY RUN" if dry else "LIVE"}')
    print('=' * 70)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(('127.0.0.1', args.port)); sock.settimeout(0.05)
    os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)
    log = open(args.log, 'w', buffering=1)
    log.write('# feedback_drive.py %s\n' % ' '.join(sys.argv[1:]))
    log.write('host_time,frame,frame_host_time,angle_deg,ncc,w_dps,dir,lead,psi_deg,write_ms\n')
    ctrl = Controller(lead=args.lead, sign=args.sign, m=args.m, latency=args.latency, vmin=args.vmin)
    leads = (SCAN_DEFAULT if args.scan == 'default' else [float(v) for v in args.scan.split(',')]) if args.scan else [args.lead]
    brought_up = False
    try:
        # ---- bring-up: pedestal, outputs, frozen oscillator, field, gains
        print('\n  bring-up:')
        # Back-to-back, not waiting on each: in C2 sequential writes made the three pedestals
        # ramp up to 125 ms apart at 4 of 8 starts (an 11% differential field; analysis/c2_20261102).
        for n in phases:
            put(f'{PREFIX}_V{n}_OFFSET', args.pedestal, wait=False)
        if args.enable_outputs:
            for n in phases:
                if not sw2_before[n] & SW2_OUTPUT_ON:
                    put(f'{PREFIX}_V{n}_SW2S', sw2_before[n] | SW2_OUTPUT_ON)
        brought_up = True
        if not dry:
            w = max(vtramp[n] for n in phases) + 1.0
            print(f'    waiting {w:.0f} s for the pedestal ramp'); time.sleep(w)
        put(f'{PREFIX}_DRV_TRAMP', 0)
        put(f'{PREFIX}_DRV_FREQ', 0)
        if not dry:
            time.sleep(1.1)          # FREQ applies at the next FE GPS second (cdsOsc), phase 0 -> COS = gain
        put(f'{PREFIX}_DRV_SINGAIN', 0)
        put(f'{PREFIX}_DRVMTRX_TRAMP', 0)
        for n in (1, 2, 3, 4):
            put(f'{MTRX}_SETTING_{n}_1', 0)
        # No gain until the tracker is heard: the first field points from a fresh angle.
        psi0 = 0.0
        if not dry:
            t_wait = time.time()
            while True:
                if time.time() - t_wait > 5.0:
                    raise RuntimeError('no fresh angle from the tracker in 5 s (is live_blob_track.py '
                                       f'running with --publish 127.0.0.1:{args.port}?) -- gains never applied')
                try:
                    k, ht, ang, ncc = sock.recv(256).decode().split(',')
                except socket.timeout:
                    continue
                if time.time() - float(ht) < 0.1:
                    psi0 = ctrl.update(float(ht), float(ang)); break
            print(f'    tracker heard: angle {float(ang):.1f} deg, ncc {float(ncc):.2f}; first field psi {psi0:.1f}')
        col = field_column(psi0)
        for n in (1, 2, 3, 4):
            put(f'{MTRX}_SETTING_{n}_2', col[n])
        put(f'{MTRX}_LOAD_MATRIX', 1)
        put(f'{PREFIX}_DRV_TRAMP', args.gain_ramp)
        put(f'{PREFIX}_DRV_COSGAIN', args.amp)
        put(f'{PREFIX}_DRVON', 1)
        fe0, h0 = fe_gps(), time.time()
        log.write('# loop_start host_time %.6f fe_gps %.0f\n' % (h0, fe0))
        print(f'  loop start, front-end GPS {fe0:.0f}; listening on udp 127.0.0.1:{args.port}')
        if dry:
            print('  [dry] would now update SETTING_{2,3,4}_2 + LOAD_MATRIX once per received angle')
            return
        # ---- loop
        t_start = time.time(); last_fresh = time.time(); low = 0; k_lead = 0; t_lead = t_start; last_write = 0.0
        ctrl.lead = leads[0]; print(f'    lead {ctrl.lead:g}')
        while True:
            now = time.time()
            if now - t_start >= args.duration * (len(leads) if args.scan else 1):
                print('  end of run'); break
            if args.scan and now - t_lead >= args.dwell and k_lead + 1 < len(leads):
                k_lead += 1; t_lead = now; ctrl.lead = leads[k_lead]
                print(f'    lead {ctrl.lead:g}  (front-end GPS {fe_gps():.0f})')
            if now - last_fresh > args.stale:
                print(f'! watchdog: no fresh angle for {now - last_fresh:.2f} s'); break
            try:
                pkt = sock.recv(256)
            except socket.timeout:
                continue
            now = time.time()                       # after the (up to 50 ms) blocking recv
            k, ht, ang, ncc = pkt.decode().split(',')
            k, ht, ang, ncc = int(k), float(ht), float(ang), float(ncc)
            if now - ht > 0.1:                      # backlog / stale frame: skip
                continue
            last_fresh = now
            low = low + 1 if ncc < args.ncc_min else 0
            if low >= 5:
                print(f'! watchdog: ncc < {args.ncc_min} for 5 frames'); break
            psi = ctrl.update(ht, ang)              # every frame: keeps the velocity fit current
            if args.rate > 0 and now - last_write < 1.0 / args.rate:
                continue                            # paced: write at most --rate times per second
            last_write = now
            col = field_column(psi)
            w = not args.no_wait                    # wait for each write to complete (back-pressure)
            t_w0 = time.time()
            for n in phases:
                put(f'{MTRX}_SETTING_{n}_2', col[n], wait=w, echo=False)
            if args.load_toggle:                    # in case LOAD_MATRIX acts only on a 0 -> 1 edge
                put(f'{MTRX}_LOAD_MATRIX', 0, wait=w, echo=False)
            put(f'{MTRX}_LOAD_MATRIX', 1, wait=w, echo=False)
            log.write('%.6f,%d,%.6f,%.3f,%.3f,%.2f,%d,%g,%.3f,%.2f\n' % (time.time(), k, ht, ang, ncc, ctrl.w, ctrl.dir, ctrl.lead, psi,
                                                                       1e3 * (time.time() - t_w0)))
    except KeyboardInterrupt:
        print('\n  Ctrl-C')
    except RuntimeError as e:
        print(f'\n! {e}')
    finally:
        if brought_up and not dry:
            print(f'\n  stopping (front-end GPS {fe_gps():.0f}):')
            put(f'{PREFIX}_DRV_TRAMP', args.gain_ramp)
            put(f'{PREFIX}_DRV_SINGAIN', 0); put(f'{PREFIX}_DRV_COSGAIN', 0)
            time.sleep(args.gain_ramp + 1.0)
            put(f'{PREFIX}_DRVON', 0)
            put(f'{PREFIX}_DRVMTRX_TRAMP', 2)
            for n, (s_, c_) in MATRIX_FWD.items():
                put(f'{MTRX}_SETTING_{n}_1', s_); put(f'{MTRX}_SETTING_{n}_2', c_)
            put(f'{MTRX}_LOAD_MATRIX', 1)
            time.sleep(4.5)
            put(f'{PREFIX}_DRVMTRX_TRAMP', before['DRVMTRX_TRAMP'] or 2)
            put(f'{PREFIX}_DRV_TRAMP', before['DRV_TRAMP'] or 5)
            for n in phases:
                put(f'{PREFIX}_V{n}_OFFSET', 0, wait=False)
            w = max(float(caget(f'{PREFIX}_V{n}_TRAMP') or 0) for n in phases) + 1.0
            time.sleep(w)
            for n in phases:
                cur = int(caget(f'{PREFIX}_V{n}_SW2R') or 0)
                want = (cur & ~SW2_OUTPUT_ON) | (sw2_before[n] & SW2_OUTPUT_ON)
                if want != cur:
                    put(f'{PREFIX}_V{n}_SW2S', want)
            offs = [caget(f'{PREFIX}_V{n}_OFFSET') for n in phases]
            print(f'  offsets now {offs}; front-end GPS {fe_gps():.0f}; log {args.log}')
        log.close()


def run_frontend(args):
    """Mode 'frontend': the y1rds commutation block (lab_utils/rcg/commutate.c, after the model change)
    points the field; worker2 only reports the camera angle. Each frame it writes TFRAME (host time of the frame),
    THETA (unwrapped deg), OMEGA (deg/s), ALPHA (deg/s^2) and SEQ to Y1:RDS-OUTS_COMM_*. Settings: M, SIGN, LEAD, LATENCY, WDOG,
    VMIN, AMP. Start: pedestal (back-to-back), outputs (if --enable-outputs), DRVON 1, first fresh angle,
    COMMSEL 1, AMP, ENABLE 0 -> 1 (re-arms the front-end watchdog). Stop: ENABLE 0 (the block ramps its gain
    to 0 in 0.5 s), COMMSEL 0, AMP 0, DRVON 0, pedestal down, then outputs restored. Oscillator gains are
    not touched (they must be 0: preflight)."""
    dry = not args.live
    if not dry:
        from epics import caget, caput
    else:
        caget = lambda pv, **k: 0.0
        caput = None
    C = f'{PREFIX}_COMM'

    def put(pv, val, wait=True, echo=True):
        if echo:
            print(f'    {"[dry] " if dry else ""}{pv:<34} <- {val:g}')
        if not dry:
            caput(pv, float(val), wait=wait, timeout=3.0)

    def fe_gps():
        return caget('Y1:DAQ-DC0_GPS') if not dry else float('nan')

    phases = (2, 3, 4)
    # The amp input must stay in 0..LIMIT: pedestal - amp >= 0 and pedestal + amp <= LIMIT.
    if args.amp <= 0 or args.pedestal < args.amp or args.pedestal + args.amp > LIMIT:
        sys.exit('! need 0 < amp <= pedestal and pedestal + amp <= %d (got amp %g, pedestal %g)' % (LIMIT, args.amp, args.pedestal))
    if not dry and caget(f'{C}_THETA') is None:
        sys.exit(f'! {C}_THETA not found: the commutation model change is not installed')
    g = [caget(f'{PREFIX}_DRV_SINGAIN'), caget(f'{PREFIX}_DRV_COSGAIN')]
    off = [caget(f'{PREFIX}_V{n}_OFFSET') for n in (1, 2, 3, 4)]
    if not dry and (any(abs(v or 0) > 1e-6 for v in g) or any(abs(v or 0) > 1e-6 for v in off)):
        sys.exit(f'! refusing: oscillator gains {g} / offsets {off} not all 0 (another drive running?)')
    sw2_before = {n: int(caget(f'{PREFIX}_V{n}_SW2R') or 0) for n in (1, 2, 3, 4)}
    vtramp = {n: float(caget(f'{PREFIX}_V{n}_TRAMP') or 0) for n in (1, 2, 3, 4)}
    print('=' * 70)
    print(f'  feedback drive, FRONT-END commutation: lead {args.lead}, sign {args.sign}, m {args.m}, '
          f'latency {args.latency} s, watchdog {args.wdog} s')
    print(f'  amp {args.amp:g}, pedestal {args.pedestal:g} (range {args.pedestal - args.amp:g}..{args.pedestal + args.amp:g}); outputs {"ON" if args.enable_outputs else "OFF -- nothing reaches the chamber"}'
          f'; {"DRY RUN" if dry else "LIVE"}')
    print('=' * 70)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(('127.0.0.1', args.port)); sock.settimeout(0.05)
    os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)
    log = open(args.log, 'w', buffering=1)
    log.write('# feedback_drive.py %s\n' % ' '.join(sys.argv[1:]))
    log.write('host_time,frame,frame_host_time,angle_deg,ncc,theta_sent,w_dps,a_dps2,seq,lead,write_ms\n')
    ctrl = Controller(lead=args.lead, sign=args.sign, m=args.m, latency=args.latency, vmin=args.vmin)
    leads = (SCAN_DEFAULT if args.scan == 'default' else [float(v) for v in args.scan.split(',')]) if args.scan else [args.lead]
    brought_up = False; seq = 0
    try:
        print('\n  bring-up:')
        put(f'{C}_ENABLE', 0); put(f'{PREFIX}_COMMSEL', 0); put(f'{C}_AMP', 0)
        for k, v in (('M', args.m), ('SIGN', args.sign), ('LEAD', leads[0]), ('LATENCY', args.latency),
                     ('WDOG', args.wdog), ('VMIN', args.vmin)):
            put(f'{C}_{k}', v)
        for n in phases:
            put(f'{PREFIX}_V{n}_OFFSET', args.pedestal, wait=False)
        if args.enable_outputs:
            for n in phases:
                if not sw2_before[n] & SW2_OUTPUT_ON:
                    put(f'{PREFIX}_V{n}_SW2S', sw2_before[n] | SW2_OUTPUT_ON)
        brought_up = True
        if not dry:
            w = max(vtramp[n] for n in phases) + 1.0
            print(f'    waiting {w:.0f} s for the pedestal ramp'); time.sleep(w)
        put(f'{PREFIX}_DRVON', 1)
        if dry:
            print('  [dry] would wait for a fresh angle, write THETA/OMEGA/ALPHA/SEQ, COMMSEL 1, AMP, ENABLE 0 -> 1,')
            print('        then write THETA/OMEGA/ALPHA/SEQ once per received angle')
            return
        t_wait = time.time()
        while True:
            if time.time() - t_wait > 5.0:
                raise RuntimeError('no fresh angle from the tracker in 5 s -- commutation never enabled')
            try:
                k, ht, ang, ncc = sock.recv(256).decode().split(',')
            except socket.timeout:
                continue
            if time.time() - float(ht) < 0.1:
                ctrl.update(float(ht), float(ang)); break

        def send():
            nonlocal seq
            seq += 1
            # TFRAME: worker2 host time of the frame behind THETA (commutate.c argin[12], 2026-11-03), written
            # before THETA/SEQ so it has landed when the new update is detected.
            for kk, vv in (('TFRAME', ctrl.hist[-1][0]), ('THETA', ctrl.th), ('OMEGA', ctrl.w), ('ALPHA', ctrl.a), ('SEQ', seq)):
                put(f'{C}_{kk}', vv, echo=False)
        send()
        put(f'{PREFIX}_COMMSEL', 1); put(f'{C}_AMP', args.amp)
        put(f'{C}_ENABLE', 0); put(f'{C}_ENABLE', 1)
        fe0, h0 = fe_gps(), time.time()
        log.write('# loop_start host_time %.6f fe_gps %.0f\n' % (h0, fe0))
        print(f'  loop start, front-end GPS {fe0:.0f}; lead {leads[0]:g}')
        t_start = time.time(); last_fresh = time.time(); low = 0; k_lead = 0; t_lead = t_start; last_write = 0.0
        frozen = False; last_gain_print = 0.0
        while True:
            now = time.time()
            if now - t_start >= args.duration * (len(leads) if args.scan else 1):
                print('  end of run'); break
            if args.scan and now - t_lead >= args.dwell and k_lead + 1 < len(leads):
                k_lead += 1; t_lead = now; put(f'{C}_LEAD', leads[k_lead])
                print(f'    lead {leads[k_lead]:g}  (front-end GPS {fe_gps():.0f})')
            if now - last_fresh > args.stale:
                print(f'! watchdog: no fresh angle for {now - last_fresh:.2f} s'); break
            try:
                pkt = sock.recv(256)
            except socket.timeout:
                continue
            now = time.time()
            k, ht, ang, ncc = pkt.decode().split(',')
            k, ht, ang, ncc = int(k), float(ht), float(ang), float(ncc)
            if now - ht > 0.1:
                continue
            last_fresh = now
            low = low + 1 if ncc < args.ncc_min else 0
            if low >= 5:
                print(f'! watchdog: ncc < {args.ncc_min} for 5 frames'); break
            ctrl.update(ht, ang)
            if args.freeze_at and now - t_start >= args.freeze_at:
                if not frozen:
                    frozen = True
                    print(f'  FREEZE: stopped sending at {now - t_start:.1f} s (front-end GPS {fe_gps():.0f}); '
                          f'ENABLE left at 1 so the FRONT-END watchdog must cut the drive')
                if now - last_gain_print > 0.25:
                    last_gain_print = now
                    print(f'    COMM_GAIN {caget(f"{C}_GAIN")}  t {now - t_start:.2f} s')
                continue
            if args.rate > 0 and now - last_write < 1.0 / args.rate:
                continue
            last_write = now
            t_w0 = time.time(); send()
            log.write('%.6f,%d,%.6f,%.3f,%.3f,%.4f,%.3f,%.2f,%d,%g,%.2f\n' % (
                time.time(), k, ht, ang, ncc, ctrl.th, ctrl.w, ctrl.a, seq, leads[k_lead], 1e3 * (time.time() - t_w0)))
    except KeyboardInterrupt:
        print('\n  Ctrl-C')
    except RuntimeError as e:
        print(f'\n! {e}')
    finally:
        if brought_up and not dry:
            print(f'\n  stopping (front-end GPS {fe_gps():.0f}):')
            put(f'{C}_ENABLE', 0)
            time.sleep(1.0)                          # the block ramps its gain to 0 in 0.5 s
            put(f'{PREFIX}_COMMSEL', 0); put(f'{C}_AMP', 0)
            put(f'{PREFIX}_DRVON', 0)
            for n in phases:
                put(f'{PREFIX}_V{n}_OFFSET', 0, wait=False)
            w = max(float(caget(f'{PREFIX}_V{n}_TRAMP') or 0) for n in phases) + 1.0
            time.sleep(w)
            for n in phases:
                cur = int(caget(f'{PREFIX}_V{n}_SW2R') or 0)
                want = (cur & ~SW2_OUTPUT_ON) | (sw2_before[n] & SW2_OUTPUT_ON)
                if want != cur:
                    put(f'{PREFIX}_V{n}_SW2S', want)
            offs = [caget(f'{PREFIX}_V{n}_OFFSET') for n in phases]
            print(f'  offsets now {offs}; COMM_GAIN {caget(f"{C}_GAIN")}; front-end GPS {fe_gps():.0f}; log {args.log}')
        log.close()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        sys.exit(selftest())
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('mode', choices=['run', 'frontend'], help='run = EPICS matrix route; frontend = y1rds commutation block')
    p.add_argument('--lead', type=float, default=45.0, help='electrical degrees ahead along the motion')
    p.add_argument('--sign', type=int, default=-1, choices=[-1, 1])
    p.add_argument('--m', type=int, default=8)
    p.add_argument('--latency', type=float, default=0.04, help='s of prediction (camera to field)')
    p.add_argument('--vmin', type=float, default=6.0, help='deg/s hysteresis for the motion direction')
    p.add_argument('--amp', type=float, default=6400.0, help='drive amplitude, counts')
    p.add_argument('--pedestal', type=float, default=6400.0, help='V{n}_OFFSET pedestal, counts (needs amp <= pedestal, pedestal + amp <= 12800)')
    p.add_argument('--duration', type=float, default=60.0, help='s (per lead when --scan)')
    p.add_argument('--scan', default='', help='comma list of leads, each held --dwell s; "default" = 45,-45,90,-90,135,-135,0,180')
    p.add_argument('--dwell', type=float, default=10.0)
    p.add_argument('--gain-ramp', type=float, default=2.0)
    p.add_argument('--stale', type=float, default=0.25)
    p.add_argument('--ncc-min', type=float, default=0.8)
    p.add_argument('--port', type=int, default=5005)
    p.add_argument('--wdog', type=float, default=0.5, help='frontend: front-end watchdog, s without a new SEQ')
    p.add_argument('--freeze-at', type=float, default=0.0, help='frontend, OUTPUTS-OFF TEST ONLY: stop sending after S s but keep ENABLE 1 (tests the front-end watchdog)')
    p.add_argument('--rate', type=float, default=None, help='max updates per second (0 = every frame; default 10 for run, 25 for frontend, above the 16 Hz EPICS tick). '
                   'F1 2026-11-02 at every frame (~50/s, no wait) measured a ~1.5-2.6 s delay')
    p.add_argument('--no-wait', action='store_true', help='send writes without waiting for completion (the F1 2026-11-02 mode)')
    p.add_argument('--load-toggle', action='store_true', help='write LOAD_MATRIX 0 then 1 each frame '
                   '(use if F1 sees only ~1 step: the record may act only on a 0 -> 1 edge)')
    p.add_argument('--log', default=os.path.expanduser('~/stator_detent/feedback_%d.csv' % int(time.time() - GPS_UNIX_OFF)))
    p.add_argument('--live', action='store_true')
    p.add_argument('--enable-outputs', action='store_true')
    args = p.parse_args()
    if args.scan:
        args.duration = args.dwell
    if args.freeze_at and args.enable_outputs:
        sys.exit('! --freeze-at is for the outputs-off watchdog test only')
    if args.rate is None:
        args.rate = 25.0 if args.mode == 'frontend' else 10.0
    run_frontend(args) if args.mode == 'frontend' else run(args)


if __name__ == '__main__':
    main()
