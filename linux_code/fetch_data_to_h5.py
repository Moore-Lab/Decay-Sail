import h5py
import numpy as np
import nds2
import time
from datetime import datetime

# LIGO documentation about fetch function and gaps: https://nds.docs.ligo.org/nds2-client/Beta/User/html/classNDS_1_1abi__0_1_1connection.html#aabecab944720bb214069b7271edc6c63

# configure the channel and duration
CHANNEL = 'Y1:RDS-LES_YAW_MON_OUT_DQ' # specify the channel to fetch data from
DURATION = 60 * 60 * 10 # Fetch data for 10 hours
GPS_UNIX_OFFSET = 315964800 # Offset from Unix time to GPS time (1970-01-01 to 1980-01-06)
# Add Unix time - might be easier than finding GPS start and end times manually

# Can look at GUI to find best GPS start and end times for data retrieval
gps_start = 1437929734 # Example fixed GPS start time (Jul 30th 2025) - change as needed
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

# AI assisted code to help with chunked data retrieval -- TEST
CHUNK_SEC  = 600                          # fetch in 10-minute slices (tune 60–1800)
DROP_NANS  = True                         # drop NaNs (split into finite runs)
WRITE_PER_SAMPLE_TIMESTAMPS = False # write timestamps for each sample (can be slow, so disable if not needed)

# ---- prepare output ----
os.makedirs("data", exist_ok=True) # ensure the data directory exists
filename = f"data/{CHANNEL.replace(':','_')}_{gps_start}_{gps_end}.h5"

with h5py.File(filename, 'w') as f:
    # metadata
    f.attrs['channel']     = CHANNEL
    f.attrs['gps_start']   = gps_start
    f.attrs['gps_end']     = gps_end
    f.attrs['created_utc'] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # extendable datasets
    dset_x = f.create_dataset('data',
                              shape=(0,), maxshape=(None,),
                              dtype='float32', chunks=True,
                              compression='gzip', compression_opts=4)

    seg = f.create_group('segments')
    seg_idx = seg.create_dataset('index_start', shape=(0,), maxshape=(None,),
                                 dtype='int64',  chunks=True)
    seg_len = seg.create_dataset('length',      shape=(0,), maxshape=(None,),
                                 dtype='int64',  chunks=True)
    seg_t0  = seg.create_dataset('gps_start',   shape=(0,), maxshape=(None,),
                                 dtype='float64', chunks=True)

    if WRITE_PER_SAMPLE_TIMESTAMPS:
        dset_ts = f.create_dataset('timestamps',
                                   shape=(0,), maxshape=(None,),
                                   dtype='float64', chunks=True,
                                   compression='gzip', compression_opts=4)

    def append_array(ds, arr):
        n0 = ds.shape[0]
        n1 = n0 + arr.size
        ds.resize((n1,))
        ds[n0:n1] = arr
        return n0

    def append_scalar(ds, val):
        n0 = ds.shape[0]
        ds.resize((n0 + 1,))
        ds[n0] = val

    # ---- chunked fetch & write ----
    t = gps_start
    total = 0
    fs_written = False

    while t < gps_end:
        stop = min(gps_end, t + CHUNK_SEC)
        try:
            bufs = conn.fetch(t, stop, [CHANNEL])  # keep your working signature
        except Exception as e:
            print(f"[warn] fetch failed t={t} stop={stop}: {e}")
            t = stop
            continue

        if not bufs:
            t = stop
            continue

        for b in bufs:
            if not fs_written:
                f.attrs['sample_rate'] = b.sample_rate
                fs_written = True

            x = b.data.astype('float32', copy=False)
            fs = b.sample_rate
            dt = 1.0 / fs
            t0_buf = b.gps_seconds + b.gps_nanoseconds * 1e-9

            if DROP_NANS and not np.all(np.isfinite(x)):
                mask = np.isfinite(x)
                if not np.any(mask):
                    continue
                idx = np.flatnonzero(mask)
                cuts = np.flatnonzero(np.diff(idx) > 1) + 1
                starts = np.r_[0, cuts]
                stops  = np.r_[cuts, idx.size]
                for s, e in zip(starts, stops):
                    i0 = idx[s]
                    i1 = idx[e - 1] + 1
                    xr = x[i0:i1]
                    t0_run = t0_buf + i0 * dt

                    start_idx = append_array(dset_x, xr)
                    append_scalar(seg_idx, start_idx)
                    append_scalar(seg_len, xr.size)
                    append_scalar(seg_t0, float(t0_run))

                    if WRITE_PER_SAMPLE_TIMESTAMPS:
                        ts = t0_run + np.arange(xr.size, dtype='float64') * dt
                        append_array(dset_ts, ts)

                    total += xr.size
            else:
                # keep NaNs (or none present)
                start_idx = append_array(dset_x, x)
                append_scalar(seg_idx, start_idx)
                append_scalar(seg_len, x.size)
                append_scalar(seg_t0, float(t0_buf))

                if WRITE_PER_SAMPLE_TIMESTAMPS:
                    ts = t0_buf + np.arange(x.size, dtype='float64') * dt
                    append_array(dset_ts, ts)

                total += x.size

        t = stop

print(f"Saved {total} samples to {filename}")


# # Old working code to fetch data, uses too much memory for large datasets - 
# # FETCH data: buffers are used to store RAW data
# buffers = conn.fetch(gps_start, gps_end, [CHANNEL,])  # Adjust start and end times as needed
# if not buffers:
#     print(f"No data found for {CHANNEL} between {gps_start} and {gps_end}.")
#     exit()
# else:
#     print(f"Fetching data from {CHANNEL} between {gps_start} and {gps_end}.")

# #buf = buffers[0]
# # print(buf)
# # print(dir(buf))
# # combine the buffers into a single array
# data = np.concatenate([buf.data for buf in buffers])
# sample_rate = buffers[0].sample_rate
# print('Fetched data')
       
# # timestamps for the data
# timestamps = []
# for buf in buffers:
#     t0 = buf.gps_seconds + buf.gps_nanoseconds * 1e-9
#     dt = 1.0 / buf.sample_rate
#     timestamps.extend(t0 + k * dt for k in range(len(buf.data)))
#     #timestamps.extend(np.arange(t0, t0 + dt * len(buf['data']), dt))
# timestamps = np.array(timestamps)
# print('Fetched timestamps')

# # Drop gaps in data
# valid = np.isfinite(data)
# data = data[valid]
# timestamps = timestamps[valid]
# print('Dropped gaps in data')

# # Create HDF5 file
# #filename = f'yaw_data_{int(time.time())}.hdf5'
# filename = f"data/{CHANNEL.replace(':', '_')}_{gps_start}_{gps_end}.hdf5"
# with h5py.File(filename, 'w') as f:
#     f.attrs['channel'] = CHANNEL
#     f.attrs['gps_start'] = gps_start
#     f.attrs['gps_end'] = gps_end
#     f.attrs['sample_rate'] = sample_rate
#     f.attrs['data_length'] = len(data)
#     #f.attrs['unit'] = 'undefined'  # Specify unit if known
#     # f.attrs['created_utc'] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
#     # f.attrs['created_local'] = datetime.now().isoformat()
    
#     # Datasets
#     f.create_dataset('data', data=data)
#     f.create_dataset('timestamps', data=timestamps)

# print(f"Saved {len(data)} samples at {sample_rate} Hz to {filename}")
    

