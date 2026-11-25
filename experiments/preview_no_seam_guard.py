"""Compare the production dry-run with and without Seam Guard, in a private copy."""
import os
import sys
import json
import shutil
import tempfile
import inspect
from pathlib import Path
from contextlib import contextmanager
import numpy as np


def source():
    import thicc_edit as te
    mod = Path(os.environ['THICC_MOD_DIR']).resolve()
    if not (mod/'Meshes'/'Position.buf').is_file():
        raise ValueError('Select an individual mod with Meshes/Position.buf first.')
    ini = Path(te.find_ini(str(mod)))
    if not (mod/'thicc.json').is_file():
        raise ValueError('Save the desired roles and morphology settings in Thicc Tool first.')
    return mod, ini


@contextmanager
def sandbox():
    mod, ini = source()
    with tempfile.TemporaryDirectory(prefix='thicc-experiment-model-') as folder:
        root = Path(folder)
        shutil.copytree(mod/'Meshes', root/'Meshes')
        for p in (ini, mod/'thicc.json', mod/'thicc_detection_cache.json'):
            if p.is_file():
                shutil.copy2(p, root/p.name)
        print('Private working copy:', root, flush=True)
        print('Using SAVED settings, not unsaved GUI controls.', flush=True)
        print('Saved seam_guard:', load_cfg(root).get('seam_guard', True), flush=True)
        yield root, ini.name


def geometry(root, ini):
    import thicc_edit as te
    meta = {}; comp = {}
    draws = te.parse_draws(str(root/ini), comp, meta)
    mesh = root/'Meshes'
    orig = mesh/'Position.buf.orig'
    if not orig.exists():
        print('WARNING: original backup absent; current positions are the engine baseline.')
        orig = mesh/'Position.buf'
    p = np.fromfile(orig, np.float32).reshape(-1,3).astype(np.float64)
    ix = np.fromfile(mesh/'Index.buf', np.uint32)
    faces = {}
    for n,(s,c) in draws.items():
        fields=meta[n]['draw'].split(','); base=int(fields[2]) if len(fields)>2 else 0
        if s<0 or c<0 or c%3 or s+c>len(ix): raise ValueError('Invalid draw: '+n)
        t=ix[s:s+c].astype(np.int64).reshape(-1,3)+base
        if t.size and (t.min()<0 or t.max()>=len(p)): raise ValueError('Invalid vertex: '+n)
        faces[n]=t
    return p, faces


def load_cfg(root):
    return json.loads((root/'thicc.json').read_text(encoding='utf-8'))


