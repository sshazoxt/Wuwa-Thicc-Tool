"""Trace production geometry stages without altering the production engine."""

EXPERIMENT_INFO = {'description': 'Trace displacement through production stages.', 'objective': 'Find the stage introducing an artifact.', 'visual': 'Console only', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

import numpy as np
from preview_no_seam_guard import sandbox, geometry, run_preview, ids_for, bands


def report(p,stages,d,faces,label):
    names=[n for n in d['skin'] if n in d['active']] or d['skin']
    ids=ids_for(faces,names)
    print('\n===== PHASE BREAKDOWN / %s ====='%label)
    print('Measured Skin:',names)
    print('Z bands use original coordinates; p95 absolute X is a lateral extent proxy.')
    bandlist=list(bands(p,ids,d['landmarks']))
    prev=p
    for stage,q in stages.items():
        delta=np.linalg.norm(q[ids]-prev[ids],axis=1)
        print('\n%s | changed > .01 cm: %d | max stage delta %.4f cm'%(stage,(delta>.01).sum(),delta.max()))
        print('Z range | lateral p95 gain vs original | stage p95 change | max vertex stage delta')
        for a,b,v in bandlist:
            base=np.percentile(np.abs(p[v,0]),95); now=np.percentile(np.abs(q[v,0]),95); prior=np.percentile(np.abs(prev[v,0]),95)
            print('%6.2f..%6.2f | %+8.3f | %+8.3f | %8.3f'%(a,b,now-base,now-prior,np.linalg.norm(q[v]-prev[v],axis=1).max()))
        prev=q
    print('Unchanged stage means disabled or no measured effect; initial field combines hips, butt, thighs and calves.')


def main():
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini)
        for enabled in (True,False):
            _,d,stages=run_preview(root,enabled,stages=True)
            report(p,stages,d,faces,'Seam Guard ON' if enabled else 'Seam Guard OFF')

if __name__=='__main__': main()
