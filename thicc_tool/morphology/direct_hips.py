"""Direct anatomical hip field in original model coordinates."""
import numpy as np
from scipy.interpolate import PchipInterpolator
from .geometry import contour
ENGINES = ('Legacy', 'Direct Section')

def smooth(t):
    t=np.clip(t,0.,1.)
    return t**3*(10+t*(-15+6*t))

class DirectHipField:
    def __init__(self, positions, triangles, L):
        self.lo=float(L['knee']+.12*(L['hip_z']-L['knee']))
        self.peak=float(L['crotch'])
        self.hi=float(L['waist'])
        self.scale=float(L['hip_half']); self.cy=float(L['cy'])
        if not np.isfinite([self.lo,self.peak,self.hi,self.scale,self.cy]).all() or not self.lo<self.peak<self.hi or self.scale<=0:
            raise ValueError('Direct Section requires valid knee, crotch, waist and hip width landmarks')
        z=np.linspace(L['knee'],self.hi,401)
        tri=np.asarray(positions)[triangles]
        zlo=tri[:,:,2].min(1); zhi=tri[:,:,2].max(1)
        bounds=[]; depths=[]
        for h in z:
            c=contour(tri[(zlo<h)&(zhi>=h)],h)
            bounds.append([c[:,0].max(),-c[:,0].min()] if len(c) else [np.nan,np.nan])
            depths.append([c[:,1].min(),c[:,1].max()] if len(c) else [np.nan,np.nan])
        b=np.asarray(bounds); good=np.isfinite(b).all(1)&(b>0).all(1)
        if good.sum()<10 or z[good][0]>self.lo or z[good][-1]<self.hi:
            raise ValueError('Direct Section: insufficient active Skin contour coverage between knee and waist')
        if np.max(np.diff(z[good])) > .05*(self.hi-self.lo):
            raise ValueError('Direct Section: substantial missing Skin sections')
        self.curves=[PchipInterpolator(z[good],b[good,j],extrapolate=False) for j in range(2)]
        d=np.asarray(depths); dg=good & np.isfinite(d).all(1) & (d[:,1]>d[:,0])
        self.depth_curve=PchipInterpolator(z[dg],d[dg],axis=0,extrapolate=False)
        self.depth_min=float(z[dg][0]); self.depth_max=float(z[dg][-1])
        self.depth_unit=.14265*float(np.median((d[dg,1]-d[dg,0])/2))
        self.zmin=float(z[good][0]); self.zmax=float(z[good][-1]); self.unit=.14265*self.scale

    def gain(self,z,amount):
        return self.unit*amount*smooth((z-self.lo)/(self.peak-self.lo))*(1-smooth((z-self.peak)/(self.hi-self.peak)))

    def field(self,x,y,z,amount,direction=(1.,1.),depth_amount=None):
        amount=float(amount)
        if not np.isfinite(amount) or not 0<=amount<=5:
            raise ValueError('Direct Section Hips must be in 0..5')
        x,y,z=np.broadcast_arrays(np.asarray(x,float),np.asarray(y,float),np.asarray(z,float))
        if depth_amount is not None and (not np.isfinite(depth_amount) or not 0<=depth_amount<=5): raise ValueError("Hips depth must be in 0..5")
        if not amount and not depth_amount:return np.zeros_like(x),np.zeros_like(x)
        h=np.clip(z,self.zmin,self.zmax)
        width=np.where(x>=0,self.curves[0](h),self.curves[1](h))
        r=np.hypot(x,y-self.cy); mask=1-smooth((r-1.35*self.scale)/(.6*self.scale))
        denom=np.sqrt(r*r+(.11*self.scale)**2); ux=x/denom; uy=(y-self.cy)/denom
        posterior=smooth((-uy+.75)/1.5)
        depth=(.20+.15*posterior)*uy*(.65+.35*ux*ux)*mask*smooth((r-.22*self.scale)/(.27*self.scale))
        gain=self.gain(z,amount)
        if depth_amount is not None:
            front,back=self.depth_curve(np.clip(z,self.depth_min,self.depth_max)).T
            v=(y-(front+back)/2)/np.maximum((back-front)/2,1e-6)
            depth=self.gain(z,depth_amount)*(self.depth_unit/self.unit)*v*mask
        else: depth=gain*depth
        return gain*x/np.maximum(width,1e-6)*mask*direction[0], depth*direction[1]
