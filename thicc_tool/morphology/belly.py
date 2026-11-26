"""Production Belly parameters and legacy Experiment 32 displacement."""
import numpy as np
from .regional import smooth

LIMITS = {'depth': (0., 1.), 'width': (.5, 3.5), 'height': (.5, 1.5), 'offset': (-.15, .10)}


def basic_parameters(amount):
    u = float(amount)
    if not np.isfinite(u) or not 0 <= u <= 1:
        raise ValueError('Belly amount must be between 0 and 1')
    return dict(depth=.66*u, width=2.+.50*u, height=1.08+.42*u, offset=-.09+.19*u)


def parameters(config):
    cfg = config or {}
    amount = float(cfg.get('amount', 0.))
    basic = basic_parameters(amount)
    if not cfg.get('advanced', False):
        return basic
    values = {k:float(cfg.get(k, basic[k])) for k in LIMITS}
    for k,v in values.items():
        lo,hi=LIMITS[k]
        if not np.isfinite(v) or not lo <= v <= hi:
            raise ValueError('Belly '+k+' outside supported range')
    return values


def lateral_profile(x, width, depth):
    """C2 falloff, progressively broader at high expansion; no hard seam."""
    t=np.abs(np.asarray(x,float))/width
    blend=smooth(depth/.66)
    legacy=smooth(1-t)
    rounded=smooth(1-t*t)
    return (1-blend)*legacy+blend*rounded


def field(controls, depth, width, height, offset, *, rounded=False):
    if not rounded:
        return controls.belly(depth=depth, width=width, height=height, offset=offset)
    from .refinement import support
    r=controls.r; g=r.L['crotch']; w=controls.center; s=r.span
    if depth == 0: return np.zeros_like(r.p)
    c=g+.57*(w-g)
    a,c,b=support(c,g+.08*(w-g),w+.06*(w-g),height,offset,s,g+.02*s,w+.10*s)
    p,z,x,y,rx,ry,e=controls._frame(a,c,b)
    yn=(p[:,1]-y)/ry
    front=smooth(yn)
    if rounded:
        # Extend around the anterior flanks as volume increases, without
        # crossing the sagittal-depth midplane into the posterior surface.
        rounding=smooth(depth/.66)
        front=(1-rounding)*front+rounding*smooth(yn/.65)
    xn=(p[:,0]-x)/rx
    lateral=lateral_profile(xn,width,depth) if rounded else smooth(1-np.abs(xn)/width)
    out=np.zeros_like(p); out[:,1]=depth*ry*e*front*lateral
    print('Belly bounds %.3f..%.3f center %.3f | width %.3f | rounded=%s'%(a,b,c,width,rounded))
    return out


def apply_belly(original, base, faces, data, config):
    from .regional import Region
    from .refinement import RegionalControls, FieldComposer
    values=parameters(config)
    if values['depth']==0: return base, None
    r=Region(original,faces,data)
    center,reliable=r.locate_waist()
    ctrl=RegionalControls(r,center)
    base=np.asarray(base,dtype=np.float32).astype(float)
    composer=FieldComposer(r,base)
    q,f,reports=composer.compose({'Belly':field(ctrl,**values)})
    q=q.astype(np.float32).astype(float)
    if len(composer.inspect(q).indices):
        raise ValueError('Belly float32 geometry failed validation')
    if f['Belly']==0 or not np.any(np.abs(q-base)>1e-6):
        raise ValueError('Belly rejected or no movable abdominal surface; check Wardrobe and settings')
    moved=np.linalg.norm(q-base,axis=1)>1e-5
    print('[BELLY] parameters=%s | waist %.3f reliable=%s | accepted=%.3f | rejected full=%d | affected=%d | max XYZ=%s' % (values,center,reliable,f['Belly'],len(reports['Belly'].indices),moved.sum(),np.max(np.abs(q-base),axis=0)))
    if moved.any(): print('[BELLY] Z range %.3f..%.3f'%(original[moved,2].min(),original[moved,2].max()))
    return q,r.allfaces
