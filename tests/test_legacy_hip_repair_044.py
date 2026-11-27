import unittest, sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'thicc_tool'))
from morphology.legacy_hip_repair import profile_bounds,weight,fit_amplitude
import thicc_edit as te

class LegacyRepair044(unittest.TestCase):
    def test_profile_bounds_and_derivatives(self):
        b=profile_bounds(te.REF);lo,peak,hi=b[:3];eps=1e-3
        np.testing.assert_allclose(weight([lo,peak,hi],b),[0,1,0],atol=1e-12)
        self.assertTrue(np.all(weight(np.linspace(lo-5,hi+5,1000),b)>=0))
        for p in (lo,peak,hi):
            a,c,d=weight([p-eps,p,p+eps],b)
            self.assertLess(abs((d-a)/(2*eps)),1e-6)
            self.assertLess(abs((a-2*c+d)/eps**2),1e-3)
    def test_amplitude_no_fixed_cap(self):
        for h in np.linspace(0,5,51):
            self.assertAlmostEqual(fit_amplitude(lambda a:.9*a,2.6*h),2.6*h/.9,places=8)
        self.assertGreater(fit_amplitude(lambda a:.9*a,13),6.)
        with self.assertRaises(ValueError):fit_amplitude(lambda a:0.,5.)
    def test_coupled_and_relative(self):
        b=profile_bounds(te.REF,True,{'peak':.1},75.)
        self.assertEqual(b[0],te.REF['knee']);self.assertEqual(b[2],te.REF['waist'])
        self.assertGreater(b[1],75.)
        self.assertEqual(profile_bounds(te.REF,relative=True)[2],te.REF['waist'])
    def test_legacy_angular_response_unchanged(self):
        from morphology.hips import accumulate
        from types import SimpleNamespace
        px=np.array([12.,-12.]);py=np.array([-6.,-6.]);z=np.array([80.,80.]);r=np.hypot(px,py+4.6);soft=np.sqrt(r*r+4);ux=px/soft;uy=(py+4.6)/soft
        sc=SimpleNamespace(hip=(np.array([70.,90.]),np.array([3.,3.])),coupled_hips=False,direction={'hips':(1.,1.)})
        def get():
            dx=np.zeros(2);dy=np.zeros(2);accumulate(sc,px,py,z,dx,dy,te.smoothstep,r,ux,uy);return dx,dy
        a=get();sc.legacy_hip_spline=lambda z:np.full_like(z,3.);b=get();np.testing.assert_array_equal(a,b)
