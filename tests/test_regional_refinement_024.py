import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'thicc_tool'))
from morphology.refinement import FieldComposer, RegionalControls, support

class FakeRegion:
    def __init__(self):
        self.p=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[3.,0.,0.],[4.,0.,0.],[3.,1.,0.]])
        self.allfaces=np.array([[0,1,2],[3,4,5]])
        self.faces={'a':self.allfaces[:1],'b':self.allfaces[1:]}
    def prepare_delta(self,d): return d

class Tests(unittest.TestCase):
    def test_independent_reduction(self):
        r=FakeRegion(); v=FieldComposer(r,r.p); a=np.zeros_like(r.p); a[:3,2]=1; b=np.zeros_like(a); b[4,0]=-2
        q,f,reports=v.compose({'safe':a,'bad':b})
        self.assertEqual(f['safe'],1); self.assertLess(f['bad'],1); self.assertEqual(len(reports['bad'].indices),1)
        np.testing.assert_allclose(q[:3],r.p[:3]+a[:3]); self.assertFalse(len(v.inspect(q).indices))
    def test_support(self):
        self.assertEqual(support(10,8,12,2,0,5,7,13),(7,10,13))
        with self.assertRaises(ValueError): support(10,8,12,1,2,5,7,13)
    def test_anterior_and_height(self):
        r=FakeRegion(); r.p=np.array([[0.,1.,8.],[0.,-1.,8.],[0.,1.,20.],[.5,-1.,5.]])
        r.span=5.; r.L={'crotch':4.,'waist':10.,'apex':5.}
        r.centers=lambda zs,z:np.tile([-1.,1.,-1.,1.],(len(z),1))
        c=RegionalControls(r,10.); b=c.belly(.6); self.assertGreater(b[0,1],0); self.assertEqual(b[1,1],0); self.assertEqual(b[2,1],0); self.assertFalse(np.any(b[:,[0,2]]))
        g=c.glute_volume(.3,.4,1.2); self.assertFalse(np.any(g[:,2])); self.assertFalse(np.any(g[0])); self.assertLess(g[3,1],0)
if __name__=='__main__': unittest.main()
