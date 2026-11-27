
EXPERIMENT_INFO = {'description': 'Compare individual regional fields and combined fields.', 'objective': 'Identify composition effects.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

import os
import numpy as np
from morphology import PreviewSession
from morphology.viewer import ExperimentViewer
from _regional_morph import cfg_for

if __name__=='__main__':
    with PreviewSession(os.environ['THICC_MOD_DIR']) as session:
        base=session.preview(cfg_for(session.saved,{'hips':2.5}));r=session.regional(base);center,_=r.locate_waist()
        fields={'Waist':r.waist(center,.82,.95),'Belly':r.belly(center,.35),'Glutes':r.glutes(.30,.40,.50),'Thighs':r.thighs(.30,.20)}
        cases=[('Hips baseline',base.positions)]
        for name,delta in fields.items():
            print(name,'raw maximum XYZ',np.max(abs(delta),axis=0))
            cases.append((name,r.apply(base.positions,delta,name)))
        combined=np.sum(list(fields.values()),axis=0)
        cases.append(('Combined fields',r.apply(base.positions,combined,'Combined fields')))
        r.report(session.original_geometry,cases)
        ExperimentViewer(session.original_geometry,session.faces,cases,r.visible,'25 | Regional field composition').show(view='back')
    print('===== EXPERIMENT 25 - REGIONAL FIELD COMPOSITION FINISHED =====')
