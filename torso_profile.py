"""Read-only experimental transverse torso profile, independent of deformation."""
import time
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks


def analyze(P, triangles, landmarks):
    span = float(landmarks['crotch'] - landmarks['knee'])
    if not np.isfinite(span) or span <= 0:
        raise ValueError('invalid knee/crotch interval')
    tri = P[triangles]
    low, high = tri[:,:,2].min(1), tri[:,:,2].max(1)
    lo = landmarks['crotch'] + .12*span
    hi = min(landmarks['crotch'] + 1.65*span, high.max())
    if hi <= lo:
        raise ValueError('insufficient torso coverage')
    zs = np.linspace(lo, hi, 81)
    rows = np.full((len(zs), 5), np.nan)
    for i,z in enumerate(zs):
        q = tri[(low <= z)&(high > z)]
        pts = []
        for a,b in ((0,1),(1,2),(2,0)):
            A,B=q[:,a],q[:,b]
            m=(A[:,2]<=z)&(B[:,2]>z) | (B[:,2]<=z)&(A[:,2]>z)
            A,B=A[m],B[m]
            pts.append(A+(B-A)*((z-A[:,2])/(B[:,2]-A[:,2]))[:,None])
        c=np.concatenate(pts)
        if len(c)<8: continue
        # Keep central lateral cluster; scale gap by the model's leg span.
        x=np.sort(c[:,0]); gap=.10*span
        groups=np.split(x,np.flatnonzero(np.diff(x)>gap)+1)
        mid=[g for g in groups if g[0]<0<g[-1]]
        if not mid: continue
        g=max(mid,key=lambda g:g[-1]-g[0]); c=c[(c[:,0]>=g[0])&(c[:,0]<=g[-1])]
        left,right=-g[0],g[-1]
        rows[i]=[left+right,np.ptp(c[:,1]),left,right,min(left,right)/max(left,right)]
    good=np.isfinite(rows[:,0]); smooth=np.full(len(zs),np.nan)
    candidates=[]
    # Never bridge missing geometry. Only interior minima with both shoulders.
    for ids in np.split(np.flatnonzero(good),np.flatnonzero(np.diff(np.flatnonzero(good))>1)+1):
        if len(ids)<11: continue
        w=gaussian_filter1d(rows[ids,0],1.5,mode='nearest'); smooth[ids]=w
        peaks,props=find_peaks(-w,prominence=.015*span,distance=5)
        for k,prom in zip(peaks,props['prominences']):
            j=ids[k]
            if k<4 or k>len(ids)-5: continue
            if not (.30 <= (zs[j]-landmarks['crotch'])/span <= 1.35): continue
            balance=rows[j,4]; coverage=len(ids)/len(zs)
            score=min(1,prom/(.08*span))*balance*coverage
            candidates.append((float(score),int(j),float(prom)))
    candidates.sort(reverse=True)
    return zs,rows,smooth,candidates


def report(P, triangles, landmarks, draws=()):
    start=time.perf_counter()
    print('\n===== TORSO PROFILE (phase 1; diagnostic only) =====')
    print('Source: original selected skin, arms filtered; alternatives may overlap.')
    zs,r,w,c=analyze(P,triangles,landmarks)
    print(' z       width    depth     left    right    slope    curvature')
    for ids in np.split(np.flatnonzero(np.isfinite(w)),np.flatnonzero(np.diff(np.flatnonzero(np.isfinite(w)))>1)+1):
        if len(ids)<3: continue
        slope=np.gradient(w[ids],zs[ids]); curve=np.gradient(slope,zs[ids])
        for j,s,k in zip(ids[::2],slope[::2],curve[::2]):
            print(f'{zs[j]:7.2f} {r[j,0]:8.2f} {r[j,1]:8.2f} {r[j,2]:8.2f} {r[j,3]:8.2f} {s:8.3f} {k:10.3f}')
    print(f'Coverage: {np.isfinite(r[:,0]).mean():.1%}; engine waist: {landmarks["waist"]:.2f}')
    for score,j,prom in c:
        print(f'Waist candidate: Z={zs[j]:.2f} width={r[j,0]:.2f} prominence={prom:.2f} evidence={score:.2f} (heuristic, not probability)')
    if not c: print('Waist unresolved: no supported interior minimum; no fallback applied.')
    else:
        score,j,_=c[0]; above=np.flatnonzero(np.isfinite(w)&(np.arange(len(w))>j)); below=np.flatnonzero(np.isfinite(w)&(np.arange(len(w))<j))
        for label,ids in [('Upper torso flank',above),('Upper hip flank',below)]:
            if len(ids):
                k=ids[np.argmax(w[ids])]; print(f'{label}: Z={zs[k]:.2f}, width={w[k]:.2f} (profile maximum, not anatomical landmark)')
    for name,t in draws:
        try:
            z,rr,ww,cc=analyze(P,t,landmarks)
            print(f'Draw {name}: coverage={np.isfinite(rr[:,0]).mean():.1%}; waist candidates='+(', '.join(f'{z[j]:.2f} ({s:.2f})' for s,j,_ in cc) or 'none'))
        except ValueError as e: print(f'Draw {name}: {e}')
    print(f'Torso profile elapsed: {time.perf_counter()-start:.3f} s; no engine landmarks changed.')


