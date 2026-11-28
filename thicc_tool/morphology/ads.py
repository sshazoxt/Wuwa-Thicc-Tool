"""Production ADS 78: native DS geometry, approved C2 Anny reference profiles."""
import json
from pathlib import Path
from functools import lru_cache
import numpy as np
from . import direct_hips, direct_thighs
from .ads_curves import Profiles

@lru_cache(maxsize=64)
def _envelope(key, lo, hi, knee, crotch, waist):
    # Exactly the experiment 78 fitting procedure. Cache immutable envelopes,
    # not model geometry; all inputs affecting the fit are included in the key.
    data = json.loads(Path(__file__).with_name('ads_profiles.json').read_text(encoding='utf-8'))
    return Profiles(data).envelope(key, lo, hi, dict(knee=knee,crotch=crotch,waist=waist))

def _curves(prefix, lo, hi, L):
    return {a:_envelope(prefix+'_'+a,float(lo),float(hi),float(L['knee']),float(L['crotch']),float(L['waist'])) for a in 'xy'}

class _Axes:
    def field(self,x,y,z,amount,direction=(1.,1.),depth_amount=None):
        self._axis='x'
        dx,_=super().field(x,y,z,amount,(direction[0],0.),0.)
        self._axis='y'
        _,dy=super().field(x,y,z,0.,(0.,direction[1]),amount if depth_amount is None else depth_amount)
        return dx,dy

@lru_cache(maxsize=1)
def _hip_type(base):
    class ADSHip(_Axes,base):
        def __init__(self,positions,triangles,L):
            super().__init__(positions,triangles,L); self._axis='x'
            self._curves=_curves('hips',self.lo,self.hi,L)
        def gain(self,z,amount):
            return self.unit*amount*np.nan_to_num(self._curves[self._axis](z),nan=0.)
    return ADSHip

@lru_cache(maxsize=1)
def _thigh_type(base):
    class ADSThigh(_Axes,base):
        def __init__(self,positions,triangles,L,hip_reference=None):
            if hip_reference is None:
                hip_reference=make_hip(positions,triangles,L)
            super().__init__(positions,triangles,L,hip_reference=hip_reference); self._axis='x'
            self._curves=_curves('thighs',self.lo,self.top,L)
        def gain(self,z,amount):
            return amount*np.nan_to_num(self._curves[self._axis](z),nan=0.)
    return ADSThigh

def make_hip(positions,triangles,L,*,ds045=False):
    base=direct_hips.DirectHipField
    # Honor existing isolated experiments that deliberately substitute a field.
    if ds045 or base.__module__ != direct_hips.__name__:
        return base(positions,triangles,L)
    return _hip_type(base)(positions,triangles,L)

def make_thigh(positions,triangles,L,hip_reference=None,*,ds045=False):
    base=direct_thighs.DirectThighField
    if ds045 or base.__module__ != direct_thighs.__name__:
        return base(positions,triangles,L,hip_reference=hip_reference)
    return _thigh_type(base)(positions,triangles,L,hip_reference=hip_reference)
