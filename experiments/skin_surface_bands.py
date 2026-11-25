"""Sample point-to-triangle distances in original and current geometry, by height."""
from itertools import combinations
import numpy as np
from preview_no_seam_guard import sandbox, geometry, load_cfg


def mesh(p,t):
    import pyvista as pv
    ids=np.unique(t); local=np.searchsorted(ids,t)
    return pv.PolyData(p[ids],np.column_stack([np.full(len(t),3),local]).ravel())


def samples(p,t):
    q=p[t]
    # Interior samples and edge midpoints; retain original triangle area weights.
    bary=np.array([[1/3,1/3,1/3],[.6,.2,.2],[.2,.6,.2],[.2,.2,.6],[.5,.5,0],[.5,0,.5],[0,.5,.5]])
    xyz=np.einsum('sj,tjk->tsk',bary,q).reshape(-1,3)
    area=np.linalg.norm(np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]),axis=1)/2
    return xyz,np.repeat(area/len(bary),len(bary))


def distances(src,dest):
    _,closest=dest.find_closest_cell(src,return_closest_point=True)
    return np.linalg.norm(src-closest,axis=1)


def main():
    import thicc_edit as te
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini)
        q=np.fromfile(root/'Meshes'/'Position.buf',np.float32).reshape(-1,3).astype(float)
        if p.shape!=q.shape: raise ValueError('Position buffers differ in length')
        result=te.run(str(root),'diagnose'); H=float(result['height']); active=set(result['full_body']['active'])
        names=[r[0] for r in result['parts'] if r[1]=='skin' and r[0] in active and faces[r[0]].size]
        print('Active Skin:',names); print('Current buffer (not unsaved preview). Distances are unsigned sampled proximity, NOT proof of triangle intersections.')
        thresholds=np.array([.001,.003,.008])*H
        print('Tolerances cm:',thresholds)
        for a,b in combinations(names,2):
            ta,tb=faces[a],faces[b]; va=p[np.unique(ta)]; vb=p[np.unique(tb)]
            if np.any(va.max(0)+thresholds[-1]<vb.min(0)) or np.any(vb.max(0)+thresholds[-1]<va.min(0)): continue
            for src,dst in ((a,b),(b,a)):
                t=faces[src]; s,w=samples(p,t); ss,_=samples(q,t)
                before=distances(s,mesh(p,faces[dst])); after=distances(ss,mesh(q,faces[dst]))
                if not (np.any(before<=thresholds[-1]) or np.any(after<=thresholds[-1])): continue
                print('\n',src,'->',dst,'| original Z bands; area-weighted sample percentages')
                print('Z range | area cm2 | before % at three thresholds | current % at three thresholds')
                lo=np.floor(s[:,2].min()); hi=np.ceil(s[:,2].max())
                for z in np.arange(lo,hi,1.):
                    m=(s[:,2]>=z)&(s[:,2]<z+1); total=w[m].sum()
                    if total<=0 or not (np.any(before[m]<=thresholds[-1]) or np.any(after[m]<=thresholds[-1])): continue
                    vals=[100*w[m & (d<=tol)].sum()/total for d in (before,after) for tol in thresholds]
                    print('%6.1f..%6.1f | %9.3f | '%(z,z+1,total)+' '.join('%6.2f'%v for v in vals))
if __name__=='__main__': main()
