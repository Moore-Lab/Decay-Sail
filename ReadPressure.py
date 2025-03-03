import serial
import time

def read_pressure(ed):
    """
    Reads the current pressure from the gauge and returns it as a float.
    """
    ED = serial.Serial(ed, baudrate=9600, bytesize=serial.EIGHTBITS,
                       parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=1)

    ED.write(str.encode("?GA1\r"))  # Query the gauge
    current_pressure = ED.readlines()

    if len(current_pressure) > 0:
        current_pressure = str(current_pressure[0])
        current_pressure = float(current_pressure[2:-3])
    else:
        time.sleep(0.5)
        ED.write(str.encode("?GA1\r"))  # Retry
        current_pressure = ED.readlines()

        current_pressure = str(current_pressure[0])
        current_pressure = float(current_pressure[2:-3])

    ED.close()
    return current_pressure