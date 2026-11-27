"""Read-only root cause experiments. No production file or source mod is written."""
import copy
import contextlib
import hashlib
import inspect
import sys
from pathlib import Path
import json
import numpy as np
from preview_no_seam_guard import sandbox, geometry, load_cfg


def isolated(saved, hips=0., thighs=0.):
    c=copy.deepcopy(saved)
    c.update(morphology_engine='Legacy', amounts=dict(hips=float(hips), thighs=float(thighs), butt=0., calves=0.),
             belly_morphology={'amount':0.}, waist_morphology={'enabled':False},
             bounce='normal', seam_guard=False, coupled_hips=False,
             relative_silhouette=False, surface_rounding=False, inner_fill=False,
             displacement_smoothing=False, advanced_clothing=False,
             final_regularization={'enabled':False}, surface_shading='Original',
             directional_expansion={k:[1.,1.] for k in ('hips','thighs','butt','calves')})
    import os
    if os.environ.get('THICC_PARAMETER_MODE','protocol')=='protocol':
        c.update(preset='pear', deformation_field='Legacy', virtual_inguinal=True,
                 advanced_arm_protection=False, directional_enabled=False,
                 inner_gap_mode='Rounded transition')
    return c


def unique_faces(p,t,tolerance=1e-5):
    # Exact-to-tolerance geometric duplicate faces, not a mesh weld or overlap boolean.
    ids=np.unique(t)
    _,inv=np.unique(np.rint(p[ids]/tolerance).astype(np.int64),axis=0,return_inverse=True)
    keys=np.sort(inv.reshape(-1)[np.searchsorted(ids,t)],axis=1)
    _,keep=np.unique(keys,axis=0,return_index=True)
    return t[np.sort(keep)]


def subset_indices(all_tri, wanted):
    """Select only faces actually used by production (arm exclusion preserved)."""
    keys={tuple(sorted(row)) for row in wanted}
    return np.fromiter((tuple(sorted(row)) in keys for row in all_tri),bool,count=len(all_tri))


@contextlib.contextmanager
def calibration_trial(limit=None, response=None, scaled_step=False):
    from morphology import calibration as m
    old=m.update_correction
    if limit is not None or response is not None:
        def update(h,env,err):
            cap=limit if response is None else response['cap']
            step=1.3 if not scaled_step else np.clip(.85/np.maximum(response['sensitivity'],.15),.5,4.)
            return np.clip(h+step*env*err,-1.,cap)
        m.update_correction=update
    try: yield
    finally: m.update_correction=old


def estimate_response(sc, points, zs, outline, original, target):
    """Probe the real field's one-unit response; no surface smoothing added."""
    old=sc.hip
    try:
        widths=[]
        for val in (0.,1.):
            sc.hip=(zs,np.full_like(zs,val,dtype=float))
            q=points.copy(); q[:,0]+=sc.field_ref(*points.T)[0]
            widths.append(outline(q))
    finally: sc.hip=old
    base=widths[0]-original
    sensitivity=widths[1]-widths[0]
    valid=np.isfinite(sensitivity)&(sensitivity>.05)&np.isfinite(base)
    required=np.full(len(zs),np.nan)
    required[valid]=np.maximum(0.,(target[valid]-base[valid])/sensitivity[valid])
    cap=np.clip(np.nan_to_num(required,nan=0.)*1.25,6.,24.)
    return dict(sensitivity=np.where(valid,sensitivity,.15),required=required,cap=cap,base=base,valid=valid)


