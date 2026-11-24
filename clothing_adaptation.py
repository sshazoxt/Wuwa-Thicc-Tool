"""Opt-in close-fitting garment displacement transfer; no collision solver."""
import numpy as np
from scipy.spatial import cKDTree


def adapt(original, deformed, skin, garments, faces, mobility, height):
    skin = np.unique(skin)
    ids = np.setdiff1d(np.unique(garments), skin)
    ids = ids[mobility[ids] > 0]
    if not len(ids) or len(skin) < 4 or height <= 0:
        print('Clothing adaptation: no eligible geometry'); return deformed
    dist, near = cKDTree(original[skin]).query(original[ids], k=4)
    radius = .012 * height
    # Only nearby, well-supported samples; avoid transferring across midline.
    anchors = skin[near]
    same = (original[anchors,0]*original[ids,0,None] >= 0)
    weights = same / np.maximum(dist, radius*.02)**2
    total = weights.sum(axis=1)
    t = np.clip(1-dist[:,0]/radius,0,1)
    blend = t**3*(10-15*t+6*t*t)*mobility[ids]
    blend[(total<=0)|(dist[:,-1]>2*radius)] = 0
    displacement = deformed-original
    target = np.sum(weights[:,:,None]*displacement[anchors],axis=1)/np.maximum(total[:,None],1e-20)
    correction = (target-displacement[ids])*blend[:,None]
    cap = .005 * height
    correction *= np.minimum(1,cap/np.maximum(np.linalg.norm(correction,axis=1),1e-20))[:,None]
    out = deformed.copy(); out[ids] += correction
    # Reject newly reversed faces, including faces shared by other draws.
    faces = np.asarray(faces).reshape(-1,3)
    def normals(p):
        a,b,c = p[faces].transpose(1,0,2); return np.cross(b-a,c-a)
    n0 = normals(original); before = np.sum(n0*normals(deformed),axis=1); after = np.sum(n0*normals(out),axis=1)
    bad = np.count_nonzero((before>=0)&(after<0))
    print('Clothing candidates: %d; adjusted: %d; max correction: %.4f; new reversed faces: %d' % (len(ids),np.count_nonzero(np.linalg.norm(correction,axis=1)>1e-6),np.linalg.norm(correction,axis=1).max(),bad))
    if bad:
        print('Clothing adaptation rejected'); return deformed
    return out
