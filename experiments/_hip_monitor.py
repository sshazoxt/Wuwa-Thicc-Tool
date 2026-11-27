"""Instrumentation of the installed engine via explicit production observers."""
import contextlib
import hashlib
import inspect
import io
import json
import textwrap
import numpy as np
from preview_no_seam_guard import sandbox, geometry, load_cfg, ids_for


def insert(src, anchor, addition, before=False):
    if src.count(anchor) != 1:
        raise RuntimeError('Unsupported engine: expected exactly one anchor: '+anchor)
    return src.replace(anchor, addition+'\n'+anchor if before else anchor+'\n'+addition, 1)


def clone(te, monitor, outline_factory=None):
    """Compatibility name: use production observers, not a source clone."""
    def observe(event,d):
        if event=='hip_target_initial': monitor.target(d,'initial')
        elif event=='hip_target_final': monitor.target(d,'final')
        elif event=='hip_iteration_before': monitor.iteration(d,'before update')
        elif event=='hip_iteration_clipped': monitor.iteration(d,'clipped')
        elif event=='hip_iteration_smoothed': monitor.iteration(d,'smoothed')
        elif event=='calibrated': monitor.calibrated(d)
        elif event=='before_field': monitor.begin_field(d)
        elif event=='after_field': monitor.end_field()
    def run(mod,mode):
        return te.run(mod,mode,observer=observe,field_observer=monitor.field,outline_factory=outline_factory)
    print('Engine source SHA256:',hashlib.sha256(inspect.getsource(te.run).encode()).hexdigest())
    from morphology.calibration import calibrate
    print('Calibration source SHA256:',hashlib.sha256(inspect.getsource(calibrate).encode()).hexdigest())
    return run


class Monitor:
    def __init__(self):
        self.targets={}; self.iterations={}; self.fields={}; self.collect=False
    def target(self,d,label):
        self.targets[label]={k:np.array(d[k],copy=True) for k in ('zs','tgt','env','T0','original_outline')}
        if 'natural' in d: self.targets[label]['natural']=d['natural'].copy()
        if 'peak' in d: self.targets[label]['peak']=float(d['peak'])
    def iteration(self,d,label):
        r=self.iterations.setdefault(int(d['it']),{})
        r[label]=d['Hc'].copy()
        if label=='before update':
            r['grow']=d['grow'].copy(); r['err']=d['err'].copy()
            r['raw update']=d['Hc']+1.3*d['env']*d['err']
    def calibrated(self,d):
        self.sc=d['sc']; self.zs=d['zs'].copy(); self.hc=d['Hc'].copy()
        self.landmarks=dict(d['L']); self.ref_points=d['PRs'].copy(); self.tri=d['tri_l'].copy()
        self.before_round=self.sc.field_ref(*self.ref_points.T)[0]
        self.actual=d['outline'](self.ref_points+np.column_stack((self.before_round,np.zeros((len(self.before_round),2)))))
        self.parts=list(d['SKIN']); self.active=list(d['reference']['active'])
        self.coupled=d['coupled']; self.relative=d['relative']
        self.amounts=dict(d['amounts'])
    def begin_field(self,d):
        self.p=d['P0'].copy(); self.allow=d['allow'].copy(); self.collect=True
    def end_field(self): self.collect=False
    def field(self,label,d):
        if not self.collect: return
        self.fields[label]=np.column_stack((d['dx'],d['dy'],np.zeros(len(d['dx']))))*d['self'].s
        if label=='hips' and 'hip_amount' in d:
            self.hip_terms={k:np.array(d[k],copy=True) for k in ('wr_hip','hip_amount','lateral','depth','pz')}


def config(te,cfg):
    c=dict(cfg); amounts=dict(te.PRESETS[c.get('preset',te.DEFAULT_CFG['preset'])]); amounts.update(c.get('amounts',{}))
    c['amounts']={k:(amounts[k] if k=='hips' else 0.) for k in ('hips','butt','thighs','calves')}
    c['seam_guard']=False
    c['morphology_engine']='Legacy'
    return c


