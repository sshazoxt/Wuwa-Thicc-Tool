"""Thicc Tool 002: weighted automatic suggestions. Never changes geometry."""
import contextlib
import math
import os
import time
import numpy as np
from . import legacy_geometry as lg, skeleton, shape_recognition, surface_evidence
from wwmi_role_evidence import _island_evidence, welded_island_evidence

WEIGHTS = dict(surface=40., stickman=25., welded=12., shape=8., height=6.,
               naming=5., topology=3., vertices=1.)
KNOWN = {0:'front_hair', 1:'back_hair', 2:'face'}

class Quiet:
    def write(self, s): return len(s)
    def flush(self): pass


def classify_part(component_id, evidence, weights=None):
    weights = WEIGHTS if weights is None else weights
    if component_id in KNOWN:
        return dict(role=KNOWN[component_id], fixed=True, score=None, coverage=None, contributions={})
    total = sum(weights.values())
    if total <= 0 or any(not math.isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError('Invalid detection weights')
    contributions = {}
    for k, w in weights.items():
        v = evidence.get(k)
        contributions[k] = None if v is None or not math.isfinite(float(v)) else w * max(-1., min(1., float(v)))
    available = sum(weights[k] for k,v in contributions.items() if v is not None)
    score = sum(v for v in contributions.values() if v is not None)*100/total
    if not available: role, strength = 'unresolved', 'insufficient'
    elif score >= 60: role, strength = 'skin', 'strong'
    elif score >= 40: role, strength = 'skin', 'candidate'
    elif score >= 20: role, strength = 'ambiguous', 'partial'
    elif score <= -20: role, strength = 'garment', 'candidate'
    else: role, strength = 'unresolved', 'insufficient'
    return dict(role=role, fixed=False, score=round(score,3) if available else None,
                strength=strength, coverage=available/total, contributions=contributions)


def evaluate(P, faces, comp, ini, meta, bones_path, load_bones, verbose=False):
    """Use the same validated draw ranges as the main tool; no saved roles enter here."""
    start=time.perf_counter(); N=len(P); names=list(faces)
    V={n:np.unique(t) for n,t in faces.items()}
    body=[n for n in names if comp[n]>=3]; face=[n for n in names if comp[n]==2]
    filtered=face+body
    def union(ns): return np.unique(np.concatenate([V[n] for n in ns])) if ns else np.empty(0,dtype=np.int64)
    def triangles(ns): return np.concatenate([faces[n] for n in ns]) if ns else np.empty((0,3),dtype=np.int64)
    faceids=union(face); filterids=union(filtered)
    H=float(P[faceids,2].max()) if len(faceids) else float(P[filterids,2].max()) if len(filterids) else float(P[:,2].max())
    extent=H-float(P[filterids,2].min()) if len(filterids) else float(np.ptp(P[:,2]))
    info={n:(float(P[V[n],2].min()),float(P[V[n],2].max()),len(V[n])) for n in names}
    print('\n===== WEIGHTED DETECTION 002 =====',flush=True)
    print('Weights:',WEIGHTS,'| face Zmax:',H,'| fixed 0/1/2 excluded')
    raw=[]; evidence={}; details={}
    for n in body:
        lo,hi,nv=info[n]; named=bool(lg.SKIN_RE.search(n)); excluded=bool(lg.NOT_SKIN_RE.search(n) or lg.FREEZE_RE.search(n))
        height=bool(H>0 and lo<.15*H and hi>.70*H)
        if not excluded and (named or (height and nv>3000)): raw.append(n)
        evidence[n]=dict(surface=None,stickman=None,welded=None,shape=None,height=float(height),naming=-1. if excluded else float(named),topology=None,vertices=float(nv>3000))
        details[n]=dict(name_skin=named,excluded_name=excluded,height_match=height,vertices=nv)
    if raw:
        lo=min(info[n][0] for n in raw)
        raw += [n for n in body if n not in raw and info[n][0]<.12*H and info[n][1]>lo-.04*H and info[n][1]<.65*H and not lg.NOT_SKIN_RE.search(n)]
    for n in body:
        e= evidence[n]; d=details[n]; d['raw_skin']=n in raw
        try:
            i,f=_island_evidence(faces[n]); d.update(islands=i,dominant_fraction=f)
            fragmented=i>=12 and f<.35 and len(faces[n])>=100
            d['fragmented']=bool(fragmented)
            # Legacy veto is only a negative vote; no candidate is removed.
            e['topology']=0. if not (n in raw and fragmented) else None
        except Exception as ex: print('[Detection] indexed',n,ex)
        try:
            j,g=welded_island_evidence(P,faces[n]); d.update(welded_islands=j,welded_dominant_fraction=g)
            e['welded']=1. if g>=.90 else .75 if g>=.70 else .25 if g>=.40 else -.50
            if 'fragmented' in d:
                import re
                rescue=d['fragmented'] and j<=2 and g>=.90 and bool(re.search(r'(?:skin|body|nude|basebody)',n,re.I))
                veto=bool(n in raw and d['fragmented'] and not rescue)
                d.update(veto_auto_skin=veto,index_fragmentation_rescued=bool(rescue)); e['topology']=-1. if veto else 0.
        except Exception as ex: print('[Detection] welded',n,ex)
        try:
            sh=shape_recognition.describe(P,faces[n],extent,debug=verbose,vertex_ids=V[n]); label=sh['label']; d['shape']={k:sh[k] for k in ('label','islands','dominant','surface')}; d['shape']['dominant_profile']=sh['profiles'][0] if sh['profiles'] else None
            e['shape']=.5 if label=='candidato volumen inferior' else -.5 if label.startswith('fragmentado') else 0.
        except Exception as ex: print('[Detection] shape',n,ex)
    print('[Detection] Topology and shape finished.',flush=True)
    bi=bw=None; unified=False
    try:
        bi,bw=load_bones(bones_path,N); vg=os.path.join(bones_path,'BlendRemapVertexVG.buf')
        unified=os.path.isfile(vg) and os.path.getsize(vg)==N*bi.shape[1]*2
    except Exception as ex: print('[Detection] Bone data unavailable:',ex)
    def stick(ns, anchor=False):
        v=union(ns); mask=np.zeros(N,bool); mask[v]=True; fm=np.zeros(N,bool); fm[np.intersect1d(faceids,v)]=True
        with contextlib.redirect_stdout(Quiet()):
            r,s=skeleton.label_bones(P,bi,bw,H,vertex_mask=mask,triangles=triangles(ns),face_mask=fm if anchor else None)
        # Individual draws need weights only on their referenced vertices.
        rw=skeleton.region_weights(bi,bw,r) if anchor else skeleton.region_weights(bi[v],bw[v],r); seeds=s['seeds']; C=s['centroid']
        good=all(seeds.get(k) is not None for k in ('foot_r','foot_l','head','hand_r','hand_l'))
        if good:
            good=bool(C[seeds['foot_r'],2]<.2*H and C[seeds['foot_l'],2]<.2*H and C[seeds['head'],2]>.75*H and min(abs(C[seeds['hand_r'],0]),abs(C[seeds['hand_l'],0]))>.08*H and all((rw[k][v] if anchor else rw[k]).sum()>100 for k in ('leg_l','leg_r','arm_l','arm_r')))
        return rw,s,good
    global_st=None
    if bi is not None and H>0:
        for n in body:
            try:
                rw,s,good=stick([n]); fractions={k:float(x.mean()) for k,x in rw.items()}
                details[n].update(stickman_complete=good,stickman_regions=fractions,stickman_seeds=s['seeds']); evidence[n]['stickman']=float(good)
            except Exception as ex: print('[Detection] individual Stickman',n,ex)
        if unified and filtered:
            try: global_st=stick(filtered,True)
            except Exception as ex: print('[Detection] filtered Stickman',ex)
    print('[Detection] Individual Stickman finished. Namespace:', 'global' if unified else 'local/unknown',flush=True)
    scoped_cache = []
    def scoped_bones():
        if unified or bi is None: return bi
        if scoped_cache: return scoped_cache[0]
        vc=np.full(N,-1,dtype=np.int64)
        for n in names:
            if np.any((vc[V[n]]!=-1)&(vc[V[n]]!=comp[n])): raise ValueError('Shared vertices across local namespaces')
            vc[V[n]]=comp[n]
        scoped_cache.append(bi+(vc[:,None]+1)*(int(bi.max())+1))
        return scoped_cache[0]
    def surfaces(ns):
        v=union(ns); t=triangles(ns)
        if global_st and global_st[2]:
            rw=global_st[0]; arm=rw['arm_l']+rw['arm_r']; v=v[arm[v]<.01]; t=t[(arm[t]<.01).all(1)]
        elif bi is not None:
            try: b=scoped_bones()
            except ValueError: b=None
            if b is not None:
                widths=[(lg.band_stats(P,v,z-1,z+1) or (np.nan,))[0] for z in np.arange(.35*H,.47*H,1.)]
                if not np.isfinite(widths).any(): raise ValueError('No thigh reference')
                half=np.nanmax(widths); nb=int(b.max())+1; wsum=np.zeros(nb); wout=np.zeros(nb); cz=np.zeros(nb)
                outside=(np.abs(P[v,0])>1.05*half).astype(float)
                for k in range(b.shape[1]):
                    ids=b[v,k]; weights=bw[v,k]; np.add.at(wsum,ids,weights); np.add.at(wout,ids,weights*outside); np.add.at(cz,ids,weights*P[v,2])
                ok=wsum>1.; wout[ok]/=wsum[ok]; cz[ok]/=wsum[ok]; arm_bone=ok&(wout>.5)&(cz>.45*H)&(cz<.88*H)
                arm=np.sum(np.where(arm_bone[b],bw,0.),axis=1); v=v[arm[v]<.01]; t=t[(arm[t]<.01).all(1)]
        if len(v)<500 or not len(t): raise ValueError('Insufficient reference geometry')
        with contextlib.redirect_stdout(Quiet()): L=lg.measure(P,v,H,t)
        if not all(np.isfinite(x) for x in L.values()) or not L['ankle']<L['knee']<L['crotch']<L['waist']: raise ValueError('Invalid reference landmarks')
        try: b=scoped_bones(); w=bw; u=unified
        except ValueError: b=w=None; u=False
        if b is None: b=np.zeros((N,1),dtype=np.int64); w=np.zeros((N,1)); u=False
        ds=[(n,faces[n],'unclassified') for n in body]
        with contextlib.redirect_stdout(Quiet()): out=surface_evidence.calculate(P,ds,L,b,w,u,ini,meta,independent=True,debug=verbose)
        return out or {},L
    all_surface={}; raw_surface={}
    for label,ns in [('all',body),('raw',raw)]:
        if not ns: continue
        if label=='raw' and not verbose and all(all_surface.get(n) is not None for n in body):
            print('[Detection] Surface raw skipped: all draws have ALL evidence.',flush=True)
            continue
        if label=='raw' and set(ns)==set(body) and all_surface:
            raw_surface=all_surface; continue
        try:
            out,L=surfaces(ns)
            print('[Detection] Surface',label,'reference:',ns,'landmarks:',L,flush=True)
            if label=='all': all_surface=out
            else: raw_surface=out
        except Exception as ex: print('[Detection] Surface',label,'unavailable:',ex,flush=True)
    final={}
    for n in names:
        if n in evidence:
            e=evidence[n]; d=details[n]; a=all_surface.get(n); b=raw_surface.get(n); s=a if a is not None else b
            d.update(surface_all=a,surface_raw=b,surface_source='all' if a is not None else 'raw' if b is not None else None)
            if s is not None:
                label,an,ac=s
                e['surface']=1. if label=='skin candidate' else -1. if label=='non-anatomical candidate' else .25 if an>0 else 0.
            f=classify_part(comp[n],e); f.update(d); f['normalized_evidence']=e
        else: f=classify_part(comp[n],{})
        final[n]=f
        print('%s | weighted=%s | score=%s | coverage=%s | contributions=%s' % (n,f['role'],f['score'],f['coverage'],f['contributions']))
        if n in evidence:
            print('  raw=%s veto=%s | indexed=%s/%s welded=%s/%s | shape=%s | stickman_complete=%s | surface_all=%s surface_raw=%s source=%s' % (f.get('raw_skin'),f.get('veto_auto_skin'),f.get('islands'),f.get('dominant_fraction'),f.get('welded_islands'),f.get('welded_dominant_fraction'),f.get('shape',{}).get('label'),f.get('stickman_complete'),f.get('surface_all'),f.get('surface_raw'),f.get('surface_source')))
    print('===== END WEIGHTED DETECTION | %.3fs =====\n'%(time.perf_counter()-start),flush=True)
    return final
