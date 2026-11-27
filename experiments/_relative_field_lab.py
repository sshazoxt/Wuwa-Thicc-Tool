"""Experiment-only field alternatives. The installed production engine is untouched."""
import contextlib
import inspect
import numpy as np
from _hip_root_lab import run, view, compare, report_profile
from preview_no_seam_guard import sandbox, geometry, load_cfg


def step01(x):
    x=np.clip(x,0.,1.)
    return x*x*x*(10+x*(-15+6*x))


def bump(z,lo,peak,hi):
    if not lo<peak<hi: raise ValueError('Invalid anatomical interval')
    return step01((z-lo)/(peak-lo))*(1-step01((z-peak)/(hi-peak)))


def section_profiles(sc, PR, tri, L):
    from morphology.geometry import contour
    # Measure the original surface in the existing reference frame. Use exact
    # plane intersections, not density-dependent vertex percentiles.
    zmodel=np.linspace(L['ankle'],L['waist'],101)
    zs=sc.zmap(zmodel); mesh=PR[tri]; hip=[]; legs={s:[] for s in (1,-1)}
    import thicc_edit as te
    for z in zs:
        c=contour(mesh,z)
        hip.append(np.max(np.hypot(c[:,0],c[:,1]-te.REF['cy'])) if len(c) else np.nan)
        for s in legs:
            k,x,y=sc.axis[s]; ax=np.interp(z,k,x); ay=np.interp(z,k,y)
            q=c[c[:,0]*s>0]
            legs[s].append(np.max(np.hypot(q[:,0]-ax,q[:,1]-ay)) if len(q) else np.nan)
    def fill(v):
        v=np.asarray(v); good=np.isfinite(v)&(v>1e-6)
        if good.sum()<5: raise RuntimeError('Insufficient measured sections')
        return np.interp(zs,zs[good],v[good]),good
    hr,hgood=fill(hip); lr={}; valid={}
    for s in legs: lr[s],valid[s]=fill(legs[s])
    return dict(z=zs,model_z=zmodel,hip=hr,legs=lr,hip_valid=hgood,leg_valid=valid)


def hip_mask(step,r,local):
    # At the measured outer surface influence is one; fade away from body.
    t=r/np.maximum(local,1e-6)
    return step(.20,.48,t)*(1-step(1.05,1.45,t))


def leg_mask(step,r,local):
    return 1-step(1.05,1.55,r/np.maximum(local,1e-6))


def ownership(px,py,pz,sc,sgn):
    dist=[]
    for s in (sgn,-sgn):
        k,x,y=sc.axis[s]; dist.append(np.hypot(px-sc.curve(k,x,pz),py-sc.curve(k,y,pz)))
    # Soft partition of unity, based on relative distances. No double strength.
    a,b=dist; return step01(np.divide(b,a+b,out=np.full_like(a,.5),where=(a+b)>1e-9))


def clone(fn, replacements, extra):
    src=inspect.getsource(fn)
    for old,new in replacements:
        if old not in src: raise RuntimeError('Unsupported engine anchor: '+old)
        src=src.replace(old,new)
    scope=dict(fn.__globals__); scope.update(extra)
    exec(compile(src,'<relative field experiment>','exec'),scope)
    return scope[fn.__name__]


