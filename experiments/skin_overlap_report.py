"""Report geometric overlap, exact quantized triangles and frozen/skin contacts."""

EXPERIMENT_INFO = {'description': 'Report geometric overlaps and exact quantized triangles.', 'objective': 'Locate duplicated and nearby surfaces.', 'visual': 'Console only', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

from itertools import combinations
import numpy as np
from scipy.spatial import cKDTree
from preview_no_seam_guard import sandbox, geometry, ids_for


def triangle_keys(p,t,tol):
    # Orientation and vertex indexing independent; quantization is not exact intersection.
    q=np.rint(p[t]/tol).astype(np.int64)
    order=np.lexsort((q[:,:,2],q[:,:,1],q[:,:,0]),axis=1)
    q=np.take_along_axis(q,order[:,:,None],axis=1)
    return set(map(tuple,q.reshape(-1,9)))


def pair_report(p,faces,roles,active,H):
    skin=[n for n in faces if roles.get(n)=='skin' and faces[n].size]
    frozen=[n for n in faces if roles.get(n)=='frozen' and faces[n].size]
    ids={n:np.unique(faces[n]) for n in skin+frozen}
    trees={n:cKDTree(p[v]) for n,v in ids.items()}
    tol=max(H*1e-6,1e-8); near=H*.001
    keys={n:triangle_keys(p,faces[n],tol) for n in skin}
    print('\n===== SKIN OVERLAP / ORIGINAL GEOMETRY =====')
    print('Exact proximity tolerance %.6f cm; near tolerance %.4f cm'%(tol,near))
    print('Near vertices are NOT proof of triangle intersection. Triangle duplicates use coordinate quantization.')
    print('A/B states: active (default INI) or not active (may be unknown).')
    for a,b in list(combinations(skin,2))+[(a,b) for a in skin for b in frozen]:
        va,vb=ids[a],ids[b]; pa,pb=p[va],p[vb]
        if np.any(pa.max(0)+near<pb.min(0)) or np.any(pb.max(0)+near<pa.min(0)): continue
        da,_=trees[b].query(pa); db,_=trees[a].query(pb)
        ma=da<=tol; mb=db<=tol; na=da<=near; nb=db<=near
        if b not in keys and (ma.any() or mb.any()): keys[b]=triangle_keys(p,faces[b],tol)
        dup=len(keys[a]&keys[b]) if b in keys else None
        if not (na.any() or nb.any() or dup): continue
        z=pa[na,2]; zz=pb[nb,2]; z=np.concatenate((z,zz))
        print('\n%s [%s,%s] <> %s [%s,%s]'%(a,roles[a],'active' if a in active else 'not active',b,roles[b],'active' if b in active else 'not active'))
        print('Shared buffer IDs: %d | coincident A/B: %d/%d (%.1f%% / %.1f%%)'%(len(np.intersect1d(va,vb)),ma.sum(),mb.sum(),100*ma.mean(),100*mb.mean()))
        print('Near A/B: %d/%d (%.1f%% / %.1f%%) | Z %.3f..%.3f cm'%(na.sum(),nb.sum(),100*na.mean(),100*nb.mean(),z.min(),z.max()))
        if dup is not None: print('Unique quantized identical triangles: %d / %d / %d'%(dup,len(keys[a]),len(keys[b])))
        if ma.any():
            print('Coincident A vertices by Z (cm):')
            zz=pa[ma,2]; lo=np.floor(zz.min()/2)*2; hi=np.floor(zz.max()/2)*2+2
            edges=np.arange(lo,hi+1,2); counts,_=np.histogram(zz,edges)
            print(' '.join('%.0f..%.0f:%d'%(x,y,c) for x,y,c in zip(edges[:-1],edges[1:],counts) if c))


def main():
    import thicc_edit as te
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini)
        result=te.run(str(root),'diagnose')
        roles={row[0]:row[1] for row in result['parts']}
        active=set(result.get('full_body',{}).get('active',[]))
        H=result.get('height')
        if not H or H<=0: raise ValueError('No valid anatomical height from Analyze.')
        pair_report(p,faces,roles,active,H)

if __name__=='__main__': main()
