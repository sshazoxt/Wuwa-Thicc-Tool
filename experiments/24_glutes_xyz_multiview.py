import os
from morphology import PreviewSession
from morphology.viewer import ExperimentViewer
from _regional_morph import cfg_for

if __name__=='__main__':
    with PreviewSession(os.environ['THICC_MOD_DIR']) as session:
        base=session.preview(cfg_for(session.saved)); r=session.regional(base)
        cases=[('Original',session.original_geometry)]
        for label,xyz in [('Width X',(.30,0,0)),('Depth Y',(0,.40,0)),('Height Z',(0,0,.50)),('Combined XYZ',(.30,.40,.50))]:
            cases.append((label,r.apply(base.positions,r.glutes(*xyz),label)))
        r.report(session.original_geometry,cases)
        ExperimentViewer(session.original_geometry,session.faces,cases,r.visible,'24 | Glutes XYZ multiview').show(view='right')
    print('===== EXPERIMENT 24 - GLUTES XYZ MULTIVIEW FINISHED =====')
