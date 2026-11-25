"""Shared experimental helpers; production source is never written."""
import inspect
import json
from contextlib import contextmanager
import numpy as np
from preview_no_seam_guard import load_cfg, ids_for, bands

@contextmanager
def patched_run(replacements):
    import thicc_edit as te
    original=te.run
    src=inspect.getsource(original)
    for old,new in replacements:
        if src.count(old)!=1:
            raise RuntimeError('Unsupported engine anchor: '+old)
        src=src.replace(old,new,1)
    scope=dict(original.__globals__)
    exec(compile(src,'<experiment-only engine>','exec'),scope)
    te.run=scope['run']
    try: yield te
    finally: te.run=original

def run_case(root, cfg, label, replacements=()):
    print('\n===== CASE: '+label+' =====',flush=True)
    cfg=dict(cfg); cfg['seam_guard']=False
    (root/'thicc.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    # Capture final field and measured references from the real pipeline.
    capture={}
    import sys
    with patched_run(replacements) as te:
        def trace(frame,event,arg):
            if frame.f_code is te.run.__code__:
                if event=='return' and isinstance(arg,dict):
                    d=frame.f_locals
                    for k in ('SKIN','L','reference','skin_tri','anatomy_names','zs','tgt','original_outline','PRs','sc','outline'):
                        if k in d: capture[k]=d[k]
                return trace
        previous=sys.gettrace(); sys.settrace(trace)
        try: result=te.run(str(root),'dry')
        finally: sys.settrace(previous)
    if not isinstance(result,dict) or 'preview_positions' not in result or 'SKIN' not in capture:
        raise RuntimeError('Engine did not complete preview.')
    return np.asarray(result['preview_positions'],dtype=float),capture

def active_skin(d):
    active=set(d['reference']['active'])
    return [n for n in d['SKIN'] if n in active] or list(d['SKIN'])

def report(p,faces,cases,d):
    names=active_skin(d); ids=ids_for(faces,names)
    print('\n===== FIXED REFERENCE MEASUREMENT =====')
    print('Measured parts:',names)
    print('Z range | n | '+ ' | '.join(label+' p95 lateral gain' for label,q in cases))
    for a,b,v in bands(p,ids,d['L']):
        x=np.percentile(abs(p[v,0]),95)
        print('%6.2f..%6.2f | %5d | '%(a,b,len(v))+' | '.join('%+.4f'%(np.percentile(abs(q[v,0]),95)-x) for _,q in cases))
    for label,q in cases:
        print(label,'max displacement:',np.linalg.norm(q[ids]-p[ids],axis=1).max())

def viewer(p,faces,cases,d,columns=3):
    import pyvista as pv
    names=active_skin(d); tri=np.concatenate([faces[n] for n in names]); ids=np.unique(tri)
    cells=np.column_stack([np.full(len(tri),3),np.searchsorted(ids,tri)]).ravel()
    cols=min(columns,len(cases)); rows=(len(cases)+cols-1)//cols
    plot=pv.Plotter(shape=(rows,cols),window_size=(1500,900),title='Thicc Tool morphology experiment')
    for i,(label,q) in enumerate(cases):
        plot.subplot(i//cols,i%cols); plot.add_mesh(pv.PolyData(q[ids],cells),color='#b7cce0'); plot.add_text(label,font_size=12); plot.view_xz(); plot.enable_parallel_projection()
    plot.link_views(); plot.reset_camera(); plot.show()

if __name__=='__main__':
    print('Shared experiment helper. Select one of the named A/B experiment scripts instead.')