@contextlib.contextmanager
def measurement_reference(te, mode):
    """Experiment-only source clone at an exact anchor, preserving roles and all output IDs."""
    if mode is None:
        yield; return
    original=te.run; src=inspect.getsource(original)
    anchor='    skin_tri = skin_tri[(armw[skin_tri] < 0.01).all(1)]'
    if src.count(anchor)!=1: raise RuntimeError('Unsupported engine: measurement anchor not unique')
    extra = """
    if set(reference['uncertain']) & set(SKIN):
        raise RuntimeError('Active Skin reference unresolved; cannot safely isolate measurements')
    _lab_names = [n for n in SKIN if n in reference['active']]
    if not _lab_names: raise RuntimeError('No active Skin reference')
    _lab_tri = np.concatenate([tris(n) for n in _lab_names])
    _lab_tri = _lab_tri[(armw[_lab_tri] < 0.01).all(1)]
    if not len(_lab_tri): raise RuntimeError('Empty active Skin reference')
    if _LAB_MEASURE_MODE == 'active_unique': _lab_tri = _LAB_UNIQUE(P0, _lab_tri)
    print('Experimental measurement reference:', _LAB_MEASURE_MODE, len(skin_tri), '->', len(_lab_tri), _lab_names)
    skin_tri = _lab_tri
    skin_core = np.unique(skin_tri)
"""
    scope=dict(original.__globals__); scope.update(_LAB_MEASURE_MODE=mode,_LAB_UNIQUE=unique_faces)
    exec(compile(src.replace(anchor,anchor+'\n'+extra,1),'<experimental measurement reference>','exec'),scope)
    te.run=scope['run']
    try: yield
    finally: te.run=original


