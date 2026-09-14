#!/usr/bin/env python3
"""Laser power step-down with a programmatic settled-check AND a rotation->libration
transition trigger.

Per the 2026-09-14 plan (`laser_stepdown_next_run_plan.md`) and the transition analysis:

  ROTATION regime -- at each commanded offset, wait ~1 tau then re-check settling
  every ~25 min up to a hard ceiling (~4 tau); stop waiting and FLAG rather than
  loop forever. Settling = `settled_check.check_settled` on the last 20 min of LES_YAW.

  TRANSITION -- the frequency track cannot be trusted once the rotor leaves clean
  rotation. We detect the FIRST transition three convergent ways (whichever fires
  first), reusing the thresholds validated in `analysis/spindown_20260913.ipynb`:
      * SNR of the LES line drops below SNR_MIN (line dying)
      * waveform kurtosis rises above KURT_ROT (sinusoid -> cusped, i.e. libration)
      * the tracked frequency RISES above its running minimum by RISE_FRAC
        (a freely coasting / power-decreasing rotor cannot speed up)
  We only trust the FIRST such transition (per the notebook) -- continuous
  rotation-vs-libration classification is NOT reliable and is not attempted.

  POST-ROTATION -- once the transition fires there is no steady state to settle to,
  so ON_TRANSITION='quick' switches to short fixed dwells (still logging f/SNR/kurt/
  amplitude every step) to step quickly toward 0; ON_TRANSITION='halt' stops and
  flags for a human/camera call instead.

Every step and every check is logged to a CSV. Run on worker2 (EPICS + NDS2 to
cymac1). Ctrl-C aborts and zeros the laser.
"""
import os, sys, time
import numpy as np
from datetime import datetime, timezone
from epics import caget, caput
import nds2
from scipy.stats import kurtosis as _kurtosis
from scipy.signal import butter, filtfilt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settled_check import check_settled, peak_in_band

# ----------------------------------------------------------------- channels
LASER        = 'Y1:RDS-OUTS_LASER'
OUTPUT_LASER = f'{LASER}_OFFSET'
LES_CH       = 'Y1:RDS-LES_YAW_IN1_DQ'
DAQ_GPS      = 'Y1:DAQ-DC0_GPS'
NDS_HOST, NDS_PORT = 'cymac1', 8088

# ----------------------------------------------------------------- STEP SCHEDULE
# EDIT ME. Coarse near the (already well-behaved) top, finer toward the low end.
# NOTE the calibration/torque have changed since July: 1300 counts = ~5.8 mW and
# ~0.75 Hz rotor now (vs 6.66 mW / 2.72 Hz then), so the sustaining-rotation
# threshold is likely much closer to 1300 -- start finer than 100-count steps.
OFFSET_VALUES = ([1300,                                  # baseline anchor (already settled)
                  1250, 1200, 1150, 1100, 1050]          # coarse 50-count, rotation regime
                 + list(range(1040, 790, -10)))          # fine 10-count, low/libration region
                                                         # (1040 -> 800). Reassess in the morning
                                                         # if the low end runs too slow.

# LIVE-EDITABLE schedule: OFFSET_VALUES above only SEEDS this file on startup; thereafter
# the script re-reads SCHEDULE_FILE before every step, so you can edit UPCOMING steps while
# it runs -- no restart, no re-spin-up. Edit only steps below the current one (the log prints
# "i=<n> offset=<x>"). A step UP (offset above the previous) is rejected -- this is a step-down.
SCHEDULE_FILE = 'laser_stepdown_schedule.txt'

# ----------------------------------------------------------------- settling policy
WINDOW_MIN      = 20.0            # LES window the check uses (matches settled_check)
INITIAL_WAIT_S  = 70 * 60        # ~1 tau before the first check
RECHECK_S       = 25 * 60        # re-check cadence
CEILING_S       = 340 * 60       # hard ceiling ~4 tau -> flag and move on
SETTLE_POLL_MIN_S = 30           # sleep granularity so Ctrl-C stays responsive

