#!/usr/bin/env python3
"""Gate 7 (L4): live angles vs blob_track.py on the recorded video. Mac, after the lab run.

    python gate7_check.py DIR/blob_live_gps<GPS>.csv [--video V.avi] [--timestamps T.csv]
                          [--outdir DIR] [--sheet PNG] [--last-s 30]

Defaults: the video and timestamps sit next to the live CSV as output_basler_gps<GPS>.avi
/ .csv (live_blob_track.py's names). Analysis only; touches no hardware.

Checks (pass marks agreed with Molly 2026-10-31, tracking HANDOFF, gate L4):
  1. dropped frames = 0: BlockID gaps in the timestamps CSV, and camera-timestamp
     intervals > 1.5x the median; frame counts of video, timestamps and live CSV agree.
  2. live = offline: blob_track.py is re-run on the saved video with the SAME centre and
     template the live run used (read from the live CSV header; centre written to
     <outdir>/centre_gps<GPS>_live.json). Pass: >= 99.9% of frames within 0.1 deg
     (wrapped difference, frames matched by index; a frame missing from either side
     counts as a failure).
  3. median NCC >= 0.9 over the whole recording; also printed for the last --last-s s.
  Plus a circled-frame sheet for Molly's eye (red = live angle, green = offline,
  yellow cross = centre): evenly spaced frames, the largest live-offline differences and
  the lowest NCC.

Angle zero: the template's (template_gps1477428272.npz: frame 0 of that video at 257 deg;
score_angles.py --offset 0.56 refers to it). This gate compares live with offline, so it
needs no offset.

Exit code 0 = all three pass, 1 = any fails, 2 = cannot run.
"""
import argparse, json, os, re, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('live_csv')
p.add_argument('--video', default='')
p.add_argument('--timestamps', default='')
p.add_argument('--outdir', default='')
p.add_argument('--sheet', default='', help='PNG path (default ../../plots/gate7_gps<GPS>_frames.png)')
p.add_argument('--last-s', type=float, default=30.0)
p.add_argument('--offline-csv', default='', help='reuse an existing blob_track.py output (skip the re-run)')
args = p.parse_args()

TOL_DEG, FRAC, NCC_MIN = 0.1, 0.999, 0.9

# ---------------------------------------------------------------- live CSV + header
with open(args.live_csv) as fh:
    head = fh.readline()
m = re.search(r'gps(\d+) centre=\(([-\d.]+),([-\d.]+)\).*template=(\S+)', head)
if not m:
    sys.exit(print('! cannot parse live CSV header:', head.strip()) or 2)
gps, cx, cy, tname = m.group(1), float(m.group(2)), float(m.group(3)), m.group(4)
replay = 'replay=' in head
live = np.genfromtxt(args.live_csv, delimiter=',', skip_header=2, dtype=None, encoding=None,
                     names=['frame', 'host', 'ang', 'r', 'ncc', 'ncc2', 'src', 'ms'])
d = os.path.dirname(os.path.abspath(args.live_csv))
video = args.video or os.path.join(d, 'output_basler_gps%s.avi' % gps)
tsf = args.timestamps or os.path.join(d, 'output_basler_gps%s.csv' % gps)
outdir = args.outdir or d
template = os.path.join(HERE, tname)
for f in (video, tsf, template):
    if not os.path.exists(f):
        sys.exit(print('! missing', f) or 2)
print('gate 7: gps%s  centre (%.4f, %.4f)  template %s%s' % (gps, cx, cy, tname,
      '  [REPLAY: not a live recording]' if replay else ''))

W, H = (int(v) for v in subprocess.run(
    ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
     '-of', 'csv=p=0', video], capture_output=True, text=True, check=True).stdout.split(','))
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                     capture_output=True, check=True).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W)
n_vid = len(frames)

# ---------------------------------------------------------------- 1. dropped frames
ts = np.genfromtxt(tsf, delimiter=',', names=True)
blk = ts['block_id'].astype(np.int64); cam = ts['cam_timestamp_ns'].astype(np.float64)
gaps = int(np.sum(np.clip(np.diff(blk) - 1, 0, None)))
dt = np.diff(cam); med_dt = np.median(dt)
late = int(np.sum(dt > 1.5 * med_dt))
counts = (n_vid, len(ts), len(live))
counts_ok = len(set(counts)) == 1
drop_ok = gaps == 0 and late == 0 and counts_ok
fps = 1e9 / med_dt if med_dt > 0 else float('nan')
print('\n1. dropped frames: BlockID gaps %d; intervals > 1.5x median %d (median %.3f ms = %.3f fps)'
      % (gaps, late, med_dt / 1e6, fps))
print('   frames: video %d, timestamps %d, live CSV %d  -> %s' % (*counts, 'agree' if counts_ok else 'DISAGREE'))
print('   %s' % ('PASS' if drop_ok else 'FAIL'))