def run(root,p,faces,saved,hips=0.,thighs=0.,reference='all',limit=None,adaptive=False,disable_hip=False,zero=False,measurement=None,scaled_step=False):
    import thicc_edit as te
    from morphology.calibration import fixed_core_outline
    from morphology.engine import PreparedGeometry
    data={}; cfg=isolated(saved,hips,thighs)
    print('\n===== CASE hips=%g thighs=%g reference=%s limit=%s adaptive=%s disable_hip=%s zero=%s ====='%(hips,thighs,reference,limit,adaptive,disable_hip,zero),flush=True)
    print('Config:',json.dumps(cfg,ensure_ascii=False,sort_keys=True),flush=True)
    response={} if adaptive else None
    print('Measurement override:',measurement,'response-scaled step:',scaled_step)
    def obs(event,d):
        if event=='hip_target_initial':
            data['target_initial']=d['tgt'].copy()
        elif event=='hip_target_final':
            data['target']=d['tgt'].copy(); data['env']=d['env'].copy()
            if response is not None:
                response.update(estimate_response(d['sc'],d['PRs'],d['zs'],d['outline'],d['original_outline'],d['tgt']))
                print('Zref | one-unit X response | estimated required Hc | experimental cap | valid')
                for z,k,r,c,v in zip(d['zs'],response['sensitivity'],response['required'],response['cap'],response['valid']):
                    print('%6.1f | %+.5f | %+.5f | %.5f | %s'%(z,k,r,c,v))
        elif event=='hip_iteration_clipped':
            data.setdefault('iterations',[]).append(d['Hc'].copy())
        elif event=='calibrated':
            data.update(zs=d['zs'].copy(),hc=d['Hc'].copy(),sv=d['sv'].copy(),tri=d['tri_l'].copy(),
                        ref=d['PRs'].copy(),names=list(d['SKIN']),active=list(d['reference']['active']),
                        L=dict(d['L']),scale=float(d['sc'].s),sc=d['sc'])
            q=d['PRs'].copy(); q[:,0]+=d['sc'].field_ref(*q.T)[0]
            data['actual']=d['outline'](q)-d['original_outline']; data['baseline']=d['original_outline'].copy()
            data['uncertain']=list(d['reference']['uncertain'])
            data['anatomy']=list(d['anatomy_names']); data['freeze']=sorted(d['freeze']); data['garments']=list(d['GARMENTS'])
            print('Landmarks (natural / effective):',d['natural'],d['L'])
            print('Leg axis:', {str(k):[np.asarray(x).tolist() for x in v] for k,v in d['sc'].axis.items()})
            print('Leg root:', None if d['sc'].root is None else {str(k):[np.asarray(x).tolist() for x in v] for k,v in d['sc'].root.items()})
        elif event=='before_field': data['allow']=d['allow'].copy()
        elif event=='before_waist': data['raw']=d['new'].copy(); data['guard']=d['guard'].copy()
    # Select active faces from the very same production triangle set, using the
    # observer's initial caller frame only to get draw identity before calibration.
    def factory(ref,tri,zs):
        if reference=='all': return fixed_core_outline(ref,tri,zs)
        frame=sys._getframe(1)
        while frame and frame.f_code is not te.run.__code__: frame=frame.f_back
        if frame is None: raise RuntimeError('Production frame unavailable')
        d=frame.f_locals
        sv=np.unique(d['skin_tri']); selected=tri
        if reference in ('active','active_unique'):
            if set(d['reference']['uncertain']) & set(d['SKIN']): raise RuntimeError('Active Skin reference unresolved; cannot safely isolate calibration')
            names=[n for n in d['SKIN'] if n in d['reference']['active']]
            if not names: raise RuntimeError('No resolved active Skin reference')
            active_tri=np.concatenate([faces[n] for n in names])
            active_tri=active_tri[(d['armw'][active_tri]<.01).all(1)]
            selected=np.searchsorted(sv,active_tri)
            if np.any(selected>=len(sv)) or not np.array_equal(sv[selected],active_tri):
                raise RuntimeError('Active triangles do not belong to the original reference')
        if reference in ('unique','active_unique'): selected=unique_faces(ref,selected)
        if not len(selected): raise RuntimeError('Empty experimental reference')
        print('Calibration reference faces:',len(tri),'->',len(selected),flush=True)
        data['reference_faces']=len(selected)
        return fixed_core_outline(ref,selected,zs)
    field_stages={}
    def field_observer(label,d):
        field_stages[label]=np.column_stack((d['dx'],d['dy']))*d['self'].s
    # Test changes to calibration or to its upstream reference only.
    with measurement_reference(te,measurement), calibration_trial(limit,response,scaled_step):
        result=te.run(str(root),'dry',config_override=cfg,observer=obs,
                      prepared_geometry=PreparedGeometry(root), outline_factory=factory if reference!='all' else None,
                      disable_hip=disable_hip,zero_calibration=zero,positions_only=True,field_observer=field_observer)
    q=np.asarray(result['preview_positions'],float)
    if 'raw' not in data or 'actual' not in data: raise RuntimeError('Incomplete engine observation')
    valid=np.isfinite(data['actual'])&(data['env']>.5)
    residual=data['target']-data['actual']
    data['residual']=float(np.max(np.abs(residual[valid]))) if valid.any() else np.nan
    print('POST calibration residual ref cm:',data['residual'],'scale:',data['scale'],'Skin:',data['names'],'active:',data['active'])
    compare(data['raw'],q,'Raw field after masks vs final arm-safety output')
    print('Active reference uncertain:',data['uncertain'])
    quality(p,q,np.concatenate([faces[n] for n in visible(data,faces)]))
    if field_stages:
        v=np.unique(np.concatenate([faces[n] for n in visible(data,faces)])); prev=np.zeros((len(p),2)); parts={}
        for label,field in field_stages.items(): parts[label]=field-prev; prev=field
        print('RAW FIELD model cm: Z | vertices | p95 outward X by contribution:',list(parts))
        for lo,hi in zip(np.linspace(data['L']['knee'],data['L']['waist'],41)[:-1],np.linspace(data['L']['knee'],data['L']['waist'],41)[1:]):
            ids=v[(p[v,2]>=lo)&(p[v,2]<hi)]
            if len(ids): print('%.3f..%.3f'%(lo,hi),len(ids),*[float(np.percentile(a[ids,0]*np.sign(p[ids,0]),95)) for a in parts.values()])
    print('Calibration finite sections:',np.sum(np.isfinite(data['actual'])),'of',len(data['actual']))
    cap=response['cap'] if response is not None else (6. if limit is None else limit)
    for i,clipped in enumerate(data.get('iterations',[])):
        print('Iteration',i+1,'upper cap sections:',np.sum(clipped>=cap-1e-8),'lower cap sections:',np.sum(clipped<=-1.+1e-8))
    print('Zref | target | actual | residual | Hc')
    for z,t,a,e,h in zip(data['zs'],data['target'],data['actual'],residual,data['hc']):
        print('%6.1f | %+8.4f | %+8.4f | %+8.4f | %+8.4f'%(z,t,a,e,h))
    return q,data


