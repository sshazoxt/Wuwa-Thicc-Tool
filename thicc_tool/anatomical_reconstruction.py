"""Experimental, read-only default-state reconstruction and ARF diagnostics.
Returns recovery candidates; the caller owns effective roles and anatomy.
"""
import ast
import operator
import re
import time
import contextlib
import io
import numpy as np

FULL_BODY = 'Full Body (virtual)'
VAR = re.compile(r'\$[\w\\.]+', re.I)
ASSIGN = re.compile(r'^(?:(?:global|persist|local|post)\s+)*(\$[\w\\.]+)\s*=\s*(.+)$', re.I)
UNKNOWN = object()
OPS = {ast.Add:operator.add, ast.Sub:operator.sub, ast.Mult:operator.mul, ast.Div:operator.truediv, ast.Mod:operator.mod, ast.Eq:operator.eq, ast.NotEq:operator.ne, ast.Lt:operator.lt, ast.LtE:operator.le, ast.Gt:operator.gt, ast.GtE:operator.ge}

def expression(text, env):
    """Restricted scalar expression evaluator; no eval, calls or external access."""
    text=text.strip()
    # Known WWMI render readiness guard (assumed ready for offline reconstruction).
    if re.fullmatch(r'ResourceMergedSkeleton\s*!==\s*null',text,re.I): return True
    names={}
    def sub(m):
        key='v'+str(len(names)); names[key]=env.get(m.group().lower(),UNKNOWN); return key
    text=VAR.sub(sub,text).replace('&&',' and ').replace('||',' or ')
    text=re.sub(r'!(?!=)',' not ',text).strip()
    def walk(n):
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float,bool)): return n.value
        if isinstance(n,ast.Name): return names.get(n.id,UNKNOWN)
        if isinstance(n,ast.UnaryOp):
            a=walk(n.operand)
            if a is UNKNOWN:return a
            if isinstance(n.op,ast.Not):return not a
            if isinstance(n.op,ast.USub):return -a
            if isinstance(n.op,ast.UAdd):return +a
        if isinstance(n,ast.BoolOp):
            a=[walk(x) for x in n.values]; known=[bool(x) for x in a if x is not UNKNOWN]
            if isinstance(n.op,ast.And):return False if False in known else UNKNOWN if UNKNOWN in a else True
            return True if True in known else UNKNOWN if UNKNOWN in a else False
        if isinstance(n,ast.BinOp) and type(n.op) in OPS:
            a,b=walk(n.left),walk(n.right);return UNKNOWN if a is UNKNOWN or b is UNKNOWN else OPS[type(n.op)](a,b)
        if isinstance(n,ast.Compare):
            a=walk(n.left); unknown=False
            for op,child in zip(n.ops,n.comparators):
                b=walk(child)
                if type(op) not in OPS:return UNKNOWN
                if a is UNKNOWN or b is UNKNOWN:unknown=True
                elif not OPS[type(op)](a,b):return False
                a=b
            return UNKNOWN if unknown else True
        return UNKNOWN
    try:return walk(ast.parse(text,mode='eval').body)
    except (SyntaxError,ValueError,TypeError,ArithmeticError,RecursionError):return UNKNOWN

def tri(v):return UNKNOWN if v is UNKNOWN else bool(v)
def both(a,b):return False if a is False or b is False else UNKNOWN if a is UNKNOWN or b is UNKNOWN else True

def sections(ini):
    out=[]; current=None
    with open(ini,encoding='utf-8-sig',errors='replace') as f:
        for i,line in enumerate(f,1):
            s=line.split(';',1)[0].strip(); m=re.fullmatch(r'\[([^]]+)\]',s)
            if m:current=[];out.append((m.group(1).lower(),current))
            elif current is not None and s:current.append((i,s))
    return out

