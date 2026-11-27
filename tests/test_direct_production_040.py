import sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'thicc_tool'))
from morphology.direct_hips import DirectHipField
from live_preview import baseline_key
from experiment_parameters import morphology_only
import thicc_edit as te
class TestDirectProduction(unittest.TestCase):
    def setUp(self):
        z=np.linspace(0,10,41); theta=np.arange(40)*2*np.pi/40
        p=np.array([[2*np.cos(t),1.5*np.sin(t),h] for h in z for t in theta]); tri=np.array([[i*40+j,i*40+(j+1)%40,(i+1)*40+j] for i in range(40) for j in range(40)]+[[i*40+(j+1)%40,(i+1)*40+(j+1)%40,(i+1)*40+j] for i in range(40) for j in range(40)])
        self.h=DirectHipField(p,tri,dict(knee=1,hip_z=5,crotch=6,waist=9,hip_half=2,cy=0)); self.p=p
    def test_peak_and_endpoints(self):
        h=self.h; self.assertEqual(h.peak,6); self.assertAlmostEqual(h.lo,1.48); self.assertEqual(h.hi,9)
        z=np.linspace(h.lo,h.hi,1001); self.assertLess(abs(z[np.argmax(h.gain(z,2))]-6),.01)
        np.testing.assert_array_equal(h.gain(np.array([h.lo,h.hi]),5),0)
    def test_neutral_and_direction(self):
        x,y,z=self.p.T; dx,dy=self.h.field(x,y,z,0); np.testing.assert_array_equal(dx,0); np.testing.assert_array_equal(dy,0)
        dx,dy=self.h.field(x,y,z,5,(0,1)); np.testing.assert_array_equal(dx,0); self.assertGreater(np.abs(dy).max(),0)
    def test_strength_and_spatial_evaluation(self):
        x,y,z=self.p.T; a=self.h.field(x,y,z,2); b=self.h.field(x,y,z,5)
        np.testing.assert_allclose(b,np.asarray(a)*2.5,atol=1e-12)
        np.testing.assert_allclose(self.h.field(x[:7],y[:7],z[:7],2),np.asarray(a)[:,:7])
    def test_config_and_cache(self):
        self.assertEqual(te.DEFAULT_CFG['morphology_engine'],'Legacy')
        self.assertNotEqual(baseline_key({}),baseline_key({'morphology_engine':'Direct Section'}))
        self.assertEqual(morphology_only({'morphology_engine':'Direct Section','anatomy':['x']}),{'morphology_engine':'Direct Section'})
if __name__=='__main__': unittest.main()