def visible(d,faces):
    names=[n for n in d['names'] if n in d['active'] and n in faces]
    if not names: raise RuntimeError('No active Skin geometry; resolve INI first')
    return names


def profile(p,q,faces,names,L,filtered=None):
    from morphology.geometry import contour
    tri=np.concatenate([faces[n] for n in names])
    if filtered is not None: tri=tri[subset_indices(tri,filtered)]
    if not len(tri): raise RuntimeError('Empty profile geometry')
    z=np.linspace(L['knee'],L['waist'],101)
    # Z is unchanged for these trials. Measure each side independently in model cm.
    def widths(a):
        t=a[tri]; out=[]
        for h in z:
            c=contour(t,h)
            out.append([max(c[c[:,0]*s>0,0]*s,default=np.nan) for s in (1,-1)])
        return np.asarray(out)
    base=widths(p); final=widths(q); gain=final-base
    return z,base,final,gain


def report_profile(p,q,faces,d,label):
    z,b,f,g=profile(p,q,faces,visible(d,faces),d['L'],d['sv'][d['tri']])
    dz=z[1]-z[0]; curvature=np.diff(g,n=2,axis=0)/dz**2
    k0=np.diff(b,n=2,axis=0)/dz**2; k1=np.diff(f,n=2,axis=0)/dz**2
    print('PROFILE',label,'model cm: Z | original R/L | final R/L | gain R/L | original curvature R/L | final curvature R/L | gain curvature R/L')
    for i in range(1,len(z)-1): print('%.4f '%z[i]+' '.join('%+.5f'%x for x in np.r_[b[i],f[i],g[i],k0[i-1],k1[i-1],curvature[i-1]]))
    if np.isfinite(curvature).any():
        j,k=np.unravel_index(np.nanargmax(np.abs(curvature)),curvature.shape)
        print('Peak gain curvature:',curvature[j,k],'at Z',z[j+1],'side',('R','L')[k])


def view(p,faces,cases,d,title):
    from morphology.viewer import ExperimentViewer
    ExperimentViewer(p,faces,cases,visible(d,faces),title).show(view='back')


def compare(a,b,label):
    delta=np.linalg.norm(a-b,axis=1)
    print(label,'max cm:',delta.max(),'RMS cm:',np.sqrt(np.mean(delta**2)),'vertices > 1e-5:',np.count_nonzero(delta>1e-5))


def quality(p,q,tri):
    a,b=p[tri],q[tri]
    u=np.cross(a[:,1]-a[:,0],a[:,2]-a[:,0]); v=np.cross(b[:,1]-b[:,0],b[:,2]-b[:,0])
    area0=np.linalg.norm(u,axis=1); area1=np.linalg.norm(v,axis=1)
    valid=area0>1e-9; ratio=area1[valid]/area0[valid]
    print('Active Skin quality (diagnostic only): original degenerate',np.sum(~valid),
          'area ratio < 0.1',np.sum(ratio<.1),'normal direction > 90 degrees',np.sum(np.einsum('ij,ij->i',u[valid],v[valid])<0))
    if len(ratio): print('Area ratio min / p01 / p99 / max:',np.percentile(ratio,[0,1,99,100]))


