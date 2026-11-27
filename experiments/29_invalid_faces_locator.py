
EXPERIMENT_INFO = {'description': 'Highlight faces rejected by geometric validation.', 'objective': 'Locate problematic triangles.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

from _refinement_lab import *
if __name__=='__main__':
    with PreviewSession(os.environ['THICC_MOD_DIR']) as s:
        base,r,c,v=setup(s); cases=[('Baseline',base.positions)]; overlays={}
        for label,d in [('Vertex Z',r.glutes(0,0,.5)),('XYZ',r.glutes(.3,.4,.5))]:
            q=base.positions+r.prepare_delta(d); report=v.inspect(q); f=v.describe(report)
            name=f'{label} full trial | {len(f)} flagged'; cases.append((name,q)); overlays[name]=f
        show(s,r,cases,'29 | Invalid faces (red)',focus='pelvis',overlays=overlays,skin=False)
    print('===== EXPERIMENT 29 - INVALID FACES LOCATOR FINISHED =====',flush=True)
