import subprocess, numpy as np, cv2, sys
W,H=256,292; step=5
p=subprocess.Popen(['ffmpeg','-v','error','-i','v.avi','-vf',f"select=not(mod(n\\,{step}))",'-vsync','0','-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE)
f0=None; out=[]
# static reference patch on the board (upper-left board area), for camera/table motion
ry0,ry1,rx0,rx1=60,120,10,70
k=0
while True:
    buf=p.stdout.read(W*H)
    if len(buf)<W*H: break
    g=np.frombuffer(buf,np.uint8).reshape(H,W).astype(np.float32)
    if f0 is None:
        f0=g.copy(); ref=f0[ry0:ry1,rx0:rx1]; ref=(ref-ref.mean())/ref.std()
    # spot centroid in an ROI around (x 103, y 152)
    y0,y1,x0,x1=130,175,80,128
    roi=cv2.GaussianBlur(g[y0:y1,x0:x1],(3,3),0)
    thr=np.percentile(roi,97)
    w=np.clip(roi-thr,0,None)
    yy,xx=np.mgrid[y0:y1,x0:x1]
    cy,cx=(w*yy).sum()/w.sum(),(w*xx).sum()/w.sum()
    # board shift by phase correlation of a static patch
    (sx,sy),_=cv2.phaseCorrelate(f0[ry0-10:ry1+10,rx0-10:rx1+10].astype(np.float64), g[ry0-10:ry1+10,rx0-10:rx1+10].astype(np.float64))
    out.append((k*step, cx, cy, sx, sy, roi.max(), g.mean()))
    k+=1
np.save('spot.npy',np.array(out)); print('frames',k)
