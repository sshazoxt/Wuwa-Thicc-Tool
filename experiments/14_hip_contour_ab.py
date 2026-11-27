
EXPERIMENT_INFO = {'description': 'Compare legacy, outer, adaptive and fixed contour estimators.', 'objective': 'Evaluate contour stability.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

from _hip_sweep import *
if __name__=='__main__':
    with sandbox() as (root,ini):
        saved=load_cfg(root); p,faces=geometry(root,ini); h=saved_hips(saved)
        # Include a higher test value even when the saved setting is stable.
        h=max(3.,h); cases=[('Original',p)]
        for method in METHODS:
            mon,q,err=run_case(root,saved,h,method); report(mon); cases.append(('%s | residual %.3f'%(method,err),q))
        viewer(p,faces,cases,[n for n in mon.active if n in mon.parts],'Hip contour comparison | Hips %.2f'%h)
