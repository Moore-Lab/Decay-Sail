import pyvisa
import numpy as np
import time

def acquire_scope_data(resource_string):
    """
    Acquires waveform data from the oscilloscope.
    Returns a dictionary with time vector and channel data.
    """
    rm = pyvisa.ResourceManager()
    inst = rm.open_resource(resource_string)
    inst.timeout = 5000

    # Reset oscilloscope
    inst.write('*RST')

    # Enable channels and set scales
    channels = {1: 1e-1, 2: 1e-1, 3: 5e-1, 4: 5e-1}
    for ch, scale in channels.items():
        inst.write(f'CHAN{ch}:STAT ON')
        inst.write(f'CHAN{ch}:SCAL {scale:.1e}')

    # Set time scale and format
    time_scale = 5
    inst.write(f'TIM:SCAL {time_scale:.3e}')
    inst.write('FORM:DATA ASC,0')

    # Set max data points and start acquisition
    inst.write('CHAN:DATA:POIN DMAX')
    inst.write('SING;*OPC?')

    # Wait for acquisition
    time.sleep(12 * time_scale)
    for _ in range(10):
        time.sleep(1)
        status = inst.query('ACQ:STAT?')
        if status.strip() == 'COMP':
            break

    # Retrieve time vector
    header = inst.query('CHAN:DATA:HEAD?').strip().split(',')
    time_vec = np.linspace(float(header[0]), float(header[1]), int(header[2]))

    # Retrieve data for each channel
    data_list = {f'channel_{ch}': np.array(inst.query(f'CHAN{ch}:DATA?').strip().split(','), dtype=float) 
                 for ch in channels.keys()}

    # Add time vector
    data_list['time'] = time_vec

    return data_list
