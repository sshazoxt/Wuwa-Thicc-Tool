"""038: read-only interventions on vertical mapping, envelope, root and target.
All monkey patches are process-local and restored on exit. No mesh export.
"""
import contextlib
import inspect
import numpy as np
from _hip_root_lab import run, view, compare, report_profile, visible
from preview_no_seam_guard import sandbox, geometry, load_cfg

TITLES={69:'HIP VERTICAL MAPPING',70:'HIP ENVELOPE ISOLATION',71:'INGUINAL MASK ISOLATION',72:'HIP CALIBRATION GRADIENT',73:'ABSOLUTE HIP CONTOUR'}


def smooth01(t):
    t=np.clip(t,0.,1.)
    return t*t*t*(10+t*(-15+6*t))


def linear_extrap(x,xk,yk):
    x=np.asarray(x,float)
    y=np.interp(x,xk,yk)
    y=np.where(x<xk[0],yk[0]+(x-xk[0])*(yk[1]-yk[0])/(xk[1]-xk[0]),y)
    return np.where(x>xk[-1],yk[-1]+(x-xk[-1])*(yk[-1]-yk[-2])/(xk[-1]-xk[-2]),y)


def mapping_knots(L,REF,omit_crotch=False):
    keys=['ankle','knee','crotch','apex','waist']
    if not L['crotch']<L['apex']<L['waist']: keys.remove('apex')
    if omit_crotch: keys=[k for k in keys if k not in ('crotch','apex')]
    a=np.array([0.]+[L[k] for k in keys]+[L['waist']+40.]); b=np.array([0.]+[REF[k] for k in keys]+[REF['waist']+40.])
    if np.any(np.diff(a)<=0) or np.any(np.diff(b)<=0): raise ValueError('Invalid vertical knots')
    return a,b


def absolute_targets(z,b,lo,peak,hi,amplitude):
    """Construct a desired half-width before deformation, with no mesh smoothing.
    Target knots use the original endpoint widths and a shared peak width.
    Invalid sections stay zero; no extrapolation across missing endpoint coverage.
    """
    z=np.asarray(z,float); b=np.asarray(b,float)
    valid=np.isfinite(b)
    if not lo<peak<hi or valid.sum()<3 or lo<z[valid][0]-1e-8 or hi>z[valid][-1]+1e-8:
        raise ValueError('Absolute target anchors outside valid calibration coverage')
    w0,wp,w1=np.interp([lo,peak,hi],z[valid],b[valid]); top=wp+amplitude
    inside=(z>=lo)&(z<=hi)&valid
    t=np.where(z<=peak,smooth01((z-lo)/(peak-lo)),smooth01((z-peak)/(hi-peak)))
    desired=np.where(z<=peak,w0+(top-w0)*t,top+(w1-top)*t)
    # Explicitly keep original outside the interval. Anchor widths are not estimated from a second mesh.
    signed=np.where(inside,desired-b,0.)
    additive=amplitude*smooth01((z-lo)/(peak-lo))*(1-smooth01((z-peak)/(hi-peak)))
    additive=np.where(inside,additive,0.)
    return additive,signed,np.maximum(signed,0.)


def clone_calibrate(fn,replacements,extra):
    src=inspect.getsource(fn)
    for old,new in replacements:
        if src.count(old)!=1: raise RuntimeError('Unsupported calibration anchor: '+old)
        src=src.replace(old,new,1)
    scope=dict(fn.__globals__);scope.update(extra)
    exec(compile(src,'<038 experimental calibration>','exec'),scope)
    return scope[fn.__name__]


