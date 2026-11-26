"""Read-only regional morphology prototypes for Thicc Tool 021.
All engine runs use a private mod copy; no installed module is overwritten.
"""
import inspect
import json
import numpy as np
from preview_no_seam_guard import sandbox, geometry, load_cfg, ids_for
from _hip_sweep import viewer


from morphology.regional import Region as RegionalFields, smooth, bump

def cfg_for(saved, amounts=None, waist=None):
    cfg=dict(saved)
    cfg['amounts']={k:0. for k in ('hips','butt','thighs','calves')}
    cfg['amounts'].update(amounts or {})
    cfg['waist_morphology']=waist or dict(enabled=False,width=1.,depth=1.)
    cfg['surface_shading']='Original'
    cfg['bounce']='normal'
    # Isolate the tested regions. Keep saved Seam Guard and anatomical roles.
    for k in ('inner_fill','displacement_smoothing','advanced_clothing','relative_silhouette','surface_rounding'):
        cfg[k]=False
    cfg['final_regularization']=dict(enabled=False)
    cfg['directional_expansion']={k:[1.,1.] for k in cfg['amounts']}
    return cfg


def baseline(root,cfg,label,disable_hip=False):
    from morphology.engine import PreviewSession
    with PreviewSession(root, private=False) as session:
        result=session.preview(cfg, disable_hip=disable_hip)
        return result.positions,result.regional_data

class Region(RegionalFields):
    def show(self,cases,title,view="back"):
        self.report(self.p,cases)
        viewer(self.p,self.faces,cases,self.visible,title,view=view)
