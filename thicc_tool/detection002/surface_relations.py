"""Phase 1.6: read-only topology, regional bone and proximity evidence."""
import re
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


def topology(P,t,eps,debug=True,vertex_ids=None):
    ids=np.unique(t) if vertex_ids is None else vertex_ids; q=P[ids]; f=np.searchsorted(ids,t)
    pairs=cKDTree(q).query_pairs(eps,output_type='ndarray')
    _,lab=connected_components(coo_matrix((np.ones(len(pairs)),(pairs[:,0],pairs[:,1])),shape=(len(q),len(q))).tocsr(),directed=False)
    _,first=np.unique(lab,return_index=True); q=q[first]; f=lab[f]
    v=q[f]; cross=np.cross(v[:,1]-v[:,0],v[:,2]-v[:,0]); area=np.linalg.norm(cross,axis=1)/2
    good=area>eps**2; deg=int((~good).sum()); f=f[good]; v=v[good]; area=area[good]; cross=cross[good]
    if not len(f): return None
    # Duplicated faces do not create false nonmanifold edges.
    _,keep=np.unique(np.sort(f,axis=1),axis=0,return_index=True); f=f[keep]; v=v[keep]; area=area[keep]; cross=cross[keep]
    normals=cross/(2*area[:,None]); edges=np.sort(f[:,[0,1,1,2,2,0]].reshape(-1,2),axis=1)
    _,ix,cnt=np.unique(edges,axis=0,return_inverse=True,return_counts=True); order=np.argsort(ix); starts=np.r_[0,np.cumsum(cnt)[:-1]]
    two=starts[cnt==2]; a=order[two]//3; b=order[two+1]//3
    angles=np.degrees(np.arccos(np.clip(np.sum(normals[a]*normals[b],axis=1),-1,1)))
    hist=np.histogram(angles,bins=[0,15,30,45,90,181])[0]; hist=hist/max(1,hist.sum())
    # DEBUG_ONLY: boundary loops are not classifier inputs.
    boundary=[]; loops=0
    if debug:
        boundary=edges[order[starts[cnt==1]]]; loops=0
        if len(boundary):
            nodes,iv=np.unique(boundary,return_inverse=True); e=iv.reshape(-1,2); _,g=connected_components(coo_matrix((np.ones(len(e)),(e[:,0],e[:,1])),shape=(len(nodes),len(nodes))).tocsr(),directed=False)
            degree=np.bincount(e.ravel(),minlength=len(nodes)); loops=sum(np.all(degree[g==k]==2) for k in np.unique(g))
    # Area-weighted deterministic sampling, independent of vertex density.
    rng=np.random.default_rng(160); n=min(1800,max(200,len(f))); ix=rng.choice(len(f),n,p=area/area.sum()); u=rng.random((n,2)); u[u.sum(1)>1]=1-u[u.sum(1)>1]
    sample=v[ix,0]+u[:,0,None]*(v[ix,1]-v[ix,0])+u[:,1,None]*(v[ix,2]-v[ix,0])
    return sample,normals[ix],hist,len(boundary),int((cnt>2).sum()),loops,deg,area.sum()


def bone_cloud(P,ids,bi,bw):
    k=bi[ids].ravel(); w=bw[ids].ravel(); xyz=np.repeat(P[ids],bi.shape[1],axis=0); good=w>0; k=k[good]; w=w[good]; xyz=xyz[good]
    keys,inv=np.unique(k,return_inverse=True); mass=np.bincount(inv,weights=w); c=np.zeros((len(keys),3)); np.add.at(c,inv,xyz*w[:,None]); c/=mass[:,None]
    return keys,c,mass/mass.sum() if mass.sum() else mass


def conditions(ini,meta):
    if not ini: return {}
    lines=open(ini,encoding='utf8',errors='replace').read().splitlines(); targets={v['line']:k for k,v in meta.items()}; stack=[]; result={}
    for i,line in enumerate(lines,1):
        s=line.split(';',1)[0].strip(); low=s.lower()
        if s.startswith('['): stack=[]
        elif low.startswith('if '): stack.append([i,s[3:],0])
        elif low.startswith('else') and stack: stack[-1][2]+=1
        elif low=='endif' and stack: stack.pop()
        if i in targets: result[targets[i]]=tuple((a,b,c) for a,b,c in stack)
    return result