@contextlib.contextmanager
def trial(flags):
    from morphology import calibration, hips, legs
    original=(calibration.calibrate,hips.accumulate,legs.accumulate)
    extra=dict(_hip_mask=hip_mask,_leg_mask=leg_mask,_ownership=ownership)
    try:
        hip_replacements=[]
        if 'hip_mask' in flags:
            hip_replacements.append(('step(4.0, 9.0, _)\n            * (1.0 - step(21.0, 27.0, _))','_hip_mask(step, _, np.interp(pz, self._lab_profiles["z"], self._lab_profiles["hip"]))'))
        if 'linear_lateral' in flags:
            hip_replacements.append(('ux * (0.55 + 0.45 * ux * ux)','ux'))
        if 'no_hip_depth' in flags:
            hip_replacements.append(('dy += hip_amount * depth * self.direction["hips"][1]','dy += 0.0'))
        if hip_replacements: hips.accumulate=clone(original[1],hip_replacements,extra)
        calibration_replacements=[]
        if 'relative_mix' in flags:
            calibration_replacements.append(('wt = smoothstep(72.0, 82.0, zs)','wt = smoothstep(float(sc.zmap(L["knee"] + .68*(L["crotch"]-L["knee"]))), float(sc.zmap(L["crotch"])), zs)'))
        if 'hip_only_target' in flags:
            calibration_replacements.append(('lower_amount = max(amounts["thighs"], 0.35 * amounts["hips"])','lower_amount = 0.35 * amounts["hips"]'))
        if 'no_floor' in flags:
            calibration_replacements.append(('lower_amount = max(amounts["thighs"], 0.35 * amounts["hips"])','lower_amount = amounts["thighs"]'))
        core_calibrate=clone(original[0],calibration_replacements,{}) if calibration_replacements else original[0]
        replacements=[]
        if 'leg_mask' in flags:
            replacements.append(('(1.0 - step(9.5, 16.0, r))','_leg_mask(step, r, np.interp(pz, self._lab_profiles["z"], self._lab_profiles["legs"][sgn]))'))
        if 'ownership' in flags:
            replacements.append(('        # Main leg displacement (applied only once).','        w = w * _ownership(px, py, pz, self, sgn)\n        # Main leg displacement (applied only once).'))
        if 'root' in flags:
            replacements += [('boundary + 6.0 + 12.0 * step(0.35, 0.95, eyu)','self._lab_model_z(boundary) + self._lab_thigh_length * (.18 + .36 * step(0.35, 0.95, eyu))'),('boundary + 18.0 + 12.0 * step(0.35, 0.95, eyu),\n                pz','self._lab_model_z(boundary) + self._lab_thigh_length * (.54 + .36 * step(0.35, 0.95, eyu)),\n                self._lab_model_z(pz)')]
        if 'local_thigh' in flags:
            # Avoid legacy anterior override: keep the newly defined local amplitude
            # and angular root fade for both field modes.
            replacements.append(('if not self.continuous:\n                effective_amount = (1.0 - mix) * leg_amount * root_fade + mix * target','if not self.continuous:\n                effective_amount = leg_amount * root_fade'))
        if replacements: legs.accumulate=clone(original[2],replacements,extra)
        def calibrate(sc,PR,skin_tri,L,amounts,cfg,REF,HIP_ENV,HIP_TARGET,smoothstep,**kw):
            sc._lab_profiles=section_profiles(sc,PR,skin_tri,L)
            sc._lab_thigh_length=float(L['crotch']-L['knee'])
            mz=np.linspace(0.,L['waist']+40.,2001); rz=sc.zmap(mz)
            sc._lab_model_z=lambda z: np.interp(z,rz,mz)
            if 'local_thigh' in flags:
                # Parameterize amplitude in actual model height, then map back.
                m=np.linspace(L['ankle'],L['waist'],241); z=sc.zmap(m)
                span=L['crotch']-L['knee']; lo=L['knee']-.08*span; hi=L['crotch']+.12*span; peak=L['knee']+.68*span
                # Reference hip width controls desired absolute gain rather than tiny local leg radii.
                gain=.132*L['hip_half']/sc.s
                calf=bump(m,L['ankle'],L['ankle']+.65*(L['knee']-L['ankle']),L['knee'])*.085*L['hip_half']/sc.s
                sc.leg=(z,gain*amounts['thighs']*bump(m,lo,peak,hi)+amounts['calves']*calf)
            if 'target' in flags:
                m=np.linspace(L['knee'],L['waist'],81); z=sc.zmap(m)
                peak=np.clip(L['hip_z'],L['knee']+.1*(L['waist']-L['knee']),L['waist']-.1*(L['waist']-L['knee']))
                gain=.143*L['hip_half']/sc.s
                # Anatomical gain curve, not a solved absolute silhouette. Legacy
                # amount blending/calibration remains intentionally unchanged.
                HIP_TARGET=list(zip(z,gain*bump(m,L['knee'],peak,L['waist'])))
                HIP_ENV=(float(z[0]),float(sc.zmap(L['knee']+.15*(peak-L['knee']))),float(sc.zmap(L['waist']-.15*(L['waist']-peak))),float(z[-1]))
            print('RELATIVE TRIAL:',sorted(flags),'thigh length model cm:',sc._lab_thigh_length,flush=True)
            return core_calibrate(sc,PR,skin_tri,L,amounts,cfg,REF,HIP_ENV,HIP_TARGET,smoothstep,**kw)
        calibration.calibrate=calibrate
        yield
    finally:
        calibration.calibrate,hips.accumulate,legs.accumulate=original


