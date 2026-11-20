#!/usr/bin/env python3
"""Does the laser glare cover the white dot? Mean top-camera images per 10 deg of rotor angle, laser on vs off (ND2 night,
glare_frames.npz from glare_frames.py on worker2). Zoom on the centre; red = on - off > 10 counts, cyan = dot (> 200).
(2026-11-20) MEASURED (averages). Result: no pixel is both glare and dot at any angle; max on-off inside the dot 3-9 counts.

    python3 glare_dot_zoom.py     # prints overlap per bin; ~/Downloads/glare_dot_zoom.png
"""
import numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt, os
z=np.load(os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/data/spinup/2026-11-18/laser/glare/glare_frames.npz'))
on,off=z['on'],z['off']
bins=[5,8,10,16,23,25,27]
r0,r1,c0,c1=110,250,50,200
fig,ax=plt.subplots(len(bins),2,figsize=(8,3.6*len(bins)))
for r,b in enumerate(bins):
    d=(on[b]-off[b])[r0:r1,c0:c1]
    ax[r,0].imshow(off[b][r0:r1,c0:c1],cmap='gray',vmin=0,vmax=255)
    ax[r,1].imshow(on[b][r0:r1,c0:c1],cmap='gray',vmin=0,vmax=255)
    ax[r,1].contour(d,levels=[10],colors='r',linewidths=0.8)
    dot=off[b][r0:r1,c0:c1]>200
    ax[r,1].contour(dot.astype(float),levels=[0.5],colors='c',linewidths=0.8)
    ov=(d>10)&dot
    print(f'{b*10}-{b*10+10}: glare px (>10) {np.sum(d>10)}, dot px {dot.sum()}, overlap {ov.sum()}, max diff on dot {d[dot].max() if dot.any() else 0:.1f}')
    ax[r,0].set_ylabel(f'{b*10}–{b*10+10}°')
    for a in ax[r]: a.set_xticks([]); a.set_yticks([])
ax[0,0].set_title('laser off (mean)'); ax[0,1].set_title('laser on (mean)\nred: on−off > 10 counts; cyan: dot (>200)')
fig.tight_layout(); fig.savefig(os.path.expanduser('~/Downloads/glare_dot_zoom.png'),dpi=110)