def run_preview(root, enabled, stages=False):
    import thicc_edit as te
    cfg=load_cfg(root); cfg['seam_guard']=enabled
    (root/'thicc.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    print('\n===== DRY RUN / SEAM GUARD %s ====='%('ON' if enabled else 'OFF'),flush=True)
    captures={}; details={}
    # Trace only the production run frame, at unique source statements. No edits or replacement formulas.
    src,start=inspect.getsourcelines(te.run)
    anchors={
        'guard input':'dx, dy = fdx * allow * guard, fdy * allow * guard',
        'after field':'sqd = np.ones(N)',
        'after legacy fill':'waist = cfg.get("waist_morphology", {})',
        'after waist':'if cfg.get("displacement_smoothing", False):',
        'after smoothing':'if cfg.get("advanced_clothing", False):',
        'after clothing':'if reconstructed_fill:',
        'after inner thigh':'reg = cfg.get("final_regularization", {})',
        'after regularization':'from anatomical_transition import blend_at_arm_boundary',
        'after arm fade':'arm_locked = arm_influence >= 0.01',
        'after arm lock':'dx, dy = (new-P0)[:,0], (new-P0)[:,1]',
    }
    locations={}
    for name,anchor in anchors.items():
        found=[start+i for i,line in enumerate(src) if line.strip()==anchor]
        if name=='after arm lock': found=[x for x in found if x>locations_inv(locations,'after arm fade')]
        if len(found)!=1: raise RuntimeError('Unsupported engine layout for stage: '+name+' (matches=%d)'%len(found))
        locations[found[0]]=name
    def local(frame,event,arg):
        if event=='line' and frame.f_lineno in locations:
            name=locations[frame.f_lineno]; d=frame.f_locals
            if name=='guard input':
                details.update(skin=list(d['SKIN']), frozen=sorted(d['freeze']), active=list(d['reference']['active']),
                               landmarks=dict(d['L']), guard=d['guard'].copy(), allow=d['allow'].copy(), H=d['H'])
                if stages:
                    raw=np.stack([d['fdx']*d['allow'],d['fdy']*d['allow'],np.zeros(len(d['P0']))],1)
                    captures['before guard']=d['P0']+raw
            elif stages:
                captures[name]=d['new'].copy()
        return local
    def global_trace(frame,event,arg):
        return local if event=='call' and frame.f_code is te.run.__code__ else None
    previous=sys.gettrace(); sys.settrace(global_trace)
    try:
        result=te.run(str(root),'dry')
    finally:
        sys.settrace(previous)
    if not details or not isinstance(result,dict) or 'preview_positions' not in result:
        raise RuntimeError('No complete experimental preview was produced.')
    final=result['preview_positions'].astype(np.float64)
    if stages: captures['final']=final
    return final,details,captures


def locations_inv(locations,name):
    return next(k for k,v in locations.items() if v==name)


def ids_for(faces,names):
    arrays=[faces[n].ravel() for n in names if n in faces and faces[n].size]
    return np.unique(np.concatenate(arrays)) if arrays else np.empty(0,dtype=np.int64)


def bands(p,ids,landmarks):
    low,high=landmarks['knee'],landmarks['waist']
    edges=np.linspace(low,high,17)
    for a,b in zip(edges[:-1],edges[1:]):
        v=ids[(p[ids,2]>=a)&(p[ids,2]<b)]
        if len(v): yield a,b,v


def compare(p,on,off,details,faces):
    ids=ids_for(faces,details['skin']); delta=np.linalg.norm(off-on,axis=1)
    print('\n===== SEAM GUARD A/B =====')
    print('Skin parts:',details['skin']); print('Frozen parts:',details['frozen'])
    print('ON and OFF are explicit experimental overrides; all other saved settings remain unchanged.')
    print('Protected moving vertices:',np.count_nonzero((details['guard']<1)&(details['allow']>0)))
    print('Skin changed > 0.01 cm:',np.count_nonzero(delta[ids]>.01),'/',len(ids))
    print('Z range | n | original / ON / OFF lateral p95 (cm) | max A/B delta | protected %')
    for a,b,v in bands(p,ids,details['landmarks']):
        w=[np.percentile(np.abs(q[v,0]),95) for q in (p,on,off)]
        print('%6.2f..%6.2f | %6d | %7.3f %7.3f %7.3f | %7.3f | %5.1f'%(a,b,len(v),*w,delta[v].max(),100*np.mean(details['guard'][v]<1)))
    rank=[]
    for n,t in faces.items():
        v=np.unique(t); d=delta[v]
        if len(d) and d.max()>.01: rank.append((d.max(),int(np.count_nonzero(d>.01)),n))
    print('Most affected draws (max cm / changed vertices):')
    for m,c,n in sorted(rank,reverse=True)[:15]: print('%8.3f %7d %s'%(m,c,n))


def viewer(p,on,off,faces,details):
    import pyvista as pv
    names=[n for n in details['skin'] if n in details['active']]
    if not names: names=details['skin']; print('WARNING: no active skin resolved; showing all Skin.')
    print('Viewer parts:',names)
    tri=np.concatenate([faces[n] for n in names if len(faces[n])]); ids=np.unique(tri)
    local=np.searchsorted(ids,tri); cells=np.column_stack([np.full(len(local),3),local]).ravel()
    plot=pv.Plotter(shape=(1,2),window_size=(1500,850),title='Thicc Tool Experiment - Seam Guard A/B')
    for i,(q,label) in enumerate(((on,'Seam Guard ON'),(off,'Seam Guard OFF'))):
        plot.subplot(0,i)
        plot.add_mesh(pv.PolyData(q[ids],cells),color='#e5a29a',show_edges=False)
        plot.add_text(label,font_size=14)
        plot.view_xz(); plot.enable_parallel_projection()
    plot.link_views(); plot.reset_camera()
    print('Close the separate 3D window to finish. Both cameras are linked.',flush=True)
    plot.show()


def main():
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini)
        on,d,_=run_preview(root,True)
        off,_,_=run_preview(root,False)
        compare(p,on,off,d,faces)
        viewer(p,on,off,faces,d)

if __name__=='__main__': main()
