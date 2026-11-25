import contextlib, io, pathlib, sys, unittest
from unittest.mock import Mock, patch
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'thicc_tool'))
from analysis_context import AnalysisContext, AnalysisOptions
from detection002 import shape_recognition as shape, surface_evidence as se, fusion
from wwmi_role_evidence import _island_evidence, welded_island_evidence
from test_performance_011 import cylinder

class SharedContext(unittest.TestCase):
    def test_lazy_and_shared(self):
        P,t=cylinder(); source=Mock(return_value=t); c=AnalysisContext(P,source,['a'])
        self.assertEqual(source.call_count,0); p=c.part('a')
        self.assertIs(p.triangles,c.triangles('a')); self.assertEqual(source.call_count,1)
        self.assertIs(p.vertex_ids,c.vertex_ids('a'))
        np.testing.assert_array_equal(p.vertex_ids[p.local_triangles],t)
        self.assertIs(c.union(['a']),c.union(['a','a']))
        self.assertEqual(p.z_info,(0.,100.,len(P)))
        self.assertFalse(c.options.debug)
    def test_bones_once_and_isolation(self):
        P,t=cylinder(); loader=Mock(return_value=(np.zeros((len(P),1),int),np.ones((len(P),1))))
        c=AnalysisContext(P,{'a':t}); a=c.bones('mesh',len(P),loader)
        self.assertIs(a,c.bones('mesh',len(P),loader)); self.assertEqual(loader.call_count,1)
        d=AnalysisContext(P+1,{'a':t}); d.bones('mesh',len(P),loader)
        self.assertEqual(loader.call_count,2); self.assertEqual(d.part('a').z_info[:2],(1.,101.))
    def test_geometry_equivalence(self):
        P,t=cylinder(); c=AnalysisContext(P,{'a':t}); p=c.part('a'); local=(p.vertex_ids,p.local_triangles)
        self.assertEqual(_island_evidence(t),_island_evidence(t,local))
        self.assertEqual(welded_island_evidence(P,t),welded_island_evidence(P,t,local_geometry=local,points=p.points))
        self.assertEqual(shape.describe(P,t,100),shape.describe(P,t,100,vertex_ids=p.vertex_ids,local_faces=p.local_triangles,points=p.points))
    def test_surface_equivalence(self):
        P,t=cylinder(); P=np.concatenate([P,P+[.2,0,0]]); faces={'a':t,'b':t+len(P)//2}; draws=[(n,v,'unclassified') for n,v in faces.items()]; L=dict(crotch=55.,ankle=5.,knee=30.,waist=70.)
        bi=np.zeros((len(P),1),int); bw=np.ones((len(P),1)); c=AnalysisContext(P,faces)
        with contextlib.redirect_stdout(io.StringIO()):
            a=se.calculate(P,draws,L,bi,bw,True); b=se.calculate(P,draws,L,bi,bw,True,context=c)
        self.assertEqual(a,b)
    def test_fusion_shared_bones(self):
        P,t=cylinder(); faces={'Body':t}; c=AnalysisContext(P,faces); loader=Mock(return_value=(np.zeros((len(P),1),int),np.ones((len(P),1))))
        c.bones('',len(P),loader)
        with contextlib.redirect_stdout(io.StringIO()), patch.object(fusion.surface_evidence,'calculate',return_value={'Body':('unresolved',.75,0.)}),patch.object(fusion.lg,'measure',return_value=dict(ankle=5.,knee=30.,crotch=55.,waist=70.)):
            fusion.evaluate(P,faces,{'Body':3},'',{},'',loader,context=c)
        self.assertEqual(loader.call_count,1)
