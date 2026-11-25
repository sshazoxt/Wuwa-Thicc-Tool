import contextlib, io, json, pathlib, sys, tempfile, unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'thicc_tool'))
import detection_cache as dc
import anatomical_reconstruction as ar
import skeleton

class ForceTransaction(unittest.TestCase):
    def test_proposal_commit_and_cache(self):
        with tempfile.TemporaryDirectory() as d:
            mod=pathlib.Path(d); cfg=mod/'thicc.json'; cfg.write_text(json.dumps({'move':['leg'],'amounts':{'hips':2},'anatomy':[]})); original=cfg.read_bytes()
            def runner(m,mode,automatic_proposal=False):
                self.assertTrue(automatic_proposal)
                return dict(parts=[['leg','skin',0,50,300,'legs']],cfg={'anatomy':['leg']},landmarks={},natural={},draw_meta={},role_evidence={},ready=True)
            with patch.object(dc,'hashes',side_effect=lambda *a: {}),contextlib.redirect_stdout(io.StringIO()):
                res=dc.diagnose(d,runner,lambda m:'mod.ini',force=True)
                self.assertEqual(cfg.read_bytes(),original)
                self.assertFalse((mod/'thicc_analysis_cache.json').exists())
                dc.accept_proposal(d,res,lambda m:'mod.ini')
                self.assertEqual(json.loads(cfg.read_text())['skin'],['leg'])
                self.assertEqual(json.loads(cfg.read_text())['amounts'],{'hips':2})
                def no_run(*a,**k):self.fail('Accepted snapshot should be reused')
                hit=dc.diagnose(d,no_run,lambda m:'mod.ini')
                self.assertEqual(hit['_cache']['source'],'full_cache')
    def test_changed_config_rejects_commit(self):
        with tempfile.TemporaryDirectory() as d:
            cfg=pathlib.Path(d)/'thicc.json';cfg.write_text('{}')
            with patch.object(dc,'hashes',side_effect=lambda *a: {}),contextlib.redirect_stdout(io.StringIO()):
                res=dc.diagnose(d,lambda *a,**k:dict(parts=[],cfg={'anatomy':[]}),lambda m:'mod.ini',force=True)
                cfg.write_text('{"changed":true}')
                with self.assertRaises(ValueError):dc.accept_proposal(d,res,lambda m:'mod.ini')
                self.assertEqual(json.loads(cfg.read_text()),{'changed':True})
    def test_inactive_arms_recovered_by_bones(self):
        # Synthetic geometry + mocked engine skeleton; tests control flow, not recognition accuracy.
        z=np.linspace(0,100,600); body=np.column_stack((np.tile([-2,2],300),np.zeros(600),z))
        arm=np.column_stack((np.repeat([-25,25],150),np.zeros(300),np.tile(np.linspace(55,78,150),2)))
        P=np.concatenate([body,arm]); faces={'body':np.arange(600).reshape(-1,3),'arms':np.arange(600,900).reshape(-1,3)};comp={n:3 for n in faces}
        evidence={'body':{'role':'skin','contributions':{'naming':5}},'arms':{'role':'unresolved','contributions':{'naming':5}}}
        ref={'active':['body'],'uncertain':[],'notes':[]}
        bi=np.zeros((900,1),dtype=int);bw=np.ones((900,1));bi[600:750]=1;bi[750:]=2
        def label(P,bi,bw,H,vertex_mask=None,triangles=None):
            present=bool(vertex_mask[600:].any()); C=np.array([[0,0,95],[-25,0,60],[25,0,60]])
            return ({0:'torso',1:'arm_l',2:'arm_r'} if present else {0:'torso'}, {'seeds':{'head':0,'hand_l':1 if present else None,'hand_r':2 if present else None},'centroid':C})
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d,'BlendRemapVertexVG.buf').write_bytes(b'\0'*(900*2))
            with patch.object(skeleton,'label_bones',side_effect=label),contextlib.redirect_stdout(io.StringIO()) as out:
                result=ar.diagnose(P,faces,comp,'',{},evidence,d,lambda *a:(bi,bw),ref)
            self.assertEqual(result,['arms']);self.assertIn("'hand_r': True",out.getvalue())
            with patch.object(skeleton,'label_bones',side_effect=label),contextlib.redirect_stdout(io.StringIO()):
                result=ar.diagnose(P,faces,comp,'',{},evidence,d,lambda *a:(bi,bw),ref,blocked={'arms'})
            self.assertEqual(result,[])
if __name__=='__main__':unittest.main()
