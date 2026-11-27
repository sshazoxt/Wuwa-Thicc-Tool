
EXPERIMENT_INFO = {'description': 'Compare production thighs, thighs without hip field and local prototype.', 'objective': 'Isolate thigh and hip interactions.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

from _regional_morph import *

if __name__=='__main__':
    with sandbox() as (root,ini):
        saved=load_cfg(root); p,f=geometry(root,ini); q,d=baseline(root,cfg_for(saved),'Neutral'); r=Region(p,f,d)
        a,_=baseline(root,cfg_for(saved,{'thighs':2.}),'Production Thighs 2')
        b,_=baseline(root,cfg_for(saved,{'thighs':2.}),'Thighs 2 without calibrated hip correction',disable_hip=True)
        c=r.apply(q,r.thighs(.30,.20),'Independent local thigh')
        r.show([('Original',p),('Thighs 2 production',a),('Thighs 2 no hip field',b),('Local thigh prototype',c)],'19 | Hip / thigh isolation')
    print('===== EXPERIMENT 19 - THIGH HIP ISOLATION FINISHED =====')
