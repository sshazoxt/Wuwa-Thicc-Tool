import os
from morphology import PreviewSession
from morphology.viewer import ExperimentViewer
from _regional_morph import cfg_for

if __name__=='__main__':
    with PreviewSession(os.environ['THICC_MOD_DIR']) as session:
        saved=session.saved; neutral=session.preview(cfg_for(saved)); r=session.regional(neutral)
        center,_=r.locate_waist(); lower=max(r.L['crotch']+.20*r.span,center-.16*r.span)
        legacy=session.preview(cfg_for(saved,waist=dict(enabled=True,width=.75,depth=.95)))
        cases=[('Original',session.original_geometry),('Legacy waist',legacy.positions)]
        for label,c in [('Localized waist',center),('Lower waist',lower)]:
            cases.append((label,r.apply(neutral.positions,r.waist(c,.75,.95),label)))
        r.report(session.original_geometry,cases)
        ExperimentViewer(session.original_geometry,session.faces,cases,r.visible,'22 | Waist multiview').show(view='right',columns=2)
    print('===== EXPERIMENT 22 - WAIST MULTIVIEW FINISHED =====')
