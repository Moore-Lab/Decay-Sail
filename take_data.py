import argparse
import time
import numpy as np
from datetime import datetime
from ReadPressure import read_pressure
from RS_RTB2004_scope import acquire_scope_data

def save_data(file_path, pressures, timestamps, scope_data):
    """
    Saves pressure readings and scope data in a single .npz file.
    """
    save_dict = {
        'pressure': np.array(pressures),
        'pressure_timestamps': np.array(timestamps),
        **scope_data  # Merge scope data
    }
    np.savez(file_path, **save_dict)
    print(f"Data saved to {file_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Read out pressure and acquire oscilloscope data")
    
    parser.add_argument('--channel_name', type=str, default='COM6', 
                        help='Serial port for pressure gauge')
    parser.add_argument('--scope_resource', type=str, 
                        default='USB0::0x0AAD::0x01D6::102215::INSTR', 
                        help='PyVISA resource string for oscilloscope')
    parser.add_argument('--sleep_time', type=float, default=0.33, 
                        help='Time between pressure readings (seconds)')
    parser.add_argument('--pressure_duration', type=int, default=15, 
                        help='Duration for pressure data collection (seconds)')

    args = parser.parse_args()

    pressures = []
    timestamps = []

    print("Starting pressure measurement...")

    start_time = time.time()
    try:
        while time.time() - start_time < args.pressure_duration:
            pressure = read_pressure(args.channel_name)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print(f"Pressure: {pressure} at {timestamp}")

            pressures.append(pressure)
            timestamps.append(timestamp)

            time.sleep(args.sleep_time)
    except Exception as e:
        print(f"Error reading pressure: {e}")

    print("Starting oscilloscope data acquisition...")
    scope_data = acquire_scope_data(args.scope_resource)

    # Generate filename with timestamp
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = f"data/combined_data_{timestamp_str}.npz"

    # Save all data
    save_data(file_path, pressures, timestamps, scope_data)