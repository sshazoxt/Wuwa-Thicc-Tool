"""Regression tests for the modular field/calibration implementation."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'thicc_tool'))
import thicc_edit as te
from morphology.calibration import calibrate
from morphology.engine import PreviewSession
from experiment_runner import discover


class MorphologyModularTests(unittest.TestCase):
    def test_reference_021(self):
        # Fixture generated using the unmodified 021 source, not the refactored code.
        with np.load(ROOT/'tests/fixtures/morphology_021.npz') as f:
            axis={sgn:(np.array([0.,50.,80.,130.]),np.array([5.,8.,9.,12.])*sgn,np.array([-4.,-3.,-5.,-6.])) for sgn in (1,-1)}
            aa=np.linspace(-np.pi,np.pi,33); roots={sgn:(aa,81+3*np.cos(aa)) for sgn in (1,-1)}
            amounts=dict(hips=3.,butt=.7,thighs=1.2,calves=.8); L=dict(te.REF,hip_z=78.)
            for i,(continuous,coupled,relative,inner) in enumerate([(False,False,False,False),(True,False,True,True),(False,True,False,False),(True,True,False,True)]):
                with self.subTest(case=i):
                    sc=te.Sculpt(amounts,inner); sc.set_frame(L); sc.axis=axis; sc.root=roots;sc.continuous=continuous
                    events=[]
                    with contextlib.redirect_stdout(io.StringIO()):
                        cal=calibrate(sc,f['P'],f['T'],L,amounts,dict(coupled_hips=coupled,relative_silhouette=relative),te.REF,te.HIP_ENV,te.HIP_TARGET,te.smoothstep,observer=lambda name,d:events.append(name))
                    for key,ref in [('Hc','correction'),('original_outline','outline'),('tgt','target'),('err','error')]:
                        np.testing.assert_allclose(cal[key],f[f'{ref}_{i}'],rtol=0,atol=1e-9,equal_nan=True)
                    self.assertEqual(events.count('hip_iteration_before'),8)
                    sc.rounding=(np.linspace(52.,84.,9),np.linspace(0,np.pi/2,9),f['rounding']);sc.direction['hips']=(1.3,.7);sc.direction['thighs']=(.8,1.1)
                    stages={}
                    sc.field_observer=lambda name,d:stages.update({name:np.stack([d['dx'].copy(),d['dy'].copy()])})
                    result=np.array(sc.field_ref(*f['test'].T))
                    np.testing.assert_allclose(result,f[f'field_{i}'],rtol=0,atol=1e-9)
                    np.testing.assert_array_equal(stages['rounding'],result)
                    self.assertEqual(list(stages),['butt','hips','legs and inner fill','rounding'])

    def test_helpers_hidden(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in ('_helper.py','21_test.py','22_test.py'): (root/name).touch()
            self.assertEqual([p.name for p in discover(root)],['21_test.py','22_test.py'])

    def test_preview_only_guard(self):
        with self.assertRaisesRegex(ValueError,'dry mode'):
            te.run('unused','write',config_override={})

    def test_session_reuses_snapshot_and_config(self):
        # No real model is needed: mock the geometry loader and dry pipeline.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'thicc.json').write_text('{"amounts":{"hips":1}}')
            obj=type('Geometry',(),{})(); obj.positions=np.zeros((3,3)); obj.faces={}; obj.context=object()
            received=[]
            def run(mod,mode,**kw):
                received.append(kw)
                # Return the expected observer events without touching disk.
                data=dict(L={},SKIN=[],GARMENTS=[],reference={'active':[]},allow=np.ones(3),guard=np.ones(3),arm_influence=np.zeros(3),H=1.,new=np.zeros((3,3)))
                kw['observer']('before_waist',data);kw['observer']('after_waist',data)
                return {'preview_positions':np.full((3,3),kw['config_override']['amounts']['hips'])}
            with patch('morphology.engine.PreparedGeometry',return_value=obj) as loader, patch.object(te,'run',side_effect=run):
                with PreviewSession(root,private=False) as session:
                    a=session.preview({'amounts':{'hips':2}}); b=session.preview({'amounts':{'hips':3}})
                    self.assertEqual(loader.call_count,1); self.assertIs(received[0]['prepared_geometry'],received[1]['prepared_geometry'])
                    self.assertEqual(session.saved['amounts']['hips'],1);self.assertTrue((a.positions==2).all());self.assertTrue((b.positions==3).all())
            self.assertEqual((root/'thicc.json').read_text(),'{"amounts":{"hips":1}}')

if __name__=='__main__': unittest.main()
