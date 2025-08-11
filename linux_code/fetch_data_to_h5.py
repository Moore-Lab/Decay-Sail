import h5py
import numpy as np
import nds2
import time
from datetime import datetime

# LIGO documentation about fetch function and gaps: https://git.ligo.org/nds/nds2-client/-/blob/master/swig/python/module/nds_python.i?ref_type=heads

CHANNEL = 'Y1:RDS-LES_YAW_MON_OUT_DQ' # specify the channel to fetch data from
DURATION = 60 * 60 * 24  # Fetch data for 1 day (86400 seconds)
GPS_UNIX_OFFSET = 315964800 # Offset from Unix time to GPS time (1970-01-01 to 1980-01-06)

# Add Unix time - might be easier than finding GPS start and end times manually

# Can look at GUI to find best GPS start and end times for data retrieval
gps_start = 1437852416 # Example fixed GPS start time (Jul 30th 2015) - change as needed
gps_end = gps_start + DURATION # or can give a specific end time

# Connect to NDS2 connection, retrieve data, and set parameters for gaps
conn = nds2.connection ('cymac1', 8088)
conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')
conn.set_parameter('GAP_HANDLER', 'STATIC_HANDLER_NAN')# fill gaps with NaNs

# Verify what’s set
print('ALLOW_DATA_ON_TAPE:', conn.get_parameter('ALLOW_DATA_ON_TAPE'))
print('GAP_HANDLER:', conn.get_parameter('GAP_HANDLER'))
print('Channel:', CHANNEL, type(CHANNEL))
print('Start time:', gps_start, 'End time:', gps_end)
print('Duration:', DURATION, 'seconds')

# FETCH data: buffers are used to store RAW data
buffers = conn.fetch(gps_start, gps_end, [CHANNEL,])  # Adjust start and end times as needed
if not buffers:
    print(f"No data found for {CHANNEL} between {gps_start} and {gps_end}.")
    exit()
else:
    print(f"Fetching data from {CHANNEL} between {gps_start} and {gps_end}.")

#buf = buffers[0]
# print(buf)
# print(dir(buf))
# combine the buffers into a single array
data = np.concatenate([buf.data for buf in buffers])
sample_rate = buffers[0].sample_rate
       
# timestamps for the data
timestamps = []
for buf in buffers:
    t0 = buf.gps_seconds + buf.gps_nanoseconds * 1e-9
    dt = 1.0 / buf.sample_rate
    timestamps.extend(t0 + k * dt for k in range(len(buf.data)))
    #timestamps.extend(np.arange(t0, t0 + dt * len(buf['data']), dt))
timestamps = np.array(timestamps)

# Drop gaps in data
valid = np.isfinite(data)
data = data[valid]
timestamps = timestamps[valid]

# Create HDF5 file
#filename = f'yaw_data_{int(time.time())}.hdf5'
filename = f"data/{CHANNEL.replace(':', '_')}_{gps_start}_{gps_end}.hdf5"
with h5py.File(filename, 'w') as f:
    f.attrs['channel'] = CHANNEL
    f.attrs['gps_start'] = gps_start
    f.attrs['gps_end'] = gps_end
    f.attrs['sample_rate'] = sample_rate
    f.attrs['data_length'] = len(data)
    #f.attrs['unit'] = 'undefined'  # Specify unit if known
    # f.attrs['created_utc'] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    # f.attrs['created_local'] = datetime.now().isoformat()
    
    # Datasets
    f.create_dataset('data', data=data)
    f.create_dataset('timestamps', data=timestamps)

print(f"Saved {len(data)} samples at {sample_rate} Hz to {filename}")
    

