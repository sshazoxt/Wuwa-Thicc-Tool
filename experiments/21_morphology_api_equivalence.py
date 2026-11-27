"""Compare direct production dry run and the modular preview API on the same snapshot."""

EXPERIMENT_INFO = {'description': 'Compare modular preview with direct production dry run.', 'objective': 'Verify numerical equivalence.', 'visual': 'Console only', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

import numpy as np
from preview_no_seam_guard import sandbox,load_cfg
from morphology import PreviewSession
import thicc_edit as te

if __name__=='__main__':
    with sandbox() as (root,ini):
        saved=load_cfg(root)
        direct=te.run(str(root),'dry')
        if not isinstance(direct,dict) or 'preview_positions' not in direct: raise RuntimeError('Direct dry preview failed')
        with PreviewSession(root,private=False) as session:
            a=session.preview(saved)
            delta=np.asarray(direct['preview_positions'],float)-a.positions
            print('Direct production vs modular API max XYZ difference (cm):',np.max(abs(delta),axis=0))
            np.testing.assert_allclose(delta,0,rtol=0,atol=1e-6)
            print('Equivalence passed for the current engine; 021 reference field/calibration regression is in tests/test_morphology_023.py.')
    print('===== EXPERIMENT 21 - MORPHOLOGY API EQUIVALENCE FINISHED =====')
