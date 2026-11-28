"""Private Direct Section copies with experimental Anny longitudinal gain curves."""
from contextlib import contextmanager
import importlib.util
import sys
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter1d
import morphology.direct_hips as hips
import morphology.direct_thighs as thighs


def clone(module, name):
    spec=importlib.util.spec_from_file_location(name,module.__file__)
    obj=importlib.util.module_from_spec(spec); sys.modules[name]=obj
    spec.loader.exec_module(obj); return obj


hip_copy=clone(hips,'morphology._experiment75_hips')
thigh_copy=clone(thighs,'morphology._experiment75_thighs')


class Profiles:
    def __init__(self,data):
        self.u=np.asarray(data['u'],float); self.curves={}
        if self.u.ndim!=1 or not np.isfinite(self.u).all() or not np.all(np.diff(self.u)>0): raise ValueError('Invalid reference grid')
        for key,values in data['profiles'].items():
            a=np.asarray(values,float); good=np.isfinite(a)
            if a.shape!=self.u.shape or good.sum()<len(a)*.85: raise ValueError('Insufficient reference coverage: '+key)
            a=np.interp(self.u,self.u[good],a[good]); self.curves[key]=PchipInterpolator(self.u,gaussian_filter1d(a,2),extrapolate=False)

    def envelope(self,key,lo,hi,L):
        z=np.linspace(lo,hi,401); u=np.interp(z,[L['knee'],L['crotch'],L['waist']],[0,1,2])
        v=np.maximum(self.curves[key](u),0.)
        # Smooth C1/C2 endpoint fade; preserve the existing support of the engine.
        t=(z-lo)/(hi-lo); v*=hip_copy.smooth(t/.12)*hip_copy.smooth((1-t)/.12)
        peak=float(v.max());
        if not np.isfinite(peak) or peak<=1e-9: raise ValueError('Reference has no positive expansion: '+key)
        return PchipInterpolator(z,v/peak,extrapolate=False)


@contextmanager
def experimental_fields(profiles):
    """Only substitute constructors during a private dry run in this worker."""
    original_h,original_t=hips.DirectHipField,thighs.DirectThighField
    class Hip(hip_copy.DirectHipField):
        def __init__(self,positions,triangles,L):
            super().__init__(positions,triangles,L); self._axis='x'
            self._curves={a:profiles.envelope('hips_'+a,self.lo,self.hi,L) for a in 'xy'}
        def gain(self,z,amount):
            return self.unit*amount*np.nan_to_num(self._curves[self._axis](z),nan=0.)
        def field(self,x,y,z,amount,direction=(1.,1.),depth_amount=None):
            self._axis='x'; dx,_=super().field(x,y,z,amount,(direction[0],0.),0.)
            self._axis='y'; _,dy=super().field(x,y,z,0.,(0.,direction[1]),amount if depth_amount is None else depth_amount)
            return dx,dy
    class Thigh(thigh_copy.DirectThighField):
        def __init__(self,positions,triangles,L,hip_reference=None):
            super().__init__(positions,triangles,L,hip_reference=hip_reference)
            self._axis='x'; self._curves={a:profiles.envelope('thighs_'+a,self.lo,self.top,L) for a in 'xy'}
        def gain(self,z,amount): return amount*np.nan_to_num(self._curves[self._axis](z),nan=0.)
        def field(self,x,y,z,amount,direction=(1.,1.),depth_amount=None):
            self._axis='x'; dx,_=super().field(x,y,z,amount,(direction[0],0.),0.)
            self._axis='y'; _,dy=super().field(x,y,z,0.,(0.,direction[1]),amount if depth_amount is None else depth_amount)
            return dx,dy
    hips.DirectHipField=Hip; thighs.DirectThighField=Thigh
    # The cloned thigh module imports the hip constructor at import time.
    thigh_copy.DirectHipField=Hip
    try: yield
    finally:
        hips.DirectHipField=original_h; thighs.DirectThighField=original_t; thigh_copy.DirectHipField=original_h
