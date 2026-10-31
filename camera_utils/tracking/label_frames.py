"""Hand-label the blob angle on selected frames (gate 3).

    python label_frames.py select  VIDEO.avi CENTRE.json BLOB.csv   # pick ~200 frames, cache them
    python label_frames.py point   GPS                              # choose the rotor point to click
    python label_frames.py label   GPS                              # pass 1: click that point on each frame
    python label_frames.py repeat  GPS                              # pass 2: 20 frames again, shuffled
    python label_frames.py compare GPS                              # pass 1 vs pass 2 agreement

Files go in labels/ (GPS = the video's GPS, e.g. 1477428272):
  frames_gps<GPS>.npz      selected frames + reference image (cache, gitignored, rebuilt by select)
  selection_gps<GPS>.csv   which frames and why they were picked
  point_gps<GPS>.json      the rotor point Molly clicks (marked on the reference image)
  labels_gps<GPS>.csv      pass 1; labels_repeat_gps<GPS>.csv  pass 2   (ground truth: commit these)

select uses the detector's output only to pick frames (by angle, speed, reversals and
low match margin); the labelling window never shows a detector angle. The reference image
is the de-rotated mean, so it is in the detector's frame, but it carries no per-frame angle.
Angles are in image coordinates (x right, y down), atan2(y - cy, x - cx), as in blob_track.py.

Labelling keys: click = label and next; s = skip (unsure); b = back one frame;
+/- = zoom; q = save and quit. Every click is saved at once; rerunning resumes.
"""
import csv, json, os, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); LAB = os.path.join(HERE, 'labels')
N_ANGLE_BINS, PER_BIN, N_FAST, N_REV, N_LOWM, N_TOTAL, N_REPEAT = 12, 10, 40, 20, 20, 200, 20
HALF = 42                                  # crop half-size around the centre, px

def paths(gps):
    p = lambda s: os.path.join(LAB, s % gps)
    return dict(npz=p('frames_gps%s.npz'), sel=p('selection_gps%s.csv'), point=p('point_gps%s.json'),
                lab=p('labels_gps%s.csv'), rep=p('labels_repeat_gps%s.csv'))

def read_blob(f):
    rows = list(csv.reader(l for l in open(f) if not l.startswith('#')))[1:]
    return np.array([[float(x) for x in r[:5]] for r in rows])

def spaced(cands, k, gap, taken):
    """Up to k frames from cands (in priority order), at least gap frames from any taken."""
    out = []
    for i in cands:
        if len(out) == k: break
        if all(abs(i - j) >= gap for j in list(taken) + out): out.append(int(i))
    return out