def audit(d):
    import thicc_edit as te
    sc=d['sc']; L=d['L']; p=sc._lab_profiles
    print('LANDMARK | model cm | Rover ref cm | mapped ref cm')
    for k,v in L.items():
        if k in ('ankle','knee','crotch','apex','waist','hip_z'): print(k,v,te.REF.get(k),float(sc.zmap(v)))
    print('X/Y shared scale:',sc.s,'hip_half:',L['hip_half'],'Rover hip_half:',te.REF['hip_half'])
    print('SECTION | Z model | Z ref | hip radius ref | R leg radius | L leg radius | measured flags | hip legacy weight at outer radius | R/L leg legacy weight')
    for i,z in enumerate(p['z']):
        r=p['hip'][i]; a,b=[p['legs'][s][i] for s in (1,-1)]
        sm=te.smoothstep
        print('%8.3f %8.3f %8.3f %8.3f %8.3f %s %s %s %.5f %.5f %.5f'%(p['model_z'][i],z,r,a,b,p['hip_valid'][i],p['leg_valid'][1][i],p['leg_valid'][-1][i],sm(4,9,r)*(1-sm(21,27,r)),1-sm(9.5,16,a),1-sm(9.5,16,b)))
    print('Radius estimates use outermost section samples on each half; above crotch they can include pelvis, not isolated leg.')


TITLES={41:'LEGACY REFERENCE AUDIT',42:'HIP RADIAL MASK AB',43:'LEG RADIUS CONTINUITY',44:'LEG FIELD OWNERSHIP',45:'HIP TARGET PROFILE',46:'ANATOMICAL ROOT FALLOFF',47:'LOCAL THIGH FIELD',48:'RELATIVE MORPHOLOGY COMPARISON'}


def execute(num):
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini); saved=load_cfg(root)
        from experiment_parameters import experiment_amounts
        requested=experiment_amounts(saved,dict(hips=3.98,thighs=2.))
        h,t=requested['hips'],requested['thighs']
        print('Hips test:',h,'Thighs test:',t,'post smoothing disabled by isolated config')
        if num in (41,43):
            with trial(set()): q,d=run(root,p,faces,saved,hips=h)
            audit(d); report_profile(p,q,faces,d,'legacy')
            if num==43:
                with trial({'leg_mask'}): v,e=run(root,p,faces,saved,thighs=t,disable_hip=True)
                with trial(set()): a,b=run(root,p,faces,saved,thighs=t,disable_hip=True)
                compare(a,v,'relative leg radius'); report_profile(p,v,faces,e,'relative leg radius')
                view(p,faces,[('Original',p),('Legacy leg mask',a),('Relative leg mask',v)],b,'43 | Leg radius continuity')
        else:
            casespec={42:[('Legacy',set(),h,0),('Relative hip mask',{'hip_mask'},h,0)],44:[('Legacy',set(),0,t),('Ownership',{'ownership'},0,t)],45:[('Legacy',set(),h,0),('Anatomical gain',{'target'},h,0)],46:[('Legacy',set(),0,t),('Relative root',{'root'},0,t)],47:[('Legacy',set(),0,t),('Local thigh amplitude',{'local_thigh'},0,t),('Local + radial + ownership',{'local_thigh','leg_mask','ownership'},0,t)],48:[('Legacy',set(),h,t),('Relative hip',{'hip_mask','target'},h,t),('Relative legs',{'leg_mask','ownership','root','local_thigh'},h,t),('Combined',{'hip_mask','target','leg_mask','ownership','root','local_thigh'},h,t)]}[num]
            cases=[('Original',p)]; base=None
            for name,flags,ha,ta in casespec:
                # 44/46/47 isolate actual thigh field, including during final application.
                with trial(flags): q,d=run(root,p,faces,saved,hips=ha,thighs=ta,disable_hip=num in (44,46,47))
                if base is None: base=q; first=d; audit(d)
                else: compare(base,q,name)
                report_profile(p,q,faces,d,name); cases.append((name,q))
            view(p,faces,cases,first,'%02d | %s'%(num,TITLES[num]))
    print('===== EXPERIMENT %02d - %s FINISHED ====='%(num,TITLES[num]),flush=True)
