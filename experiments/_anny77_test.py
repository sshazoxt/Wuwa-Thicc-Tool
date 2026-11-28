import unittest
import numpy as np
from _anny77_transfer import Transfer
from _anny77_controls import SPECS
class Test(unittest.TestCase):
    def test_identity_and_full_body(self):
        z=np.linspace(0,4,81); theta=np.linspace(0,2*np.pi,32,endpoint=False)
        p=np.array([[np.cos(t),np.sin(t),h] for h in z for t in theta]); base=p.copy()
        mobility=np.ones(len(p)); mobility[0]=0
        L=dict(knee=1,crotch=2,waist=3,hip_half=1,cy=0)
        r=dict(knee=1,crotch=2,waist=3,half_width=1,half_depth=1)
        tr=Transfer(p,base,L,r,np.arange(len(p)),mobility,4)
        np.testing.assert_array_equal(tr.apply(base),p)
        q=tr.apply(base+np.array([.1,.2,0]))
        np.testing.assert_array_equal(q[0],p[0])
        np.testing.assert_allclose(q[1:]-p[1:],np.broadcast_to([.1,.2,0],q[1:].shape),atol=1e-12)
        self.assertGreater(np.max(np.abs(q[p[:,2]>3]-p[p[:,2]>3])),0)
    def test_controls(self):
        self.assertEqual(len({s[0] for s in SPECS}),len(SPECS))
        self.assertEqual(SPECS[0][0],'build')
if __name__=='__main__': unittest.main()
