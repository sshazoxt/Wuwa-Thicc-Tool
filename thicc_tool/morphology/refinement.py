"""Experimental regional controls; never called by production Apply."""
from dataclasses import dataclass
import numpy as np
from .regional import bump, smooth


def support(center, lo, hi, height, offset, span, floor, ceiling):
    if height <= 0 or floor >= ceiling: raise ValueError('Invalid support')
    c=center+offset*span
    if not floor<c<ceiling: raise ValueError('Center outside anatomical limits')
    a=max(floor,c-(center-lo)*height); b=min(ceiling,c+(hi-center)*height)
    if not a<c<b: raise ValueError('Invalid support bounds')
    return a,c,b

class RegionalControls:
    def __init__(self,region,center): self.r=region; self.center=center
    def _frame(self,a,c,b):
        r=self.r; p=r.p; z=p[:,2]; bounds=r.centers(np.linspace(a,b,31),z)
        x=(bounds[:,0]+bounds[:,1])*.5; y=(bounds[:,2]+bounds[:,3])*.5
        rx=np.maximum((bounds[:,1]-bounds[:,0])*.5,1e-6); ry=np.maximum((bounds[:,3]-bounds[:,2])*.5,1e-6)
        return p,z,x,y,rx,ry,bump(z,a,c,b)
    def waist(self,width=1.,depth=1.,height=1.,offset=0.):
        r=self.r; c=self.center; s=r.span; g=r.L['crotch']
        a,c,b=support(c,max(g+.08*(c-g),c-.42*s),c+.19*s,height,offset,s,g+.04*s,c+.24*s)
        p,z,x,y,rx,ry,e=self._frame(a,c,b); out=np.zeros_like(p)
        out[:,0]=(p[:,0]-x)*(width-1)*e; out[:,1]=(p[:,1]-y)*(depth-1)*e
        print('Waist bounds',a,c,b,'width/depth',width,depth); return out
    def belly(self,depth=.35,width=1.,height=1.,offset=0.):
        if width<=0: raise ValueError('Belly width must be positive')
        r=self.r; g=r.L['crotch']; w=self.center; s=r.span; c=g+.57*(w-g)
        a,c,b=support(c,g+.08*(w-g),w+.06*(w-g),height,offset,s,g+.02*s,w+.10*s)
        p,z,x,y,rx,ry,e=self._frame(a,c,b); out=np.zeros_like(p)
        front=smooth((p[:,1]-y)/ry); lateral=smooth(1-np.abs(p[:,0]-x)/(width*rx))
        out[:,1]=depth*ry*e*front*lateral
        print('Belly bounds',a,c,b,'width support',width); return out
    def glute_volume(self,width=.30,depth=.40,height=1.,offset=0.):
        r=self.r; s=r.span; g=r.L['crotch']; lo=g-.32*s; hi=r.L['waist']-.12*s
        c=float(np.clip(r.L['apex'],lo+.25*(hi-lo),hi-.25*(hi-lo)))
        a,c,b=support(c,lo,hi,height,offset,s,g-.65*s,r.L['waist']-.04*s)
        p,z,x,y,rx,ry,e=self._frame(a,c,b); e*=smooth((y-p[:,1])/(.65*ry))
        out=np.zeros_like(p); out[:,0]=(p[:,0]-x)*width*e; out[:,1]=(p[:,1]-y)*depth*e
        print('Glute volume bounds',a,c,b); return out

@dataclass
class FaceReport:
    indices: np.ndarray
    reversed: np.ndarray
    compressed: np.ndarray

class FieldComposer:
    """Sequential acceptance with cumulative validation against the fixed baseline.
    Order is explicit; accepted earlier fields are never reduced retroactively.
    """
    def __init__(self, region, base):
        self.r=region; self.base=np.asarray(base,float); self.f=region.allfaces
        self.n0=self.normals(region.p); self.nb=self.normals(self.base)
        self.an=np.linalg.norm(self.nb,axis=1)
        self.good=(np.linalg.norm(self.n0,axis=1)>1e-9)&(self.an>1e-9)&(np.sum(self.n0*self.nb,axis=1)>0)
    def normals(self,q):
        t=q[self.f]; return np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
    def inspect(self,q):
        n=self.normals(q); rev=self.good&(np.sum(self.n0*n,axis=1)<=0); small=self.good&(np.linalg.norm(n,axis=1)<.15*self.an)
        return FaceReport(np.flatnonzero(rev|small),np.flatnonzero(rev),np.flatnonzero(small))
    def compose(self,fields):
        q=self.base.copy(); factors={}; rejected={}
        for name,delta in fields.items():
            d=self.r.prepare_delta(delta); full=self.inspect(q+d); rejected[name]=full
            for factor in (1.,.75,.5,.375,.25,.125,0.):
                candidate=q+factor*d; report=self.inspect(candidate)
                if not len(report.indices): break
            q=candidate; factors[name]=factor
            print('Field',name,'accepted',factor,'full trial rejected',len(full.indices),'accepted max XYZ',np.max(np.abs(factor*d),axis=0))
        final=self.inspect(q)
        if len(final.indices): raise RuntimeError('Combined validation failed')
        return q,factors,rejected
    def describe(self,report):
        ids=report.indices; f=self.f[ids]; print('Rejected:',len(ids),'orientation:',len(report.reversed),'area:',len(report.compressed))
        if len(f):
            xyz=self.r.p[f].mean(1); print('Original centroid bounds',xyz.min(0),xyz.max(0))
        start=0
        for name,tri in self.r.faces.items():
            end=start+len(tri); count=np.count_nonzero((ids>=start)&(ids<end))
            if count: print(name,'rejected faces',count)
            start=end
        return f