def select(video, centre_file, blob_file):
    import cv2
    gps = video.split('gps')[-1].split('.')[0]; P = paths(gps); os.makedirs(LAB, exist_ok=True)
    cx, cy = json.load(open(centre_file))['centre_xy_px']
    o = read_blob(blob_file); n = len(o); ang = o[:, 1]
    w = np.degrees(np.unwrap(np.deg2rad(ang))); v = np.gradient(w)
    rng = np.random.default_rng(0); chosen = {}
    # 1. evenly in angle, spread in time within each bin
    for b in range(N_ANGLE_BINS):
        idx = np.nonzero((ang // (360 / N_ANGLE_BINS)).astype(int) == b)[0]
        if len(idx): pick = idx[np.linspace(0, len(idx) - 1, min(PER_BIN, len(idx))).astype(int)]
        else: pick = []
        for i in spaced(pick, PER_BIN, 5, chosen): chosen[i] = 'angle_bin_%d' % b
    # 2. fastest (most blur)
    for i in spaced(np.argsort(-np.abs(v)), N_FAST, 25, chosen): chosen[i] = 'fast'
    # 3. reversals (speed changes sign), largest swings first
    rev = np.nonzero(np.sign(v[1:]) != np.sign(v[:-1]))[0] + 1
    swing = np.array([np.ptp(w[max(0, i - 50):i + 50]) for i in rev])
    for i in spaced(rev[np.argsort(-swing)], N_REV, 25, chosen): chosen[i] = 'reversal'
    # 4. lowest detector margin (best match minus best elsewhere)
    for i in spaced(np.argsort(o[:, 3] - o[:, 4]), N_LOWM, 25, chosen): chosen[i] = 'low_margin'
    # 5. fill with random frames
    for i in spaced(rng.permutation(n), N_TOTAL - len(chosen), 5, chosen): chosen[i] = 'random'
    frames = np.array(sorted(chosen))
    order = rng.permutation(len(frames))                      # labelling order: shuffled
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                         capture_output=True, check=True).stdout
    H, W = 292, 256
    a = np.frombuffer(raw, np.uint8).reshape(-1, H, W)
    ref = np.zeros((H, W), np.float32)                        # de-rotated mean, every 5th frame
    for i in range(0, n, 5):
        M = cv2.getRotationMatrix2D((cx, cy), ang[i] - ang[0], 1.0)
        ref += cv2.warpAffine(a[i].astype(np.float32), M, (W, H))
    ref /= len(range(0, n, 5))
    np.savez_compressed(P['npz'], frames=frames, order=order, imgs=a[frames], ref=ref,
                        ref_frame=0, centre=np.array([cx, cy]), video=os.path.basename(video))
    with open(P['sel'], 'w') as fh:
        fh.write('frame,reason\n')
        for i in frames: fh.write('%d,%s\n' % (i, chosen[i]))
    print('%d frames -> %s' % (len(frames), P['sel']))
    print({k: sum(1 for x in chosen.values() if x.startswith(k)) for k in ['angle', 'fast', 'reversal', 'low_margin', 'random']})

def show_crop(ax, img, c, zoom):
    h = HALF / zoom
    ax.imshow(img, cmap='gray', vmin=0, vmax=255, interpolation='nearest')
    ax.set_xlim(c[0] - h, c[0] + h); ax.set_ylim(c[1] + h, c[1] - h); ax.set_xticks([]); ax.set_yticks([])

def choose_point(gps):
    import matplotlib.pyplot as plt
    P = paths(gps); d = np.load(P['npz']); c = d['centre']
    fig, ax = plt.subplots(figsize=(7, 7)); show_crop(ax, d['ref'], c, 1)
    ax.set_title('Click the rotor point you will click on every frame\n(a sharp, easy-to-find spot on the blob)')
    got = {}
    def on(e):
        if e.inaxes is ax and e.xdata is not None:
            got['xy'] = (e.xdata, e.ydata); plt.close(fig)
    fig.canvas.mpl_connect('button_press_event', on); plt.show()
    if 'xy' not in got: print('no point chosen'); return
    x, y = got['xy']
    json.dump({'ref_xy_px': [round(x, 2), round(y, 2)], 'centre_xy_px': c.tolist(),
               'ref_angle_deg': round(float(np.degrees(np.arctan2(y - c[1], x - c[0]))), 2),
               'ref_r_px': round(float(np.hypot(x - c[0], y - c[1])), 2)}, open(P['point'], 'w'), indent=1)
    print('saved', P['point'])

def load_labels(f):
    if not os.path.exists(f): return {}
    return {int(r['frame']): r for r in csv.DictReader(open(f))}

def label(gps, repeat=False):
    import matplotlib.pyplot as plt
    P = paths(gps); d = np.load(P['npz']); c = d['centre']; pt = json.load(open(P['point']))
    imgs = dict(zip(d['frames'].tolist(), d['imgs']))
    if repeat:
        done = [f for f, r in load_labels(P['lab']).items() if r['status'] == 'ok']
        if len(done) < N_REPEAT: sys.exit('pass 1 has only %d labelled frames' % len(done))
        queue = list(np.random.default_rng(1).choice(sorted(done), N_REPEAT, replace=False))
        out = P['rep']
    else:
        queue = d['frames'][d['order']].tolist(); out = P['lab']
    labels = load_labels(out)
    todo = [f for f in queue if f not in labels]
    st = dict(k=0, zoom=1.0)
    fig, (ax, axr) = plt.subplots(1, 2, figsize=(13, 7), gridspec_kw=dict(width_ratios=[3, 1.3]))
    show_crop(axr, d['ref'], c, 1); axr.plot(*pt['ref_xy_px'], 'r+', ms=14, mew=1.5)
    axr.set_title('reference: click this point\n(it will be at another angle)', fontsize=9)

    def save():
        with open(out, 'w') as fh:
            fh.write('frame,x_px,y_px,angle_deg,r_px,status\n')
            for f in sorted(labels): r = labels[f]; fh.write('%s,%s,%s,%s,%s,%s\n' % (
                f, r['x_px'], r['y_px'], r['angle_deg'], r['r_px'], r['status']))

    def draw():
        ax.clear()
        if st['k'] >= len(todo):
            ax.set_title('done: %d labelled. Close the window.' % len(labels)); fig.canvas.draw_idle(); return
        f = todo[st['k']]; show_crop(ax, imgs[f], c, st['zoom'])
        ax.set_title('%s  %d / %d   (frame %d)   click = label, s = skip, b = back, +/- zoom, q = quit'
                     % ('PASS 2' if repeat else 'PASS 1', st['k'] + 1, len(todo), f), fontsize=9)
        fig.canvas.draw_idle()

    def record(f, x, y, status):
        if status == 'ok':
            a = np.degrees(np.arctan2(y - c[1], x - c[0])) % 360; r = np.hypot(x - c[0], y - c[1])
            labels[f] = dict(x_px='%.2f' % x, y_px='%.2f' % y, angle_deg='%.2f' % a, r_px='%.2f' % r, status='ok')
        else:
            labels[f] = dict(x_px='', y_px='', angle_deg='', r_px='', status=status)
        save(); st['k'] += 1; draw()

    def on_click(e):
        if e.inaxes is ax and e.xdata is not None and st['k'] < len(todo) and e.button == 1:
            record(todo[st['k']], e.xdata, e.ydata, 'ok')

    def on_key(e):
        if st['k'] < len(todo) and e.key == 's': record(todo[st['k']], 0, 0, 'skip')
        elif e.key == 'b' and st['k'] > 0:
            st['k'] -= 1; labels.pop(todo[st['k']], None); save(); draw()
        elif e.key in ('+', '='): st['zoom'] = min(st['zoom'] * 1.4, 4); draw()
        elif e.key == '-': st['zoom'] = max(st['zoom'] / 1.4, 0.7); draw()
        elif e.key == 'q': save(); plt.close(fig)

    fig.canvas.mpl_connect('button_press_event', on_click); fig.canvas.mpl_connect('key_press_event', on_key)
    for k in list(plt.rcParams):
        if k.startswith('keymap.') and any(x in plt.rcParams[k] for x in ('s', 'b', 'q', '+', '-', '=')):
            plt.rcParams[k] = [x for x in plt.rcParams[k] if x not in ('s', 'b', 'q', '+', '-', '=')]
    draw(); fig.ui = (on_click, on_key, record, todo); plt.show(); save()
    print('%d labels in %s' % (len(labels), out))

def compare(gps):
    P = paths(gps); a, b = load_labels(P['lab']), load_labels(P['rep'])
    common = [f for f in b if f in a and a[f]['status'] == b[f]['status'] == 'ok']
    if not common: sys.exit('no frames labelled in both passes')
    d = np.array([((float(b[f]['angle_deg']) - float(a[f]['angle_deg'])) + 180) % 360 - 180 for f in common])
    print('%d frames in both passes: mean %.2f deg, rms %.2f, max |diff| %.2f' % (len(d), d.mean(), np.sqrt((d**2).mean()), np.abs(d).max()))
    for f, x in sorted(zip(common, d), key=lambda t: -abs(t[1]))[:5]: print('  frame %d: %+.2f deg' % (f, x))

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'select': select(*sys.argv[2:5])
    elif cmd == 'point': choose_point(sys.argv[2])
    elif cmd == 'label': label(sys.argv[2])
    elif cmd == 'repeat': label(sys.argv[2], repeat=True)
    elif cmd == 'compare': compare(sys.argv[2])
    else: sys.exit(__doc__)
