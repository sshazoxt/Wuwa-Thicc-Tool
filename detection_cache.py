"""004: content addressed detection and complete diagnostic snapshots (JSON only)."""
import ast
import contextlib
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import numpy as np
import scipy

ROOT = Path(__file__).resolve().parent
SCHEMA = 1
VERSION = '1.0.0'
FORCE = False
LAST_SOURCE = 'real'
CACHEABLE = True


def plain(x):
    if isinstance(x, np.ndarray): return plain(x.tolist())
    if isinstance(x, np.generic): return plain(x.item())
    if isinstance(x, float) and not math.isfinite(x): return None
    if isinstance(x, dict): return {str(k): plain(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)): return [plain(v) for v in x]
    return x


def canonical(x):
    return json.dumps(plain(x), sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(items):
    h=hashlib.sha256()
    for name,value in items:
        h.update(canonical(name)); h.update(b'\0')
        if isinstance(value,Path):
            if value.is_file():
                h.update(b'file\0')
                with value.open('rb') as f:
                    for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
            else: h.update(b'missing\0')
        else: h.update(canonical(value))
        h.update(b'\0')
    return h.hexdigest()


def hashes(mod,ini):
    mod=Path(mod); mesh=mod/'Meshes'; pos=mesh/'Position.buf.orig'
    if not pos.is_file(): pos=mesh/'Position.buf'
    env=(SCHEMA,sys.version,np.__version__,scipy.__version__)
    # AST separation: changing weights/classify_part alone need not rerun detectors.
    fusion=ast.parse((ROOT/'detection002/fusion.py').read_text(encoding='utf-8'))
    cls=[]; det=[]
    for node in fusion.body:
        is_cls=isinstance(node,ast.FunctionDef) and node.name=='classify_part' or isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='WEIGHTS' for t in node.targets)
        (cls if is_cls else det).append(ast.dump(node,include_attributes=False))
    main=ast.parse((ROOT/'thicc_edit.py').read_text(encoding='utf-8'))
    loader=[ast.dump(n,include_attributes=False) for n in ast.walk(main) if isinstance(n,ast.FunctionDef) and n.name in ('find_ini','parse_draws','load_bones','verts','tris') or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DRAW_RE' for t in n.targets)]
    detectors=[('env',env),('fusion',det),('loader',loader)]
    detectors += [(p.name,p) for p in sorted((ROOT/'detection002').glob('*.py')) if p.name!='fusion.py']
    detectors += [(n,ROOT/n) for n in ('wwmi_role_evidence.py','wwmi_structure.py','detection_cache.py')]
    # Full snapshot includes all engine modules, not UI or viewer.
    engine=[('env',env)]+[(p.name,p) for p in sorted(ROOT.glob('*.py')) if p.name!='viewer3d.py']
    return dict(detectors_hash=digest(detectors),classifier_hash=digest([('classifier',cls)]),
                mesh_hash=digest([('ini',Path(ini)),('ini_name',Path(ini).name),('position',pos)]+[(n,mesh/n) for n in ('Index.buf','Blend.buf','BlendRemapVertexVG.buf')]),
                analysis_hash=digest(engine))


def read(path):
    try:
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        if data['schema']==SCHEMA and isinstance(data['payload'],dict) and data['integrity']==digest([('payload',data['payload'])]): return data['payload']
    except (OSError,ValueError,TypeError,KeyError,AttributeError): pass
    return {}


def write(path,payload):
    tmp=None
    try:
        payload=plain(payload)
        wrapper=dict(schema=SCHEMA,integrity=digest([('payload',payload)]),payload=payload)
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=Path(path).parent,delete=False) as f:
            tmp=f.name; json.dump(wrapper,f,ensure_ascii=False,allow_nan=False); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path); tmp=None
        return True
    except (OSError,ValueError,TypeError) as e:
        print('[Cache] Cannot save:',e); return False
    finally:
        if tmp:
            try: os.unlink(tmp)
            except OSError: pass


class Tee:
    def __init__(self,stream): self.stream=stream; self.buffer=io.StringIO()
    def write(self,s): self.buffer.write(s); return self.stream.write(s)
    def flush(self): self.stream.flush()
    def __getattr__(self,k): return getattr(self.stream,k)


