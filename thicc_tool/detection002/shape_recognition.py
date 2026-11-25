"""Experimental read-only shape inventory. No sculpt or INI writes."""
import argparse, hashlib, json, time
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
VERSION=3

def section_signature(tt, zz, h):
    # Intersect triangles with a plane; preserve separate contours and open curves.
    pts=np.zeros((len(tt),3,2)); counts=np.zeros(len(tt),int)
    for u,v in ((0,1),(1,2),(2,0)):
        aa,bb=tt[:,u],tt[:,v]; ix=np.flatnonzero((aa[:,2]<zz)!=(bb[:,2]<zz))
        a,b=aa[ix],bb[ix]; pts[ix,counts[ix]]=a[:,:2]+((zz-a[:,2])/(b[:,2]-a[:,2]))[:,None]*(b[:,:2]-a[:,:2]); counts[ix]+=1
    seg=pts[counts==2,:2]; length=np.linalg.norm(seg[:,1]-seg[:,0],axis=1); seg=seg[length>h*1e-8]; length=length[length>h*1e-8]
    if not len(seg): return None
    xy=seg.reshape(-1,2); _,inv=np.unique(np.round(xy/h,5),axis=0,return_inverse=True); edges=inv.reshape(-1,2)
    n=int(inv.max())+1; k,labels=connected_components(coo_matrix((np.ones(len(edges)),(edges[:,0],edges[:,1])),shape=(n,n)).tocsr(),directed=False)
    degree=np.bincount(inv,minlength=n); contours=[]
    for j in range(k):
        sel=labels[edges[:,0]]==j; v=seg[sel]; w=length[sel]; center=np.average(v.mean(1),axis=0,weights=w); widths=np.ptp(v.reshape(-1,2),axis=0)
        closed=bool(np.all(degree[labels==j]==2)); contours.append(dict(center=(center/h).tolist(),width=(widths/h).tolist(),length=float(w.sum()/h),closed=closed))
    contours.sort(key=lambda c:c['length'],reverse=True)
    center=np.average(seg.mean(1),axis=0,weights=length)
    return dict(z=float(zz/h),center=(center/h).tolist(),width=(np.ptp(xy,axis=0)/h).tolist(),length=float(length.sum()/h),contours=contours[:8],count=k)

def describe(p,t,h,debug=False,vertex_ids=None,local_faces=None,points=None):
    ids = np.unique(t) if vertex_ids is None else vertex_ids
    inv=np.searchsorted(ids,t) if local_faces is None else local_faces; q=p[ids] if points is None else points
    # Weld duplicate seam positions for analysis only, never edit the source.
    _, w=np.unique(np.round(q/max(h,1e-9),5),axis=0,return_inverse=True)
    a=w[inv]; x=a.ravel(); y=a[:,[1,2,0]].ravel()
    k,l=connected_components(coo_matrix((np.ones(len(x),dtype=np.uint8),(x,y)),shape=(int(w.max())+1,)*2).tocsr(),directed=False)
    tri=q[inv]; area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
    areas=np.bincount(l[a[:,0]],weights=area,minlength=k); total=max(float(areas.sum()),1e-12)
    islands=[]
    for j in np.argsort(areas)[::-1][:12]:
        mask=l[w]==j; r=q[mask]; z=r[:,2]; ext=np.ptp(r,axis=0); frac=float(areas[j]/total)
        item=dict(area_fraction=frac,extent=(ext/h).tolist(),low=(r.min(0)/h).tolist(),high=(r.max(0)/h).tolist())
        # DEBUG_ONLY: detailed PCA and section signatures.
        if debug:
            # Area-weighted faces give a less tessellation-dependent PCA.
            f=l[a[:,0]]==j; centers=tri[f].mean(1); weights=area[f]; mu=np.average(centers,axis=0,weights=weights) if weights.sum()>0 else centers.mean(0)
            d=centers-mu; cov=(d*weights[:,None]).T@d/max(float(weights.sum()),1e-12); eig=np.maximum(np.linalg.eigvalsh(cov)[::-1],0)
            # Occupied cross section proxy from actual triangle/plane intersections.
            sections=[]; tt=tri[f]; low=tt[:,:,2].min(1); high=tt[:,:,2].max(1)
            signatures=[]
            for zz in np.linspace(float(z.min()),float(z.max()),18)[1:-1]:
                sig=section_signature(tt[(low<zz)&(high>=zz)],zz,h)
                if sig is None: continue
                signatures.append(sig); sections.append([sig['z'],*sig['width'],*sig['center']])
            widths=np.array([v['width'] for v in signatures]); centers=np.array([v['center'] for v in signatures]); zs=np.array([v['z'] for v in signatures]); span=max(ext[2]/h,1e-9)
            morph=dict(samples=len(signatures),drift=float(np.linalg.norm(np.diff(centers,axis=0),axis=1).sum()/span) if len(centers)>1 else None, width_ratio=float(np.median(widths[:,0])/max(np.median(widths[:,1]),1e-9)) if len(widths) else None, bilateral=float(np.mean([any(c['center'][0]<-.01 for c in v['contours']) and any(c['center'][0]>.01 for c in v['contours']) for v in signatures])) if signatures else None)
            item.update(pca=(eig/max(float(eig.sum()),1e-12)).tolist(),sections=sections,signatures=signatures,morph=morph)
        islands.append(item)
    # Conservative shape candidates, not semantic skin classification.
    lower=[i for i in islands if i['extent'][2]>.25 and i['low'][2]<.36 and i['high'][2]>.35 and i['area_fraction']>.12 and .035<i['extent'][0]<.60 and .025<i['extent'][1]<.45 and abs((i['low'][1]+i['high'][1])/2)<.18]
    if lower: label='candidato volumen inferior'
    elif islands[0]['area_fraction']<.25 and k>12: label='fragmentado: revisar accesorios'
    else: label='indeterminado'
    return dict(vertices=len(ids),islands=int(k),surface=float(total),dominant=float(areas.max()/total),label=label,profiles=islands)

