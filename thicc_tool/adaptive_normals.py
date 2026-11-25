"""Transport authored vertex frames using actual incident triangle deformation."""
import numpy as np


def unit(a):
    return a / np.maximum(np.linalg.norm(a, axis=-1, keepdims=True), 1e-12)


def surface_frames(p, q, faces, tangent, normal, moved, mode):
    # Process each indexed triangle once; do not weld unrelated UV seams or variants.
    f = np.asarray(faces, dtype=np.int64)
    f = f[(f >= 0).all(1) & (f < len(p)).all(1)]
    f = f[moved[f].any(1)]
    _, ids = np.unique(np.sort(f, axis=1), axis=0, return_index=True)
    f = f[ids]
    tn = np.zeros_like(p); nn = np.zeros_like(p); gn = np.zeros_like(p)
    weight = np.zeros(len(p)); rejected = 0
    for start in range(0, len(f), 16384):
        ix = f[start:start+16384]
        a, b = p[ix], q[ix]
        e, h = a[:,1]-a[:,0], a[:,2]-a[:,0]
        E, H = b[:,1]-b[:,0], b[:,2]-b[:,0]
        cross, cross1 = np.cross(e,h), np.cross(E,H)
        area, area1 = np.linalg.norm(cross,axis=1), np.linalg.norm(cross1,axis=1)
        ok = (area > 1e-10) & (area1 > 1e-10)
        ok &= (area > 1e-7*np.linalg.norm(e,axis=1)*np.linalg.norm(h,axis=1))
        ok &= (area1 > 1e-7*np.linalg.norm(E,axis=1)*np.linalg.norm(H,axis=1))
        rejected += int((~ok).sum())
        ix,e,h,E,H,cross,cross1,area = [v[ok] for v in (ix,e,h,E,H,cross,cross1,area)]
        if not len(ix): continue
        # Extend the surface map along its unit normal, without invented thickness scaling.
        A = np.stack((e,h,unit(cross)),axis=2)
        B = np.stack((E,H,unit(cross1)),axis=2)
        F = B @ np.linalg.inv(A)
        Fit = np.linalg.inv(F).transpose(0,2,1)
        for k in range(3):
            v = ix[:,k]
            t = unit(np.einsum('nij,nj->ni',F,tangent[v]))
            n = unit(np.einsum('nij,nj->ni',Fit,normal[v]))
            np.add.at(tn,v,t*area[:,None]); np.add.at(nn,v,n*area[:,None]); np.add.at(gn,v,cross1)
            np.add.at(weight,v,area)
    valid = moved & (weight>0) & (np.linalg.norm(nn,axis=1)>1e-12)
    result_n = normal.copy(); result_t = tangent.copy()
    target = unit(gn) if mode == 'Geometric' else unit(nn)
    valid &= np.linalg.norm(target,axis=1)>0.5
    if mode == 'Geometric':
        # Respect original normal orientation even for reversed index winding.
        target[(target*unit(nn)).sum(1)<0] *= -1
    result_n[valid] = target[valid]
    t = tn - (tn*result_n).sum(1)[:,None]*result_n
    tok = valid & (np.linalg.norm(t,axis=1)>1e-12)
    result_t[tok] = unit(t[tok])
    print('Surface frame coverage: %d / %d moved vertices; rejected degenerate faces: %d' % (valid.sum(),moved.sum(),rejected))
    return result_t, result_n, valid
