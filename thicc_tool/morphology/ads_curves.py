"""C2 monotone piecewise Bernstein profiles. No mesh smoothing."""
import numpy as np
from scipy.interpolate import PchipInterpolator, BPoly
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import minimize
from scipy.special import comb


def basis(t,n):
    t=np.asarray(t,float).reshape(-1,1); k=np.arange(n+1)
    return comb(n,k)*t**k*(1-t)**(n-k)


def fit_half(t,target,span_fraction,n=10):
    # Monotone coefficients, three equal at each endpoint => C2 flat joins.
    m=n-4
    C=np.zeros((n+1,m))
    for j in range(m): C[3+j:,j]=1
    A=basis(t,n)@C
    grid=np.linspace(0,1,201)
    D=n*(n-1)*basis(grid,n-2)@np.diff(C,n=2,axis=0)
    # Penalize bending in the common normalized anatomical coordinate.
    scale=.00065/max(span_fraction,1e-6)**4
    Q=A.T@A/len(t)+scale*(D.T@D/len(grid))
    b=A.T@target/len(t)
    r=minimize(lambda x:float(x@Q@x-2*b@x),np.full(m,1/m),jac=lambda x:2*(Q@x-b),bounds=[(0,1)]*m,constraints=[{'type':'eq','fun':lambda x:x.sum()-1,'jac':lambda x:np.ones(m)}],method='SLSQP',options={'ftol':1e-12,'maxiter':300})
    if not r.success: raise RuntimeError('Adaptive profile optimization: '+r.message)
    x=np.maximum(r.x,0); x/=x.sum(); return C@x


class Envelope:
    def __init__(self,lo,peak,hi,left,right):
        self.lo,self.peak,self.hi,self.left,self.right=lo,peak,hi,left,right
        self.poly=BPoly(np.column_stack((left,right[::-1])),[lo,peak,hi],extrapolate=False)
    def __call__(self,z):
        return np.nan_to_num(self.poly(z),nan=0.)



class Profiles:
    def __init__(self,data):
        self.u=np.asarray(data['u'],float); self.curves={}; self.diagnostics={}
        if self.u.ndim!=1 or not np.isfinite(self.u).all() or not np.all(np.diff(self.u)>0): raise ValueError('Invalid grid')
        for key in ('hips_x','hips_y','thighs_x','thighs_y'):
            a=np.asarray(data['profiles'][key],float); good=np.isfinite(a)
            if a.shape!=self.u.shape or good.sum()<.85*len(a): raise ValueError('Invalid profile '+key)
            self.curves[key]=PchipInterpolator(self.u,gaussian_filter1d(np.interp(self.u,self.u[good],a[good]),2),extrapolate=False)
    def envelope(self,key,lo,hi,L):
        z=np.linspace(lo,hi,401); u=np.interp(z,[L['knee'],L['crotch'],L['waist']],[0,1,2]); raw=np.maximum(self.curves[key](u),0)
        if raw.max()<=1e-9: raise ValueError('Empty profile '+key)
        raw/=raw.max(); idx=int(raw.argmax()); idx=np.clip(idx,1,len(z)-2); peak=z[idx]
        left=fit_half((z[:idx+1]-lo)/(peak-lo),raw[:idx+1],(peak-lo)/(hi-lo))
        right=fit_half((hi-z[idx:])/(hi-peak),raw[idx:],(hi-peak)/(hi-lo))
        curve=Envelope(lo,peak,hi,left,right)
        t=(z-lo)/(hi-lo); smooth=lambda t: (lambda q:q**3*(10+q*(-15+6*q)))(np.clip(t,0,1))
        old=raw*smooth(t/.12)*smooth((1-t)/.12); old/=old.max()
        new=curve(z)
        def metrics(v):
            d=np.gradient(v,z); dd=np.gradient(d,z)
            return dict(peak_z=float(z[v.argmax()]),max_slope=float(np.max(np.abs(d))),max_curvature=float(np.max(np.abs(dd))),upper_slope=float(np.max(np.abs(d[idx:]))),area=float(np.trapz(v,z)))
        self.diagnostics[key]=dict(z=z.tolist(),raw=raw.tolist(),ads75=old.tolist(),ads78=new.tolist(),old_metrics=metrics(old),new_metrics=metrics(new))
        print('ADS78',key,self.diagnostics[key]['old_metrics'],'=>',self.diagnostics[key]['new_metrics'],flush=True)
        return curve
