"""Persistent CPU Anny worker. Only generates native reference meshes."""
import sys,json,traceback
from pathlib import Path
import numpy as np

def main():
    import torch,anny
    model=anny.Anny(topology='anny',rig='anny',local_changes='default',phenotypes='all').to(device='cpu',dtype=torch.float32)
    model.eval()
    phen={k:.5 for k in model.phenotype_labels}; phen.update(age=.67,gender=1.)
    targets={'hips':['hip-scale-horiz-incr'],'hips_y':['hip-scale-depth-incr'],'butt':['buttocks-volume-incr'],'thighs':['l-upperleg-scale-horiz-incr','r-upperleg-scale-horiz-incr'],'thighs_y':['l-upperleg-scale-depth-incr','r-upperleg-scale-depth-incr'],'calves':['measure-calf-circ-incr'],'belly':['stomach-pregnant-incr']}
    missing=set(sum(targets.values(),[]))-set(model.local_change_labels)
    if missing: raise RuntimeError('Missing Anny targets: '+str(missing))
    def vertices(changes):
        with torch.no_grad(): out=model(phenotype_kwargs=phen,local_changes_kwargs=changes)
        return out['rest_vertices'][0].detach().cpu().numpy().astype(np.float64)
    base=vertices({})
    print('ANNY76_READY',flush=True)
    for line in sys.stdin:
        try:
            req=json.loads(line)
            if req.get('close'):break
            changes={n:float(req['values'][k]) for k,names in targets.items() for n in names if req['values'][k]!=0}
            q=vertices(changes) if changes else base.copy()
            if q.shape!=base.shape or not np.isfinite(q).all():raise ValueError('Invalid Anny output')
            np.savez(req['output'],base=base,target=q,faces=model.faces.detach().cpu().numpy())
            print('ANNY76_OK',flush=True)
        except Exception:
            traceback.print_exc();print('ANNY76_ERROR',flush=True)
if __name__=='__main__':main()