def surface_proximity(p,q,faces,names,lo,hi):
    """Area-weighted point-to-triangle sample distances, not intersection proof."""
    import pyvista as pv
    from itertools import combinations
    tol=np.array([.001,.005,.015])*(hi-lo)
    print('Active surface proximity tolerances (cm):',tol.tolist())
    def mesh(points,t):
        ids=np.unique(t); cells=np.column_stack((np.full(len(t),3),np.searchsorted(ids,t))).ravel()
        return pv.PolyData(points[ids],cells)
    for a,b in combinations(names,2):
        ta,tb=faces[a],faces[b]
        za=p[ta,2]; zb=p[tb,2]
        low=max(lo,float(za.min()),float(zb.min())); high=min(hi,float(za.max()),float(zb.max()))
        if high<=low: continue
        for src,dst in ((a,b),(b,a)):
            t=faces[src]; z=p[t,2]
            t=t[(z.max(1)>=low)&(z.min(1)<=high)]
            if not len(t): continue
            if len(t)>3000:
                t=t[np.sort(np.random.default_rng(30).choice(len(t),3000,replace=False))]
            bary=np.array([[1/3,1/3,1/3],[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]])
            x=p[t]; y=q[t]; area=np.linalg.norm(np.cross(x[:,1]-x[:,0],x[:,2]-x[:,0]),axis=1)/2
            w=np.repeat(area/len(bary),len(bary)); x=np.einsum('sj,tjk->tsk',bary,x).reshape(-1,3); y=np.einsum('sj,tjk->tsk',bary,y).reshape(-1,3)
            before_mesh=mesh(p,faces[dst]); after_mesh=mesh(q,faces[dst])
            _,near0=before_mesh.find_closest_cell(x,return_closest_point=True)
            _,near1=after_mesh.find_closest_cell(y,return_closest_point=True)
            d0=np.linalg.norm(x-near0,axis=1); d1=np.linalg.norm(y-near1,axis=1)
            print('SURFACE SAMPLE',src,'->',dst,'| original Z | sampled area | proximity before % | after %')
            for l,h in zip(np.linspace(low,high,11)[:-1],np.linspace(low,high,11)[1:]):
                m=(x[:,2]>=l)&(x[:,2]<h); total=w[m].sum()
                if total>0:
                    print('%.3f..%.3f'%(l,h),float(total),*[round(100*float(w[m&(ds<=r)].sum()/total),3) for ds in (d0,d1) for r in tol])


def overlap(p,q,faces,d):
    from scipy.spatial import cKDTree
    from morphology.geometry import contour
    names=d['names']; lo,hi=d['L']['knee'],d['L']['waist']
    print('Overlap diagnostics: sampled nearest vertices, not triangle collision or proof of duplicate surface.')
    print('Skin part summary (original model cm):')
    for n in names:
        v=np.unique(faces[n]); print(n,'active=',n in d['active'],'vertices=',len(v),'faces=',len(faces[n]),'Z=',p[v,2].min(),p[v,2].max())
    alltri=d['sv'][d['tri']]; dup=unique_faces(p,alltri)
    print('Production triangle count:',len(alltri),'after geometric face deduplication:',len(dup))
    # Controlled split: same exact triangles and coordinates, split/reorder only.
    from morphology.calibration import fixed_core_outline
    r,t,z=d['ref'],d['tri'],d['zs']; a=fixed_core_outline(r,t,z)
    mid=np.median(r[t,2].mean(axis=1)); mask=r[t,2].mean(axis=1)<mid
    b=fixed_core_outline(r,np.concatenate([t[~mask],t[mask]]),z)
    moved=r.copy(); moved[:,0]+=d['sc'].field_ref(*r.T)[0]
    print('Controlled partition (identical union, reordered by height): original/final equal:',np.allclose(a(r),b(r),equal_nan=True),np.allclose(a(moved),b(moved),equal_nan=True))
    for i,n in enumerate(names):
        v=np.unique(faces[n]); v=v[(p[v,2]>=lo)&(p[v,2]<=hi)]
        if not len(v): continue
        for m in names[i+1:]:
            w=np.unique(faces[m]); w=w[(p[w,2]>=lo)&(p[w,2]<=hi)]
            if not len(w): continue
            dist,ix=cKDTree(p[w]).query(p[v]); good=dist<.1
            if not good.any(): continue
            a,b=v[good],w[ix[good]]; dd=np.linalg.norm((q-p)[a]-(q-p)[b],axis=1)
            print(n,'|',m,'active=',n in d['active'],m in d['active'],'near <0.1cm=',len(a),'exact <1e-5=',np.sum(dist[good]<1e-5),'Z range=',p[a,2].min(),p[a,2].max(),'displacement difference p95/max=',np.percentile(dd,95),dd.max())
    try:
        surface_proximity(p,q,faces,visible(d,faces),lo,hi)
    except Exception as exc:
        print('Optional point-to-triangle proximity unavailable:',repr(exc))
    print('SECTION OWNERSHIP: model Z | part | active | points | original R/L | deformed R/L')
    for z in np.linspace(lo,hi,41):
        for n in names:
            c=contour(p[faces[n]],z)
            if len(c):
                after=contour(q[faces[n]],z)
                print('%.3f'%z,n,n in d['active'],len(c),*[max(v[v[:,0]*sign>0,0]*sign,default=np.nan) for v in (c,after) for sign in (1,-1)])


