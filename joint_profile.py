"""Read-only bilateral joint profile; candidates, not rig joint coordinates."""
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from torso_profile import sections


def report(P, raw, L, sinfo=None):
    print('\n===== JOINT PROFILE (phase 1.3; diagnostic only) =====')
    ankle,knee,crotch=(float(L[k]) for k in ('ankle','knee','crotch'))
    span=crotch-ankle
    if not np.isfinite(span) or span<=0 or not ankle<knee<crotch:
        print('Invalid reference interval; unresolved.'); return
    z=np.linspace(ankle-.08*span,crotch-.06*span,121)
    for side,sgn in [('right',1),('left',-1)]:
        t=raw[(sgn*P[raw,0]>0).all(1)]
        if not len(t): print(side, 'no unilateral skin'); continue
        # Center diagnostic coordinates at each cut using intersection bounds.
        used=np.unique(t); Q=P.copy(); q=P[t]; low=q[:,:,2].min(1); high=q[:,:,2].max(1)
        widths=[]; depths=[]
        for h in z:
            hit=q[(low<=h)&(high>h)]; pts=[]
            for a,b in ((0,1),(1,2),(2,0)):
                A,B=hit[:,a],hit[:,b]; m=((A[:,2]<=h)&(B[:,2]>h))|((B[:,2]<=h)&(A[:,2]>h)); A,B=A[m],B[m]
                pts.append(A+(B-A)*((h-A[:,2])/(B[:,2]-A[:,2]))[:,None])
            c=np.concatenate(pts)
            if not len(c): widths.append(np.nan); depths.append(np.nan); continue
            center=(c[:,0].min()+c[:,0].max())/2
            Q[used,0]=P[used,0]-center
            v=sections(Q,t,[h],span)[0]
            if v and v[0][0] and v[1]==1: widths.append(v[0][2]); depths.append(v[0][3])
            else: widths.append(np.nan); depths.append(np.nan)
        W,D=np.array(widths),np.array(depths); valid=np.flatnonzero(np.isfinite(W)&np.isfinite(D))
        print(f'{side}: closed sections {len(valid)}/{len(z)}; engine knee={knee:.2f}, ankle={ankle:.2f}')
        if sinfo:
            chain=sinfo['paths'].get('foot_r' if sgn==1 else 'foot_l',[])
            print('  bone centroid Z (not joint centers):', ', '.join(f'{sinfo["centroid"][b,2]:.2f}' for b in chain))
        for name,ref in [('knee',knee),('ankle',ankle)]:
            candidates=[]
            for run in np.split(valid,np.flatnonzero(np.diff(valid)>1)+1):
                if len(run)<9: continue
                w=gaussian_filter1d(W[run],1.4); d=gaussian_filter1d(D[run],1.4)
                # Equivalent ellipse area proxy; also inspect width separately.
                a=np.sqrt(w*d)
                for metric,label in [(a,'W/D'),(w,'width')]:
                    peaks,props=find_peaks(-metric,prominence=.003*span)
                    for k,p in zip(peaks,props['prominences']):
                        j=run[k]
                        if abs(z[j]-ref)>.24*span or k<3 or k>len(run)-4: continue
                        # Half-prominence envelope, diagnostic only; reject truncated extent.
                        level=metric[k]+.5*p; lo=hi=k
                        while lo>0 and metric[lo]<level: lo-=1
                        while hi<len(run)-1 and metric[hi]<level: hi+=1
                        extent=(z[run[lo]],z[run[hi]]) if metric[lo]>=level and metric[hi]>=level else None
                        candidates.append((abs(z[j]-ref)/span-.15*(label=='W/D'),j,label,p,extent))
            if not candidates: print(f'  {name}: unresolved; no supported closed-contour minimum'); continue
            _,j,label,p,extent=min(candidates,key=lambda x:x[0])
            print(f'  {name}: candidate Z={z[j]:.2f} W/D={W[j]:.2f}/{D[j]:.2f} metric={label} prominence={p:.3f}')
            print('    provisional transition envelope '+(f'Z={extent[0]:.2f}..{extent[1]:.2f}' if extent else 'unresolved'))
        print('  Z | width | depth (closed only)')
        for i in range(0,len(z),4): print(f'  {z[i]:.2f} | {W[i]:.2f} | {D[i]:.2f}')
    print('No engine landmarks or vertices changed.')
