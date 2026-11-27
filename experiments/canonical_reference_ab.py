"""Isolate redundant reference samples without changing moving/frozen roles."""

EXPERIMENT_INFO = {'description': 'Compare redundant versus canonical reference samples.', 'objective': 'Test influence of redundant reference geometry.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

from scipy.spatial import cKDTree
import numpy as np
from preview_no_seam_guard import sandbox, geometry, load_cfg
from _morph_ab import run_case, report, viewer

def duplicates(p,faces,d):
    active=set(d['reference']['active']); skin=d['SKIN']; tol=max(1e-8, max(p[:,2])*1e-6)
    removed=[]
    for n in skin:
        if n in active: continue
        v=p[np.unique(faces[n])]
        for a in skin:
            if a not in active: continue
            w=p[np.unique(faces[a])]
            if len(v) and len(w):
                x=np.mean(cKDTree(w).query(v)[0]<=tol); y=np.mean(cKDTree(v).query(w)[0]<=tol)
                if min(x,y)>=.4:
                    removed.append(n); print('Reference candidate excluded:',n,'matches',a,'fractions',x,y); break
    return removed

def main():
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini); cfg=load_cfg(root)
        saved,d=run_case(root,cfg,'Saved reference')
        # Explicitly test inactive frozen variants in a private configuration only.
        # Candidates must be geometrically very similar and inactive under default INI.
        active=set(d['reference']['active']); extras=[]
        for n in cfg.get('freeze',[]):
            if n in active or n not in faces or not faces[n].size: continue
            v=p[np.unique(faces[n])]
            for a in d['SKIN']:
                if a not in active: continue
                w=p[np.unique(faces[a])]; tol=max(1e-8,max(p[:,2])*1e-6)
                if len(w) and min(np.mean(cKDTree(w).query(v)[0]<=tol),np.mean(cKDTree(v).query(w)[0]<=tol))>=.4:
                    extras.append(n); break
        if extras:
            print('Experimental alternative candidates (not a production role decision):',extras)
            cfg=dict(cfg); cfg['skin']=list(dict.fromkeys(list(d['SKIN'])+extras)); cfg['freeze']=[n for n in cfg.get('freeze',[]) if n not in extras]; cfg['move']=[n for n in cfg.get('move',[]) if n not in extras]; cfg['anatomy']=list(dict.fromkeys(list(d['anatomy_names'])+extras))
            a,d=run_case(root,cfg,'All candidate variants moving')
        else: a=saved
        removed=duplicates(p,faces,d)
        if not removed:
            print('No inactive Skin variants met the conservative two-way 40% coincidence rule. No A/B change attempted.'); return
        # Restrict measurements before roles/masks are constructed, keep all effective roles intact.
        literal=repr(set(removed))
        replacements=[('    anatomy_v = context.union(anatomy_names)', '    anatomy_v = context.union([n for n in anatomy_names if n not in '+literal+'])'),
        ('    skin_v = context.union(SKIN)','    _experiment_skin = SKIN\n    SKIN = [n for n in SKIN if n not in '+literal+']\n    skin_v = context.union(SKIN)'),
        ('    freeze = set(cfg["freeze"])','    SKIN = _experiment_skin\n    freeze = set(cfg["freeze"])'),
        ('fit_rounding(sc, PR, [tris(n) for n in SKIN], L)','fit_rounding(sc, PR, [tris(n) for n in SKIN if n not in '+literal+'], L)'),
        ('    fdx, fdy = sc.field(P0[:, 0], P0[:, 1], P0[:, 2])','    fdx, fdy = sc.field(P0[:, 0], P0[:, 1], P0[:, 2])\n    skin_v = context.union(SKIN)\n    skin_core = skin_v[armw[skin_v] < 0.01]\n    skin_tri = np.concatenate([tris(n) for n in SKIN])\n    skin_tri = skin_tri[(armw[skin_tri] < 0.01).all(1)]')]
        b,e=run_case(root,cfg,'Canonical reference',replacements)
        print('Saved/canonical landmarks:',d['L'],e['L']); print('Roles unchanged:',d['SKIN']==e['SKIN'])
        cases=[('Original',p),('Saved roles',saved),('All moving reference',a),('Canonical reference',b)] if extras else [('Original',p),('Saved reference',a),('Canonical reference',b)]
        report(p,faces,cases,d); viewer(p,faces,cases,d)
if __name__=='__main__': main()