def execute(num):
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini); saved=load_cfg(root)
        from experiment_parameters import experiment_amounts
        requested=experiment_amounts(saved,dict(hips=3.98,thighs=2.))
        h,t=requested['hips'],requested['thighs']
        import thicc_edit as te
        print('Installed engine SHA256:',hashlib.sha256(Path(te.__file__).read_bytes()).hexdigest())
        print('Original positions SHA256:',hashlib.sha256(p.tobytes()).hexdigest())
        print('Comparison Hips:',h,'field mode:',isolated(saved,h,t).get('deformation_field','Legacy'),'saved landmark overrides:',saved.get('landmarks',{}))
        if num==34:
            cases=[('Original',p)]
            for x in sorted(set([0.,1.,1.5,1.75,2.,3.,h,5.])):
                q,d=run(root,p,faces,saved,hips=x); report_profile(p,q,faces,d,str(x)); cases.append(('Hips %.2f | residual %.3f'%(x,d['residual']),q))
            view(p,faces,cases,d,'34 | Fixed Core sweep')
        elif num==35:
            cases=[('Original',p)]
            for cap in (6.,9.,12.,18.):
                q,d=run(root,p,faces,saved,hips=h,limit=cap); report_profile(p,q,faces,d,str(cap)); cases.append(('Cap %g | residual %.3f'%(cap,d['residual']),q))
            view(p,faces,cases,d,'35 | Calibration limit A/B')
        elif num==36:
            q,d=run(root,p,faces,saved,hips=h); overlap(p,q,faces,d); report_profile(p,q,faces,d,'all Skin'); cases=[('Original',p),('All Skin',q)]
            for ref in ('unique','active','active_unique'):
                v,e=run(root,p,faces,saved,hips=h,reference=ref); compare(q,v,ref); report_profile(p,v,faces,d,ref); cases.append((ref+' | %.3f'%e['residual'],v))
            view(p,faces,cases,d,'36 | Segmentation and overlapping references')
        elif num==37:
            regression(root,p,faces,saved,h)
        elif num==38:
            q,d=run(root,p,faces,saved,hips=h); a,e=run(root,p,faces,saved,hips=h,adaptive=True); b,f=run(root,p,faces,saved,hips=h,adaptive=True,scaled_step=True)
            cases=[('Original',p),('Fixed cap',q),('Response-based cap',a),('Response-based cap + step',b)]
            for label,v in cases[1:]: report_profile(p,v,faces,d,label)
            compare(q,a,'adaptive cap'); compare(q,b,'adaptive cap + step'); view(p,faces,cases,d,'38 | Response-aware calibration')
        elif num==39:
            q,d=run(root,p,faces,saved,thighs=t); a,e=run(root,p,faces,saved,thighs=t,disable_hip=True); b,f=run(root,p,faces,saved,hips=h); c,g=run(root,p,faces,saved,hips=h,thighs=t); cases=[('Original',p),(f'Thighs {t:g} production',q),(f'Thighs {t:g} no calibrated hip',a),('Hips only',b),('Combined',c)]
            for label,v in cases[1:]: report_profile(p,v,faces,d,label)
            compare(q,a,'Thighs with vs without calibration'); view(p,faces,cases,d,'39 | Thigh field isolation')
        elif num==40:
            q,d=run(root,p,faces,saved,hips=h); cases=[('Original',p),('All Skin measurements',q)]
            for ref in ('active','active_unique'):
                v,e=run(root,p,faces,saved,hips=h,measurement=ref)
                print('Landmarks all/alternative:',d['L'],e['L']); print('Roles unchanged:',d['names']==e['names'] and d['anatomy']==e['anatomy'] and d['freeze']==e['freeze'] and d['garments']==e['garments'])
                compare(q,v,'measurement '+ref); report_profile(p,v,faces,d,ref); cases.append((ref+' measurements',v))
            view(p,faces,cases,d,'40 | Upstream anatomical reference A/B')
        else: raise ValueError(num)
    print('===== EXPERIMENT %02d - %s FINISHED ====='%(num,TITLES[num]),flush=True)


