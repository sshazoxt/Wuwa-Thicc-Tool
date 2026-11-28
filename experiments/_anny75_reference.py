"""Experiment 75: reference extraction. Runs in separate Anny Python environment."""
import json, sys
from pathlib import Path
import numpy as np

MORPHS = {
    'hips_x': ['hip-scale-horiz-incr'],
    'hips_y': ['hip-scale-depth-incr'],
    'thighs_x': ['l-upperleg-scale-horiz-incr','r-upperleg-scale-horiz-incr'],
    'thighs_y': ['l-upperleg-scale-depth-incr','r-upperleg-scale-depth-incr'],
}


def sections(vertices, faces, heights, center):
    import trimesh
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    rows=[]; merged=[]
    for z in heights:
        cut=mesh.section(plane_origin=[0,0,float(z)],plane_normal=[0,0,1])
        if cut is None: rows.append([np.nan]*4); merged.append(False); continue
        loops=[p for p in cut.discrete if len(p)>3 and np.linalg.norm(p[0]-p[-1])<1e-5]
        # Keep central torso loop, otherwise closest left/right leg loops. Reject hands.
        central=[p for p in loops if p[:,0].min()<center<p[:,0].max()]
        if central:
            q=max(central,key=lambda p: np.ptp(p[:,0])); sides=[q[q[:,0]>=center],q[q[:,0]<=center]]; merged.append(True)
        else:
            sides=[]
            for sign in (1,-1):
                candidates=[p for p in loops if sign*(p[:,0].mean()-center)>0]
                if not candidates: break
                sides.append(min(candidates,key=lambda p: abs(p[:,0].mean()-center)))
            merged.append(False)
        if len(sides)!=2 or any(len(p)<2 for p in sides): rows.append([np.nan]*4); continue
        a,b=sides; q=np.concatenate(sides)
        rows.append([np.ptp(q[:,0])/2,np.ptp(q[:,1])/2,(np.ptp(a[:,0])+np.ptp(b[:,0]))/4,(np.ptp(a[:,1])+np.ptp(b[:,1]))/4])
    return np.array(rows),np.array(merged)


def main(output):
    import torch, anny
    from anny.anthropometry import Anthropometry
    from importlib.metadata import version
    model=anny.Anny(topology='anny',rig='anny',local_changes='default',phenotypes='all').to(device='cpu',dtype=torch.float32)
    model.eval(); labels=set(model.local_change_labels)
    missing=set(sum(MORPHS.values(),[]))-labels
    if missing: raise RuntimeError('Missing Anny targets: '+str(sorted(missing)))
    phen={k:.5 for k in model.phenotype_labels}; phen.update(age=.67,gender=1.)
    def run(changes):
        with torch.no_grad(): return model(phenotype_kwargs=phen,local_changes_kwargs=changes)
    def verts(o): return o['rest_vertices'][0].detach().cpu().numpy().astype(float)
    base=run({}); p=verts(base); faces=model.faces.detach().cpu().numpy(); anth=Anthropometry(model)
    waist=float(np.median(p[anth.waist_vertex_indices,2])); center=float(np.median(p[anth.waist_vertex_indices,0]))
    # Identify knee from named lower-leg joint heads; fail rather than use a fixed body height.
    heads=base['rest_bone_heads'][0].detach().cpu().numpy(); names=list(model.bone_labels)
    ids=[i for i,n in enumerate(names) if any(k in n.lower().replace('-','').replace('_','') for k in ('lowerleg','shin','calf','tibia')) and not any(k in n.lower() for k in ('twist','roll','helper'))]
    if not ids: raise RuntimeError('Cannot identify Anny knee joint: '+str(names))
    knee=float(max(heads[ids,2])); span=waist-knee
    if span<=0: raise RuntimeError('Invalid reference knee/waist')
    z=np.linspace(knee,waist,201); neutral,merged=sections(p,faces,z,center)
    # First central loop that stays connected towards waist; ignores isolated false joins.
    roots=[i for i in range(1,len(z)-10) if merged[i:].mean()>.98 and merged[i:i+8].all()]
    if not roots: raise RuntimeError('Cannot locate reference groin topology')
    crotch=float(z[roots[0]])
    if not knee<crotch<waist: raise RuntimeError('Invalid reference crotch')
    u=np.interp(z,[knee,crotch,waist],[0,1,2]); data={'u':u,'neutral':neutral.tolist(),'landmarks':dict(knee=knee,crotch=crotch,waist=waist),'anny_version':version('anny'),'phenotype':phen,'profiles':{},'measurements':{}}
    for name,keys in MORPHS.items():
        col={'hips_x':0,'hips_y':1,'thighs_x':2,'thighs_y':3}[name]
        for strength in (.5,1.,2.):
            q=verts(run({k:strength for k in keys})); b,_=sections(q,faces,z,center); delta=b[:,col]-neutral[:,col]
            # Convert to JSON without nonstandard NaN values.
            data['measurements'][f'{name}_{strength}']=[float(x) if np.isfinite(x) else None for x in delta]
            if strength==1.: data['profiles'][name]=data['measurements'][f'{name}_{strength}']
        print('Anny reference:',name,keys,flush=True)
    data['neutral']=[[float(x) if np.isfinite(x) else None for x in row] for row in neutral]
    data['u']=u.tolist(); data['targets']=MORPHS
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    tmp=output.with_suffix('.tmp'); tmp.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8'); tmp.replace(output)
    print('Anny profiles saved:',output,flush=True)

if __name__=='__main__': main(sys.argv[1])
