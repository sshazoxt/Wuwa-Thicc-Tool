"""Experimental contour estimators. No production files are changed."""
import json
import numpy as np
import _hip_monitor as hm
from preview_no_seam_guard import sandbox, geometry, load_cfg

METHODS=('legacy','outer','adaptive','fixed_core','fixed_outer')

def width(c,method):
    c=np.sort(np.asarray(c))
    if len(c)<6: return np.nan
    if method=='outer': return c[-1]
    if method=='adaptive':
        gaps=np.diff(np.unique(c)); positive=gaps[gaps>1e-6]
        limit=max(2.5, 8*np.median(positive)) if len(positive) else 2.5
    else: limit=2.5
    idx=np.flatnonzero(np.diff(c)>limit)
    return c[idx[0]] if len(idx) else c[-1]

def make_outline(contour, original, triangles, zs, method):
    if method == "fixed_core":
        from morphology.calibration import fixed_core_outline
        return fixed_core_outline(original, triangles, zs, contour=contour)
    # The calibration changes X only, so plane/edge intersection ordering is invariant.
    base=[np.abs(contour(original[triangles],z)[:,0]) for z in zs]
    masks=[]
    for c in base:
        m=c<26.
        if method=='fixed_core' and m.sum()>=6:
            m &= c<=width(c[m],'legacy')+1e-8
        masks.append(m)
    def outline(q):
        tri=q[triangles]; out=np.full(len(zs),np.nan)
        for i,z in enumerate(zs):
            c=np.abs(contour(tri,z)[:,0])
            if method.startswith('fixed_'):
                if len(c)!=len(base[i]): raise RuntimeError('Section correspondence changed; fixed contour invalid')
                v=c[masks[i]]
                if len(v)>=6: out[i]=v.max()
            else: out[i]=width(c[c<26.],method)
        return out
    return outline

class SweepMonitor(hm.Monitor):
    def __init__(self): super().__init__(); self.gaps={}
    def iteration(self,d,label):
        super().iteration(d,label)
        if label!='before update': return
        tri=d['Q'][d['tri_l']]; import thicc_edit as te
        rows=[]
        for i,z in enumerate(d['zs']):
            c=np.sort(np.abs(te.contour(tri,z)[:,0])); c=c[c<26.]
            if len(c)<6: continue
            gap=np.max(np.diff(c)); discarded=c[-1]-width(c,'legacy')
            if discarded>1e-7: rows.append((float(z),float(gap),float(discarded)))
        self.gaps[int(d['it'])]=rows

def run_case(root,saved,hips,method):
    import thicc_edit as te
    cfg=hm.config(te,saved); cfg['amounts']['hips']=float(hips)
    (root/'thicc.json').write_text(json.dumps(cfg,ensure_ascii=False),encoding='utf-8')
    print('\n===== HIPS %.3f | %s ====='%(hips,method),flush=True)
    mon=SweepMonitor()
    run=hm.clone(te,mon,outline_factory=lambda p,t,z:make_outline(te.contour,p,t,z,method))
    q=hm.run_quiet(run,root)
    if len(mon.iterations)!=8 or not mon.fields: raise RuntimeError('Incomplete instrumentation')
    target=mon.targets['final']['tgt']; env=mon.targets['final']['env']; residual=target-(mon.actual-mon.targets['initial']['original_outline'])
    valid=np.isfinite(residual)&(env>.5)
    err=float(np.max(abs(residual[valid]))) if valid.any() else float('nan')
    print('Post calibration residual (ref cm):',err)
    for it,r in mon.iterations.items():
        rows=mon.gaps[it]; peak=max(rows,key=lambda x:x[2]) if rows else None
        print('Iteration',it+1,'residual',float(np.max(abs(r['err']))),'legacy gap cuts',len(rows),'largest cut (Zref,gap,lost width)',peak,'clipped',int(np.sum((r['raw update']<-1)|(r['raw update']>6))))
    return mon,q,err

def report(mon):
    a=mon.targets['initial']; b=mon.targets['final']; gain=mon.actual-a['original_outline']; zm=hm.inverse_z(mon,mon.zs)
    print('Zref | Zmodel | baseline | target | actual | error | Hc')
    for i,z in enumerate(mon.zs):
        if b['env'][i]>0 or abs(gain[i])>1e-5:
            print('%6.2f %7.2f | %7.3f %7.3f %7.3f %7.3f %7.3f'%(z,zm[i],a['original_outline'][i],b['tgt'][i],gain[i],b['tgt'][i]-gain[i],mon.hc[i]))

def viewer(p,faces,cases,names,title,view='back'):
    from morphology.viewer import ExperimentViewer
    ExperimentViewer(p,faces,cases,names,title).show(view=view)

def saved_hips(saved):
    import thicc_edit as te
    return hm.config(te,saved)['amounts']['hips']
