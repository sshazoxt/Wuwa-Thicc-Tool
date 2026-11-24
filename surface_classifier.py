"""Experimental evidence aggregation. Never assigns engine roles."""
import numpy as np


def classify(records, pairs):
    by={r['name']:r for r in records}
    scores={}; reasons={}; anchors=set()
    for r in records:
        n=r['name']; c=r['counts']; hard=r['hard']; waist=r['waist']; k=r['knees']
        s=0.; a=0.; why=[]
        if c is not None:
            t,x,y=np.asarray(c)/61
            if t>=.35 and waist: s+=3; why.append('continuous torso with narrowing')
            if max(x,y)>=.65 and k: s+=3; why.append('continuous leg with knee narrowing')
            if min(x,y)>=.65: s+=1; why.append('bilateral closed leg profiles')
            if max(t,x,y)<.12: a+=1; why.append('little closed contour evidence in tested windows')
        if hard is not None:
            if hard<=.04: s+=.75; why.append('smooth surface (weak evidence)')
            if hard>=.12: a+=2; why.append('many sharp dihedral edges')
        if s>=3.5 and a<2: anchors.add(n)
        scores[n]=[s,a]; reasons[n]=why
    relations=[]
    for p in pairs:
        x,y=p['names']; u,v=p['near']; align=p['align']; bone=p['bone']; ex=p['exclusive']
        if min(u,v)>=.85 and align>=.85:
            relations.append((x,y,'alternative candidate' if ex else 'coincident/variant candidate; exclusivity unknown'))
        for n,m,own,other in ((x,y,u,v),(y,x,v,u)):
            if m not in anchors or ex: continue
            if own>=.65 and other<=.35 and align>=.65:
                # Keep strongest pair only, not votes from duplicated body variants.
                r=by[n]; weight=1.5+(0.5 if bone is not None and bone>=.5 else 0)
                if weight>r.get('layer_weight',0): r['layer_weight']=weight; r['layer_reason']=f'localized overlap with {m} ({own:.0%}/{other:.0%}, bone={bone if bone is not None else "n/a"})'
    for r in records:
        n=r['name']; s,a=scores[n]; a+=r.get('layer_weight',0)
        why=reasons[n]+([r['layer_reason']] if 'layer_reason' in r else [])
        if s>=3.5 and a<2: label='skin candidate'; strength='strong' if s>=4.5 else 'moderate'
        elif a>=3 and s<2: label='non-anatomical candidate'; strength='moderate'
        else: label='unresolved'; strength='insufficient/conflicting'
        print(f'  {n} [{r["role"]}] -> {label}; support={strength}; anatomy={s:.2f}; accessory={a:.2f}')
        print('    evidence: '+('; '.join(why) or 'no decisive evidence'))
    for x,y,state in relations: print(f'  relationship: {x} <> {y}: {state}')


def report(records,pairs):
    print('\n===== SURFACE CLASSIFICATION (phase 1.7; diagnostic only) =====')
    print('Heuristic support, not probabilities. Vertex counts and island counts are not classification votes. Existing roles are displayed only.')
    classify(records,pairs)
    print('No roles, anatomy membership, landmarks or vertices changed. Head/hands/feet and mixed draws may remain unresolved.')
