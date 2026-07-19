"""Continuous vacuum-gauge pressure logger for the Linux DAQ machine.

Replaces the Windows-era ReadPressure.py workflow: same gauge, same serial
protocol (?GA1 query at 9600 8N1, float reply), but runs as a long-lived
logger writing timestamped daily CSVs instead of one-shot reads. Plain
pyserial -- no VISA/NI stack needed (visausb.py is not required for this).

Bring-up on a new machine:
    python3 log_pressure.py --list-ports          # find the gauge's device path
    python3 log_pressure.py --once --port <path>  # single test read, prints raw + parsed
    python3 log_pressure.py --port <path>         # start logging (Ctrl-C to stop)

Notes:
  - Prefer the /dev/serial/by-id/... path over /dev/ttyUSB0 -- it is stable
    across replugs and reboots.
  - If you get a permissions error on the port:  sudo usermod -a -G dialout $USER
    (then log out and back in).
  - Each CSV row keeps the raw reply string alongside the parsed float, so a
    protocol surprise shows up in the log instead of being silently mangled.
"""

import argparse
import csv
import glob
import os
import re
import sys
import time
from datetime import datetime, timezone

import serial

DEFAULT_INTERVAL_S = 10.0
DEFAULT_OUT_DIR = os.path.expanduser("~/pressure_logs")
QUERY = b"?GA1\r"
BAUD = 9600
READ_TIMEOUT_S = 1.0
RECONNECT_WAIT_S = 5.0

# Matches scientific or plain decimal notation anywhere in the reply
FLOAT_RE = re.compile(r"[-+]?\d+\.?\d*(?:[Ee][-+]?\d+)?")


def candidate_ports():
    ports = sorted(glob.glob("/dev/serial/by-id/*"))
    ports += sorted(glob.glob("/dev/ttyUSB*"))
    return ports


def open_gauge(port):
    return serial.Serial(port, baudrate=BAUD, bytesize=serial.EIGHTBITS,
                         parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                         timeout=READ_TIMEOUT_S)


def read_pressure(gauge):
    """One query. Returns (raw_reply_str, parsed_float_or_None)."""
    gauge.reset_input_buffer()
    gauge.write(QUERY)
    raw = gauge.read_until(b"\r")
    if not raw:
        # one retry, matching the old ReadPressure.py behavior
        time.sleep(0.5)
        gauge.write(QUERY)
        raw = gauge.read_until(b"\r")
    raw_str = raw.decode(errors="replace").strip()
    m = FLOAT_RE.search(raw_str)
    return raw_str, (float(m.group(0)) if m else None)


def csv_path(out_dir, when_utc):
    return os.path.join(out_dir, f"pressure_{when_utc.strftime('%Y%m%d')}.csv")


def append_row(out_dir, when_utc, raw_str, value):
    path = csv_path(out_dir, when_utc)
    new_file = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["utc_iso", "unix_s", "pressure", "raw_reply"])
        w.writerow([when_utc.isoformat(), f"{when_utc.timestamp():.3f}",
                    "" if value is None else f"{value:.4e}", raw_str])
    return path


def log_forever(port, interval_s, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    gauge = None
    n_ok = n_bad = 0
    print(f"Logging {port} every {interval_s:.0f} s -> {out_dir}  (Ctrl-C to stop)")
    try:
        while True:
            t_loop = time.monotonic()
            now = datetime.now(timezone.utc)
            try:
                if gauge is None or not gauge.is_open:
                    gauge = open_gauge(port)
                    print(f"[{now:%H:%M:%S}] serial port open")
                raw_str, value = read_pressure(gauge)
            except (serial.SerialException, OSError) as e:
                print(f"[{now:%H:%M:%S}] serial error: {e} -- reconnecting in "
                      f"{RECONNECT_WAIT_S:.0f} s", file=sys.stderr)
                try:
                    if gauge is not None:
                        gauge.close()
                except Exception:
                    pass
                gauge = None
                time.sleep(RECONNECT_WAIT_S)
                continue

            append_row(out_dir, now, raw_str, value)
            if value is None:
                n_bad += 1
                print(f"[{now:%H:%M:%S}] unparseable reply: {raw_str!r}",
                      file=sys.stderr)
            else:
                n_ok += 1
                if n_ok % 60 == 1:   # a heartbeat line every ~10 min at 10 s cadence
                    print(f"[{now:%H:%M:%S}] p = {value:.3e}  "
                          f"({n_ok} ok / {n_bad} bad since start)")

            time.sleep(max(0.0, interval_s - (time.monotonic() - t_loop)))
    except KeyboardInterrupt:
        print(f"\nStopped. {n_ok} good readings, {n_bad} bad, last file: "
              f"{csv_path(out_dir, datetime.now(timezone.utc))}")
    finally:
        if gauge is not None and gauge.is_open:
            gauge.close()


def main():
    ap = argparse.ArgumentParser(description="Continuous vacuum-gauge CSV logger")
    ap.add_argument("--port", help="serial device (prefer /dev/serial/by-id/...)")
    ap.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S,
                    help=f"seconds between polls (default {DEFAULT_INTERVAL_S:.0f})")
    ap.add_argument("--outdir", default=DEFAULT_OUT_DIR,
                    help=f"output directory (default {DEFAULT_OUT_DIR})")
    ap.add_argument("--once", action="store_true",
                    help="single test reading: print raw + parsed, no CSV")
    ap.add_argument("--list-ports", action="store_true",
                    help="list candidate serial ports and exit")
    args = ap.parse_args()

    if args.list_ports:
        ports = candidate_ports()
        if not ports:
            print("No candidate serial ports found (is the USB adapter plugged in?)")
        for p in ports:
            print(p)
        return

    if not args.port:
        ports = candidate_ports()
        if len(ports) == 1:
            args.port = ports[0]
            print(f"Auto-selected only candidate port: {args.port}")
        else:
            ap.error("--port required (run --list-ports to see candidates)")

    if args.once:
        gauge = open_gauge(args.port)
        try:
            raw_str, value = read_pressure(gauge)
        finally:
            gauge.close()
        print(f"raw reply : {raw_str!r}")
        print(f"parsed    : {value}")
        sys.exit(0 if value is not None else 1)

    log_forever(args.port, args.interval, args.outdir)


if __name__ == "__main__":
    main()
