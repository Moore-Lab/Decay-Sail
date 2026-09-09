#!/usr/bin/env python3
"""Fetch multiple channels over a GPS time range and upload to Dropbox."""

import h5py
import numpy as np
import nds2
import os
import subprocess
from datetime import datetime

GPS_START = 1467323190  # ~3 days before GPS end
GPS_END   = 1467582390  # current DAQ GPS time (2026-07-05 to 2026-07-08)

CHUNK_SEC = 600
DROP_NANS = True

CHANNELS = [
    ('Y1:RDS-LES_PIT_IN1_DQ',  'Microspheres/TFINER/data/LES_pit'),
    ('Y1:RDS-LES_YAW_IN1_DQ',  'Microspheres/TFINER/data/LES_yaw'),
    ('Y1:RDS-PD_IN1_DQ',        'Microspheres/TFINER/data/PD'),
    ('Y1:RDS-OUTS_V1_OUT_DQ',   'Microspheres/TFINER/data/Electrodes'),
    ('Y1:RDS-OUTS_V2_OUT_DQ',   'Microspheres/TFINER/data/Electrodes'),
    ('Y1:RDS-OUTS_V3_OUT_DQ',   'Microspheres/TFINER/data/Electrodes'),
    ('Y1:RDS-OUTS_V4_OUT_DQ',   'Microspheres/TFINER/data/Electrodes'),
]


def fetch_channel(conn, channel, gps_start, gps_end):
    os.makedirs("data", exist_ok=True)
    filename = f"data/{channel.replace(':', '_')}_{gps_start}_{gps_end}.h5"

    print(f"\n{'='*60}")
    print(f"Channel : {channel}")
    print(f"GPS     : {gps_start} → {gps_end}  ({(gps_end-gps_start)/3600:.1f} h)")
    print(f"Output  : {filename}")
    print(f"{'='*60}")

    with h5py.File(filename, 'w') as f:
        f.attrs['channel']     = channel
        f.attrs['gps_start']   = gps_start
        f.attrs['gps_end']     = gps_end
        f.attrs['created_utc'] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        dset_x  = f.create_dataset('data',      shape=(0,), maxshape=(None,),
                                   dtype='float32', chunks=True,
                                   compression='gzip', compression_opts=4)
        seg     = f.create_group('segments')
        seg_idx = seg.create_dataset('index_start', shape=(0,), maxshape=(None,), dtype='int64',   chunks=True)
        seg_len = seg.create_dataset('length',      shape=(0,), maxshape=(None,), dtype='int64',   chunks=True)
        seg_t0  = seg.create_dataset('gps_start',   shape=(0,), maxshape=(None,), dtype='float64', chunks=True)

        def append_array(ds, arr):
            n0 = ds.shape[0]; n1 = n0 + arr.size
            ds.resize((n1,)); ds[n0:n1] = arr
            return n0

        def append_scalar(ds, val):
            n0 = ds.shape[0]; ds.resize((n0+1,)); ds[n0] = val

        t = gps_start; total = 0; fs_written = False
        while t < gps_end:
            stop = min(gps_end, t + CHUNK_SEC)
            try:
                bufs = conn.fetch(t, stop, [channel])
            except Exception as e:
                print(f"  [warn] fetch failed t={t}: {e}")
                t = stop; continue

            if not bufs:
                t = stop; continue

            for b in bufs:
                if not fs_written:
                    f.attrs['sample_rate'] = b.sample_rate
                    fs_written = True

                x  = b.data.astype('float32', copy=False)
                fs = b.sample_rate
                dt = 1.0 / fs
                t0 = b.gps_seconds + b.gps_nanoseconds * 1e-9

                if DROP_NANS and not np.all(np.isfinite(x)):
                    mask = np.isfinite(x)
                    if not np.any(mask):
                        continue
                    idx   = np.flatnonzero(mask)
                    cuts  = np.flatnonzero(np.diff(idx) > 1) + 1
                    starts = np.r_[0, cuts]
                    stops_ = np.r_[cuts, idx.size]
                    for s, e in zip(starts, stops_):
                        i0 = idx[s]; i1 = idx[e-1]+1
                        xr = x[i0:i1]; t0r = t0 + i0*dt
                        si = append_array(dset_x, xr)
                        append_scalar(seg_idx, si)
                        append_scalar(seg_len, xr.size)
                        append_scalar(seg_t0,  float(t0r))
                        total += xr.size
                else:
                    si = append_array(dset_x, x)
                    append_scalar(seg_idx, si)
                    append_scalar(seg_len, x.size)
                    append_scalar(seg_t0,  float(t0))
                    total += x.size

            t = stop
            pct = (t - gps_start) / (gps_end - gps_start) * 100
            print(f"  {pct:5.1f}%  t={t}  samples={total}", end='\r', flush=True)

    size_mb = os.path.getsize(filename) / 1e6
    print(f"\n  Done: {total} samples, {size_mb:.1f} MB → {filename}")
    return filename


def upload(filename, dropbox_path):
    dest = f"dropbox:{dropbox_path}/{os.path.basename(filename)}"
    print(f"  Uploading to {dest} ...")
    result = subprocess.run(
        ['rclone', 'copyto', filename, dest, '--progress'],
        capture_output=False
    )
    if result.returncode == 0:
        print(f"  Upload complete.")
    else:
        print(f"  [warn] rclone exited {result.returncode}")


def main():
    print("Connecting to NDS2 on cymac1:8088 ...")
    conn = nds2.connection('cymac1', 8088)
    conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')
    conn.set_parameter('GAP_HANDLER', 'STATIC_HANDLER_NAN')
    print("Connected.\n")

    for channel, dropbox_path in CHANNELS:
        filename = fetch_channel(conn, channel, GPS_START, GPS_END)
        upload(filename, dropbox_path)

    print("\nAll channels complete.")


if __name__ == '__main__':
    main()