def standalone_guards(sec):
    """Only bypass unknown external, whole-component gates in offline reconstruction.
    A local declaration or key binding always takes precedence. Never bypass a
    branch with alternatives or a predicate that mixes local and external state.
    """
    local=set()
    for name,lines in sec:
        if name=='constants' or name.startswith('key'):
            for _,line in lines:
                a=ASSIGN.match(line)
                if a: local.add(a.group(1).lower())
                if name.startswith('key'): local.update(v.lower() for v in VAR.findall(line))
    result={}
    for name,lines in sec:
        if not re.fullmatch(r'textureoverridecomponent\d+',name): continue
        stack=[]; blocks={}; draws=[]; valid=True
        for lineno,line in lines:
            m=re.match(r'^(if|elif|else|endif)\b\s*(.*)$',line,re.I)
            if m:
                cmd,cond=m.group(1).lower(),m.group(2)
                if cmd=='if':
                    if not stack: blocks[lineno]=[cond,False]
                    stack.append(lineno)
                elif not stack: valid=False; break
                elif cmd=='endif': stack.pop()
                elif len(stack)==1: blocks[stack[0]][1]=True
            elif re.match(r'drawindexed\s*=',line,re.I):
                draws.append(stack[0] if stack else None)
        if not valid or stack or not draws or len(set(draws))!=1 or draws[0] is None: continue
        line=draws[0]; cond,alternatives=blocks[line]
        variables={v.lower() for v in VAR.findall(cond)}
        # Simple external scalar predicate only; no mixed expressions or calls.
        if alternatives or len(variables)!=1 or variables & local: continue
        v=next(iter(variables))
        if not v.startswith('$\\'): continue
        if not re.fullmatch(r'!?\s*'+re.escape(v)+r'(?:\s*(?:==|!=|<=|>=|<|>)\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+))?',cond.strip(),re.I): continue
        result[line]=cond
    return result

def reconstruct(ini,meta):
    """Resolve default constants, Present assignments and component draw guards.
    Unknown expressions do not silently select geometry. Duplicate section names
    are preserved; unsupported render state is reported, not executed.
    """
    sec=sections(ini); by={}
    for name,lines in sec:by.setdefault(name,[]).append(lines)
    guards=standalone_guards(sec)
    env={}; active=set(); uncertain=set(); notes=set(); mapped={int(v['line']):n for n,v in meta.items()}; visited_draws=set()
    def execute(lines,outer=True,depth=0):
        if depth>12:notes.add('CommandList recursion limit');return
        stack=[]; state=outer
        for lineno,s in lines:
            m=re.match(r'^(if|elif|else|endif)\b\s*(.*)$',s,re.I)
            if m:
                cmd,cond=m.group(1).lower(),m.group(2)
                if cmd=='if':
                    v=tri(expression(cond,env)) if state is not False else False
                    if v is UNKNOWN and lineno in guards:
                        v=True; notes.add('Standalone external component guard assumed active: '+guards[lineno])
                    stack.append([state,v]);state=both(state,v)
                elif not stack:notes.add('Unbalanced condition at line '+str(lineno))
                elif cmd=='endif':state=stack.pop()[0]
                else:
                    parent,taken=stack[-1]; remaining=UNKNOWN if taken is UNKNOWN else not taken
                    v=True if cmd=='else' else tri(expression(cond,env)) if parent is not False and remaining is not False else False
                    state=both(parent,both(remaining,v))
                    stack[-1][1]=True if taken is True or v is True else UNKNOWN if taken is UNKNOWN or v is UNKNOWN else False
                continue
            if state is False:continue
            if lineno in mapped:
                visited_draws.add(lineno)
                (active if state is True else uncertain).add(mapped[lineno]);continue
            if re.match(r'drawindexed\s*=',s,re.I):notes.add('Draw outside supported Wardrobe ranges at line '+str(lineno));continue
            a=ASSIGN.match(s)
            if a:
                key=a.group(1).lower()
                if s.lower().startswith('post '):continue
                env[key]=expression(a.group(2),env) if state is True else UNKNOWN
                continue
            r=re.match(r'run\s*=\s*(\S+)',s,re.I)
            if r:
                target=r.group(1).lower()
                # Only local CommandLists; external WWMI calls are not executed.
                if target.startswith('commandlist') and target in by:
                    if len(by[target])!=1:notes.add('Ambiguous CommandList: '+target);continue
                    execute(by[target][0],state,depth+1)
                elif target.startswith('customshader') and target in by:
                    if any(re.match(r'drawindexed\s*=',line,re.I) for block in by[target] for _,line in block):notes.add('CustomShader draw not represented: '+target)
        if stack:notes.add('Unclosed conditional block')
    for lines in by.get('constants',[]):execute(lines)
    # Offline model is assumed registered and visible, not at game boot time.
    env.update({'$mod_enabled':1,'$object_detected':1,'$active':1})
    for k in list(env):
        if re.fullmatch(r'\$merge_status_id(?:_\d+)?',k):env[k]=2
    for lines in by.get('present',[]):execute(lines)
    # Present may reset detection flags; next render is assumed active.
    env.update({'$mod_enabled':1,'$object_detected':1,'$active':1})
    for name,lines in sec:
        if re.fullmatch(r'textureoverridecomponent\d+',name):execute(lines)
    # Commented draws are intentionally not rendered. Unresolved branches are excluded.
    active={n for n in active if meta[n].get('visible',True)}
    uncertain={n for n in uncertain-active if meta[n].get('visible',True)}
    if uncertain:notes.add('Unknown draw guards: %d'%len(uncertain))
    return dict(active=[n for n in meta if n in active],uncertain=[n for n in meta if n in uncertain],notes=sorted(notes))

