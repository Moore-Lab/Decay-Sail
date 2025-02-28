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

# import pyvisa
# import numpy as np
# import matplotlib.pyplot as plt
# import time
# from datetime import datetime
# import random

# # Make sure device is set to USB-TMC mode before running

# # User input pressure
# pressure = "1000_mbar"

# # Initialize resource manager 
# rm = pyvisa.ResourceManager()
# print(rm)

# # Connect to device
# resource_string = 'USB0::0x0AAD::0x01D6::102215::INSTR'  # USB-TMC
# inst = rm.open_resource(resource_string)

# inst.timeout = 5000

# # Following example in ROHDE & SCHWARZ R&S RTB2004 USER MANUAL
# # Reset and clear to default settings
# inst.write('*RST')

# # Enable channels and set scales
# # channel 1: X; channel 2: Y; channel 3: SUM; channel 4: arb function generator
# channels = {1: 1e-1, 2: 1e-1, 3: 5e-1, 4: 5e-1}
# for ch, scale in channels.items():
#     inst.write(f'CHAN{ch}:STAT ON')
#     inst.write(f'CHAN{ch}:SCAL {scale:.1e}')

# # Set time scale and data format
# time_scale = 5
# inst.write(f'TIM:SCAL {time_scale:.3e}')
# inst.write('FORM:DATA ASC,0')

# # Set data points to default and start acquisition
# inst.write('CHAN:DATA:POIN DMAX') #('CHAN:DATA:POIN DEF') # 
# inst.write('SING;*OPC?')

# # Wait for acquisition to complete
# # Set time for data aquisition
# time.sleep(12 * time_scale)
# for _ in range(10):
#     time.sleep(1)
#     status = inst.query('ACQ:STAT?')
#     if status == 'COMP':
#         break

# # Retrieve the header and time vector
# header = inst.query('CHAN:DATA:HEAD?').strip().split(',')
# time_vec = np.linspace(float(header[0]), float(header[1]), int(header[2]))

# # Retrieve data for each channel
# data_list = {}
# for ch in channels.keys():
#     data = inst.query(f'CHAN{ch}:DATA?').strip()
#     data_list[ch] = np.array(data.split(','), dtype=float)

# # Time for labelling files
# timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Format: YYYYMMDD_HHMMSS

# # Dynamically create the file name
# file_name = f"{pressure}_scope_data_sample_pulse_{timestamp}.npz"

# # Save the data with the dynamically generated file name
# np.savez(file_name, **{f'channel_{ch}': data for ch, data in data_list.items()}, t=time_vec)

# Plot the data
# plt.figure()
# for ch, data in data_list.items():
#     plt.plot(time_vec, data, label=f'Channel {ch}')
# plt.legend()
# plt.show()
