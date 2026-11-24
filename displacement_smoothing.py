"""Experimental Taubin filter on displacement, not on original positions."""
import numpy as np
from scipy.sparse import coo_matrix

def smooth_displacement(p, new, faces, allow, guard, iterations=4):
    d = new-p
    active = (allow >= .999999) & (guard >= .999999) & (np.linalg.norm(d,axis=1)>1e-9)
    # Pin duplicate positions (UV splits and alternate meshes), including near duplicates.
    _, inverse, counts = np.unique(np.round(p,5),axis=0,return_inverse=True,return_counts=True)
    active &= counts[inverse.reshape(-1)] == 1
    f=np.asarray(faces,dtype=np.int64).reshape(-1,3)
    e=np.concatenate((f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]))
    e=np.unique(np.sort(e,axis=1),axis=0); e=e[e[:,0]!=e[:,1]]
    i,j=e.T
    # Fixed neighbours anchor transitions; no spatial proximity edges.
    a=coo_matrix((np.ones(2*len(i)),(np.r_[i,j],np.r_[j,i])),shape=(len(p),len(p))).tocsr()
    degree=np.asarray(a.sum(axis=1)).ravel(); active &= degree>0
    out=d.copy()
    for _ in range(iterations):
        for factor in (.45,-.48):
            lap=a@out/np.maximum(degree,1)[:,None]-out
            out[active]+=factor*lap[active]
    candidate=p+out; candidate[~active]=new[~active]
    # Reject a pass that introduces a new flipped face relative to the base.
    def normals(q):
        t=q[f]; return np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
    n=normals(p); before=np.einsum('ij,ij->i',n,normals(new))<0; after=np.einsum('ij,ij->i',n,normals(candidate))<0
    added=int(np.count_nonzero(after & ~before))
    peak=float(np.linalg.norm(candidate-new,axis=1).max())
    print(f'Taubin: eligible={active.sum()} / {len(p)}; peak correction={peak:.5f}; new flipped faces={added}')
    if added or not np.isfinite(candidate).all():
        print('Taubin rejected; retaining unsmoothed geometry.'); return new
    return candidate
