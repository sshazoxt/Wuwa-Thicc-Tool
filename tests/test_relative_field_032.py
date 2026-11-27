import sys
from pathlib import Path
import unittest
from types import SimpleNamespace
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'thicc_tool'),str(ROOT/'experiments')]
import _relative_field_lab as lab
import thicc_edit as te
from morphology import calibration,hips,legs

class RelativeFieldTests(unittest.TestCase):
    def test_bump_limits(self):
        np.testing.assert_allclose(lab.bump(np.array([-1,0,1,2,3]),0,1,2),[0,0,1,0,0])
    def test_radial_scale_invariance(self):
        r=np.linspace(0,30,31); a=np.full_like(r,12.)
        for f in (lab.hip_mask,lab.leg_mask):
            np.testing.assert_allclose(f(te.smoothstep,r,a),f(te.smoothstep,3*r,3*a))
            self.assertAlmostEqual(f(te.smoothstep,a,a)[0],1.)
    def test_ownership_partition(self):
        sc=SimpleNamespace(axis={s:(np.array([0,1]),np.array([s,s]),np.zeros(2)) for s in (1,-1)},curve=lambda x,y,z:np.interp(z,x,y))
        x=np.linspace(-2,2,100); y=np.zeros_like(x); z=y.copy()
        a=lab.ownership(x,y,z,sc,1); b=lab.ownership(x,y,z,sc,-1)
        np.testing.assert_allclose(a+b,1.)
        self.assertGreater(a[-1],a[0])
    def test_all_overrides_compile_and_restore(self):
        old=(calibration.calibrate,hips.accumulate,legs.accumulate)
        with self.assertRaises(ValueError):
            with lab.trial({'hip_mask','leg_mask','ownership','root','local_thigh','target'}):
                self.assertIsNot(legs.accumulate,old[2]); raise ValueError('test')
        self.assertEqual(old,(calibration.calibrate,hips.accumulate,legs.accumulate))
    def test_relative_leg_field_neutral(self):
        sc=te.Sculpt(dict(hips=0.,thighs=0.,butt=0.,calves=0.),False)
        sc.axis={s:(np.array([0.,120.]),np.array([s*8.,s*8.]),np.zeros(2)) for s in (1,-1)}
        sc._lab_profiles=dict(z=np.array([0.,120.]),legs={s:np.array([5.,5.]) for s in (1,-1)})
        sc._lab_thigh_length=30.; sc._lab_model_z=lambda z:z
        x=np.array([-12.,12.]); y=np.zeros(2); z=np.array([60.,60.]); dx=y.copy(); dy=y.copy()
        with lab.trial({'leg_mask','ownership','root','local_thigh'}):
            legs.accumulate(sc,x,y,z,dx,dy,te.smoothstep,te.LEG_KNOTS)
        np.testing.assert_array_equal(dx,0); np.testing.assert_array_equal(dy,0)
if __name__=='__main__': unittest.main()
