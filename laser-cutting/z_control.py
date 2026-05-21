"""
Z-stage controller for the laser cutter (Adafruit Motor Shield v2 + Uno).

Two ways to use:
  1) Interactive REPL:    python z_control.py
  2) Single command:      python z_control.py "Z 0.1"
                          python z_control.py "+50"
                          python z_control.py "?"

Commands forwarded to the Arduino:
  +N    step +N        -N    step -N
  Z<f>  move <f> mm (signed, e.g. Z0.1, Z-0.05)
  R     release coils
  S<n>  set RPM (1-300)
  ?     print status
"""

import os
import sys
import time
import serial
from serial.tools import list_ports

# Arduino Uno USB IDs (covers both arduino.cc and arduino.org boards).
_ARDUINO_VIDS = {0x2341, 0x2A03, 0x1A86}

BAUD = 115200


def find_port():
    """Locate the Arduino's serial port.

    Order of preference:
      1) Z_PORT environment variable (explicit override)
      2) A connected device with a known Arduino USB vendor ID
      3) The single available port, if there's exactly one
    """
    env = os.environ.get("Z_PORT")
    if env:
        return env
    ports = list(list_ports.comports())
    for p in ports:
        if p.vid in _ARDUINO_VIDS:
            return p.device
    if len(ports) == 1:
        return ports[0].device
    raise RuntimeError(
        "Could not auto-detect the Arduino port. "
        "Set the Z_PORT environment variable (e.g. Z_PORT=COM3)."
    )


PORT = find_port()


def open_port(port=None, baud=BAUD):
    if port is None:
        port = PORT
    ser = serial.Serial(port, baud, timeout=2)
    time.sleep(2.0)  # Uno resets on serial open; wait for sketch to boot
    ser.reset_input_buffer()
    return ser


def send(ser, cmd, wait=0.1):
    """Send a command and print any response lines."""
    ser.write((cmd.strip() + "\n").encode())
    ser.flush()
    time.sleep(wait)
    # Read whatever's available
    out = []
    deadline = time.time() + 5.0
    while time.time() < deadline:
        line = ser.readline().decode(errors="replace").strip()
        if not line:
            if out:
                break
            continue
        out.append(line)
        if line.startswith("OK") or line.startswith("ERR") or line.startswith("STATUS"):
            # one more tiny grace period in case there's a trailing line
            time.sleep(0.05)
            while ser.in_waiting:
                extra = ser.readline().decode(errors="replace").strip()
                if extra:
                    out.append(extra)
            break
    for line in out:
        print(line)
    return out


def repl():
    ser = open_port()
    print(f"Connected to {PORT} @ {BAUD}. Ctrl-D / Ctrl-C to quit.")
    # Drain READY banner
    time.sleep(0.2)
    while ser.in_waiting:
        line = ser.readline().decode(errors="replace").strip()
        if line:
            print("<", line)
    while True:
        try:
            cmd = input("z> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not cmd:
            continue
        if cmd in ("q", "quit", "exit"):
            break
        send(ser, cmd)
    ser.close()


def main():
    if len(sys.argv) > 1:
        cmd = " ".join(sys.argv[1:])
        ser = open_port()
        send(ser, cmd)
        ser.close()
    else:
        repl()


if __name__ == "__main__":
    main()
