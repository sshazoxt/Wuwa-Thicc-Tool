"""Experimental C2 profile interpolation, preserving sampled amplitudes."""
import numpy as np
from scipy.interpolate import CubicSpline, PchipInterpolator

def profile(x,y):
    x,y=np.asarray(x),np.asarray(y)
    f=CubicSpline(x,y,bc_type='clamped')
    return lambda z:f(np.clip(z,x[0],x[-1]))

def angular_profile(a,z):
    a=np.mod(a,2*np.pi); order=np.argsort(a); a,z=a[order],np.asarray(z)[order]
    keep=np.r_[True,np.diff(a)>1e-8]; a,z=a[keep],z[keep]
    if len(a)<3: return lambda t:np.interp(t,a,z,period=2*np.pi)
    f=CubicSpline(np.r_[a,a[0]+2*np.pi],np.r_[z,z[0]],bc_type='periodic')
    return lambda t:f((t-a[0])%(2*np.pi)+a[0])

def quintic(a,b,x):
    t=np.clip((x-a)/(b-a),0.,1.)
    return t**3*(10+t*(-15+6*t))
