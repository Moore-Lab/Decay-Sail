import argparse
import time
import numpy as np
import os
import pyvisa
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

# data taking function 
def run_measurement(args):
    ''' Run one cycle'''
    pressures = []
    timestamps = []

    start_time = time.time()
    print('Starting new measurement...')

    while time.time() - start_time < args.pressure_duration:
        try:
            pressure = read_pressure(args.channel_name)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if not np.isnan(pressure):
                pressures.append(pressure)
                timestamps.append(timestamp)

            else:
                Print('Skipping invalid pressure reading...')

        except Exception as e:
            print('Skipping measurement. Error: ', e)
        
        time.sleep(args.sleep_time)

    print('Starting scope data acquisition...')
    scope_data = acquire_scope_data(args.scope_resource)

    # Create directory with today's date (YYYYMMDD)
    today = datetime.now().strftime('%Y%m%d')
    #os.makedirs(f'data/{today}', exist_ok=True) # might need to change due to windows convention
    daily_dir = os.path.join(args.output_dir, today)
    os.makedirs(daily_dir, exist_ok=True)

    # Generate filename with timestamp
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    #file_path = f'data/{today}/combined_data_{timestamp_str}.npz' # might need to change due to windows convention
    file_path = os.path.join(daily_dir, f'combined_data_{timestamp_str}.npz')

    # Save all data
    save_data(file_path, pressures, timestamps, scope_data)

    print('Measurement complete.')

    # found lockbutton on scope - probably don't need
    # try: 
    #     rm = pyvisa.ResourceManager()
    #     inst = rm.open_resource(args.scope_resource)
    #     inst.write("SYST:LOC") # return scope to manual mode after measurements
    #     inst.close()
    #     rm.close()
    #     print('Scope returned to manual mode')
    # except Exception as e:
    #     print('Could not return to manual mode dure to error: ', e)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Read out pressure and acquire oscilloscope data')
    parser.add_argument('--channel_name', type=str, default='COM6', help='Serial port for pressure gauge')
    parser.add_argument('--scope_resource', type=str, default='USB0::0x0AAD::0x01D6::102215::INSTR', help='PyVISA resource string for oscilloscope')
    parser.add_argument('--sleep_time', type=float, default=0.33, help='Time between pressure readings (seconds)')
    parser.add_argument('--pressure_duration', type=int, default=15, help='Duration for pressure data collection (seconds)')
    parser.add_argument('--output_dir', type=str, default='data', help='Output directory for data files')
    parser.add_argument('--continuous', action='store_true', help='Run measurement continuously')
    args = parser.parse_args()
    
    print('Starting measurement... Press Ctrl+C to stop')

    try:
        if args.continuous:
            while True:
                run_measurement(args)
        else:
            run_measurement(args)

    except KeyboardInterrupt:
        print('Measurement stopped by user')
    except Exception as e:
        print(f'Error during measurement: {e}')