def coverage(P,ids,lo,hi):
    """Conservative provisional Z-band coverage trigger, not a material classifier."""
    out={}; h=hi-lo
    for name,a,b in [('feet',0,.14),('calves',.14,.32),('thighs',.32,.49),('pelvis',.49,.60),('waist',.60,.72)]:
        pts=P[ids]; q=pts[(pts[:,2]>=lo+a*h)&(pts[:,2]<lo+b*h)] if h>0 else pts[:0]
        out[name]=bool(len(q)>=20 and (name not in ('feet','calves','thighs') or ((q[:,0]<0).sum()>=10 and (q[:,0]>0).sum()>=10)))
    return out

def diagnose(P,faces,comp,ini,meta,evidence,bones_path,load_bones,reference,blocked=(), anatomy=(), effective_skin=None,context=None):
    """One conditional invocation; returns conservative anatomical recovery candidates."""
    from scipy.spatial import cKDTree
    from detection002 import skeleton
    from analysis_context import AnalysisContext
    context=context or AnalysisContext(P,faces)
    start=time.perf_counter(); V={n:context.vertex_ids(n) for n in faces}
    def union(names):return context.union(names)
    body=union([n for n in V if comp[n]>=3]); face=union([n for n in V if comp[n]==2]); skin_names=[n for n in V if comp[n]>=3 and evidence[n]['role']=='skin'] if effective_skin is None else list(effective_skin); skin=union(skin_names)
    if not len(body):print('[ARF] Skipped: no body candidates.');return
    baseline=union([n for n in reference['active'] if comp[n]>=3]); baseline=baseline if len(baseline) else body
    lo=float(P[baseline,2].min()); hi=float(P[face,2].max()) if len(face) else float(P[baseline,2].max())
    cov=coverage(P,skin,lo,hi)
    # Use the same unified skeleton implementation as the deformation engine.
    # A missing hand cannot be detected by projecting onto a reference without arms.
    import os
    import skeleton as engine_skeleton
    bi=bw=None
    try:
        bi,bw=context.bones(bones_path,len(P),load_bones); vg=os.path.join(bones_path,'BlendRemapVertexVG.buf')
        if not (os.path.isfile(vg) and os.path.getsize(vg)==len(P)*bi.shape[1]*2): bi=bw=None
    except Exception: bi=bw=None
    def bone_map(names):
        if bi is None or not names: return None,None
        try:
            mask=np.zeros(len(P),bool); mask[union(names)]=True
            with contextlib.redirect_stdout(io.StringIO()):
                r,info=engine_skeleton.label_bones(P,bi,bw,hi,vertex_mask=mask,triangles=np.concatenate([faces[n] for n in names]))
            return engine_skeleton.region_weights(bi,bw,r),info
        except Exception as e:
            print('[ARF] Skeleton coverage unavailable:',repr(e)); return None,None
    base_anatomy=list(anatomy) if anatomy else list(dict.fromkeys(skin_names+[n for n in V if comp[n]==2]))
    def upper_coverage(weights,info,ids):
        if info is None: return {}
        seeds=info['seeds']; C=info['centroid']
        out={}
        for side in ('r','l'):
            hand=seeds.get('hand_'+side)
            good=hand is not None and abs(C[hand,0])>.08*hi and weights['arm_'+side][ids].sum()>100
            out['arm_'+side]=bool(good); out['hand_'+side]=bool(good)
        out['head']=bool(seeds.get('head') is not None and C[seeds['head'],2]>.75*hi)
        return out
    base_rw,base_info=bone_map(base_anatomy)
    upper=upper_coverage(base_rw,base_info,union(base_anatomy))
    cov.update(upper)
    print('[ARF] Automatic Skin / Anatomy coverage:',cov)
    if all(cov.values()):print('[ARF] Skipped: lower-body coverage present; required skeleton branches available.');return
    print('\n===== ARF CONDITIONAL RECOVERY =====')
    active=reference['active']; print('[ARF] Default active parts:',len(active)); print('[ARF] Active:',active); print('[ARF] Uncertain:',reference['uncertain']);print('[ARF] INI notes:',reference['notes'])
    names=[n for n in active if comp[n]>=2]; ids=union(names)
    if not len(ids):print('[ARF] No resolved reference; no suggestions.');return
    zlo=float(P[ids,2].min()); zhi=float(P[face,2].max()) if len(face) else float(P[ids,2].max()); h=zhi-zlo
    if h<=0:print('[ARF] Invalid reference extent.');return
    # Prefer known skin/name-positive active parts for reference; retain other active
    # geometry if it is needed to cover a missing region. This is only a spatial map.
    preferred=[n for n in names if comp[n]==2 or (evidence[n].get('contributions',{}).get('naming') or 0)>0 or evidence[n]['role']=='skin']
    refids=union(preferred); pc=coverage(P,refids,zlo,zhi)
    refnames=preferred
    preferred_complete=all(pc.values())
    if not preferred_complete:
        refids=ids; refnames=names
        print('[ARF] Reference includes clothing/unknown surfaces; material cannot be inferred from overlap alone.')
    print('[ARF] Reference coverage:',coverage(P,refids,zlo,zhi))
    z=(P[refids,2]-zlo)/h; labels=np.select([z<.14,z<.32,z<.49,z<.60,z<.72,z<.88],['feet','calves','thighs','pelvis','waist','torso'],default='head_neck')
    try:
        import os
        bi,bw=context.bones(bones_path,len(P),load_bones); vg=os.path.join(bones_path,'BlendRemapVertexVG.buf')
        if not (os.path.isfile(vg) and os.path.getsize(vg)==len(P)*bi.shape[1]*2):raise ValueError('Local/unknown bone namespace; spatial fallback only')
        mask=np.zeros(len(P),bool);mask[refids]=True; fm=np.zeros(len(P),bool);fm[np.intersect1d(face,refids)]=True
        with contextlib.redirect_stdout(io.StringIO()):
            r,s=skeleton.label_bones(P,bi,bw,zhi,vertex_mask=mask,triangles=np.concatenate([faces[n] for n in refnames]),face_mask=fm)
        rw=skeleton.region_weights(bi,bw,r); arm=rw['arm_l'][refids]+rw['arm_r'][refids]; head=rw['head'][refids]
        labels[arm>.55]='arms';labels[head>.65]='head_neck'
        print('[ARF] Bone seeds:',s['seeds'])
    except Exception as e:print('[ARF] Bone segmentation unavailable:',e)
    tree=cKDTree(P[refids]); print('[ARF] Region map is provisional; nearest-vertex distances are not proof of skin.')
    recovered=[]
    # Expand the anatomical hypothesis with eligible inactive alternatives too.
    # Do not add clothing just because its mesh occupies the same area.
    eligible=[n for n in V if comp[n]>=3 and n not in blocked and n not in reference['uncertain']
              and evidence[n]['role'] in ('ambiguous','unresolved')
              and (evidence[n].get('contributions',{}).get('naming') or 0)>0
              and not evidence[n].get('veto_auto_skin',False) and len(V[n])>=20]
    expanded=list(dict.fromkeys(base_anatomy+preferred+eligible))
    expanded_rw,expanded_info=bone_map(expanded) if upper and not all(upper.values()) else (None,None)
    print('[ARF] Expanded skeleton seeds:',expanded_info['seeds'] if expanded_info else 'not available / not needed')
    upper_candidates=[]
    for n in V:
        if comp[n]<3:continue
        q=V[n]; d,j=tree.query(P[q]); near=labels[j]; u,c=np.unique(near,return_counts=True); fractions={k:round(100*int(v)/len(q),1) for k,v in zip(u,c)}
        # Active geometry may match itself. Report this explicitly rather than calling it validation.
        selfmatch=bool(np.intersect1d(q,refids).size); naming=evidence[n].get('contributions',{}).get('naming')
        close=float(np.mean(d<=.015*h)); lower=sum(fractions.get(k,0) for k in ('feet','calves','thighs','pelvis','waist'))
        candidate=('review lower-body anatomical candidate' if lower>=60 and close>=.75 and (naming or 0)>0 else 'review material' if close>=.75 else 'weak spatial match')
        if (preferred_complete and lower>=60 and close>=.75 and (naming or 0)>0
                and evidence[n]['role'] in ('ambiguous','unresolved')
                and n not in reference['uncertain'] and n not in blocked and len(q)>=20
                and not evidence[n].get('veto_auto_skin',False)):
            recovered.append(n)
        # Upper limbs can be absent from the default outfit. Use their own
        # weights in the expanded skeleton, not nearest pelvis vertices.
        if n in eligible and expanded_rw is not None:
            arm_r=float(expanded_rw['arm_r'][q].mean()); arm_l=float(expanded_rw['arm_l'][q].mean())
            if arm_r+arm_l>=.60 and ((not upper.get('arm_r',True) and arm_r>=.20) or (not upper.get('arm_l',True) and arm_l>=.20)):
                upper_candidates.append(n); candidate='upper-limb bone candidate'
            # Neck/head bridge: positive name, high central location and close reference.
            elif not all(upper.values()) and fractions.get('head_neck',0)>=60 and close>=.75 and float(np.abs(P[q,0]).max())<.14*h and float(P[q,2].min())>zlo+.75*h:
                upper_candidates.append(n); candidate='head/neck bridge candidate'
        if selfmatch: candidate+='; reference member, not independent validation'
        print('[ARF] %s | %s | regions=%s | distance median=%.5f H p90=%.5f H | near=%.1f%% | naming=%s | self-reference=%s | original=%s | suggestion=%s'%(n,'active' if n in active else 'inactive/unknown',fractions,np.median(d)/h,np.percentile(d,90)/h,100*close,naming,selfmatch,evidence[n]['role'],candidate))
    # Validate the proposed upper recovery against the engine skeleton, not
    # merely the provisional nearest-vertex region map.
    lower_recovered=list(recovered)
    proposed=list(dict.fromkeys(base_anatomy+lower_recovered+upper_candidates))
    if upper_candidates:
        r2,i2=bone_map(proposed); u2=upper_coverage(r2,i2,union(proposed))
        if any(u2.get(k,False) and not v for k,v in upper.items()): recovered.extend(upper_candidates)
        else: print('[ARF] Upper candidates did not restore a missing skeleton branch:',upper_candidates)
    recovered=list(dict.fromkeys(recovered))
    def candidate_coverage(names):
        out=coverage(P,union(skin_names+names),lo,hi)
        if upper:
            anat=list(dict.fromkeys(base_anatomy+names)); r2,i2=bone_map(anat)
            out.update(upper_coverage(r2,i2,union(anat)) or {k:False for k in upper})
        return out
    improved=candidate_coverage(recovered)
    if not any(improved.get(k,False) and not v for k,v in cov.items()):
        recovered=[]; improved=dict(cov)
    print('[ARF] Recovery candidates:',recovered)
    print('[ARF] Candidate coverage:',improved)
    print('===== END ARF | %.3fs =====\n'%(time.perf_counter()-start))
    return recovered