# ----------------------------------------------------------------- transition trigger
# thresholds from analysis/spindown_20260913.ipynb (validated there)
SNR_MIN    = 20.0                # line SNR below this = line dying
KURT_ROT   = -1.0               # kurtosis above this = leaving the sinusoid (rotation)
RISE_FRAC  = 0.02               # freq above running-min by this fraction = a rise
ON_TRANSITION   = 'quick'       # 'quick' (short dwells to 0) or 'halt' (stop + flag)
LIBRATION_DWELL_S = 25 * 60     # post-transition per-step dwell: long enough for a clean
                                # 20-min f_lib measurement window, well under the 70-min
                                # rotation wait (5 min was too short -- poor statistics)
_run_min_f = np.inf             # running minimum LES line freq across the whole run

# ----------------------------------------------------------------- pressure (manual)
PRESSURE_START = None            # gauge reading (mbar) before launch, logged once

# ----------------------------------------------------------------- logging
_gps0 = None
def _logpath():
    return os.path.join(os.getcwd(), f'laser_stepdown_log_gps{_gps0}.csv')

def log(msg, also_print=True):
    with open(_logpath(), 'a') as f:
        f.write(f'{int(time.time())},{msg}\n')
    if also_print:
        print(msg)

def gps_now():
    return int(caget(DAQ_GPS))

# ----------------------------------------------------------------- LES pull + diagnostics
def pull_les(conn, window_min=WINDOW_MIN):
    """Most recent `window_min` min of LES_YAW, ending at the latest flushed frame."""
    daq = gps_now()
    latest = None
    for back in range(4, 600, 4):
        t = daq - back
        try:
            b = conn.fetch(t - 2, t, [LES_CH])[0]
            if np.isfinite(b.data).any():
                latest = t; break
        except Exception:
            pass
    if latest is None:
        raise RuntimeError('no flushed LES_YAW frame within 600 s of DAQ-now')
    end, start = latest, latest - int(window_min * 60)
    ys, fs, t = [], None, start
    while t < end:
        stop = min(end, t + 300)
        b = conn.fetch(t, stop, [LES_CH])[0]
        if fs is None:
            fs = b.sample_rate
        ys.append(b.data.astype(float)); t = stop
    y = np.concatenate(ys)
    return y[np.isfinite(y)], fs, end

