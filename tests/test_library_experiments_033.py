import json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'thicc_tool'))
from library_experiment_analysis import prepare

class LibraryExperimentTests(unittest.TestCase):
    def fixture(self,d):
        root=Path(d)/'source'; (root/'Meshes').mkdir(parents=True)
        (root/'Meshes'/'Position.buf').write_bytes(b'positions'); (root/'mod.ini').write_text('ini')
        (root/'thicc.json').write_text('{"amounts":{"hips":3.98}}')
        out=Path(d)/'out';out.mkdir();return root,Path(d)/'snapshot',out
    def test_private_analysis_archives_effective_settings(self):
        with tempfile.TemporaryDirectory() as d:
            src,target,out=self.fixture(d)
            def diagnose(mod,*a):
                self.assertEqual(Path(mod),target)
                return dict(ready=True,cfg={'amounts':{'hips':3.98},'anatomy':['Body']},parts=[('Body','skin'),('Hair','frozen'),('Top','garment')])
            with patch.dict(sys.modules,{'thicc_edit':types.SimpleNamespace(run=None,find_ini=None),'detection_cache':types.SimpleNamespace(diagnose=diagnose)}):prepare(src,target,out)
            cfg=json.loads((out/'settings.json').read_text());self.assertEqual(cfg['skin'],['Body']);self.assertEqual(cfg['move'],['Top']);self.assertEqual(cfg['freeze'],['Hair']);self.assertEqual(cfg['amounts']['hips'],3.98)
            self.assertEqual(json.loads((target/'thicc.json').read_text()),cfg)
            self.assertEqual(json.loads((src/'thicc.json').read_text()),{'amounts':{'hips':3.98}})
    def test_unready_anatomy_does_not_publish_settings(self):
        with tempfile.TemporaryDirectory() as d:
            src,target,out=self.fixture(d)
            with patch.dict(sys.modules,{'thicc_edit':types.SimpleNamespace(run=None,find_ini=None),'detection_cache':types.SimpleNamespace(diagnose=lambda *a:dict(ready=False,warnings=['missing pelvis']))}):
                with self.assertRaisesRegex(ValueError,'missing pelvis'):prepare(src,target,out)
            self.assertFalse((out/'settings.json').exists())
    def test_missing_config_is_created_only_in_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            src,target,out=self.fixture(d);(src/'thicc.json').unlink()
            with patch.dict(sys.modules,{'thicc_edit':types.SimpleNamespace(run=None,find_ini=None),'detection_cache':types.SimpleNamespace(diagnose=lambda *a:dict(ready=True,cfg={'anatomy':['Body']},parts=[('Body','skin')]))}):prepare(src,target,out)
            self.assertFalse((src/'thicc.json').exists());self.assertTrue((target/'thicc.json').exists())
