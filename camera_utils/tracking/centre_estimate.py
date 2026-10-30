"""Estimate the rotation centre of the rotor in a Basler recording, three ways.

    python centre_estimate.py VIDEO.avi WIDTH HEIGHT

a) circle fit to the edge of the region that moves (frame-to-frame spread)
b) circle fit to the white blob's path (rough detector: largest compact bright spot)
c) least-squares crossing point of the sail line over all frames

Prints all three; a person picks the centre by eye on overlaid frames and records it in
centre_gps<GPS>.json. FFV1 is decoded with ffmpeg (OpenCV on the Mac can't read it).
First used 2026-10-30 on output_basler_gps1477419607.avi: c) = (116.2, 180.2) was chosen.
"""
import subprocess, sys
import numpy as np, cv2
video, W, H = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                     capture_output=True, check=True).stdout
a = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32); n = len(a)
med=np.median(a[::5],axis=0); sd=a[::5].std(axis=0)

def fit_circle(x,y):
    A=np.c_[2*x,2*y,np.ones_like(x)]; b=x**2+y**2
    (cx,cy,c),*_=np.linalg.lstsq(A,b,rcond=None); return cx,cy,np.sqrt(c+cx**2+cy**2)

# (a) edge of the moving region in the spread image
m=(sd>0.35*sd.max()).astype(np.uint8)
cnts,_=cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
c=max(cnts,key=cv2.contourArea)[:,0,:].astype(float)
A=fit_circle(c[:,0],c[:,1]); print('a) spread-disc edge  cx=%.1f cy=%.1f R=%.1f'%A)

# per frame: bright components above the median
lines=[]; blobs=[]
y0,x0=int(A[1]),int(A[0]); R=int(A[2])+6
for i in range(n):
    d=a[i]-med
    sub=np.zeros_like(d); sub[y0-R:y0+R,x0-R:x0+R]=d[y0-R:y0+R,x0-R:x0+R]
    thr=max(40,np.percentile(sub[y0-R:y0+R,x0-R:x0+R],98.5))
    bw=(sub>thr).astype(np.uint8)
    k,lab,st,cen=cv2.connectedComponentsWithStats(bw)
    for j in range(1,k):
        if st[j,4]<8: continue
        ys,xs=np.nonzero(lab==j); pts=np.c_[xs,ys].astype(float); mu=pts.mean(0)
        ev,evec=np.linalg.eigh(np.cov((pts-mu).T)); elong=np.sqrt(ev[1]/max(ev[0],1e-3))
        if elong>4 and st[j,4]>=15: lines.append((mu,evec[:,1],i))
        elif elong<2.5: blobs.append((mu,st[j,4],i))
# (c) sail lines: point nearest all lines
P=np.zeros((2,2)); q=np.zeros(2)
for mu,v,_ in lines:
    M=np.eye(2)-np.outer(v,v); P+=M; q+=M@mu
cs=np.linalg.solve(P,q); print('c) sail-line crossing cx=%.1f cy=%.1f  (%d frames with a line)'%(cs[0],cs[1],len(set(l[2] for l in lines))))
# (b) blob orbit: largest compact component per frame
best={}
for mu,area,i in blobs:
    if i not in best or area>best[i][1]: best[i]=(mu,area)
bx=np.array([v[0] for v in best.values()])
B=fit_circle(bx[:,0],bx[:,1])
r=np.hypot(bx[:,0]-B[0],bx[:,1]-B[1])
print('b) blob-orbit fit     cx=%.1f cy=%.1f R=%.1f   (%d frames; radial scatter %.1f px)'%(B[0],B[1],B[2],len(bx),r.std()))

print('--- refined')
# blob orbit with iterative outlier rejection
pts=bx.copy()
for it in range(6):
    cx,cy,R=fit_circle(pts[:,0],pts[:,1]); r=np.hypot(pts[:,0]-cx,pts[:,1]-cy)
    keep=np.abs(r-np.median(r))<2.5*1.4826*np.median(np.abs(r-np.median(r)))
    pts=pts[keep]
print('b) blob orbit (robust)  cx=%.1f cy=%.1f R=%.1f  kept %d/%d, radial scatter %.2f px'%(cx,cy,R,len(pts),len(bx),np.hypot(pts[:,0]-cx,pts[:,1]-cy).std()))
Bb=(cx,cy)
# sail: line midpoints and robust crossing
mids=np.array([l[0] for l in lines])
print('   sail-component centroid median  x=%.1f y=%.1f'%tuple(np.median(mids,0)))
L=lines
for it in range(5):
    P=np.zeros((2,2)); q=np.zeros(2)
    for mu,v,_ in L:
        M=np.eye(2)-np.outer(v,v); P+=M; q+=M@mu
    cs=np.linalg.solve(P,q)
    d=np.array([abs(np.cross(v,cs-mu)) for mu,v,_ in L])
    L=[l for l,dd in zip(L,d) if dd<max(2.0,np.median(d)*2.5)]
print('c) sail crossing (robust) cx=%.1f cy=%.1f  kept %d lines, median miss %.2f px'%(cs[0],cs[1],len(L),np.median(d)))
