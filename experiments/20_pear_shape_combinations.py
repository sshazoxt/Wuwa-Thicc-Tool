
EXPERIMENT_INFO = {'description': 'Compare regional combinations for different silhouettes.', 'objective': 'Evaluate combined proportions.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

from _regional_morph import *

if __name__=='__main__':
    with sandbox() as (root,ini):
        saved=load_cfg(root); p,f=geometry(root,ini)
        q,d=baseline(root,cfg_for(saved,{'hips':2.5}),'Fixed Core Hips 2.5'); r=Region(p,f,d); w,_=r.locate_waist()
        cases=[('Original',p),('Hips only',q)]
        for label,wa,be,gl,th in [('Slim torso / pear',.82,.10,(.22,.32,.25),(.24,.17)),('Fuller lower abdomen',.95,.35,(.25,.35,.35),(.28,.22)),('Stylized pear',.75,.15,(.38,.48,.45),(.38,.28))]:
            delta=r.waist(w,wa,1.,be)+r.butt(*gl)+r.thighs(*th)
            cases.append((label,r.apply(q,delta,label)))
        r.show(cases,'20 | Experimental regional combinations')
    print('===== EXPERIMENT 20 - PEAR SHAPE COMBINATIONS FINISHED =====')
