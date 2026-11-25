"""Isolate sliders using the production pipeline, with calibration intact."""
from preview_no_seam_guard import sandbox, geometry, load_cfg
from _morph_ab import run_case, report, viewer

def main():
    import thicc_edit as te
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini); cfg=load_cfg(root)
        amounts=dict(te.PRESETS[cfg.get('preset',te.DEFAULT_CFG['preset'])]); amounts.update(cfg.get('amounts',{}))
        keys=('hips','butt','thighs','calves')
        base,d=run_case(root,cfg,'Combined')
        cases=[('Original',p),('Combined',base)]
        for key in keys:
            c=dict(cfg); c['amounts']={**amounts,**{k:amounts[k] if k==key else 0.0 for k in keys}}
            q,_=run_case(root,c,key+' only'); cases.append((key+' only',q))
        print('Note: each slider case recalibrates the field; these are not additive contributions. Other saved options remain unchanged.')
        report(p,faces,cases,d); viewer(p,faces,cases,d)
if __name__=='__main__': main()
