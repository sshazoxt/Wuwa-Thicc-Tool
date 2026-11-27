"""Read-only cross-section occupancy and contour experiments, patch 035."""
import contextlib
from itertools import combinations
import numpy as np
from _hip_root_lab import run, visible, view, compare, report_profile
from preview_no_seam_guard import sandbox, geometry, load_cfg

TITLES={52:'OVERLAP CONTOUR MONITOR',53:'OUTER ENVELOPE HIPS',54:'CONTOUR OWNERSHIP',55:'OVERLAP AWARE REFERENCE',56:'SLICE OVERLAP VOLUME',57:'TOPOLOGY INVARIANCE'}

def segments(tri,z):
    # Half-open edge convention; avoid coincident plane/vertex ambiguity by sampling midpoints.
    tri=tri[(tri[:,:,2].min(1)<z)&(tri[:,:,2].max(1)>z)]
    pts=[]; ids=[]
    for i,j in ((0,1),(1,2),(2,0)):
        a,b=tri[:,i],tri[:,j]; m=(a[:,2]<z)!=(b[:,2]<z)
        a,b=a[m],b[m]; t=(z-a[:,2])/(b[:,2]-a[:,2]); pts.extend(a[:,:2]+t[:,None]*(b[:,:2]-a[:,:2])); ids.extend(np.flatnonzero(m))
    if not ids:return np.empty((0,2,2))
    order=np.argsort(ids,kind='stable'); ids=np.asarray(ids)[order]; pts=np.asarray(pts)[order]
    _,first,count=np.unique(ids,return_index=True,return_counts=True); first=first[count==2]
    return np.stack((pts[first],pts[first+1]),axis=1)

def occupancy(seg,x,y,tol):
    """Parity fill of closed slice loops only; invalid open/branching sections are unknown."""
    if not len(seg):return np.zeros((len(y),len(x)),bool),True
    key=np.rint(seg/tol).astype(np.int64); _,inv=np.unique(key.reshape(-1,2),axis=0,return_inverse=True); e=inv.reshape(-1,2)
    good=e[:,0]!=e[:,1]; e=e[good]; seg=seg[good]
    _,ix=np.unique(np.sort(e,axis=1),axis=0,return_index=True); e=e[ix]; seg=seg[ix]
    _,deg=np.unique(e,return_counts=True)
    if np.any(deg!=2):return None,False
    mask=np.zeros((len(y),len(x)),bool)
    for j,h in enumerate(y):
        a,b=seg[:,0],seg[:,1]; m=(a[:,1]<h)!=(b[:,1]<h); a,b=a[m],b[m]
        cross=np.sort(a[:,0]+(h-a[:,1])*(b[:,0]-a[:,0])/(b[:,1]-a[:,1]))
        if len(cross)%2:return None,False
        mask[j]=np.searchsorted(cross,x,side='right')%2==1
    return mask,True

