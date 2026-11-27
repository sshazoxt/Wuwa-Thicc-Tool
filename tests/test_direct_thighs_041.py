import sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'thicc_tool'))
from morphology.direct_thighs import DirectThighField
class DirectThighTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        z=np.linspace(0,12,61); theta=np.arange(48)*2*np.pi/48
        p=[]; faces=[]
        for sign in (1,-1):
            offset=len(p)
            p.extend([[sign*2.4+1.4*np.cos(t),1.2*np.sin(t),h] for h in z for t in theta])
            for i in range(len(z)-1):
                for j in range(48):
                    a=offset+i*48+j; b=offset+i*48+(j+1)%48
                    faces.extend([[a,b,a+48],[b,b+48,a+48]])
        cls.p=np.array(p); cls.tri=np.array(faces); cls.f=DirectThighField(cls.p,cls.tri,dict(knee=2,crotch=10,waist=12,hip_z=9,hip_half=3.8,cy=0))
    def test_neutral_and_bounds(self):
        np.testing.assert_array_equal(self.f.field(*self.p.T,0),0)
        d=np.array(self.f.field(*self.p.T,2)); np.testing.assert_array_equal(d[:,(self.p[:,2]<=2)|(self.p[:,2]>=self.f.top)],0)
    def test_direction_and_symmetry(self):
        f=self.f; z=f.peak
        a=f.field(np.array([3.8,-3.8]),np.array([0.,0.]),np.array([z,z]),2)
        self.assertGreater(a[0][0],0); np.testing.assert_allclose(a[0][0],-a[0][1])
        np.testing.assert_array_equal(f.field(*self.p.T,2,(0,1))[0],0)
    def test_medial_and_peak(self):
        f=self.f; z=f.peak; x=np.array([1.,-1.,0.]); dx,dy=f.field(x,np.zeros(3),np.full(3,z),2)
        self.assertGreater(x[0]+dx[0],0); self.assertLess(x[1]+dx[1],0); self.assertEqual(dx[2],0)
        self.assertAlmostEqual(f.gain(z,2),2)
    def test_pelvis_transition(self):
        self.assertGreater(self.f.gain(self.f.hi,2),0)
        self.assertEqual(self.f.gain(self.f.top,2),0)
        self.assertGreater(self.f.peak,self.f.lo+.7*(self.f.hi-self.f.lo))
    def test_scale(self):
        f=DirectThighField(self.p*3,self.tri,dict(knee=6,crotch=30,waist=36,hip_z=27,hip_half=11.4,cy=0)); np.testing.assert_allclose(f.field(*(self.p*3).T,1),np.array(self.f.field(*self.p.T,1))*3,atol=1e-10)
if __name__=='__main__': unittest.main()
