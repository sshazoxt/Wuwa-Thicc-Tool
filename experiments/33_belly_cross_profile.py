"""Compare old and new transverse profiles without writing buffers."""

EXPERIMENT_INFO = {'description': 'Compare legacy and extended transverse belly profiles.', 'objective': 'Evaluate lateral coverage and shape.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

import os
from morphology import PreviewSession
from morphology.belly import field, basic_parameters
from morphology.refinement import RegionalControls, FieldComposer
from _refinement_lab import compare

if __name__ == '__main__':
    with PreviewSession(os.environ['THICC_MOD_DIR']) as s:
        base=s.preview({'belly_morphology':{'amount':0.},'waist_morphology':{'enabled':False}})
        r=s.regional(base); center,_=r.locate_waist(); c=RegionalControls(r,center)
        v=FieldComposer(r,base.positions)
        p=dict(depth=.66,width=2.,height=1.32,offset=-.03)
        fields={'Basic max':field(c,**basic_parameters(1.)), 'Legacy .66 / 2':field(c,**p,rounded=False),
                'Rounded .66 / 2':field(c,**p,rounded=True), 'Rounded .66 / 2.5':field(c,**{**p,'width':2.5},rounded=True),
                'Rounded .66 / 3.5':field(c,**{**p,'width':3.5},rounded=True)}
        compare(s,r,v,fields,'33 | Belly transverse profile A/B',view='perspective')
    print('===== EXPERIMENT 33 - BELLY CROSS PROFILE FINISHED =====',flush=True)
