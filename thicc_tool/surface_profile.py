"""Phase 1.4: read-only evidence from independent draws and connected islands."""
import time
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from torso_profile import sections


def islands(t):
    ids, inv = np.unique(t, return_inverse=True)
    q = inv.reshape(-1, 3)
    a=q.ravel(); b=q[:,[1,2,0]].ravel()
    g=coo_matrix((np.ones(len(a)),(a,b)),shape=(len(ids),len(ids))).tocsr()
    _, lab=connected_components(g,directed=False)
    labels=lab[q[:,0]]
    order=np.argsort(labels); cuts=np.flatnonzero(np.diff(labels[order]))+1
    return [t[i] for i in np.split(order,cuts)]


def profile(P,t,z,span,side=0):
    out=np.full((len(z),4),np.nan)
    if side: t=t[(side*P[t,0]>0).all(1)]
    if not len(t): return out
    # Per-cut recentering for unilateral contours; source coordinates untouched.
    ids, inv=np.unique(t,return_inverse=True); Q=P[ids].copy(); tt=inv.reshape(-1,3)
    q=Q[tt]; low=q[:,:,2].min(1); high=q[:,:,2].max(1)
    for i,h in enumerate(z):
        hit=q[(low<=h)&(high>h)]
        if not len(hit): continue
        pts=[]
        for a,b in ((0,1),(1,2),(2,0)):
            A,B=hit[:,a],hit[:,b]; m=((A[:,2]<=h)&(B[:,2]>h))|((B[:,2]<=h)&(A[:,2]>h)); A,B=A[m],B[m]
            pts.append(A[:,:2]+(B[:,:2]-A[:,:2])*((h-A[:,2])/(B[:,2]-A[:,2]))[:,None])
        c=np.concatenate(pts)
        if not len(c): continue
        center=(c[:,0].min()+c[:,0].max())/2 if side else 0.
        R=Q.copy(); R[:,0]-=center
        v=sections(R,tt,[h],span)[0]
        if v and v[0][0] and v[1]==1:
            out[i]=v[0][2],v[0][3],center,(c[:,1].min()+c[:,1].max())/2
    return out


def valid(a): return np.isfinite(a[:,0])


def minima(a,z,span,ref=None):
    found=[]; ids=np.flatnonzero(valid(a))
    for run in np.split(ids,np.flatnonzero(np.diff(ids)>1)+1):
        if len(run)<9: continue
        w=gaussian_filter1d(a[run,0],1.2)
        k,props=find_peaks(-w,prominence=.008*span)
        for j,p in zip(k,props['prominences']):
            if j<3 or j>=len(run)-3: continue
            h=z[run[j]]
            if ref is not None and abs(h-ref)>.24*span: continue
            found.append((float(p),float(h)))
    return sorted(found,reverse=True)


def compare(a,b,span):
    va,vb=valid(a),valid(b); both=va&vb
    if both.sum()<8: return 'insufficient overlap',0.,np.nan
    overlap=both.sum()/min(va.sum(),vb.sum())
    err=np.sqrt(np.mean((a[both]-b[both])**2))/span
    return ('compatible profile' if overlap>=.75 and err<=.025 else 'different profile'),overlap,err


def report(P,draws,L):
    start=time.perf_counter(); span=float(L['crotch']-L['ankle'])
    print('\n===== INDEPENDENT SURFACES (phase 1.4; diagnostic only) =====')
    if not np.isfinite(span) or span<=0: print('Invalid search interval'); return
    # Broad windows inherited from current model references, not fixed centimeters.
    zt=np.linspace(L['crotch']+.04*span,L['crotch']+.95*span,61)
    zl=np.linspace(L['ankle']-.08*span,L['crotch']-.06*span,61)
    grids=[('torso',zt,0),('right',zl,1),('left',zl,-1)]
    records=[]; skipped=0
    for name,t,role in draws:
        if not len(t): continue
        lo,hi=P[t,2].min(),P[t,2].max()
        if hi-lo<.08*span or hi<zl[0] or lo>zt[-1]: skipped+=1; continue
        groups=islands(t); significant=[g for g in groups if np.ptp(P[g,2])>=.12*span and len(g)>=12]
        significant.sort(key=len,reverse=True)
        tests=[(name,t)] + [(f'{name} / island {i+1}',g) for i,g in enumerate(significant[:6]) if len(g)<len(t)]
        print(f'Draw {name} [{role}]: Z={lo:.2f}..{hi:.2f}; islands={len(groups)}; significant={len(significant)}; tested individually={len(tests)-1}')
        for label,g in tests:
            profiles=[profile(P,g,z,span,s) for _,z,s in grids]
            counts=[int(valid(a).sum()) for a in profiles]
            print(f'  {label}: closed T/R/L={counts[0]}/{counts[1]}/{counts[2]} of 61')
            for (region,z,s),a in zip(grids,profiles):
                refs=[('waist',None)] if not s else [('knee',L['knee']),('ankle',L['ankle'])]
                for kind,ref in refs:
                    peaks=minima(a,z,span,ref)
                    if peaks: print(f'    {region} {kind} narrowing: '+', '.join(f'Z={h:.2f} (prom={p:.2f})' for p,h in peaks[:3]))
            if max(counts)>=8: records.append((label,role,profiles,g))
    print(f'Skipped short/outside draws: {skipped}; island cap six per draw; open cuts not filled.')
    print('--- PROFILE COMPATIBILITY (not proof of interchangeable INI conditions) ---')
    for i,(n,r,A,t) in enumerate(records):
        for m,s,B,u in records[i+1:]:
            if n.split(' / island ')[0]==m.split(' / island ')[0]: continue
            for (region,_,_),a,b in zip(grids,A,B):
                state,overlap,err=compare(a,b,span)
                if state=='compatible profile': print(f'  {region}: {n} <> {m}; overlap={overlap:.0%}; normalized RMS={err:.4f}')
    print('--- COMPLEMENTARY DRAW TEST (virtual union, selected skin only) ---')
    # Test pairs with adjacent/partially overlapping vertical extents. Never merge variants globally.
    skin=[(n,t) for n,t,r in draws if r=='skin' and len(t)]
    for i,(n,t) in enumerate(skin):
        for m,u in skin[i+1:]:
            a,b=P[t,2],P[u,2]; overlap=min(a.max(),b.max())-max(a.min(),b.min())
            if overlap> .35*min(np.ptp(a),np.ptp(b)) or overlap<-.03*span: continue
            for region,z,s in grids:
                A=profile(P,t,z,span,s); B=profile(P,u,z,span,s); C=profile(P,np.concatenate([t,u]),z,span,s)
                gained=valid(C)&~(valid(A)|valid(B)); lost=(valid(A)|valid(B))&~valid(C)
                if gained.any() or (valid(C).sum()>max(valid(A).sum(),valid(B).sum()) and not lost.any()):
                    print(f'  {region}: {n} + {m}; closed={valid(C).sum()}/61; new weld cuts={gained.sum()}; lost={lost.sum()}; provisional')
    print(f'Surface analysis elapsed: {time.perf_counter()-start:.3f} s; no roles, landmarks or vertices changed.')