@contextlib.contextmanager
def trial(mode):
    import thicc_edit as te
    from morphology import calibration as c
    old_frame=te.Sculpt.set_frame; old_cal=c.calibrate; old_smooth=c.smooth_correction
    try:
        if mode in ('linear_map','no_crotch_map'):
            def set_frame(sc,L):
                old_frame(sc,L)
                a,b=mapping_knots(L,te.REF,mode=='no_crotch_map')
                sc.zmap=(lambda z:linear_extrap(z,a,b)) if mode=='linear_map' else te.pchip(a,b)
                print('Experimental vertical knots:',a.tolist(),b.tolist())
            te.Sculpt.set_frame=set_frame
        if mode in ('root_none','root_skinning'):
            def root_cal(sc,*args,**kw):
                if mode=='root_none': sc.root=None
                return old_cal(sc,*args,**kw)
            c.calibrate=root_cal
        if mode=='no_convolution':
            c.smooth_correction=lambda Hc,g,env:Hc*env
        if mode in ('quintic_env','model_env','unit_response','additive','absolute','absolute_positive'):
            def make_target(sc,L,zs,original,amounts):
                good=np.isfinite(original)
                if good.sum()<3: raise ValueError('Not enough valid sections')
                lo=max(float(sc.zmap(L['knee'])),float(zs[good][0])); hi=min(float(sc.zmap(L['waist'])),float(zs[good][-1]))
                peak=float(np.clip(sc.zmap(L['hip_z']),lo+.15*(hi-lo),hi-.15*(hi-lo)))
                # Sample the curve in model-height coordinates, not Rover centimetres.
                m=np.linspace(L['knee']-10,L['waist']+10,4001); r=sc.zmap(m)
                mz=np.interp(zs,r,m); a,b,d=np.interp([lo,peak,hi],r,m)
                amp=.143*L['hip_half']/sc.s*amounts['hips']
                result=absolute_targets(mz,original,a,b,d,amp)
                print('TARGET anchors model cm:',a,b,d,'peak gain ref cm:',amp,'mode:',mode,flush=True)
                return result[{'additive':0,'absolute':1,'absolute_positive':2}[mode]]
            def solve(sc,PRs,zs,outline,base,tgt,env):
                before=sc.hip
                try:
                    samples=[]
                    for value in (0.,1.):
                        sc.hip=(zs,np.full_like(zs,value)); q=PRs.copy(); q[:,0]+=sc.field_ref(*PRs.T)[0]; samples.append(outline(q))
                    sensitivity=samples[1]-samples[0]; offset=samples[0]-base
                    good=np.isfinite(sensitivity)&(sensitivity>.05)&np.isfinite(offset)&(env>0)
                    h=np.zeros_like(zs);h[good]=(tgt[good]-offset[good])/sensitivity[good]
                    print('Unit-response valid sections',int(good.sum()),'of',len(zs),'uncapped min/max',float(h.min()),float(h.max()))
                    return np.clip(h,-1.,6.)*env
                finally:sc.hip=before
            replacements=[]
            if mode=='quintic_env':
                replacements.append(('env = smoothstep(a, b, zs) * (1.0 - smoothstep(c, d, zs))','env = _smooth01((zs-a)/(b-a)) * (1.0-_smooth01((zs-c)/(d-c)))'))
            if mode=='model_env':
                replacements.append(('env = smoothstep(a, b, zs) * (1.0 - smoothstep(c, d, zs))','_mz = np.linspace(L["knee"]-10,L["waist"]+15,4001)\n    _rz = sc.zmap(_mz)\n    _za, _zb, _zc, _zd = np.interp([a,b,c,d],_rz,_mz)\n    _z = np.interp(zs,_rz,_mz)\n    env = smoothstep(_za,_zb,_z)*(1.0-smoothstep(_zc,_zd,_z))'))
            if mode in ('additive','absolute','absolute_positive'):
                replacements.append(('    if observer is not None: observer("hip_target_final", locals())','    tgt = _make_target(sc,L,zs,original_outline,amounts)\n    if observer is not None: observer("hip_target_final", locals())'))
            if mode=='unit_response':
                replacements += [('    for it in range(1 if zero_calibration else 8):','    Hc = _solve(sc,PRs,zs,outline,original_outline,tgt,env)\n    for it in range(1):'),('        Hc = np.zeros_like(Hc) if zero_calibration else update_correction(Hc, env, err)','        Hc = Hc.copy()'),('        Hc = smooth_correction(Hc, g, env)','        Hc = Hc.copy()')]
            c.calibrate=clone_calibrate(old_cal,replacements,dict(_smooth01=smooth01,_make_target=make_target,_solve=solve))
        yield
    finally:
        te.Sculpt.set_frame=old_frame;c.calibrate=old_cal;c.smooth_correction=old_smooth


