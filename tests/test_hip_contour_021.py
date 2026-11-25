"""Regression for dynamic gap rejection in hip calibration."""
import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'thicc_tool'))
import thicc_edit as te
from experiment_runner import completion_message


def section(xs):
    # Each triangle intersects Z=1 at its two vertical edges.
    points=[]
    for a,b in zip(xs[::2],xs[1::2]):
        points.extend([[a,0,0],[b,0,0],[a,1,2]])
    p=np.asarray(points,float)
    return p,np.arange(len(p)).reshape(-1,3)


class HipContourTests(unittest.TestCase):
    def test_threshold_crossing(self):
        p,t=section([0,0,2,2,4.49,4.49,6,6,8,8,10,10])
        z=np.array([1.])
        f=te.fixed_core_outline(p,t,z)
        q=p.copy(); q[q[:,0]>=4.49,0]+=.02
        base=te.contour(p[t],1)[:,0]; deformed=te.contour(q[t],1)[:,0]
        self.assertAlmostEqual(te.torso_half(base),10.)
        self.assertAlmostEqual(te.torso_half(deformed),2.)
        self.assertAlmostEqual(f(p)[0],10.)
        self.assertAlmostEqual(f(q)[0],10.02)

    def test_excluded_original_samples_stay_excluded(self):
        p,t=section([0,0,1,1,2,2,8,8,10,10,30,30])
        f=te.fixed_core_outline(p,t,[1.])
        q=p.copy(); q[q[:,0]<=2,0]+=1.; q[q[:,0]>=8,0]=20
        self.assertAlmostEqual(f(p)[0],2.)
        self.assertAlmostEqual(f(q)[0],3.)

    def test_sparse_core_and_missing_section(self):
        p,t=section([0,0,5,5,6,6,7,7])
        f=te.fixed_core_outline(p,t,[1.,3.])
        self.assertAlmostEqual(f(p)[0],0.)
        self.assertTrue(np.isnan(f(p)[1]))

    def test_completion_identity(self):
        for status,code in [('Finished',0),('Cancelled',1),('Error',2)]:
            msg=completion_message('15_improved_hips_full_body.py',status,1.234,code)
            self.assertIn('15_improved_hips_full_body.py',msg)
            self.assertIn(status.upper(),msg)
            self.assertIn(f'exit {code}',msg)

if __name__=='__main__': unittest.main()
