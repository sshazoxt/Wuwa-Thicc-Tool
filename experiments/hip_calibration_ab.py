"""Compare the production field against zero lateral calibration correction."""

EXPERIMENT_INFO = {'description': 'Compare production field and zero lateral correction.', 'objective': 'Isolate hip calibration contribution.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

import numpy as np
from preview_no_seam_guard import sandbox, geometry, load_cfg
from _morph_ab import run_case, report, viewer

def main():
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini); cfg=load_cfg(root)
        a,d=run_case(root,cfg,'Calibration ON')
        b,e=run_case(root,cfg,'Calibration correction ZERO',zero_calibration=True)
        print('ZERO removes the calibrated hip correction, not just iterative refinement; all other saved settings remain.')
        for label,v in [('ON',d),('ZERO',e)]:
            q=v['PRs'].copy(); q[:,0]+=v['sc'].field_ref(*q.T)[0]
            actual=v['outline'](q)-v['original_outline']
            print('\nReference Z | target | actual | residual (reference cm):',label)
            for z,t,g in zip(v['zs'],v['tgt'],actual):
                if np.isfinite(g): print('%6.1f | %+8.3f | %+8.3f | %+8.3f'%(z,t,g,t-g))
        cases=[('Original',p),('Calibration ON',a),('Correction ZERO',b)]
        report(p,faces,cases,d); viewer(p,faces,cases,d)
if __name__=='__main__': main()
