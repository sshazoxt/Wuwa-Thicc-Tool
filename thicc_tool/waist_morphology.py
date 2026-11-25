"""Independent waist scaling, with conservative landmark and face checks."""
import numpy as np

def smooth(t):
    t=np.clip(t,0.,1.)
    return t**3*(10+t*(-15+6*t))

def deform(P,Q,skin_tri,faces,eligible,mobility,L,width,depth,contour,manual=False):
    if not np.all(np.isfinite([width,depth])) or not (.6<=width<=1.5 and .6<=depth<=1.5):
        raise ValueError('Waist factors must be between 0.60 and 1.50')
    if width==depth==1: return Q
    from torso_profile import sections
    z=L['waist']; span=L['crotch']-L['knee']; hip=L['hip_z']
    lo=max(hip,z-.55*span); hi=z+.40*span
    if not (span>0 and L['crotch']<z<hi and lo<z):
        print('Waist skipped: invalid landmark order'); return Q
    zs=np.linspace(lo,hi,31); k=np.argmin(abs(zs-z)); zs[k]=z
    # Only intact central skin sections; no fallback to hair, clothing or frozen torso.
    profile=sections(P,skin_tri,zs,span)
    valid=np.array([p is not None and p[0][0] and p[1]==1 for p in profile])
    if not valid[max(0,k-2):k+3].all() or not (0<k<len(zs)-1):
        print('Waist skipped: missing continuous skin around center; check Skin role and Measurements'); return Q
    w=np.array([p[0][2] if ok else np.nan for p,ok in zip(profile,valid)])
    a=k; b=k
    while a>0 and valid[a-1]: a-=1
    while b<len(zs)-1 and valid[b+1]: b+=1
    if not manual and (a==k or b==k or w[k]>1.05*min(np.nanmax(w[a:k]),np.nanmax(w[k+1:b+1]))):
        print('Waist skipped: automatic landmark lacks narrowing evidence; verify Measurements'); return Q
    lo,hi=zs[a],zs[b]
    if min(z-lo,hi-z)<.10*span:
        print('Waist skipped: insufficient transition coverage'); return Q
    centers=[]
    for h in zs[a:b+1]:
        c=contour(Q[skin_tri],h); centers.append((c[:,1].min()+c[:,1].max())*.5)
    ids=np.flatnonzero(eligible & (mobility>0) & (P[:,2]>lo)&(P[:,2]<hi))
    h=P[ids,2]; e=smooth(np.where(h<z,(h-lo)/(z-lo),(hi-h)/(hi-z)))*mobility[ids]
    cy=np.interp(h,zs[a:b+1],centers)
    d=np.zeros_like(Q); d[ids,0]=Q[ids,0]*(width-1)*e; d[ids,1]=(Q[ids,1]-cy)*(depth-1)*e
    active=np.any(d!=0,axis=1); f=faces[active[faces].any(1)]
    def normals(A):
        t=A[f]; return np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
    n0=normals(P); n1=normals(Q); good=(n0*n1).sum(1)>0
    for factor in (1.,.5,.25,.125):
        R=Q+factor*d; n=normals(R)
        if np.all((n0[good]*n[good]).sum(1)>0) and np.all(np.linalg.norm(n[good],axis=1)>=.15*np.linalg.norm(n1[good],axis=1)):
            print('Waist center Z %.2f; support %.2f..%.2f; X %.2f Y %.2f; accepted strength %.3f; moved %d' %(z,lo,hi,width,depth,factor,active.sum())); return R
    print('Waist skipped: face safety check failed'); return Q