def scan(p,q,faces,d,res=160,nz=64):
    names=visible(d,faces); tri=d['sv'][d['tri']]; allowed={tuple(sorted(t)) for t in tri}
    ts={n:faces[n][np.array([tuple(sorted(t)) in allowed for t in faces[n]],bool)] for n in names}; ts={n:t for n,t in ts.items() if len(t)}
    lo,hi=d['L']['knee'],d['L']['waist']; dz=(hi-lo)/nz; zs=lo+(np.arange(nz)+.5)*dz
    points=p[np.unique(np.concatenate(list(ts.values())))]; xy0=points[:,:2].min(0); xy1=points[:,:2].max(0); step=max(xy1-xy0)/res; tol=step*1e-4
    x=np.arange(xy0[0]+step/2,xy1[0],step); y=np.arange(xy0[1]+step/2,xy1[1],step)
    pairs=list(combinations(ts,2)); stats={pair:[] for pair in pairs}; widths={n:[] for n in ts}; union=[]; after=[]; counts=[]
    print('Slice spacing cm',dz,'XY cell cm',step,'closure tolerance cm',tol)
    for z in zs:
        masks={}; w=[]; v=[]
        for n,t in ts.items():
            s=segments(p[t],z); s1=segments(q[t],z); m,ok=occupancy(s,x,y,tol); masks[n]=m if ok else None
            a=np.max(np.abs(s[:,:,0])) if len(s) else np.nan; b=np.max(np.abs(s1[:,:,0])) if len(s1) else np.nan
            widths[n].append(a); w.append(a); v.append(b)
            print('SLICE',round(z,4),n,'closed',ok,'half width original/final',a,b)
        union.append(np.nanmax(w) if np.isfinite(w).any() else np.nan); after.append(np.nanmax(v) if np.isfinite(v).any() else np.nan)
        valid=[m for m in masks.values() if m is not None]; counts.append(sum(m is None for m in masks.values()))
        for pair in pairs:
            a,b=(masks[n] for n in pair); area=np.nan if a is None or b is None else np.count_nonzero(a&b)*step**2; stats[pair].append(area)
            if np.isfinite(area) and area>0:print('INTERSECTION',round(z,4),pair,'area cm2',area)
    for pair,values in stats.items():
        a=np.asarray(values); good=np.isfinite(a); hit=good&(a>0)
        print('PAIR',pair,'valid slices',int(good.sum()),'/',nz,'sampled partial volume cm3',np.nansum(a)*dz,'positive Z',zs[hit].tolist())
    return zs,widths,np.asarray(union),np.asarray(after),stats,counts

@contextlib.contextmanager
def outline_trial(mode,faces=None):
    from morphology import calibration as c
    old=c.fixed_core_outline
    def factory(p,t,zs):
        from morphology.geometry import contour
        if mode=='duplicate':return old(p,np.concatenate([t,t[t[:,0]%2==0]]),zs)
        if mode=='split':return old(p,np.concatenate([t[::2],t[1::2]]),zs)
        # Production already excludes arm faces. No second displacement, no vertex deletion.
        masks=[]
        for z in zs:
            x=np.abs(contour(p[t],z)[:,0]); masks.append(np.ones(len(x),bool))
        def evaluate(q):
            out=[]
            for z,m in zip(zs,masks):
                x=np.abs(contour(q[t],z)[:,0]); out.append(np.max(x[m]) if m.any() else np.nan)
            return np.asarray(out)
        return evaluate
    c.fixed_core_outline=factory
    try:yield
    finally:c.fixed_core_outline=old

def execute(num):
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini); saved=load_cfg(root)
        q,d=run(root,p,faces,saved,hips=2.); cases=[('Original',p),('Legacy Hips 2',q)]
        if num in (52,54,56):
            z,w,u,a,stats,invalid=scan(p,q,faces,d,res=240 if num==56 else 120)
            if num==56:scan(p,q,faces,d,res=120)
            for i,h in enumerate(z):
                cand=[(v[i],n) for n,v in w.items() if np.isfinite(v[i])]; owner=max(cand)[1] if cand else None
                print('OWNER',h,owner,'outer original/final',u[i],a[i],'invalid sections',invalid[i])
            # Render actual selected active geometry; individual component panels for diagnostics.
            view(p,faces,cases,d,f'{num} | {TITLES[num]}')
        elif num in (53,55,57):
            modes=('outer',) if num==53 else (('active_unique', 'outer') if num==55 else ('split','duplicate'))
            for mode in modes:
                if mode=='active_unique':r,e=run(root,p,faces,saved,hips=2.,reference=mode)
                else:
                    with outline_trial(mode):r,e=run(root,p,faces,saved,hips=2.)
                compare(q,r,mode); report_profile(p,r,faces,e,mode); cases.append((mode,r))
            view(p,faces,cases,d,f'{num} | {TITLES[num]}')
    print(f'===== EXPERIMENT {num} - {TITLES[num]} FINISHED =====',flush=True)
