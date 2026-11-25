import contextlib, io, pathlib, sys, unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'thicc_tool'))
from detection002 import shape_recognition as shape, surface_evidence as se, surface_relations as sr, skeleton, fusion
from wwmi_role_evidence import _island_evidence, welded_island_evidence

def cylinder():
    z=np.linspace(0,100,21); a=np.linspace(0,2*np.pi,24,endpoint=False)
    P=np.array([[10*np.cos(t),8*np.sin(t),h] for h in z for t in a]); faces=[]
    for j in range(len(z)-1):
        for k in range(len(a)):
            x=j*len(a)+k; y=j*len(a)+(k+1)%len(a); faces.extend([[x,y,x+len(a)],[y,y+len(a),x+len(a)]])
    return P,np.array(faces)

class Performance(unittest.TestCase):
    def test_shape_debug_equivalence(self):
        P,t=cylinder(); a=shape.describe(P,t,100,debug=True); b=shape.describe(P,t,100,vertex_ids=np.unique(t))
        for k in ('label','vertices','islands','surface','dominant'): self.assertEqual(a[k],b[k])
        self.assertTrue('signatures' in a['profiles'][0]); self.assertNotIn('signatures',b['profiles'][0])
        for x,y in zip(a['profiles'],b['profiles']): self.assertEqual({k:x[k] for k in y},y)
    def test_surface_debug_equivalence(self):
        P,t=cylinder(); P=np.concatenate([P,P+[.2,0,0]]); draws=[('a',t,'unclassified'),('b',t+len(P)//2,'unclassified')]; L=dict(crotch=55.,ankle=5.,knee=30.,waist=70.)
        bi=np.zeros((len(P),1),int); bw=np.ones((len(P),1))
        with contextlib.redirect_stdout(io.StringIO()):
            a=se.calculate(P,draws,L,bi,bw,True,independent=True,debug=True)
            with patch.object(se.sp,'report',side_effect=AssertionError('debug called')),patch.object(se,'welded_groups',side_effect=AssertionError('debug called')):
                b=se.calculate(P,draws,L,bi,bw,True,independent=True)
        self.assertEqual(a,b)
    def test_indexed_connectivity(self):
        rng=np.random.default_rng(31)
        for _ in range(40):
            t=rng.integers(0,90,(30,3)); groups=[]
            for row in t:
                g=set(row); hit=[i for i,x in enumerate(groups) if g & x[0]]; count=1
                for i in reversed(hit):
                    v,n=groups.pop(i); g|=v; count+=n
                groups.append((g,count))
            self.assertEqual(_island_evidence(t),(len(groups),max(x[1] for x in groups)/len(t)))
        self.assertEqual(_island_evidence(np.empty((0,3),int)),(0,0.))
        P=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,0],[1,0,0],[0,-1,0]],float); t=np.arange(6).reshape(-1,3)
        self.assertEqual(welded_island_evidence(P,t),(1,1.))
    def test_local_region_weights(self):
        rng=np.random.default_rng(7); bi=rng.integers(0,8,(200,4)); bw=rng.random((200,4)); v=np.arange(10,90); r={i:('torso' if i%2 else 'arm_l') for i in range(8)}
        full=skeleton.region_weights(bi,bw,r); local=skeleton.region_weights(bi[v],bw[v],r)
        for k in full: np.testing.assert_array_equal(full[k][v],local[k])
    def test_raw_only_when_missing(self):
        P,t=cylinder(); faces={'Body':t,'Hat':t[-30:]}; comp={n:3 for n in faces}; L=dict(ankle=5.,knee=30.,crotch=55.,waist=70.)
        def no_bones(*a): raise ValueError('fixture')
        for missing in (False,True):
            a={'Body':('unresolved',.75,0.)}; b={'Hat':('non-anatomical candidate',0.,3.)}
            if not missing: a.update(b)
            with patch.object(fusion.lg,'measure',return_value=L),patch.object(fusion.surface_evidence,'calculate',side_effect=[a,b]) as calc,contextlib.redirect_stdout(io.StringIO()):
                out=fusion.evaluate(P,faces,comp,'',{},'',no_bones)
            self.assertEqual(calc.call_count,2 if missing else 1)
            self.assertEqual(out['Hat']['contributions']['surface'],-40.)
            self.assertEqual(out['Body']['contributions']['surface'],10.)