def report(P,draws,L,bi,bw,unified,ini=None,meta=None,debug=True):
    span=float(L['crotch']-L['ankle']); print('\n===== SURFACE RELATIONS (phase 1.6; diagnostic only) =====')
    if not np.isfinite(span) or span<=0:return {},[]
    eps=max(span*1e-5,1e-7); near=.035*span; cond=conditions(ini,meta or {}); records=[]; top={}; pairs=[]
    for name,t,role in draws:
        if not len(t):continue
        r=topology(P,t,eps,debug=debug)
        if r is None:continue
        s,n,h,b,nm,loops,deg,area=r; lo,hi=np.min(s,axis=0),np.max(s,axis=0)
        if debug:
            z=np.quantile(s[:,2],[.01,.5,.99]); raw=P[t,2]
            print(f'{name} [{role}]: area={area:.2f}; Z raw={raw.min():.2f}..{raw.max():.2f}; area Z01/50/99={z.round(2)}; boundary={b}; loops={loops}; nonmanifold={nm}; degenerate={deg}; dihedral%={np.round(h*100,1)}')
        top[name]=float(h[3:].sum()) if h.sum()>0 else None
        if cond.get(name):print('  INI branches:',cond[name])
        records.append((name,role,t,s,n,lo,hi,cKDTree(s)))
    print('--- REGIONAL PROXIMITY / BONE EVIDENCE ---')
    for i,(a,ra,t,x,n,lo,hi,tree) in enumerate(records):
        for b,rb,u,y,m,l,k,other in records[i+1:]:
            if np.any(np.maximum(lo,l)-np.minimum(hi,k)>near):continue
            d,j=other.query(x); e,v=tree.query(y); p=d<near; q=e<near
            if max(p.mean(),q.mean())<.20:continue
            # Local overlap region, not whole-draw bone distributions.
            low=np.maximum(lo,l)-near; high=np.minimum(hi,k)+near
            def regional(t):
                ids=np.unique(t); pts=P[ids]; return ids[((pts>=low)&(pts<=high)).all(1)]
            ia,ib=regional(t),regional(u); bone='n/a'; bone_score=None
            if len(ia) and len(ib):
                A,C,W=bone_cloud(P,ia,bi,bw); B,D,V=bone_cloud(P,ib,bi,bw)
                if unified:
                    bm=dict(zip(B,V)); bone_score=sum(min(w,bm.get(k,0)) for k,w in zip(A,W)); bone=f'global overlap={bone_score:.1%}'
                elif len(A) and len(B):
                    da,ja=cKDTree(D).query(C); db,jb=cKDTree(C).query(D); ok=(jb[ja]==np.arange(len(A)))&(da<near)
                    score=np.minimum(W[ok],V[ja[ok]]).sum(); bone_score=float(score); bone=f'local centroid candidate overlap={score:.1%} ({ok.sum()} mutual pairs; not bone identity)'
            align=np.median(np.abs(np.sum(n[p]*m[j[p]],axis=1))) if p.any() else np.nan
            if debug: signed=np.median(np.sum((x[p]-y[j[p]])*m[j[p]],axis=1))/span if p.any() else np.nan
            exclusive=any(i==j and c!=d for i,_,c in cond.get(a,()) for j,_,d in cond.get(b,()))
            pairs.append(dict(names=(a,b),near=(float(p.mean()),float(q.mean())),align=align,bone=bone_score,exclusive=exclusive))
            if debug: print(f'  {a} <> {b}: nearby A/B={p.mean():.1%}/{q.mean():.1%}; median distances/span={np.median(d)/span:.4f}/{np.median(e)/span:.4f}; normal alignment={align:.3f}; signed local projection/span={signed:.4f}; {bone}; same-if distinct branch={exclusive}')
    print('Proximity uses sampled surfaces, not exact raycasting or closed-volume containment. No roles changed.')
    return top,pairs
