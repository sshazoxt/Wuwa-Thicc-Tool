
EXPERIMENT_INFO = {'description': 'Compare waist width, depth, height and offset.', 'objective': 'Evaluate independent waist controls.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

from _refinement_lab import *
if __name__=='__main__':
    with PreviewSession(os.environ['THICC_MOD_DIR']) as s:
        base,r,c,v=setup(s)
        compare(s,r,v,{'Width .75':c.waist(.75),'Depth .75':c.waist(depth=.75),'Depth 1.35':c.waist(depth=1.35),'Height .65':c.waist(.75,.85,.65),'Offset -.15':c.waist(.75,.85,1,-.15)},'26 | Waist 4D')
    print('===== EXPERIMENT 26 - WAIST 4D CONTROLS FINISHED =====',flush=True)
