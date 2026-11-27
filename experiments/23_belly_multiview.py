
EXPERIMENT_INFO = {'description': 'Inspect belly depth variants with synchronized views.', 'objective': 'Evaluate anterior volume.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

import os
from morphology import PreviewSession
from morphology.viewer import ExperimentViewer
from _regional_morph import cfg_for

if __name__=='__main__':
    with PreviewSession(os.environ['THICC_MOD_DIR']) as session:
        base=session.preview(cfg_for(session.saved)); r=session.regional(base); center,_=r.locate_waist()
        cases=[('Original',session.original_geometry)]
        for amount in (.15,.35,.60):
            label='Belly %.2f'%amount; cases.append((label,r.apply(base.positions,r.belly(center,amount),label)))
        r.report(session.original_geometry,cases)
        ExperimentViewer(session.original_geometry,session.faces,cases,r.visible,'23 | Belly multiview').show(view='right',columns=2)
    print('===== EXPERIMENT 23 - BELLY MULTIVIEW FINISHED =====')