def sections(P, triangles, zs, span):
    """Virtual weld of section edges, not source vertices. Open contours stay open."""
    t=P[triangles]; low=t[:,:,2].min(1); high=t[:,:,2].max(1)
    eps=max(span*1e-5,1e-7); out=[]
    for z in zs:
        q=t[(low<=z)&(high>z)]
        hits=np.zeros((len(q),3,2)); valid=np.zeros((len(q),3),bool)
        for k,(a,b) in enumerate(((0,1),(1,2),(2,0))):
            A,B=q[:,a],q[:,b]; m=(A[:,2]<=z)&(B[:,2]>z)|(B[:,2]<=z)&(A[:,2]>z)
            valid[:,k]=m; hits[m,k]=A[m,:2]+(B[m,:2]-A[m,:2])*((z-A[m,2])/(B[m,2]-A[m,2]))[:,None]
        seg=hits[valid & (valid.sum(1)==2)[:,None]].reshape(-1,2,2)
        if not len(seg): out.append(None); continue
        # Snap near-coincident endpoints; remove repeated undirected segments.
        from scipy.spatial import cKDTree
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        pts=seg.reshape(-1,2); unique,inv=np.unique(pts,axis=0,return_inverse=True)
        pairs=cKDTree(unique).query_pairs(eps,output_type='ndarray')
        graph=coo_matrix((np.ones(len(pairs)),(pairs[:,0],pairs[:,1])),shape=(len(unique),len(unique))).tocsr()
        _,labels=connected_components(graph,directed=False)
        edges=np.unique(np.sort(labels[inv].reshape(-1,2),axis=1),axis=0); edges=edges[edges[:,0]!=edges[:,1]]
        if not len(edges): out.append(None); continue
        count=int(labels.max())+1; coords=np.zeros((count,2)); np.add.at(coords,labels,unique); coords/=np.bincount(labels)[:,None]
        graph=coo_matrix((np.ones(len(edges)),(edges[:,0],edges[:,1])),shape=(count,count)).tocsr()
        _,groups=connected_components(graph,directed=False); degree=np.bincount(edges.ravel(),minlength=count)
        choices=[]
        for g in np.unique(groups[degree>0]):
            ids=np.flatnonzero((groups==g)&(degree>0)); c=coords[ids]
            if not (c[:,0].min()<0<c[:,0].max()): continue
            closed=bool(np.all(degree[ids]==2)); width,depth=np.ptp(c,axis=0)
            choices.append((closed,float(width*depth),float(width),float(depth),int(np.sum(degree[ids]==1))))
        choices.sort(reverse=True)
        out.append((choices[0],len(choices)) if choices else None)
    return out


