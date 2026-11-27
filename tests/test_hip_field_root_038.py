import sys
from pathlib import Path
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'experiments'),str(ROOT/'thicc_tool')]
from _hip_field_root_isolation import absolute_targets, mapping_knots, linear_extrap, trial

class HipRootIsolationTests(unittest.TestCase):
    def test_absolute_target_anchors(self):
        z=np.linspace(0,10,101); b=5+np.sin(z/2)
        additive,signed,positive=absolute_targets(z,b,1.,5.,9.,2.)
        np.testing.assert_allclose([signed[10],signed[50],signed[90]],[0,2,0],atol=1e-12)
        self.assertTrue(np.all(positive>=0));self.assertEqual(additive[50],2.)
        self.assertTrue(np.all(signed[z<1]==0));self.assertTrue(np.all(signed[z>9]==0))
    def test_map(self):
        L=dict(ankle=10,knee=30,crotch=50,apex=48,waist=70); R=dict(ankle=16,knee=50,crotch=82,apex=87,waist=105)
        a,b=mapping_knots(L,R);np.testing.assert_allclose(linear_extrap(a,a,b),b)
        a,b=mapping_knots(L,R,True);self.assertNotIn(50,a);self.assertTrue(np.all(np.diff(b)>0))
        self.assertLess(linear_extrap(-1,a,b),0)
    def test_patch_restore_and_compile(self):
        import thicc_edit as te
        from morphology import calibration as c
        orig=(te.Sculpt.set_frame,c.calibrate,c.smooth_correction)
        for mode in ('linear_map','no_crotch_map','root_none','root_skinning','quintic_env','model_env','unit_response','no_convolution','additive','absolute','absolute_positive'):
            with self.assertRaisesRegex(RuntimeError,'test sentinel'):
                with trial(mode):raise RuntimeError('test sentinel')
            self.assertEqual(orig,(te.Sculpt.set_frame,c.calibrate,c.smooth_correction))
    def test_missing_anchors_rejected(self):
        with self.assertRaises(ValueError):absolute_targets(np.arange(5.),np.array([np.nan,1,2,3,4]),0,2,4,1)
    def test_calibration_variants_execute(self):
        import thicc_edit as te
        from morphology import calibration as c
        from types import SimpleNamespace
        # Sixteen vertices per ring, connected by triangles; actual calibration outline.
        z=np.linspace(49,119,71); angle=np.linspace(0,2*np.pi,32,endpoint=False)
        pts=np.array([[12*np.cos(a),-4.6+8*np.sin(a),h] for h in z for a in angle]); tris=[]
        for i in range(len(z)-1):
            for j in range(32):
                a=i*32+j;b=i*32+(j+1)%32;tris.extend([(a,b,a+32),(b,b+32,a+32)])
        tris=np.array(tris); L=dict(te.REF,hip_z=82.)
        class Fake:
            hip=None;coupled_hips=False;s=1.;root=None
            def zmap(self,z):return np.asarray(z)
            def field_ref(self,x,y,z):
                gain=np.interp(z,*self.hip) if self.hip is not None else np.zeros_like(z)
                return np.sign(x)*gain,np.zeros_like(x)
        for mode in ('legacy','quintic_env','model_env','no_convolution','unit_response','additive','absolute','absolute_positive'):
            with self.subTest(mode=mode),trial(mode):
                d=c.calibrate(Fake(),pts,tris,L,dict(hips=2.,thighs=0.),{},te.REF,te.HIP_ENV,te.HIP_TARGET,te.smoothstep)
                self.assertTrue(np.all(np.isfinite(d['Hc'])))
                self.assertTrue(np.all(np.isfinite(d['tgt'])))