def derivatives(p,q,faces,d,label):
    from morphology.geometry import contour
    from _hip_root_lab import subset_indices
    sc=d['sc'];L=d['L']; tri=np.concatenate([faces[n] for n in visible(d,faces)])
    tri=tri[subset_indices(tri,d['sv'][d['tri']])]; m=np.linspace(L['knee'],L['waist'],401); r=sc.zmap(m)
    print('MAP slope/curvature extrema',float(np.min(np.gradient(r,m))),float(np.max(np.gradient(r,m))),float(np.max(np.abs(np.gradient(np.gradient(r,m),m)))))
    print('FIELD PROFILE',label,'Z model | Zref | side | original width | final width | actual gain | field gain at original contour point | Hc | dZref/dZ')
    slope=np.gradient(r,m)
    for sign in (1,-1):
        rows=[]
        for i,z in enumerate(m):
            a=contour(p[tri],z);b=contour(q[tri],z);a=a[a[:,0]*sign>0];b=b[b[:,0]*sign>0]
            if not len(a) or not len(b):continue
            pt=a[np.argmax(sign*a[:,0])]; w0=sign*pt[0];w1=float(np.max(sign*b[:,0]));dx,_=sc.field(pt[0:1],pt[1:2],np.array([z])); rows.append((z,r[i],sign,w0,w1,w1-w0,sign*dx[0],np.interp(r[i],d['zs'],d['hc']),slope[i]))
        rows=np.asarray(rows)
        if len(rows)<3:continue
        for row in rows:print(' '.join('%.6f'%x for x in row))
        for col,name in ((5,'surface gain'),(6,'field sampled along original outline')):
            curv=np.gradient(np.gradient(rows[:,col],rows[:,0]),rows[:,0]); j=np.argmax(np.abs(curv[2:-2]))+2
            print('PEAK',name,'side',sign,'Z',rows[j,0],'second derivative',curv[j],'distance to crotch',abs(rows[j,0]-L['crotch']))
    print('CALIBRATION TARGET/ENVELOPE',label,'Zref | baseline | target gain | attained gain | env | Hc')
    for row in zip(d['zs'],d['baseline'],d['target'],d['actual'],d['env'],d['hc']):print(' '.join('%.6f'%x for x in row))


def execute(num):
    plans={69:[('Legacy','legacy',2.,0.),('Linear same knots','linear_map',2.,0.),('PCHIP without crotch/apex','no_crotch_map',2.,0.)],70:[('Legacy','legacy',2.,0.),('Quintic envelope','quintic_env',2.,0.),('Model-height envelope','model_env',2.,0.)],71:[('Legacy','legacy',2.,0.),('Skinning root','root_skinning',2.,0.),('No root','root_none',2.,0.),('Thighs positive control','legacy',0.,2.),('Thighs no root','root_none',0.,2.)],72:[('Legacy','legacy',2.,0.),('Zero calibration','zero',2.,0.),('No internal convolution','no_convolution',2.,0.),('One-unit response','unit_response',2.,0.)],73:[('Legacy','legacy',2.,0.),('Anatomical additive','additive',2.,0.),('Absolute signed','absolute',2.,0.),('Absolute expand only','absolute_positive',2.,0.)]}
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini);saved=load_cfg(root);cases=[('Original',p)]; base=None; thigh_base=None
        for label,mode,h,t in plans[num]:
            # isolated() forces virtual_inguinal=True in protocol mode, so switch
            # the virtual root selection at its construction, not in saved settings.
            import thicc_edit as te
            old_roots=te.morphological_roots
            try:
                if mode=='root_skinning':te.morphological_roots=lambda *a,**k:None
                with trial(mode):q,d=run(root,p,faces,saved,hips=h,thighs=t,zero=mode=='zero')
            finally:te.morphological_roots=old_roots
            if base is None:base=q;first=d
            if t==0:compare(base,q,label)
            elif thigh_base is None:thigh_base=q
            else:compare(thigh_base,q,label)
            report_profile(p,q,faces,d,label)
            derivatives(p,q,faces,d,label)
            cases.append((label,q))
        view(p,faces,cases,first,f'{num} | {TITLES[num]}')
    print(f'===== EXPERIMENT {num} - {TITLES[num]} FINISHED =====',flush=True)
