"""Phase 1.5: diagnostic-only surface evidence and content-addressed cache."""
import contextlib, hashlib, io, json, os, tempfile, time
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from . import surface_profile as sp
from . import surface_relations as sr
from . import surface_classifier as sc


def welded_groups(P,t,eps):
    ids,inv=np.unique(t,return_inverse=True); q=inv.reshape(-1,3)
    xyz=P[ids]; pairs=cKDTree(xyz).query_pairs(eps,output_type='ndarray')
    a=np.concatenate([q.ravel(),pairs[:,0]]); b=np.concatenate([q[:,[1,2,0]].ravel(),pairs[:,1]])
    _,lab=connected_components(coo_matrix((np.ones(len(a)),(a,b)),shape=(len(ids),len(ids))).tocsr(),directed=False)
    labels=lab[q[:,0]]; order=np.argsort(labels); cuts=np.flatnonzero(np.diff(labels[order]))+1
    return [t[i] for i in np.split(order,cuts)]


def bone_distribution(ids,bi,bw):
    k=bi[ids].ravel(); w=bw[ids].ravel(); unique,ix=np.unique(k,return_inverse=True)
    sums=np.bincount(ix,weights=w); total=sums.sum()
    return dict(zip(unique,sums/total)) if total>0 else {}


def similarity(a,b):
    return sum(min(v,b.get(k,0)) for k,v in a.items())


def calculate(P,draws,L,bi,bw,unified,ini=None,meta=None,independent=False, debug=False):
    span=float(L['crotch']-L['ankle']); eps=max(span*1e-5,1e-7)
    if not np.isfinite(span) or span<=0: print('Invalid interval'); return
    # Retain phase 1.4 output for comparison; cached together with new evidence.
    # DEBUG_ONLY: legacy profile report; no classification inputs.
    if debug: sp.report(P,draws,L,independent=independent)
    print('\n===== SURFACE EVIDENCE (phase 1.5; diagnostic only) =====')
    print(f'Virtual seam tolerance={eps:.6g}; bone namespace: '+('unified' if unified else 'component scoped; cross-draw comparison disabled'))
    zt=np.linspace(L['crotch']+.04*span,L['crotch']+.95*span,61)
    zl=np.linspace(L['ankle']-.08*span,L['crotch']-.06*span,61)
    grids=[('torso',zt,0),('right',zl,1),('left',zl,-1)]
    records=[]; evidence={}
    for name,t,role in draws:
        if not len(t): continue
        ids=np.unique(t); lo,hi=P[ids,2].min(),P[ids,2].max()
        evidence[name]=dict(name=name,role=role,counts=None,waist=False,knees=False,hard=None)
        if debug:
            raw=sp.islands(t); welded=welded_groups(P,t,eps)
            print(f'{name} [{role}]: index islands={len(raw)}; welded islands={len(welded)}')
        if hi-lo<.08*span or hi<zl[0] or lo>zt[-1]: continue
        profiles=[sp.profile(P,t,z,span,s) for _,z,s in grids]
        counts=[int(sp.valid(a).sum()) for a in profiles]
        evidence[name].update(counts=counts,waist=bool(sp.minima(profiles[0],zt,span)),knees=any(bool(sp.minima(a,z,span,L["knee"])) for a,z in zip(profiles[1:],[zl,zl])))
        if debug:
            bones=bone_distribution(ids,bi,bw) if unified else {}
            records.append((name,t,role,lo,hi,profiles,bones,counts))
            if role!='skin' and max(counts)>=12:
                print(f'  Review non-skin surface: closed T/R/L={counts}; not a skin classification')
                for (region,z,s),a in zip(grids,profiles):
                    if not s:
                        for p,h in sp.minima(a,z,span)[:2]: print(f'    waist candidate Z={h:.2f}; prominence={p:.2f}')
    # DEBUG_ONLY: pair profiles and virtual complementary surfaces.
    if debug:
        print('--- PAIR EVIDENCE / ALTERNATIVE OR LAYER ---')
        print('Bone overlap is a whole-draw histogram, not proof of equivalent surfaces or INI exclusivity.')
        for i,(n,t,r,lo,hi,A,a,ac) in enumerate(records):
            for m,u,s,j,k,B,b,bc in records[i+1:]:
                score=similarity(a,b) if unified and a and b else None
                label='n/a' if score is None else f'{score:.1%}'
                for (region,z,side),x,y in zip(grids,A,B):
                    state,overlap,err=sp.compare(x,y,span)
                    if state=='compatible profile':
                        print(f'  {region}: {n} <> {m}; RMS={err:.4f}; overlap={overlap:.0%}; bone overlap={label}; possible variant/layer')
        print('--- VIRTUAL COMPLEMENTARY CANDIDATES ---')
        # Include excluded draws; only test vertically adjacent nontrivial surfaces.
        # Prioritize surfaces with closed evidence, plus selected skin; no global union.
        eligible=[r for r in records if (not independent and r[2]=='skin') or max(r[7])>=12]
        for i,(n,t,r,lo,hi,A,a,ac) in enumerate(eligible):
            for m,u,s,j,k,B,b,bc in eligible[i+1:]:
                overlap=min(hi,k)-max(lo,j)
                if overlap> .35*min(hi-lo,k-j) or overlap<-.03*span: continue
                for (region,z,side),x,y in zip(grids,A,B):
                    if not ((sp.valid(x)|sp.valid(y)).any()): continue
                    c=sp.profile(P,np.concatenate([t,u]),z,span,side)
                    vx,vy,vc=sp.valid(x),sp.valid(y),sp.valid(c)
                    new=vc&~(vx|vy); lost=(vx|vy)&~vc
                    if lost.any() or not new.any() or vc.sum()<=max(vx.sum(),vy.sum()): continue
                    print(f'  {region}: {n} + {m}; closed={vc.sum()}/61; new closed cuts={new.sum()}; lost=0; provisional')
                    if not side:
                        for p,h in sp.minima(c,z,span)[:2]: print(f'    virtual waist candidate Z={h:.2f}; prominence={p:.2f}')
        print('No roles, engine landmarks or vertices changed; no INI exclusivity inferred.')
    top,pairs=sr.report(P,draws,L,bi,bw,unified,ini,meta,debug=debug)
    for name,hard in top.items(): evidence[name]["hard"]=hard
    return sc.report(list(evidence.values()),pairs)

