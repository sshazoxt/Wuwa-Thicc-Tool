import sys, tempfile, unittest, types
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'thicc_tool'))
from experiment_worker import prepare_snapshot, install_capture

class ExperimentsTests(unittest.TestCase):
    def test_snapshot_isolated_and_reused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'mod'; (root/'Meshes').mkdir(parents=True)
            f=root/'Meshes'/'Position.buf'; f.write_bytes(b'original')
            (root/'mod.ini').write_text('ini'); (root/'thicc.json').write_text('{}')
            target=Path(d)/'snapshot'; prepare_snapshot(root,target)
            f.write_bytes(b'changed'); prepare_snapshot(root,target)
            self.assertEqual((target/'Meshes'/'Position.buf').read_bytes(),b'original')
            (target/'Meshes'/'Position.buf').write_bytes(b'test')
            self.assertEqual(f.read_bytes(),b'changed')
    def test_capture_consecutive_and_close(self):
        class Plotter:
            def __init__(self,**kw): self.kw=kw; self.window_size=(1500,900); self.closed=False
            def show(self,**kw):
                self.show_kw=kw; Path(kw['screenshot']).write_bytes(b'png')
            def close(self):self.closed=True
        with tempfile.TemporaryDirectory() as d, patch.dict(sys.modules,{'pyvista':types.SimpleNamespace(Plotter=Plotter)}):
            install_capture(Path(d),'test'); a=Plotter(); a.show(); b=Plotter(); b.show()
            self.assertTrue(a.kw['off_screen']); self.assertTrue(a.closed and b.closed)
            self.assertFalse(a.show_kw['interactive']); self.assertEqual(a.show_kw['window_size'],(3000,1800))
            self.assertEqual(sorted(p.name for p in Path(d).glob('*.png')),['test_01.png','test_02.png'])
    def test_capture_closes_on_failure(self):
        class Plotter:
            def __init__(self,**kw):self.window_size=(10,10); self.closed=False
            def show(self,**kw):raise ValueError('render')
            def close(self):self.closed=True
        with tempfile.TemporaryDirectory() as d, patch.dict(sys.modules,{'pyvista':types.SimpleNamespace(Plotter=Plotter)}):
            install_capture(Path(d),'test'); a=Plotter()
            with self.assertRaises(ValueError):a.show()
            self.assertTrue(a.closed)
if __name__=='__main__':unittest.main()
