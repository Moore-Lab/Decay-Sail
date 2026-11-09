#!/usr/bin/env python3
"""Re-draw Molly's 2026-11-06 centre_overlay.py click fits on frame 3000 of each video, in click order.

    python render_clicks.py [--clicks DIR] [--out ../../plots]

The clicks were made before centre_overlay.py saved images. Inputs are the worker2 files,
copied to Dropbox TFINER/data/rotor_centering/2026-11-06/click_check/:
  log.csv (rows 1-5), board*.json (pad points; each file holds only the last board fit
  saved under that name), and overlay_stdout_run5.txt (run 5 was printed, not logged).
The run -> video table is from the decay-sail-9f session, which ran the clicks.
Rotor rim points were not saved, except run 5's (relayed in text). Runs 1-2 produced no fits.
Times in log.csv are worker2 local (EST = UTC-5).
Writes clickfit_<order>_run<k>_gps<GPS>.png and clickfit_sheet.png.
"""
import argparse, csv, json, os, subprocess
import numpy as np, cv2

V = os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER')
VIDEOS = {'1478031606': f'{V}/data/osc_chirp/2026-11-06/output_basler_gps1478031606.avi',
          '1478037739': f'{V}/videos/output_basler_gps1478037739.avi',
          '1478039512': f'{V}/videos/output_basler_gps1478039512.avi',
          '1478040383': f'{V}/videos/output_basler_gps1478040383.avi'}
# run, video, state, log row (None = printed only), board-points json (None = not saved)
RUNS = [(3, '1478037739', 'after tilt change + camera move', 1, 'board.json'),
        (4, '1478031606', 'before (camera elsewhere)', 2, 'board_pre.json'),
        (5, '1478039512', 'walk-back (printed only)', None, None),
        (6, '1478039512', 'walk-back', 3, 'board_walkback.json'),
        (7, '1478040383', 'final', 4, None),
        (8, '1478040383', 'final, board re-clicked', 5, 'board_tilt4.json')]
# run 5: from overlay_stdout_run5.txt (both fits printed in board mode) + relayed rim points
RUN5 = dict(board=(123.68, 160.43, 126.30), rotor=(123.12, 159.10, 37.53),
            rotor_pts=[(105.33, 192.33), (135.33, 194.33), (147.67, 187.67), (150.33, 133.33),
                       (139.00, 125.00), (90.33, 141.00)])


def frame(path, n=3000):
    png = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'select=eq(n\\,{n})', '-vframes', '1',
                          '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True, check=True).stdout
    return cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--clicks', default=f'{V}/data/rotor_centering/2026-11-06/click_check')
    ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', '..', 'plots'))
    a = ap.parse_args()
    rows = list(csv.DictReader(open(os.path.join(a.clicks, 'log.csv'))))
    S, tiles = 3, []
    for order, (run, gps, state, row, bjson) in enumerate(RUNS, 1):
        if row:
            r = rows[row - 1]
            board = tuple(float(r[k]) for k in ('board_cx', 'board_cy', 'board_R'))
            rotor = tuple(float(r[k]) for k in ('rotor_cx', 'rotor_cy', 'rotor_R'))
            when = r['time'] + ' EST'; rpts = []
        else:
            board, rotor, rpts, when = RUN5['board'], RUN5['rotor'], RUN5['rotor_pts'], 'printed, not logged'
        bpts = []
        if bjson:
            d = json.load(open(os.path.join(a.clicks, bjson)))
            if abs(d['cx'] - board[0]) < 0.01 and abs(d['cy'] - board[1]) < 0.01:   # json matches this fit
                bpts = d['points']
        img = cv2.cvtColor(cv2.resize(frame(VIDEOS[gps]), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST),
                           cv2.COLOR_GRAY2BGR)
        P = lambda x, y: (int(round(x * S)), int(round(y * S)))
        for (cx, cy, R), pts, col in ((board, bpts, (0, 220, 255)), (rotor, rpts, (255, 120, 255))):
            cv2.circle(img, P(cx, cy), int(round(R * S)), col, 1, cv2.LINE_AA)
            cv2.drawMarker(img, P(cx, cy), col, cv2.MARKER_CROSS, 20, 2)
            for x, y in pts:
                cv2.circle(img, P(x, y), 5, col, 2, cv2.LINE_AA)
        dx, dy = rotor[0] - board[0], rotor[1] - board[1]
        txt = [f'#{order}  run {run}  gps{gps}  frame 3000', state, when,
               f'rotor - board: ({dx:+.2f}, {dy:+.2f}) px  |d| {np.hypot(dx, dy):.2f}',
               f'pads shown: {len(bpts) or "not saved"}   rim pts shown: {len(rpts) or "not saved"}']
        for i, t in enumerate(txt):
            for c, w in (((0, 0, 0), 3), ((255, 255, 255), 1)):
                cv2.putText(img, t, (6, 20 + 20 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, w, cv2.LINE_AA)
        name = os.path.join(a.out, f'clickfit_{order}_run{run}_gps{gps}.png')
        cv2.imwrite(name, img); print(name, f'({dx:+.2f}, {dy:+.2f})', f'pads {len(bpts)} rim {len(rpts)}')
        tiles.append(img)
    sheet = np.vstack([np.hstack(tiles[i:i + 3]) for i in (0, 3)])
    cv2.imwrite(os.path.join(a.out, 'clickfit_sheet.png'), cv2.resize(sheet, None, fx=0.5, fy=0.5))


if __name__ == '__main__':
    main()