def report_continuity(P, raw, filtered, landmarks, anatomy, bones=None):
    start=time.perf_counter(); span=landmarks['crotch']-landmarks['knee']
    z,r,w,c=analyze(P,raw,landmarks)
    R=sections(P,raw,z,span); F=sections(P,filtered,z,span); A=sections(P,anatomy,z,span)
    print('\n===== TORSO CONTINUITY (phase 1.1; diagnostic only) =====')
    print('Virtual contour union across selected draws; no gap filling. Anatomy may include clothing/alternatives.')
    ceiling=None
    if bones:
        print('Stickman centroid references (not joint positions): '+str(bones))
        if 'pelvis' in bones and 'head' in bones and bones['head']>bones['pelvis']:
            ceiling=bones['head']
    else: print('Stickman unavailable; geometric candidates only.')
    def desc(v):
        if v is None: return 'missing'
        (closed,_,width,depth,ends),n=v
        return f'{width:.2f}/{depth:.2f} '+('closed' if closed else f'open/branched({ends} ends)')+f' [{n}]'
    print('Z | raw skin W/D | filtered skin W/D | selected anatomy W/D [central contours]')
    for i in range(0,len(z),2): print(f'{z[i]:7.2f} | {desc(R[i])} | {desc(F[i])} | {desc(A[i])}')
    # A true waist candidate needs a locally continuous single closed central contour.
    # Use raw contours so arm filtering cannot manufacture a minimum.
    widths=np.array([v[0][2] if v and v[0][0] and v[1]==1 else np.nan for v in R]); ids=np.flatnonzero(np.isfinite(widths)); found=[]
    for run in np.split(ids,np.flatnonzero(np.diff(ids)>1)+1):
        if len(run)<9: continue
        sm=gaussian_filter1d(widths[run],1.2); peaks,props=find_peaks(-sm,prominence=.015*span)
        for k,p in zip(peaks,props['prominences']):
            j=run[k]; rel=(z[j]-landmarks['crotch'])/span
            if k<4 or k>len(run)-5 or not .30<=rel<=1.35 or (ceiling is not None and z[j]>=ceiling): continue
            found.append((p,j))
    for p,j in sorted(found,reverse=True): print(f'Continuous waist candidate Z={z[j]:.2f}; prominence={p:.2f}; provisional (neck/axilla not yet fully localized)')
    if not found: print('Continuous waist unresolved; incomplete/overlapping contours or no supported minimum. No fallback.')
    print(f'Continuity elapsed: {time.perf_counter()-start:.3f} s; no engine landmarks changed.')


