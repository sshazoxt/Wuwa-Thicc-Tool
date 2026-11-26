import sys, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'thicc_tool'))
from morphology.belly import basic_parameters, parameters, lateral_profile, field, apply_belly
from morphology.refinement import RegionalControls

class BellyTests(unittest.TestCase):
    def test_basic_endpoints(self):
        for u,expected in [(0,[0,2,1.08,-.09]),(.5,[.33,2.25,1.29,.005]),(1,[.66,2.5,1.5,.10])]:
            np.testing.assert_allclose(list(basic_parameters(u).values()),expected)
        self.assertEqual(parameters({}),basic_parameters(0))
        self.assertEqual(parameters({'amount':.5,'depth':.99}),basic_parameters(.5))
        self.assertEqual(parameters({'advanced':True,'depth':.66,'width':3.5})['width'],3.5)
        with self.assertRaises(ValueError): parameters({'advanced':True,'width':4})
        with self.assertRaises(ValueError): basic_parameters(float('nan'))
    def test_profile(self):
        x=np.linspace(0,3.5,501)
        a=lateral_profile(x,2,.66); b=lateral_profile(x,3.5,.66)
        self.assertTrue(np.all(b>=a-1e-12)); self.assertTrue(np.all(np.diff(b)<=1e-12))
        self.assertEqual(a[0],1); self.assertEqual(a[-1],0)
        self.assertAlmostEqual(lateral_profile(2-1e-4,2,.66),0,places=9)
        np.testing.assert_allclose(lateral_profile(-x,2,.66),a)
    def test_zero_is_exact_noop(self):
        base=np.arange(12,dtype=float).reshape(4,3)
        q,tri=apply_belly(None,base,None,None,{})
        self.assertIs(q,base); self.assertIsNone(tri)
    def test_full_geometry_stage(self):
        # Open tube, split by Z rings, plus a frozen unrelated triangle.
        angles=np.arange(48)*2*np.pi/48; zs=np.linspace(4,12,33)
        p=np.array([[2*np.cos(a),1.5*np.sin(a),z] for z in zs for a in angles])
        t=[]
        for j in range(len(zs)-1):
            for i in range(48):
                a=j*48+i; b=j*48+(i+1)%48; t.extend([[a,b,a+48],[b,b+48,a+48]])
        n=len(p); p=np.vstack([p,[[10,0,8],[11,0,8],[10,0,9]]]); t=np.array(t)
        faces={'body':t,'frozen':np.array([[n,n+1,n+2]])}; allow=np.ones(len(p)); allow[n:]=0
        data=dict(L={'knee':0,'crotch':4,'waist':10},skin=['body'],garments=[],active=['body','frozen'],allow=allow,guard=np.ones(len(p)),arm=np.zeros(len(p)),H=12)
        with patch('morphology.regional.Region.locate_waist',return_value=(10.,True)):
            q,_=apply_belly(p,p,faces,data,{'amount':1})
        np.testing.assert_array_equal(q[n:],p[n:]); np.testing.assert_allclose(q[:,[0,2]],p[:,[0,2]],atol=1e-6)
        self.assertGreater((q-p)[:,1].max(),.1)
        np.testing.assert_allclose(q[p[:,1]<0],p[p[:,1]<0],atol=1e-6)
