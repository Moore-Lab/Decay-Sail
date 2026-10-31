#!/usr/bin/env python3
"""Fetch LES PIT and YAW for the span of a Basler video and upload them to Dropbox.

    python3 fetch_les_for_video.py VIDEO_GPS [--duration S] [--pad S]

Read-only (EPICS caget + NDS fetch); commands nothing. Run on worker2.

VIDEO_GPS is the number in output_basler_gps<GPS>.avi, which is TRUE GPS (worker2 clock).
NDS data are stamped in the front end's clock, which runs ahead of true GPS by a wandering
amount (CLAUDE.md), so the offset is read live from Y1:DAQ-DC0_GPS. It drifts, possibly by
seconds per hour, so the window is padded (default 300 s each side) and the video is aligned
to the LES afterwards from the motion itself. The offset used is stored in each file.

Writes data/<channel>_<fe_start>_<fe_end>.h5 (batch_fetch.py format) and uploads each to
Dropbox Microspheres/TFINER/data/LES_video/ with rclone.
"""
import argparse, time
import h5py, nds2
from epics import caget
from batch_fetch import fetch_channel, upload

GPS_UNIX_OFF = 315964800 - 18          # Unix -> GPS, 18 leap seconds
CHANNELS = ['Y1:RDS-LES_PIT_IN1_DQ', 'Y1:RDS-LES_YAW_IN1_DQ']
DEST = 'Microspheres/TFINER/data/LES_video'

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('video_gps', type=int, help='true GPS from the video file name')
p.add_argument('--duration', type=float, default=270, help='video length, s (default 270)')
p.add_argument('--pad', type=float, default=300, help='extra seconds each side (default 300)')
a = p.parse_args()

fe = caget('Y1:DAQ-DC0_GPS', timeout=2.0)
true_now = time.time() - GPS_UNIX_OFF
if not fe:
    raise SystemExit('could not read Y1:DAQ-DC0_GPS; not guessing the offset')
offset = float(fe) - true_now
print('front-end GPS %d, true GPS %.1f -> front end ahead by %.1f s (read now)' % (fe, true_now, offset))

start = int(a.video_gps + offset - a.pad)
end = int(a.video_gps + a.duration + offset + a.pad) + 1
print('video true GPS %d..%d -> fetching front-end GPS %d..%d' % (
    a.video_gps, a.video_gps + a.duration, start, end))

conn = nds2.connection('cymac1', 8088)
conn.set_parameter('ALLOW_DATA_ON_TAPE', '1')
conn.set_parameter('GAP_HANDLER', 'STATIC_HANDLER_NAN')
for ch in CHANNELS:
    fn = fetch_channel(conn, ch, start, end)
    with h5py.File(fn, 'a') as f:
        f.attrs['video_true_gps'] = a.video_gps
        f.attrs['fe_minus_true_gps_s'] = offset
        f.attrs['offset_read_true_gps'] = true_now
    upload(fn, DEST)
print('done; offset %.1f s was read at true GPS %.0f, %.1f h after the video started' % (
    offset, true_now, (true_now - a.video_gps) / 3600))
