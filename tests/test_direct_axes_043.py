import unittest
import numpy as np
import test_direct_thighs_041 as thigh_tests
import test_direct_production_040 as hip_tests
class AxisTests(unittest.TestCase):
    def test_thigh_axes(self):
        thigh_tests.DirectThighTests.setUpClass(); f=thigh_tests.DirectThighTests.f; p=thigh_tests.DirectThighTests.p
        self.check_axes(f,p)
    def test_hip_axes(self):
        t=hip_tests.TestDirectProduction(); t.setUp(); self.check_axes(t.h,t.p)
    def check_axes(self,f,p):
        a=np.asarray(f.field(*p.T,2,depth_amount=0)); b=np.asarray(f.field(*p.T,0,depth_amount=2)); c=np.asarray(f.field(*p.T,2,depth_amount=2))
        np.testing.assert_array_equal(a[1],0); np.testing.assert_array_equal(b[0],0)
        self.assertGreater(np.abs(a[0]).max(),0); self.assertGreater(np.abs(b[1]).max(),0)
        np.testing.assert_allclose(c,a+b,atol=1e-12)
