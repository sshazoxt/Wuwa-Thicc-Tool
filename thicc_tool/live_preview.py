"""Isolated, disposable live geometry preview. Never writes source mod files."""
from pathlib import Path
import json
import shutil
import sys
import pickle
import os

MESH_FILES=('Position.buf','Position.buf.orig','Vector.buf','Vector.buf.orig','Index.buf','Blend.buf','BlendRemapVertexVG.buf')

def signature(mod,ini):
    paths=[Path(ini),Path(mod)/'thicc.json']+[Path(mod)/'Meshes'/n for n in MESH_FILES]
    result=[]
    for p in paths:
        try:
            st=p.stat(); result.append((str(p),st.st_size,st.st_mtime_ns))
        except FileNotFoundError: result.append((str(p),None,None))
    return tuple(result)

def snapshot(mod,work,ini):
    source=Path(mod); root=Path(work)/'snapshot'; mesh=root/'Meshes'; mesh.mkdir(parents=True)
    for n in MESH_FILES:
        p=source/'Meshes'/n
        if p.is_file(): shutil.copyfile(p,mesh/n)
    for p in (Path(ini),source/'thicc.json',source/'thicc_detection_cache.json'):
        if p.is_file(): shutil.copyfile(p,root/p.name)
    return root

def baseline_key(cfg):
    # Only Belly may change. Preserve every other config value conservatively.
    import thicc_edit as te
    cfg={**te.DEFAULT_CFG, **cfg}
    cfg.pop('belly_morphology',None)
    cfg.pop('waist_morphology',None)  # production does not execute experimental Waist
    return json.dumps(cfg,sort_keys=True,ensure_ascii=False,allow_nan=False)

def capture_baseline(d):
    import numpy as np
    return dict(key=baseline_key(d['cfg']), original=d['P0'],
                base=np.asarray(d['new'],dtype=np.float32).copy(),
                faces={n:d['tris'](n) for n in d['DRAWS']},
                data=dict(L=dict(d['L']),skin=list(d['SKIN']),garments=list(d['GARMENTS']),
                          active=list(d['reference']['active']),allow=d['allow'].copy(),
                          guard=d['guard'].copy(),arm=d['arm_influence'].copy(),H=d['H']))

def store_baseline(path,baseline,mod,ini):
    baseline=dict(baseline,signature=signature(mod,ini))
    path=Path(path); tmp=path.with_suffix('.tmp')
    with tmp.open('wb') as f: pickle.dump(baseline,f,protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp,path)

def cached_belly(path,mod,ini,cfg):
    import numpy as np
    from morphology.belly import apply_belly
    if not path or not Path(path).is_file(): return None
    # Only accepts a cache created in the parent application's own temporary directory.
    with open(path,'rb') as f: b=pickle.load(f)
    if b['signature']!=signature(mod,ini) or b['key']!=baseline_key(cfg): return None
    q,_=apply_belly(b['original'],b['base'],b['faces'],b['data'],cfg.get('belly_morphology',{}))
    return np.asarray(q,dtype=np.float32)

def run(mod,work,cache=None):
    import numpy as np
    import thicc_edit as te
    work=Path(work); cfg=json.loads((work/'request.json').read_text(encoding='utf-8'))
    ini=te.find_ini(mod)
    q=cached_belly(cache,mod,ini,cfg)
    if q is not None:
        print('[Live] Reused production baseline (Belly only).')
        np.save(work/'positions.npy',q,allow_pickle=False); return
    root=snapshot(mod,work,ini)
    # Explicitly disable legacy Waist even if present in an old saved JSON.
    cfg['waist_morphology']={'enabled':False}
    baseline={}
    def observe(event,d):
        if event=='before_belly': baseline.update(capture_baseline(d))
    result=te.run(str(root),'dry',config_override=cfg,positions_only=True,observer=observe)
    if not isinstance(result,dict) or result.get('preview_positions') is None: raise RuntimeError('Preview unavailable')
    np.save(work/'positions.npy',result['preview_positions'],allow_pickle=False)
    if baseline: store_baseline(work/'belly_baseline.pkl',baseline,mod,ini)

if __name__=='__main__': run(*sys.argv[1:])