def run_quiet(run,root):
    log=io.StringIO()
    try:
        with contextlib.redirect_stdout(log): result=run(str(root),'dry')
    except BaseException:
        print(log.getvalue()[-16000:]); raise
    for ln in log.getvalue().splitlines():
        if any(t in ln for t in ('hip calibration:', 'Hip center','Hip reference Z','rounding:','Field mode:','landmarks:','frame: lateral scale')): print(ln)
    if not isinstance(result,dict) or 'preview_positions' not in result: raise RuntimeError('Preview did not complete')
    return np.asarray(result['preview_positions'],float)


def capture(root, verify=False):
    import thicc_edit as te
    cfg=config(te,load_cfg(root)); print('Experimental settings:',cfg['amounts'],'Seam Guard OFF')
    (root/'thicc.json').write_text(json.dumps(cfg,ensure_ascii=False),encoding='utf-8')
    mon=Monitor(); cloned=clone(te,mon)
    if verify:
        print('Running original engine for equivalence...',flush=True)
        base=run_quiet(te.run,root)
        (root/'thicc.json').write_text(json.dumps(cfg,ensure_ascii=False),encoding='utf-8')
    print('Running instrumented clone...',flush=True)
    q=run_quiet(cloned,root)
    if verify:
        delta=np.max(np.abs(base-q)); print('Clone vs original max coordinate difference (cm):',delta)
        if not np.allclose(base,q,atol=1e-6,rtol=0): raise RuntimeError('Clone differs from original; discard diagnostic')
    if not mon.fields or len(mon.iterations)!=8: raise RuntimeError('Incomplete monitoring')
    print('Amounts:',mon.amounts,'coupled:',mon.coupled,'relative:',mon.relative,'scale:',mon.sc.s)
    print('Landmarks:',mon.landmarks)
    return mon,q


def inverse_z(mon,z):
    # Invert the actual monotone mapping by interpolation over a dense model grid.
    grid=np.linspace(0,mon.landmarks['waist']+40,20001); mapped=mon.sc.zmap(grid)
    if np.any(np.diff(mapped)<=0): raise RuntimeError('Nonmonotone mapping')
    return np.interp(z,mapped,grid,left=np.nan,right=np.nan)


def profile(mon):
    import thicc_edit as te
    a=mon.targets['initial']; b=mon.targets['final']; z=mon.zs
    print('\n===== HIP PROFILE / REFERENCE AND MODEL COORDINATES =====')
    print('Widths and growth in reference cm; Zmodel in model cm. Outer=max filtered contour, chosen=torso_half.')
    print('Zref Zmodel | base chosen outer gap_max points | target_initial target_final env Hc | actual growth residual | outer_final gap_final points_final')
    tri=mon.ref_points[mon.tri]; moved=mon.ref_points.copy(); moved[:,0]+=mon.before_round; tri2=moved[mon.tri]
    for i,(zr,zm) in enumerate(zip(z,inverse_z(mon,z))):
        c=np.sort(np.abs(te.contour(tri,zr)[:,0])); c=c[c<26.]
        cc=np.abs(te.contour(tri2,zr)[:,0]); cc=np.sort(cc[cc<26.])
        outer=c[-1] if len(c) else np.nan; gap=np.max(np.diff(c)) if len(c)>1 else np.nan
        gain=mon.actual[i]-a['original_outline'][i]
        print(f'{zr:6.1f} {zm:7.2f} | {a["original_outline"][i]:7.3f} {outer:7.3f} {gap:7.3f} {len(c):5d} | {a["tgt"][i]:7.3f} {b["tgt"][i]:7.3f} {b["env"][i]:5.2f} {mon.hc[i]:7.3f} | {gain:7.3f} {b["tgt"][i]-gain:7.3f} | {np.max(cc) if len(cc) else np.nan:7.3f} {np.max(np.diff(cc)) if len(cc)>1 else np.nan:7.3f} {len(cc):5d}')


def iterations(mon):
    print('\n===== CALIBRATION ITERATIONS =====')
    for it,r in mon.iterations.items():
        print(f'Iteration {it+1}: max residual={np.max(np.abs(r["err"])):.4f}; clipping low/high={np.sum(r["raw update"]<-1)}/{np.sum(r["raw update"]>6)}')
        print('Zref | old Hc | growth | error | raw | clipped | smoothed')
        for i,z in enumerate(mon.zs):
            print(f'{z:6.1f} | '+ ' | '.join(f'{r[k][i]:+8.4f}' for k in ('before update','grow','err','raw update','clipped','smoothed')))


