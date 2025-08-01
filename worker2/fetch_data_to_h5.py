import h5py
import numpy as np
import nds2
import time
from datetime import datetime

CHANNEL = 'Y1:RDS-LES_YAW_MON_OUT_DQ' # specify the channel to fetch data from
DURATION = 60 * 60  # Fetch data for 1 hour (3600 seconds)
USE_END_Now = True  # Use current time as end time

# TIME
# If USE_END_Now is True, use current time as end time
if USE_END_Now:
    gps_end = int(time.time())  # Current time as end time
else:
    gps_end = 1700000000 # Example fixed end time - change as needed

# Fetching duration and end time
gps_start = gps_end - DURATION  # Start time is whatever duration before end time

# Open NDS2 connection
conn = nds2.connection ('cymac1', 8088)
conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')

print('Channel:', CHANNEL, type(CHANNEL))
print('Start time:', gps_start, 'End time:', gps_end)
print('Duration:', DURATION, 'seconds')

# FETCH data: buffers are used to store RAW data
buffers = conn.fetch(CHANNEL, gps_start, gps_end)  # Adjust start and end times as needed
if not buffers:
    print(f"No data found for {CHANNEL} between {gps_start} and {gps_end}.")
else:
    print(f"Fetching data from {CHANNEL} between {gps_start} and {gps_end}.")

# combine the buffers into a single array
data = np.concatenate([buffer['data'] for buffer in buffers])
sample_rate = buffers[0]['sample_rate'] if buffers else None
       
# timestamps for the data
timestamps = []
for buf in buffers:
    t0 = buf.seconds + buf.nanoseconds * 1e-9
    dt = 1.0 / buf['sample_rate']
    timestamps.extend(t0 + k * dt for k in range(len(buf['data'])))
    #timestamps.extend(np.arange(t0, t0 + dt * len(buf['data']), dt))
timestamps = np.array(timestamps)

# Create HDF5 file
#filename = f'yaw_data_{int(time.time())}.hdf5'
filename = f"{CHANNEL.replace(':', '_')}_{gps_start}_{gps_end}.hdf5"
with h5py.File(filename, 'w') as f:
    f.attrs['channel'] = CHANNEL
    f.attrs['gps_start'] = gps_start
    f.attrs['gps_end'] = gps_end
    f.attrs['sample_rate'] = sample_rate
    f.attrs['data_length'] = len(data)
    f.attrs['unit'] = 'undefined'  # Specify unit if known
    f.attrs['created_utc'] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    f.attrs['created_local'] = datetime.now().isoformat()
    
    # Datasets
    f.create_dataset('data', data=data)
    f.create_dataset('timestamps', data=timestamps)

print(f"Saved {len(data)} samples at {sample_rate} Hz to {filename}")
    