# ---------------------------------------------------------------- 2. live vs offline
off_csv = args.offline_csv
if not off_csv:
    cj = os.path.join(outdir, 'centre_gps%s_live.json' % gps)
    json.dump({'centre_xy_px': [cx, cy], 'source': 'live_blob_track.py header of ' +
               os.path.basename(args.live_csv)}, open(cj, 'w'))
    off_csv = os.path.join(outdir, 'blob_offline_gps%s.csv' % gps)
    cmd = [sys.executable, os.path.join(HERE, 'blob_track.py'), video, str(W), str(H), cj, '0', '0',
           off_csv, '--template', template]
    print('\n   running: ' + ' '.join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
    print('   ' + r.stdout.strip().replace('\n', '\n   '))
    if r.returncode:
        sys.exit(print('! blob_track.py failed:', r.stderr) or 2)
off = np.genfromtxt(off_csv, delimiter=',', skip_header=2, dtype=None, encoding=None,
                    names=['frame', 'ang', 'r', 'ncc', 'ncc2', 'src'])
la = dict(zip(live['frame'].tolist(), live['ang'])); oa = dict(zip(off['frame'].tolist(), off['ang']))
allf = sorted(set(la) | set(oa))
diff = np.array([abs((la[k] - oa[k] + 180) % 360 - 180) if k in la and k in oa else np.inf for k in allf])
n_miss = int(np.isinf(diff).sum()); fin = diff[np.isfinite(diff)]
frac = float(np.mean(diff <= TOL_DEG)) if len(diff) else 0.0
match_ok = frac >= FRAC
print('\n2. live vs offline (%d frames, %d missing from one side): within %.1f deg %.4f%%; '
      'max %.4f deg; median %.4f deg' % (len(allf), n_miss, TOL_DEG, 100 * frac,
                                        fin.max() if len(fin) else np.nan, np.median(fin) if len(fin) else np.nan))
print('   %s (need >= %.1f%%)' % ('PASS' if match_ok else 'FAIL', 100 * FRAC))

# ---------------------------------------------------------------- 3. NCC
ncc = live['ncc']; nlast = int(round(args.last_s * fps)) if np.isfinite(fps) else len(ncc)
ncc_med, ncc_last = float(np.median(ncc)), float(np.median(ncc[-nlast:]))
ncc_ok = ncc_med >= NCC_MIN
print('\n3. live NCC median %.3f (last %.0f s: %.3f); 1st percentile %.3f; sail-blanked %.1f%% of frames'
      % (ncc_med, args.last_s, ncc_last, np.percentile(ncc, 1), 100 * np.mean(live['src'] == 'blanked')))
print('   %s (need >= %.2f)' % ('PASS' if ncc_ok else 'FAIL', NCC_MIN))

# ---------------------------------------------------------------- circled-frame sheet
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
fidx = live['frame']; order = np.argsort(np.where(np.isfinite(diff), diff, 1e9))
dsel = [allf[i] for i in order[::-1][:4]]
dval = dict(zip(allf, diff))
nsel = fidx[np.argsort(ncc)[:4]].tolist()
esel = np.linspace(0, n_vid - 1, 8).astype(int).tolist()
sel = []
for k, why in [(k, 'even') for k in esel] + [(k, 'max diff') for k in dsel] + [(k, 'low NCC') for k in nsel]:
    if 0 <= k < n_vid and k not in [s[0] for s in sel]:
        sel.append((int(k), why))
cols = 4; rows = int(np.ceil(len(sel) / cols))
fig, axs = plt.subplots(rows, cols, figsize=(3.2 * cols, 3.6 * rows))
lrow = {int(k): i for i, k in enumerate(fidx)}; orow = {int(k): i for i, k in enumerate(off['frame'])}
for ax, (k, why) in zip(np.ravel(axs), sel):
    ax.imshow(frames[k], cmap='gray', vmin=0, vmax=255)
    ax.plot(cx, cy, '+', color='yellow', ms=8)
    t = ''
    if k in orow:
        i = orow[k]; a = np.deg2rad(off['ang'][i])
        ax.plot(cx + off['r'][i] * np.cos(a), cy + off['r'][i] * np.sin(a), 'o', mfc='none', mec='lime', ms=14)
    if k in lrow:
        i = lrow[k]; a = np.deg2rad(live['ang'][i])
        ax.plot(cx + live['r'][i] * np.cos(a), cy + live['r'][i] * np.sin(a), 'o', mfc='none', mec='red', ms=9)
        t = '%.1f deg  ncc %.2f' % (live['ang'][i], live['ncc'][i])
    if why == 'max diff':
        why = 'max diff %.3f deg' % dval.get(k, np.inf)
    ax.set_title('frame %d (%s)\n%s' % (k, why, t), fontsize=8)
    ax.set_xlim(cx - 60, cx + 60); ax.set_ylim(cy + 60, cy - 60); ax.axis('off')
for ax in np.ravel(axs)[len(sel):]:
    ax.axis('off')
fig.suptitle('gate 7 gps%s: red = live, green = offline, yellow = centre' % gps, fontsize=10)
fig.tight_layout()
sheet = args.sheet or os.path.join(HERE, '..', '..', 'plots', 'gate7_gps%s_frames.png' % gps)
os.makedirs(os.path.dirname(os.path.abspath(sheet)), exist_ok=True)
fig.savefig(sheet, dpi=110)
print('\nsheet: %s' % os.path.abspath(sheet))

ok = drop_ok and match_ok and ncc_ok
print('\nGATE 7: %s (dropped %s, live=offline %s, NCC %s)%s' % (
    'PASS' if ok else 'FAIL', *('pass' if x else 'FAIL' for x in (drop_ok, match_ok, ncc_ok)),
    '  [replay test, not the lab gate]' if replay else ''))
sys.exit(0 if ok else 1)
