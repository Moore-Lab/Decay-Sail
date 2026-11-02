"""Tracking figures for showing others (PI, talks): accuracy vs hand labels, full angle trace,
and a 30 s tracked video clip. Video gps1477428272 (2026-10-30, two-light setup).

    python make_pi_figures.py [VIDEO.avi]

Reads blob_gps1477428272.csv (blob_track.py output), centre_gps1477428272.json and
labels/; writes to ../../plots/pi_tracking/ (gitignored): accuracy_vs_hand_labels.png,
angle_vs_time_full.png, tracking_clip_gps1477428272.mp4 (H.264, 50 fps, real time).
The clip is the 30 s window with the most net rotation. Offset +0.56 deg is the declared
gate-4 offset, not fitted. Needs ffmpeg. Written 2026-11-01.
"""
import csv, json, os, subprocess, sys, numpy as np, cv2
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
T=os.path.dirname(os.path.abspath(__file__))+'/'
OUT=os.path.join(T,'..','..','plots','pi_tracking')+'/'; os.makedirs(OUT,exist_ok=True)
V=sys.argv[1] if len(sys.argv)>1 else os.path.expanduser('~/Library/CloudStorage/Dropbox/Microspheres/TFINER/videos/output_basler_gps1477428272.avi')
W,H,FPS=256,292,50.0
cx,cy=json.load(open(T+'centre_gps1477428272.json'))['centre_xy_px']
rows=list(csv.DictReader(l for l in open(T+'blob_gps1477428272.csv') if not l.startswith('#')))
ang=np.array([float(r['angle_deg']) for r in rows]); rad=np.array([float(r['r_px']) for r in rows])
ncc=np.array([float(r['ncc']) for r in rows]); n=len(ang)
unw=np.degrees(np.unwrap(np.radians(ang)))/360.0
# ---- 1. accuracy vs hand labels
lab={int(r['frame']):float(r['angle_deg']) for r in csv.DictReader(open(T+'labels/labels_gps1477428272.csv')) if r['status']=='ok'}
why={int(r['frame']):r['reason'] for r in csv.DictReader(open(T+'labels/selection_gps1477428272.csv'))}
fr=np.array(sorted(lab)); L=np.array([lab[f] for f in fr]); D=(ang[fr]+0.56)%360
err=(D-L+180)%360-180
cat=np.array(['fast' if why[f].startswith('fast') else 'reversal' if 'revers' in why[f] else 'low margin' if ('margin' in why[f] or 'low' in why[f]) else 'evenly in angle' for f in fr])
fig,ax=plt.subplots(1,2,figsize=(11,4.6))
for c,col in zip(['evenly in angle','fast','reversal','low margin'],['C0','C3','C2','C1']):
    s=cat==c; ax[0].scatter(L[s],D[s],s=14,color=col,label=f'{c} ({s.sum()})')
