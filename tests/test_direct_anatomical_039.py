import unittest,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'thicc_tool'))
from _direct_anatomical_lab import DirectHip
class DirectTests(unittest.TestCase):
    def setUp(self):
        z=np.linspace(0,10,41); theta=np.arange(40)*2*np.pi/40
        self.p=np.array([[2*np.cos(t),1.5*np.sin(t),h] for h in z for t in theta]); self.tri=np.array([[i*40+j,i*40+(j+1)%40,(i+1)*40+j] for i in range(40) for j in range(40)]+[[i*40+(j+1)%40,(i+1)*40+(j+1)%40,(i+1)*40+j] for i in range(40) for j in range(40)])
        self.L=dict(knee=1,hip_z=5,crotch=6,waist=9,hip_half=2,cy=0); self.h=DirectHip(self.p,self.tri,self.L)
    def test_neutral(self):
        for m in ('Direct Section','Direct Silhouette'): np.testing.assert_array_equal(self.h.displacement(0,m),0)
    def test_monotone_gain(self):
        self.assertGreater(np.abs(self.h.displacement(5)[:,0]).max(),np.abs(self.h.displacement(2)[:,0]).max())
    def test_waist_and_height(self):
        for m in ('Direct Section','Direct Silhouette'):
            q=self.h.displacement(5,m); np.testing.assert_array_equal(q[self.p[:,2]>=9],0); np.testing.assert_array_equal(q[:,2],0); self.assertTrue(np.isfinite(q).all())
    def test_duplicate_reference(self):
        other=DirectHip(self.p,np.concatenate([self.tri,self.tri]),self.L); np.testing.assert_allclose(other.displacement(2),self.h.displacement(2))
if __name__=='__main__': unittest.main()
