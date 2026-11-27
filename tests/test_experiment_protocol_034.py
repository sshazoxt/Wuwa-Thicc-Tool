import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'thicc_tool'),str(ROOT/'experiments')]
from experiment_parameters import experiment_amounts, morphology_only, overlay
from experiment_runner import experiment_details, parameter_source, experiment_tooltip
from experiment_worker import script_config
from _hip_root_lab import isolated
from _hip_target_followup import case_plan
from _relative_field_lab import trial
from morphology import calibration, hips, legs

class ExperimentProtocolTests(unittest.TestCase):
    def test_metadata_explicit_current_and_protocol_default(self):
        self.assertEqual(parameter_source({}), 'protocol')
        self.assertEqual(parameter_source(experiment_details(ROOT/'experiments'/'32_belly_live_apply.py')), 'current')
        self.assertEqual(parameter_source(experiment_details(ROOT/'experiments'/'14_hip_contour_ab.py')), 'saved')
        self.assertIn('Parameter source: protocol',experiment_tooltip(ROOT/'experiments'/'45_hip_target_profile.py'))
        with self.assertRaises(ValueError): parameter_source({'parameter_source':'invalid'})

    def test_fixed_protocol_independent_of_saved_values(self):
        a={'preset':'pear','amounts':{'hips':0.,'thighs':.17}}
        b={'preset':'butt','amounts':{'hips':5.,'thighs':1.2}}
        d={'hips':3.98,'thighs':2.}
        with patch.dict(os.environ,THICC_PARAMETER_MODE='protocol'):
            self.assertEqual(experiment_amounts(a,d),d)
            self.assertEqual(experiment_amounts(b,d),d)
        for mode in ('saved','current'):
            with patch.dict(os.environ,THICC_PARAMETER_MODE=mode):
                self.assertEqual(experiment_amounts(a,d),{'hips':0.,'thighs':.17})

    def test_protocol_options_same_but_anatomy_native(self):
        a={'skin':['A'],'landmarks':{'waist':80},'deformation_field':'Continuous','advanced_arm_protection':True,'virtual_inguinal':False}
        b={'skin':['B'],'landmarks':{'waist':100},'deformation_field':'Legacy'}
        with patch.dict(os.environ,THICC_PARAMETER_MODE='protocol'):
            x,y=isolated(a,3.98,2.),isolated(b,3.98,2.)
        self.assertEqual(morphology_only(x),morphology_only(y))
        self.assertEqual(x['skin'],['A']); self.assertEqual(y['skin'],['B'])
        self.assertEqual(x['landmarks'],a['landmarks'])
        self.assertEqual(x['deformation_field'],'Legacy')
        self.assertFalse(x['final_regularization']['enabled'])
        self.assertEqual(a['deformation_field'],'Continuous')

    def test_library_override_does_not_transfer_anatomy(self):
        a={'skin':['A'],'anatomy':['A'],'landmarks':{'waist':80},'amounts':{'hips':3.}}
        b={'skin':['B'],'anatomy':['B'],'landmarks':{'waist':100},'amounts':{'hips':0.},'surface_rounding':False}
        result=overlay(a,b)
        self.assertEqual(result['skin'],['A']); self.assertEqual(result['anatomy'],['A']); self.assertEqual(result['landmarks'],a['landmarks'])
        self.assertEqual(result['amounts'],{'hips':0.}); self.assertFalse(result['surface_rounding'])
        self.assertEqual(a['amounts'],{'hips':3.})

    def test_private_configuration_restored_on_error_and_next_script(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); mod=root/'model'; mod.mkdir(); p=mod/'thicc.json'; base=root/'base.json'; override=root/'current.json'
            p.write_text('{"skin":["A"],"amounts":{"hips":1}}'); initial=p.read_bytes()
            override.write_text('{"skin":["B"],"amounts":{"hips":0}}')
            with self.assertRaises(RuntimeError):
                with script_config(mod,base,override) as q:
                    self.assertEqual(json.loads(q.read_text()),{'skin':['A'],'amounts':{'hips':0}})
                    raise RuntimeError('experiment error')
            self.assertEqual(p.read_bytes(),initial)
            # Simulate an interrupted preceding worker leaving an override behind.
            p.write_text('{"amounts":{"hips":5}}')
            with script_config(mod,base) as q: self.assertEqual(q.read_bytes(),initial)
            self.assertEqual(p.read_bytes(),initial)

    def test_missing_baseline_not_created_by_temporary_override(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); mod=root/'model'; mod.mkdir(); base=root/'base.json'; override=root/'current.json'; override.write_text('{"amounts":{"hips":0}}')
            with script_config(mod,base,override,'full') as p: self.assertTrue(p.exists())
            self.assertFalse((mod/'thicc.json').exists())
            with script_config(mod,base) as p: self.assertFalse(p.exists())

    def test_followup_case_plans_compile_and_restore(self):
        original=(calibration.calibrate,hips.accumulate,legs.accumulate)
        for num in (49,50,51):
            cases=case_plan(num,3.98,2.)
            self.assertEqual(len(cases),5)
            self.assertEqual(cases[0][1],set())
            for _,flags,h,t in cases:
                self.assertEqual(h,3.98); self.assertEqual(t,2. if num==51 else 0.)
                with trial(flags): self.assertTrue(callable(calibration.calibrate))
                self.assertEqual(original,(calibration.calibrate,hips.accumulate,legs.accumulate))

    def test_hip_field_terms_numeric(self):
        from types import SimpleNamespace
        sc=SimpleNamespace(hip=(np.array([0.,100.]),np.array([1.,1.])),coupled_hips=False,direction={'hips':[1.,1.]})
        from thicc_edit import smoothstep
        r=np.array([12.]);ux=np.array([.6]);uy=np.array([.8]); z=np.array([70.]);x=r*ux;y=r*uy
        with trial({'linear_lateral','no_hip_depth'}):
            dx=np.zeros(1);dy=np.zeros(1);hips.accumulate(sc,x,y,z,dx,dy,smoothstep,r,ux,uy)
            np.testing.assert_allclose(dx,ux);np.testing.assert_array_equal(dy,0.)

if __name__=='__main__': unittest.main()