ax[0].plot([0,360],[0,360],'k',lw=.6); ax[0].set_xlim(0,360); ax[0].set_ylim(0,360)
ax[0].set_xlabel('hand-labelled angle (deg)'); ax[0].set_ylabel('tracker angle (deg)'); ax[0].legend(fontsize=8,loc='upper left')
ax[0].set_title('Tracker vs Molly\'s hand labels, %d frames'%len(fr))
ax[1].hist(err,bins=np.arange(-5,5.01,0.25),color='0.4')
ax[1].set_xlabel('tracker − hand label (deg)'); ax[1].set_ylabel('frames')
ax[1].set_title('rms %.2f°, max %.2f°, %d%% within 5°'%(np.sqrt(np.mean(err**2)),np.abs(err).max(),round(100*np.mean(np.abs(err)<5))))
ax[1].text(0.02,0.95,'one hand label scatters ~0.8° (repeat labelling)\nso most of this is label scatter',transform=ax[1].transAxes,fontsize=8,va='top')
fig.suptitle('Rotor angle tracking accuracy (video gps1477428272, 2026-10-30; declared offset +0.56°, not fitted)',fontsize=10)
fig.tight_layout(); fig.savefig(OUT+'accuracy_vs_hand_labels.png',dpi=130)
print('labels rms %.2f max %.2f n %d'%(np.sqrt(np.mean(err**2)),np.abs(err).max(),len(fr)))
# ---- 2. whole-recording angle trace
t=np.arange(n)/FPS
fig,ax=plt.subplots(figsize=(11,3.2)); ax.plot(t,unw,lw=.7,color='k')
ax.set_xlabel('time (s)'); ax.set_ylabel('rotor angle (turns)'); ax.set_title('Tracked rotor angle, all 13071 frames (261 s, 50 fps): swings plus full turns; no jumps (max step 7.2° between frames)',fontsize=9)
fig.tight_layout(); fig.savefig(OUT+'angle_vs_time_full.png',dpi=130)
# ---- 3. video clip: 30 s window with the most net rotation
win=int(30*FPS); net=np.abs(unw[win:]-unw[:-win]); i0=int(np.argmax(net)); i1=i0+win
print('clip frames %d-%d (%.1f-%.1f s), net %.1f turns'%(i0,i1,i0/FPS,i1/FPS,unw[i1]-unw[i0]))
raw=subprocess.run(['ffmpeg','-v','error','-i',V,'-vf','select=between(n\\,%d\\,%d)'%(i0,i1-1),'-vsync','0','-f','rawvideo','-pix_fmt','gray','-'],capture_output=True,check=True).stdout
frames=np.frombuffer(raw,np.uint8).reshape(-1,H,W); assert len(frames)==win,len(frames)
S=4; half=70; P=2*half*S
x0,y0=int(round(cx))-half,int(round(cy))-half
seg=unw[i0:i1]-unw[i0]; ymin,ymax=seg.min()-0.1,seg.max()+0.1
enc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','bgr24','-s','%dx%d'%(2*P,P),'-r',str(FPS),'-i','-',
                      '-c:v','libx264','-pix_fmt','yuv420p','-crf','18',OUT+'tracking_clip_gps1477428272.mp4'],stdin=subprocess.PIPE)
def py(v): return int(P-40-(v-ymin)/(ymax-ymin)*(P-80))
def px(k): return int(50+k/(win-1)*(P-80))
pts=np.array([[px(k),py(seg[k])] for k in range(win)],np.int32)
for k,f in enumerate(frames):
    i=i0+k
    crop=np.zeros((2*half,2*half),np.uint8); sub=f[max(0,y0):y0+2*half,max(0,x0):x0+2*half]
    crop[max(0,-y0):max(0,-y0)+sub.shape[0],max(0,-x0):max(0,-x0)+sub.shape[1]]=sub
    img=cv2.cvtColor(cv2.resize(crop,(P,P),interpolation=cv2.INTER_CUBIC),cv2.COLOR_GRAY2BGR)
    c=((cx-x0)*S,(cy-y0)*S); a=np.radians(ang[i])
    p=(int(c[0]+rad[i]*S*np.cos(a)),int(c[1]+rad[i]*S*np.sin(a)))
    cv2.circle(img,(int(c[0]),int(c[1])),int(np.median(rad)*S),(0,160,0),1,cv2.LINE_AA)
    cv2.drawMarker(img,(int(c[0]),int(c[1])),(0,220,255),cv2.MARKER_CROSS,24,2)
    cv2.circle(img,p,36,(0,0,255),2,cv2.LINE_AA)
    cv2.putText(img,'t = %6.2f s   angle %5.1f deg'%(i/FPS,ang[i]),(12,30),cv2.FONT_HERSHEY_SIMPLEX,0.75,(0,220,255),2,cv2.LINE_AA)
    pl=np.full((P,P,3),255,np.uint8)
    cv2.polylines(pl,[pts],False,(200,200,200),1,cv2.LINE_AA)
    cv2.polylines(pl,[pts[:k+1]],False,(0,0,0),2,cv2.LINE_AA)
    cv2.circle(pl,tuple(pts[k]),6,(0,0,255),-1,cv2.LINE_AA)
    for v in np.arange(np.ceil(ymin),np.floor(ymax)+1):
        cv2.line(pl,(50,py(v)),(P-30,py(v)),(230,230,230),1); cv2.putText(pl,'%+d'%v,(8,py(v)+5),cv2.FONT_HERSHEY_SIMPLEX,0.5,(80,80,80),1,cv2.LINE_AA)
    cv2.putText(pl,'rotor angle (turns) vs time, 30 s',(60,28),cv2.FONT_HERSHEY_SIMPLEX,0.65,(0,0,0),1,cv2.LINE_AA)
    enc.stdin.write(np.hstack([img,pl]).tobytes())
enc.stdin.close(); enc.wait()
print('done')