def measured(mon,faces):
    names=[n for n in mon.parts if n in mon.active and n in faces]
    if not names: raise RuntimeError('No resolved active Skin parts; cannot compare')
    print('Measured active parts:',names)
    return names,ids_for(faces,names)


def components(mon,faces):
    names,ids=measured(mon,faces); p=mon.p
    print('\n===== FIELD COMPONENTS / MODEL CM =====')
    prev=np.zeros_like(p); terms={}
    for label,a in mon.fields.items():
        terms[label]=a-prev; prev=a
    edges=np.arange(np.floor(mon.landmarks['knee']),np.ceil(mon.landmarks['waist'])+1)
    print('Zmodel | n | '+' | '.join(k+' outward p95' for k in terms)+' | total outward p95 | hip weight p95')
    for lo,hi in zip(edges[:-1],edges[1:]):
        v=ids[(p[ids,2]>=lo)&(p[ids,2]<hi)]
        if not len(v): continue
        s=np.sign(p[v,0]); vals=[np.percentile(a[v,0]*s,95) for a in terms.values()]
        w=np.percentile(mon.hip_terms['wr_hip'][v],95) if hasattr(mon,'hip_terms') else np.nan
        print(f'{lo:5.1f}..{hi:5.1f} | {len(v):5d} | '+' | '.join(f'{x:+7.3f}' for x in vals)+f' | {np.percentile(prev[v,0]*s,95):+7.3f} | {w:6.3f}')
    for name in names:
        tri=faces[name]; ed=np.concatenate((tri[:,[0,1]],tri[:,[1,2]],tri[:,[2,0]])); ed=np.unique(np.sort(ed,axis=1),axis=0)
        dist=np.linalg.norm(p[ed[:,0]]-p[ed[:,1]],axis=1); valid=(dist>1e-5)&(p[ed,2].mean(1)>=mon.landmarks['knee'])&(p[ed,2].mean(1)<=mon.landmarks['waist'])
        if not np.any(valid): continue
        ed=ed[valid]; dist=dist[valid]
        print('Largest lateral displacement gradient per original mesh edge:',name)
        for label,a in mon.fields.items():
            slope=np.abs(a[ed[:,0],0]-a[ed[:,1],0])/dist
            i=int(np.argmax(slope)); print(label,'p99',round(float(np.percentile(slope,99)),4),'max',round(float(slope[i]),4),'at Z',round(float(p[ed[i],2].mean()),3),'edge',ed[i].tolist())
    return terms


def show(mon,faces,q):
    import pyvista as pv
    names,ids=measured(mon,faces); tri=np.concatenate([faces[n] for n in names]); cells=np.column_stack((np.full(len(tri),3),np.searchsorted(ids,tri))).ravel()
    hip=mon.fields['hips']-mon.fields['butt']; values=hip[ids,0]*np.sign(mon.p[ids,0]); lim=max(1e-6,float(np.max(np.abs(values))))
    plot=pv.Plotter(shape=(1,3),window_size=(1500,850),title='Hip field monitor')
    for i,(label,pts) in enumerate([('Original + hip displacement map',mon.p),('Raw hip contribution',mon.p+hip),('Final preview',q)]):
        plot.subplot(0,i); mesh=pv.PolyData(pts[ids],cells); mesh['Hip outward (cm)']=values
        plot.add_mesh(mesh,scalars='Hip outward (cm)',clim=(-lim,lim),cmap='coolwarm'); plot.add_text(label,font_size=11); plot.view_xz(); plot.enable_parallel_projection()
    plot.link_views(); plot.reset_camera(); plot.show()


def main(mode):
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini); mon,q=capture(root,verify=mode=='trace')
        if mode in ('profile','trace'): profile(mon)
        if mode in ('components','trace'): components(mon,faces)
        if mode=='trace': iterations(mon)
        if mode=='visual': components(mon,faces); show(mon,faces,q)
