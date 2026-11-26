"""Explicit experimental buffer writer. Never invoked by production Apply.
Backups are immutable; current files are checked against the session snapshot.
"""
from pathlib import Path
import hashlib
import os
import tempfile
import numpy as np

FILES=('Position.buf','Vector.buf')

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def snapshot(mod):
    mesh=Path(mod)/'Meshes'
    paths=[mesh/n for n in FILES+('Index.buf',)]
    paths += [mesh/(n+'.orig') for n in FILES]
    if paths[-2].exists()!=paths[-1].exists():
        raise RuntimeError('Incomplete .orig backup pair; restore/check originals before experimenting.')
    return {p.name:digest(p) if p.is_file() else None for p in paths}


def stage(mesh,data):
    fd,name=tempfile.mkstemp(prefix='.thicc-belly-',suffix='.tmp',dir=mesh)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
    except BaseException:
        Path(name).unlink(missing_ok=True); raise
    return Path(name)


def write_buffers(mod, expected, positions, vectors):
    mesh=Path(mod)/'Meshes'
    p=np.asarray(positions,dtype='<f4'); v=np.asarray(vectors)
    if p.ndim!=2 or p.shape[1]!=3 or not np.isfinite(p).all() or v.dtype!=np.int8 or v.shape!=(len(p),8):
        raise ValueError('Invalid output buffers')
    if snapshot(mod)!=expected: raise RuntimeError('Mod buffers changed during this session; reopen Belly Lab.')
    before={n:(mesh/n).read_bytes() for n in FILES}
    if len(before[FILES[0]])!=p.nbytes or len(before[FILES[1]])!=v.nbytes:
        raise ValueError('Output sizes differ from current buffers')
    for n in FILES:
        backup=mesh/(n+'.orig')
        if backup.exists() and backup.stat().st_size!=len(before[n]):
            raise ValueError('Original buffer size mismatch: '+str(backup))
    pending={}; rollback={}; created=[]; replaced=[]
    try:
        for n,data in zip(FILES,(p.tobytes(),v.tobytes())):
            pending[n]=stage(mesh,data); rollback[n]=stage(mesh,before[n])
        if snapshot(mod)!=expected: raise RuntimeError('Mod changed while staging output')
        if expected[FILES[0]+'.orig'] is None:
            for n in FILES:
                target=mesh/(n+'.orig')
                # Exclusive creation: never replace a pre-existing backup.
                with open(target,'xb') as f:
                    created.append(target); f.write(before[n]); f.flush(); os.fsync(f.fileno())
                print('Original backup created:',target,flush=True)
        for n in FILES:
            os.replace(pending[n],mesh/n); replaced.append(n)
    except BaseException:
        errors=[]
        for n in reversed(replaced):
            try: os.replace(rollback[n],mesh/n)
            except OSError as exc: errors.append(str(exc))
        if not errors:
            for target in created: target.unlink(missing_ok=True)
        if errors:
            # Preserve rollback files if recovery itself failed.
            print('ROLLBACK FAILED; recovery files:',rollback,flush=True)
            rollback.clear()
            raise RuntimeError('Rollback failed: '+'; '.join(errors))
        raise
    finally:
        for f in list(pending.values())+list(rollback.values()): f.unlink(missing_ok=True)
    print('Experimental Belly: Position.buf and Vector.buf written.',flush=True)
    return snapshot(mod)


def belly_vectors(base, final, vectors, faces, shading):
    """Keep the production baseline frames, transport only the added Belly delta."""
    from adaptive_normals import surface_frames, unit
    p=np.asarray(base,float); q=np.asarray(final,dtype='<f4').astype(float)
    vec=np.asarray(vectors,dtype=np.int8).copy()
    if vec.shape!=(len(p),8): raise ValueError('Missing or invalid baseline Vector.buf')
    moved=np.linalg.norm(q-p,axis=1)>1e-6
    if shading=='Original' or not moved.any(): return vec
    t=unit(vec[:,:3].astype(float)); n=unit(vec[:,4:7].astype(float))
    mode='Geometric' if shading=='Geometric' else 'Adaptive'
    t1,n1,valid=surface_frames(p,q,faces,t,n,moved,mode)
    tok=valid & (np.abs((t*n).sum(1))<.2)
    pack=lambda x:np.clip(np.rint(x*127),-127,127).astype(np.int8)
    vec[tok,:3]=pack(t1[tok]); vec[valid,4:7]=pack(n1[valid])
    return vec