def rotation_diag(les, fs):
    """(f_line, snr, kurt) for the transition trigger. f_line = dominant LES line;
    kurt = shape of the high-passed decimated waveform (sinusoid ~ -1.4, cusp ~ +0.9)."""
    fline, snr = peak_in_band(les[-int(120 * fs):], fs, 0.1, 4.0)
    d = max(int(fs // 16), 1)
    m = (len(les) // d) * d
    y16 = les[:m].reshape(-1, d).mean(1)
    b, a = butter(4, 0.1 / (fs / d / 2), 'high')
    ku = float(_kurtosis(filtfilt(b, a, y16 - y16.mean())))
    return (fline if fline and fline > 0 else np.nan), snr, ku

def transition_reasons(f_line, snr, ku):
    """First-wins list of reasons the rotor has left clean rotation ([] = still rotating)."""
    global _run_min_f
    r = []
    if snr < SNR_MIN:
        r.append(f'SNR {snr:.1f}<{SNR_MIN}')
    if ku > KURT_ROT:
        r.append(f'kurt {ku:+.2f}>{KURT_ROT}')
    if np.isfinite(f_line) and np.isfinite(_run_min_f) and f_line > _run_min_f * (1 + RISE_FRAC):
        r.append(f'freq rose {f_line:.4f}>{_run_min_f:.4f}x{1+RISE_FRAC:g}')
    if np.isfinite(f_line):                       # update running min AFTER the rise test
        _run_min_f = min(_run_min_f, f_line)
    return r

# ----------------------------------------------------------------- settle loop
def wait_until_settled(conn, offset):
    """Returns (status, result) with status in {'settled','ceiling','transition'}.
    Evaluates the transition trigger on every check so we do not burn the full
    ceiling once the rotor has left rotation."""
    def _sleep(total):
        done = 0.0
        while done < total:
            dt = min(SETTLE_POLL_MIN_S, total - done)
            time.sleep(dt); done += dt

    log(f'step {offset}: initial wait {INITIAL_WAIT_S/60:.0f} min (~1 tau)')
    _sleep(INITIAL_WAIT_S)
    elapsed = INITIAL_WAIT_S
    while True:
        les, fs, gps = pull_les(conn)
        f_line, snr, ku = rotation_diag(les, fs)
        reasons = transition_reasons(f_line, snr, ku)
        res = check_settled(les, fs, f_line if np.isfinite(f_line) else 1.5, verbose=False)
        log(f'check,offset={offset},gps={gps},elapsed_min={elapsed/60:.0f},'
            f'f_line={f_line:.4f},snr={snr:.1f},kurt={ku:+.3f},run_min_f={_run_min_f:.4f},'
            f'n={res.get("n")},f_mean={res.get("f_mean")},slope_hz_s={res.get("slope_hz_per_s")},'
            f'slope_ok={res.get("slope_ok")},half_ok={res.get("half_ok")},'
            f'settled={res.get("pass")},transition={"|".join(reasons) if reasons else ""}')
        if reasons:
            log(f'step {offset}: >>> TRANSITION (left clean rotation): {"; ".join(reasons)} '
                f'(f_line {f_line:.4f}, snr {snr:.0f}, kurt {ku:+.2f})')
            return 'transition', res
        if res.get('pass'):
            log(f'step {offset}: SETTLED at {elapsed/60:.0f} min, f_line {res.get("f_mean"):.4f} Hz')
            return 'settled', res
        if elapsed >= CEILING_S:
            log(f'step {offset}: !! CEILING {CEILING_S/60:.0f} min, NOT settled -- moving on, flagged')
            return 'ceiling', res
        _sleep(RECHECK_S); elapsed += RECHECK_S

# ----------------------------------------------------------------- quick (post-transition) step
def quick_dwell(conn, offset):
    """Short fixed dwell used after the transition -- no settled-check, just log the
    state so the libration/optical-spring behaviour is captured on the way to 0."""
    def _sleep(total):
        done = 0.0
        while done < total:
            time.sleep(min(SETTLE_POLL_MIN_S, total - done)); done += min(SETTLE_POLL_MIN_S, total - done)
    log(f'step {offset}: POST-ROTATION quick dwell {LIBRATION_DWELL_S/60:.0f} min')
    _sleep(LIBRATION_DWELL_S)
    les, fs, gps = pull_les(conn)
    f_line, snr, ku = rotation_diag(les, fs)
    log(f'post,offset={offset},gps={gps},f_line={f_line:.4f},snr={snr:.1f},kurt={ku:+.3f},'
        f'amp_rms={les.std():.1f}')

# ----------------------------------------------------------------- shutdown
def safe_shutdown():
    caput(OUTPUT_LASER, 0, wait=True, timeout=3.0)
    log('ABORT: laser offset set to 0 for safe shutdown.')

# ----------------------------------------------------------------- live schedule file
def seed_schedule(path):
    """Write OFFSET_VALUES to the live-editable schedule file (overwrites on each run)."""
    with open(path, 'w') as f:
        f.write('# laser step-down schedule -- one offset (counts) per line.\n')
        f.write('# LIVE-EDITABLE: re-read before every step. Edit steps BELOW the current one\n')
        f.write('# (the log prints "i=<n> offset=<x>"). A step UP (> the previous) is rejected.\n')
        for v in OFFSET_VALUES:
            f.write(f'{v}\n')

def read_schedule(path):
    """Parse the schedule file into int offsets. Robust to comments, blanks and a
    mid-edit partial read (unparseable tokens are skipped). None if missing."""
    try:
        vals = []
        with open(path) as f:
            for line in f:
                s = line.split('#', 1)[0].strip()
                for tok in s.replace(',', ' ').split():
                    try:
                        vals.append(int(round(float(tok))))
                    except ValueError:
                        pass
        return vals
    except FileNotFoundError:
        return None

# ----------------------------------------------------------------- main
def main():
    global _gps0
    _gps0 = gps_now()
    initial = caget(OUTPUT_LASER)
    conn = nds2.connection(NDS_HOST, NDS_PORT)
    conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')
    conn.set_parameter('GAP_HANDLER', 'STATIC_HANDLER_NAN')

    log(f'# laser step-down start DAQ_GPS={_gps0} UTC={datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}')
    log(f'# initial offset {initial}  schedule {OFFSET_VALUES}')
    log(f'# transition thresholds SNR_MIN={SNR_MIN} KURT_ROT={KURT_ROT} RISE_FRAC={RISE_FRAC} '
        f'ON_TRANSITION={ON_TRANSITION}')
    log(f'# pressure_start_mbar {PRESSURE_START}')
    if PRESSURE_START is None:
        print('  (reminder: set PRESSURE_START before an unattended run)')

    seed_schedule(SCHEDULE_FILE)
    log(f'# live schedule file: {os.path.abspath(SCHEDULE_FILE)} -- edit UPCOMING steps here')
    print(f'  edit the schedule live at: {os.path.abspath(SCHEDULE_FILE)}')

    post_rotation = False
    prev_offset = float(initial)     # current laser level; enforce step-DOWN only
    step_i = 0
    try:
        while True:
            sched = read_schedule(SCHEDULE_FILE)
            if not sched:                       # unreadable/empty -> fall back to the seed
                sched = list(OFFSET_VALUES)
            if step_i >= len(sched):
                log('# schedule exhausted (no more steps in the file).')
                break
            offset = float(sched[step_i])

            # safety: reject a step UP -- a typo in the file must never raise laser power
            if offset > prev_offset + 0.5:
                log(f'i={step_i} offset={offset:.0f}: > previous {prev_offset:.0f} -- step UP '
                    f'REJECTED (this is a step-down). Skipping; fix the schedule file.')
                step_i += 1
                continue

            caput(OUTPUT_LASER, offset, wait=True, timeout=3.0)
            time.sleep(1.0)
            log(f'step,i={step_i},offset={offset:.0f},readback={caget(OUTPUT_LASER)},'
                f'gps={gps_now()},UTC={datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ}')

            if post_rotation:
                quick_dwell(conn, offset)
            else:
                status, res = wait_until_settled(conn, offset)
                if status == 'transition':
                    if ON_TRANSITION == 'halt':
                        log('*** TRANSITION + ON_TRANSITION=halt: stopping and flagging for a '
                            'human/camera call. Laser left at current offset. ***')
                        print('\n*** ROTATION ENDED -- halted. Check the rotor (camera) before continuing. ***')
                        break
                    log('*** TRANSITION: switching to POST-ROTATION quick-step mode toward 0. ***')
                    post_rotation = True
                    quick_dwell(conn, offset)   # give this step a quick dwell too
                else:
                    log(f'i={step_i} offset={offset:.0f}: done (status={status})')
            prev_offset = offset
            step_i += 1
        log('# schedule complete. RECORD END PRESSURE manually now.')
        print('\n*** RECORD THE END PRESSURE from the gauge now. ***')
    except KeyboardInterrupt:
        log('step-down stopped by user (Ctrl-C).')
        safe_shutdown()
    finally:
        log(f'# final offset {caget(OUTPUT_LASER)}; log at {_logpath()}')

if __name__ == '__main__':
    main()