def report_regions(P, raw, filtered, landmarks, bones=None):
    """Experimental landmarks from intact contours; never updates the engine."""
    start=time.perf_counter()
    span=landmarks['crotch']-landmarks['knee']
    if not np.isfinite(span) or span<=0: raise ValueError('invalid leg span')
    z,_,_,_=analyze(P,raw,landmarks)
    R=sections(P,raw,z,span); F=sections(P,filtered,z,span)
    valid=np.array([v is not None and v[0][0] and v[1]==1 for v in R])
    w=np.array([v[0][2] if ok else np.nan for v,ok in zip(R,valid)])
    d=np.array([v[0][3] if ok else np.nan for v,ok in zip(R,valid)])
    print('\n===== ANATOMICAL REGIONS (phase 1.2; diagnostic only) =====')
    print('Raw closed contours; filter compared, not used to remove torso surface.')
    damaged=[i for i in np.flatnonzero(valid) if F[i] is None or not F[i][0][0] or F[i][0][2]<.9*w[i] or F[i][0][3]<.9*d[i]]
    if damaged: print(f'Filter damage: {len(damaged)} sections; first Z={z[damaged[0]]:.2f}; last Z={z[damaged[-1]]:.2f}')
    ids=np.flatnonzero(valid); candidates=[]
    for run in np.split(ids,np.flatnonzero(np.diff(ids)>1)+1):
        if len(run)<9: continue
        ww=gaussian_filter1d(w[run],1.2); dd=gaussian_filter1d(d[run],1.2)
        # A rapid lateral expansion can indicate the arm/torso junction.
        dw=np.diff(w[run]); jumps=np.flatnonzero((dw>.12*span)&(dw>.25*w[run[:-1]]))
        ceiling=z[run[jumps[0]+1]] if len(jumps) else np.inf
        if len(jumps): print(f'Axilla/arm-merge transition candidate Z={ceiling:.2f} (width jump; not a joint)')
        for k in find_peaks(-ww,prominence=.015*span)[0]:
            j=run[k]
            if k<4 or k>len(run)-5 or not .30<=(z[j]-landmarks['crotch'])/span<=1.35 or z[j]>=ceiling: continue
            # Require supported narrowing in width; depth corroborates locally.
            a=max(0,k-4); b=min(len(run)-1,k+4)
            depth_support=min(dd[a],dd[b])-dd[k]
            candidates.append((min(ww[:k].max(),ww[k+1:].max())-ww[k],j,depth_support,ceiling))
        if len(jumps):
            after=run[jumps[0]+1:]; neck=[]
            for j in after[1:-1]:
                if w[j]<=w[j-1] and w[j]<=w[j+1] and w[j]<.5*w[after].max(): neck.append(j)
            if neck: print(f'Neck narrowing candidate Z={z[neck[0]]:.2f}; provisional')
    if candidates:
        p,j,ds,ceiling=max(candidates,key=lambda x:x[0]); print(f'Waist candidate Z={z[j]:.2f}; width={w[j]:.2f}; depth={d[j]:.2f}; prominence={p:.2f}; local depth support={ds:.2f}')
        above=np.flatnonzero(valid&(z>z[j])&(z<ceiling))
        if len(above): print(f'Upper torso supported profile Z={z[above[0]]:.2f}..{z[above[-1]]:.2f}; rib boundary unresolved')
    else: print('Waist unresolved; no fallback.')
    # Use each leg separately. A lateral half is not a closed contour if it crosses midline.
    for side,sgn in [('right',1),('left',-1)]:
        t=raw[(sgn*P[raw,0]>0).all(1)]
        if not len(t): print(f'{side}: no unilateral skin triangles'); continue
        q=P[t]; ankle,knee,crotch=[landmarks[k] for k in ('ankle','knee','crotch')]
        zz=np.linspace(max(q[:,:,2].min(),ankle-.20*span),min(q[:,:,2].max(),crotch-.12*span),101)
        if zz[-1]<=zz[0]: continue
        # Translate only diagnostic copy to make each closed leg contour central at each slice.
        widths=[]; depths=[]
        for h in zz:
            hit=q[(q[:,:,2].min(1)<=h)&(q[:,:,2].max(1)>h)]; pts=[]
            for a,b in ((0,1),(1,2),(2,0)):
                A,B=hit[:,a],hit[:,b]; m=((A[:,2]<=h)&(B[:,2]>h))|((B[:,2]<=h)&(A[:,2]>h)); A,B=A[m],B[m]
                pts.append(A+(B-A)*((h-A[:,2])/(B[:,2]-A[:,2]))[:,None])
            c=np.concatenate(pts); widths.append(np.ptp(c[:,0]) if len(c)>=6 else np.nan); depths.append(np.ptp(c[:,1]) if len(c)>=6 else np.nan)
        widths=np.array(widths); depths=np.array(depths)
        print(f'{side} leg: engine knee={knee:.2f}, ankle={ankle:.2f}; geometric candidates only')
        for name,ref in [('knee',knee),('ankle',ankle)]:
            ix=np.flatnonzero(np.isfinite(widths)&(abs(zz-ref)<=.22*span)); found=[]
            for run in np.split(ix,np.flatnonzero(np.diff(ix)>1)+1):
                if len(run)<5: continue
                sm=gaussian_filter1d(widths[run],1.0)
                for k in find_peaks(-sm,prominence=.005*span)[0]:
                    if k>0 and k<len(run)-1: found.append(run[k])
            if found:
                j=min(found,key=lambda j:abs(zz[j]-ref)); print(f'  {name} narrowing Z={zz[j]:.2f} W/D={widths[j]:.2f}/{depths[j]:.2f}; protected extent unresolved')
            else: print(f'  {name} narrowing unresolved (no supported local minimum)')
    print(f'Region elapsed: {time.perf_counter()-start:.3f} s; no engine landmarks changed.')
