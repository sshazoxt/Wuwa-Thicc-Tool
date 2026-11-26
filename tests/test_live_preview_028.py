import ast
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'thicc_tool'))
import live_preview as lp
import thicc_edit as te
from morphology.belly import apply_belly
from viewer3d import update_preview

class LiveTests(unittest.TestCase):
    def test_snapshot_is_private(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); mod=root/'mod'; (mod/'Meshes').mkdir(parents=True)
            ini=mod/'mod.ini'; ini.write_text('dummy'); (mod/'Meshes'/'Position.buf').write_bytes(b'original')
            work=root/'work'; work.mkdir(); sig=lp.signature(mod,ini)
            copy=lp.snapshot(mod,work,ini)
            (copy/'Meshes'/'Position.buf').write_bytes(b'changed')
            self.assertEqual((mod/'Meshes'/'Position.buf').read_bytes(),b'original')
            self.assertEqual(lp.signature(mod,ini),sig)
            self.assertFalse((mod/'Meshes'/'Position.buf.orig').exists())

    def test_cache_key_and_external_change(self):
        with tempfile.TemporaryDirectory() as d:
            mod=Path(d); (mod/'Meshes').mkdir(); ini=mod/'mod.ini'; ini.write_text('x')
            cfg={'amounts':{'hips':2},'belly_morphology':{'amount':.2}}
            p=np.arange(9,dtype=np.float32).reshape(3,3)
            b=dict(key=lp.baseline_key(cfg),original=p,base=p,faces={},data={})
            cache=mod/'cache.pkl'; lp.store_baseline(cache,b,mod,ini)
            cfg2={**cfg,'belly_morphology':{'amount':.5}}
            with patch('morphology.belly.apply_belly',return_value=(p+1,None)) as f:
                np.testing.assert_array_equal(lp.cached_belly(cache,mod,ini,cfg2),p+1)
                self.assertEqual(f.call_count,1)
                self.assertIsNone(lp.cached_belly(cache,mod,ini,{**cfg2,'amounts':{'hips':3}}))
                ini.write_text('changed')
                self.assertIsNone(lp.cached_belly(cache,mod,ini,cfg2))
                self.assertEqual(f.call_count,1)

    def test_positions_only_cannot_write(self):
        with self.assertRaisesRegex(ValueError,'dry mode'):
            te.run('unused','write',positions_only=True)

    def test_mesh_update_preserves_order(self):
        class Mesh: pass
        a,b=Mesh(),Mesh(); q=np.arange(18).reshape(6,3)
        update_preview([(np.array([4,0,1]),a),(np.array([2,5]),b)],q)
        np.testing.assert_array_equal(a.points,q[[4,0,1]])
        np.testing.assert_array_equal(b.points,q[[2,5]])
        with self.assertRaises(ValueError): update_preview([],np.array([[np.nan,0,0]]))

    def test_debounce_policy(self):
        # Exercise the real GUI methods without Qt/OpenGL dependencies.
        ast_tree=ast.parse((ROOT/'thicc_tool'/'thicc_tool_gui.pyw').read_text())
        app=next(n for n in ast_tree.body if isinstance(n,ast.ClassDef) and n.name=='App')
        methods=[n for n in app.body if isinstance(n,ast.FunctionDef) and n.name in ('_live_pressed','_live_released','_live_changed')]
        namespace={}; exec(compile(ast.Module(body=methods,type_ignores=[]),'<gui-methods>','exec'),namespace)
        class Timer:
            active=False; starts=0
            def stop(self): self.active=False
            def start(self): self.active=True; self.starts+=1
        class Check:
            def isChecked(self): return True
        class Dummy:
            _live_dirty=False; _live_generation=0; _live_job=None; busy=False; _closing=False
        x=Dummy(); x._live_drag=set(); x._live_delay=Timer(); x.live_check=Check()
        press=namespace['_live_pressed']; release=namespace['_live_released']; changed=namespace['_live_changed']
        press(x,'slider'); release(x,'slider'); self.assertFalse(x._live_delay.active)
        press(x,'slider'); changed(x); changed(x); self.assertFalse(x._live_delay.active)
        release(x,'slider'); self.assertTrue(x._live_delay.active)
        press(x,'slider'); self.assertFalse(x._live_delay.active); changed(x); release(x,'slider'); self.assertEqual(x._live_delay.starts,2)

if __name__=='__main__': unittest.main()
