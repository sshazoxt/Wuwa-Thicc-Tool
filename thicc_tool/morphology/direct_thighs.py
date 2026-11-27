"""Anatomical thigh expansion in native model coordinates, shared by all draws."""
import numpy as np
from scipy.interpolate import PchipInterpolator
from .geometry import contour
from .direct_hips import smooth, DirectHipField

class DirectThighField:
    def __init__(self, positions, triangles, L, hip_reference=None):
        self.lo=float(L['knee']); self.hi=float(L['crotch'])
        if not np.isfinite([self.lo,self.hi]).all() or self.hi<=self.lo:
            raise ValueError('Direct Thighs requires increasing knee and crotch landmarks')
        span=self.hi-self.lo
        self.peak=self.lo+.72*span
        self.top=self.hi+.26*(float(L['waist'])-self.hi)
        self.hip_reference=hip_reference if hip_reference is not None else DirectHipField(positions, triangles, L)
        if not self.peak<self.hi<self.top<self.hip_reference.hi:
            raise ValueError('Direct Thighs requires valid pelvis and waist landmarks')
        tri=np.asarray(positions)[triangles]; zlo=tri[:,:,2].min(1); zhi=tri[:,:,2].max(1)
        zs=np.linspace(self.lo,self.hi-.015*span,161)
        self.sections={}; self.units={}
        for sign in (1,-1):
            rows=[]
            for z in zs:
                q=contour(tri[(zlo<z)&(zhi>=z)],z); q=q[q[:,0]*sign>0]
                if len(q)<8: rows.append([np.nan]*4); continue
                x=q[:,0]*sign; y=q[:,1]; rows.append([x.min(),x.max(),y.min(),y.max()])
            b=np.asarray(rows); good=np.isfinite(b).all(1)&(b[:,1]>b[:,0])&(b[:,3]>b[:,2]); h=zs[good]; b=b[good]
            if len(h)<20 or h[0]>self.lo+.05*span or h[-1]<self.hi-.06*span or np.max(np.diff(h))>.06*span:
                raise ValueError('Direct Thighs: insufficient active Skin section coverage')
            self.sections[sign]=(h[0],h[-1],PchipInterpolator(h,b,axis=0,extrapolate=False))
            mid=(h>self.lo+.25*span)&(h<self.lo+.8*span)
            self.units[sign]=.32*float(np.median((b[mid,1]-b[mid,0])/2))
        # Shared pelvis depth reference, measured from original active Skin.
        heights=np.linspace(self.lo,self.hip_reference.hi,401)
        rows=[]
        for h in heights:
            q=contour(tri[(zlo<h)&(zhi>=h)],h)
            rows.append([q[:,1].min(),q[:,1].max()] if len(q) else [np.nan,np.nan])
        bounds=np.asarray(rows); good=np.isfinite(bounds).all(1)&(bounds[:,1]>bounds[:,0])
        if good.sum()<20 or not good[0] or not good[-1] or np.max(np.diff(heights[good]))>.05*(heights[-1]-heights[0]):
            raise ValueError('Direct Thighs: insufficient shared pelvis depth coverage')
        self.depth_curve=PchipInterpolator(heights[good],bounds[good],axis=0,extrapolate=False)
    def gain(self,z,amount):
        t=np.clip((z-self.lo)/(self.peak-self.lo),0.,1.)
        return amount*smooth(t**.72)*(1-smooth((z-self.peak)/(self.top-self.peak)))
    def field(self,x,y,z,amount,direction=(1.,1.),depth_amount=None):
        amount=float(amount)
        if not np.isfinite(amount) or not 0<=amount<=2: raise ValueError('Direct Thighs must be in 0..2')
        x,y,z=np.broadcast_arrays(np.asarray(x,float),np.asarray(y,float),np.asarray(z,float))
        dx=np.zeros_like(x); dy=np.zeros_like(x)
        if depth_amount is not None and (not np.isfinite(depth_amount) or not 0<=depth_amount<=2): raise ValueError("Thighs depth must be in 0..2")
        if not amount and not depth_amount:return dx,dy
        valid=(z>self.lo)&(z<self.top)
        xv,yv,zv=x[valid],y[valid],z[valid]
        gain=self.gain(zv,amount)
        depth_gain=self.gain(zv,amount if depth_amount is None else depth_amount)
        span=self.hi-self.lo
        blend=smooth((zv-(self.hi-.40*span))/(.50*span))
        hip=self.hip_reference
        front,back=self.depth_curve(np.clip(zv,self.lo,hip.hi)).T
        globv=(yv-(front+back)/2)/((back-front)/2)
        rad=np.hypot(xv,yv-hip.cy)
        mask=1-smooth((rad-1.35*hip.scale)/(.6*hip.scale))
        for sign,(lo,hi,curve) in self.sections.items():
            inner,outer,lf,lb=curve(np.clip(zv,lo,hi)).T
            width=hip.curves[0 if sign==1 else 1](np.clip(zv,hip.zmin,hip.zmax))
            anchor=(1-blend)*inner
            u=(sign*xv-anchor)/np.maximum(width-anchor,1e-6)
            owner=smooth(sign*xv/np.maximum(.18*width,1e-9))
            g=gain*self.units[sign]
            raw=g*u*mask*owner*direction[0]
            clearance=np.maximum(.30*sign*xv,1e-12)
            raw=np.where(raw<0,clearance*np.tanh(raw/clearance),raw)
            dx[valid]+=sign*raw
            vv=(1-blend)*(yv-(lf+lb)/2)/((lb-lf)/2)+blend*globv
            depth_scale=self.units[sign]*.65 if depth_amount is None else .32*((1-blend)*(lb-lf)/2+blend*(back-front)/2)
            dy[valid]+=depth_gain*depth_scale*vv*mask*owner*direction[1]
        return dx,dy
