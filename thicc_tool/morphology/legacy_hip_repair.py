"""044: constrain the Legacy hip calibration to a broad C2 reference profile.

The calibrated radial/angular field, depth, reference frame and all other
regional fields are retained. No vertex or displacement smoothing is used.
"""
import numpy as np


def profile_bounds(ref, coupled=False, ctrl=None, hip_ref=None, relative=False):
    knee, crotch, waist = (float(ref[k]) for k in ('knee','crotch','waist'))
    span = crotch-knee
    if span <= 0 or waist <= crotch:
        raise ValueError('Invalid Legacy hip calibration landmarks')
    lo = knee+.06*span
    peak = crotch-.10*span
    hi = waist+1.1*(float(ref['apex'])-crotch)
    if relative:
        hi = waist
    if coupled:
        ctrl = ctrl or {}
        upper,lower,shift = (float(ctrl.get(k,v)) for k,v in [('upper',1.4),('lower',1.65),('peak',0.)])
        if not (.5<=upper<=2.5 and .5<=lower<=2.5 and -.3<=shift<=.3):
            raise ValueError('Invalid hip profile controls')
        lo,hi=knee,waist
        peak=float(hip_ref)+shift*(hi-hip_ref if shift>=0 else hip_ref-lo)
        if not lo<peak<hi: raise ValueError('Invalid coupled hip peak')
    else:
        upper=lower=1.
    return lo,peak,hi,lower,upper


def weight(z, bounds):
    lo,peak,hi,lower,upper=bounds
    z=np.asarray(z,float)
    t=np.clip(np.where(z<peak,(peak-z)/(peak-lo),(z-peak)/(hi-peak)),0.,1.)
    spread=np.where(z<peak,lower,upper)
    t=t/(spread+(1-spread)*t)
    # Algebraically stable quintic complement near the zero endpoints.
    u=1.-t
    return u**3*(10.+u*(-15.+6.*u))


def fit_amplitude(measure, desired):
    """Calibrate a scalar against the actual fixed-core outline.

    The permitted correction scales with the requested growth and measured
    local response, rather than an absolute cap inherited from Rover.
    """
    if not np.isfinite(desired) or desired<0: raise ValueError('Invalid hip growth target')
    if desired==0: return 0.
    response=float(measure(1.))
    if not np.isfinite(response) or response<=.05:
        raise ValueError('Legacy hip calibration: insufficient lateral response')
    estimate=desired/response
    cap=max(2.*estimate,1.)
    low,high=0.,cap
    amp=float(np.clip(estimate,low,high))
    for _ in range(8):
        actual=float(measure(amp))
        if not np.isfinite(actual): raise ValueError('Non-finite Legacy hip response')
        err=desired-actual
        if abs(err)<=max(.005,.002*desired): break
        if err>0: low=amp
        else: high=amp
        candidate=amp*desired/actual if actual>1e-8 else (low+high)/2
        amp=float(candidate if low<candidate<high else (low+high)/2)
    return amp


def fit(sc, PRs, tri_l, zs, original_outline, outline, target, ref, amounts,
        *, coupled=False, relative=False, ctrl=None, hip_ref=None, factory=None):
    """Fit the original Legacy multidirectional field, not a Direct Section field."""
    from .calibration import fixed_core_outline
    bounds=profile_bounds(ref,coupled,ctrl,hip_ref,relative)
    lo,peak,hi,_,_=bounds
    sample_z=np.linspace(peak-3.,peak+3.,7)
    local_outline=(factory or fixed_core_outline)(PRs,tri_l,sample_z)
    base_local=local_outline(PRs)
    sc.hip=None; sc.legacy_hip_spline=None
    baseline=PRs.copy(); baseline[:,0]+=sc.field_ref(*PRs.T)[0]
    natural_local=local_outline(baseline)-base_local
    valid=np.isfinite(base_local)&np.isfinite(natural_local)
    if valid.sum()<3: raise ValueError('Insufficient Legacy hip contour coverage')
    target_peak=float(np.interp(peak,zs,target)) if (coupled or relative) else 2.60*float(amounts['hips'])
    target_peak=max(0.,target_peak)
    # The existing leg/glute fields already supply part of the total outline.
    # Keep a positive hip response while avoiding adding the entire target twice.
    natural_peak=float(np.median(natural_local[valid]))
    desired=max(.35*target_peak,target_peak-max(0.,natural_peak))
    shape=weight(zs,bounds)
    def set_field(a):
        sc.hip=(zs,a*shape)
        sc.legacy_hip_spline=lambda z: a*weight(z,bounds)
    def measure(a):
        set_field(a)
        q=PRs.copy(); q[:,0]+=sc.field_ref(*PRs.T)[0]
        return float(np.median((local_outline(q)-base_local-natural_local)[valid]))
    amp=fit_amplitude(measure,desired);set_field(amp)
    natural=outline(baseline)-original_outline
    tgt=np.nan_to_num(natural,nan=0.)+desired*shape
    q=PRs.copy();q[:,0]+=sc.field_ref(*PRs.T)[0]
    err=np.where(np.isfinite(original_outline),tgt-(outline(q)-original_outline),np.nan)
    print('[Legacy 044] profile bounds %.3f / %.3f / %.3f; target peak %.3f; natural %.3f; calibrated amplitude %.3f' %(lo,peak,hi,target_peak,natural_peak,amp))
    return amp*shape,shape,tgt,err