def detection(P,faces,comp,ini,meta,bones_path,load_bones):
    global LAST_SOURCE,CACHEABLE
    from detection002.fusion import evaluate,classify_part
    mod=Path(ini).parent; path=mod/'thicc_detection_cache.json'; start=time.perf_counter()
    keys=hashes(mod,ini); old=read(path) if not FORCE else {}
    valid=all(old.get(k)==keys[k] for k in ('detectors_hash','mesh_hash')) and set(old.get('parts',{}))==set(faces)
    if valid:
        parts=old['parts']; same=old.get('classifier_hash')==keys['classifier_hash']
        if not same:
            for n,part in parts.items():
                part.update(classify_part(comp[n],part.get('normalized_evidence',{})))
            print('[Cache] Detector evidence HIT; classifier changed. Recomputed weights.')
            # Replay raw report with explicit superseding scores, not stale scores silently.
            buf=io.StringIO()
            buf.write('===== UPDATED WEIGHTED CLASSIFICATION =====\n')
            for n,p in parts.items(): print(n,p['role'],p['score'],p['contributions'],file=buf)
            # Keep original detector diagnostics, explicitly identify old score lines.
            raw=old.get('raw_console',old.get('console',''))
            report='[Cache] Original detector report (historical weighted scores below; see updated classification at end).\n'+raw+buf.getvalue()
            print(report,end='')
            old.update(keys,parts=parts,console=report,raw_console=raw); write(path,old)
            LAST_SOURCE='reclassified'
        else:
            print('[Cache] Detection HIT — use Analyze > Force analyze to rebuild.')
            print(old.get('console',''),end=''); LAST_SOURCE='detection_cache'
        print('[Cache] Detection load %.3fs; original %.3fs'%(time.perf_counter()-start,old.get('seconds',0)))
        return parts
    print('[Cache] Detection MISS:', 'forced' if FORCE else 'missing, changed or invalid')
    tee=Tee(sys.stdout)
    with contextlib.redirect_stdout(tee): parts=evaluate(P,faces,comp,ini,meta,bones_path,load_bones)
    console=tee.buffer.getvalue(); seconds=time.perf_counter()-start
    LAST_SOURCE='real'
    unexpected=any(line.startswith(('[Detection] indexed ', '[Detection] welded ', '[Detection] shape ', '[Detection] individual Stickman ')) for line in console.splitlines())
    CACHEABLE=not unexpected
    if unexpected:
        print('[Cache] Detector errors reported; incomplete evidence will not be saved as a reusable snapshot.')
    elif hashes(mod,ini)==keys:
        write(path,dict(**keys,parts=parts,console=console,seconds=seconds,created_at=time.time(),detection_version=VERSION))
    else:
        CACHEABLE=False
        print('[Cache] Inputs changed during detection; snapshot not saved.')
    return parts


def diagnose(mod,run,find_ini,force=False):
    global FORCE,LAST_SOURCE,CACHEABLE
    FORCE=force; LAST_SOURCE='real'; CACHEABLE=True; start=time.perf_counter(); mod=Path(mod).resolve(); ini=find_ini(str(mod)); path=mod/'thicc_analysis_cache.json'
    def key():
        h=hashes(mod,find_ini(str(mod)))
        cfg=mod/'thicc.json'
        h['config_hash']=digest([('cfg',json.loads(cfg.read_text(encoding='utf-8')) if cfg.is_file() else {})])
        h['mod_path']=str(mod)
        return h
    keys=key(); old=read(path) if not force else {}
    result=old.get('result')
    if old.get('keys')==keys and isinstance(result,dict) and all(k in result for k in ('parts','cfg','landmarks','natural','draw_meta','role_evidence','ready')) and isinstance(old.get('console'),str):
        print('[Cache] FULL HIT — complete analysis loaded. Use Analyze > Force analyze to rebuild.',flush=True)
        print(old['console'],end=''); result['_cache']=dict(source='full_cache',seconds=time.perf_counter()-start,original_seconds=old.get('seconds',0)); return result
    print('[Cache] Full analysis MISS:', 'forced' if force else 'missing, changed or invalid',flush=True)
    tee=Tee(sys.stdout)
    with contextlib.redirect_stdout(tee), contextlib.redirect_stderr(tee): result=run(str(mod),'diagnose')
    seconds=time.perf_counter()-start
    if isinstance(result,dict):
        if not CACHEABLE:
            print('[Cache] Full snapshot not saved because detector errors were reported.')
        elif key()==keys:
            write(path,dict(keys=keys,result=result,console=tee.buffer.getvalue(),seconds=seconds,created_at=time.time(),detection_version=VERSION))
        else: print('[Cache] Inputs changed during analysis; full snapshot not saved.')
        result['_cache']=dict(source=LAST_SOURCE,seconds=seconds,original_seconds=seconds)
    return result