TITLES={34:'FIXED CORE SWEEP',35:'HIP CALIBRATION LIMITS',36:'SEGMENTATION AND CONTOUR',37:'HIP REGRESSION COMPARISON',38:'ADAPTIVE CALIBRATION',39:'THIGH FIELD ISOLATION',40:'UPSTREAM ANATOMICAL REFERENCE'}


def regression(root,p,faces,saved,h):
    import thicc_edit as te
    import sys
    from pathlib import Path
    q,d=run(root,p,faces,saved,hips=h)
    # Archived exact engine file from patch 021, with installed dependencies.
    raw=Path(__file__).with_name('_engine_021.txt').read_bytes(); src=raw.decode('utf-8')
    print('Archived engine 021 SHA256:',hashlib.sha256(raw).hexdigest())
    scope={'__name__':'hip_regression_021','__file__':te.__file__}
    exec(compile(src,'<archived engine 021>','exec'),scope)
    cfg=isolated(saved,h); (root/'thicc.json').write_text(json.dumps(cfg,ensure_ascii=False),encoding='utf-8')
    old_data={}
    def trace(frame,event,arg):
        if frame.f_code is scope['run'].__code__:
            if event=='return':
                for k in ('SKIN','L','skin_tri','reference','P0'):
                    if k in frame.f_locals: old_data[k]=frame.f_locals[k]
            return trace
    previous=sys.gettrace(); sys.settrace(trace)
    try: old=scope['run'](str(root),'dry')
    finally: sys.settrace(previous)
    a=np.asarray(old['preview_positions'],float)
    if a.shape!=q.shape: raise RuntimeError('Vertex counts differ')
    print('021 Skin:',old_data.get('SKIN'),'current Skin:',d['names'])
    print('021 landmarks:',old_data.get('L'),'current:',d['L'])
    print('021 vs current active:',old_data.get('reference',{}).get('active'),d['active'])
    print('021 and current triangle arrays equal:',np.array_equal(old_data.get('skin_tri'),d['sv'][d['tri']]))
    print('021 original positions equal:',np.array_equal(old_data.get('P0'),p))
    compare(a,q,'021 vs current (shared installed dependencies)')
    report_profile(p,a,faces,d,'021'); report_profile(p,q,faces,d,'current')
    view(p,faces,[('Original',p),('021 archived engine',a),('Current engine',q)],d,'37 | Regression comparison')
