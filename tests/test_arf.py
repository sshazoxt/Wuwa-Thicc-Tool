"""Headless tests; run with Python from the repository root."""
import contextlib, io, pathlib, sys, tempfile, unittest
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'thicc_tool'))
import anatomical_reconstruction as a
import thicc_edit as te
import viewer3d as viewer

class ReconstructionTests(unittest.TestCase):
    def test_default_and_unknown(self):
        text='''[Constants]
global persist $variant = 0
global $selected = 0
[Present]
if $variant == 0
 $selected = 1
else
 $selected = 2
endif
[TextureOverrideComponent3]
if $mod_enabled
 if ResourceMergedSkeleton !== null
  if $selected == 1
   ; Draw body A
   drawindexed = 3, 0, 0
  elif $selected == 2
   ; Draw body B
   drawindexed = 3, 3, 0
  endif
  if $unknown
   ; Draw unknown A
   drawindexed = 3, 6, 0
  else
   ; Draw unknown B
   drawindexed = 3, 9, 0
  endif
  ; Draw hidden
  ; drawindexed = 3, 12, 0
 endif
endif
[ResourceTexture0]
[ResourceTexture0]
'''
        with tempfile.TemporaryDirectory() as d:
            path=pathlib.Path(d)/'mod.ini';path.write_text(text);meta={};te.parse_draws(path,metadata=meta);r=a.reconstruct(path,meta)
            self.assertEqual(r['active'],['body A']);self.assertEqual(r['uncertain'],['unknown A','unknown B'])
    def test_expression_restricted(self):
        self.assertIs(a.expression('__import__("os")',{}),a.UNKNOWN)
        self.assertEqual(a.expression('$a == 1 && $b == 0',{'$a':1,'$b':0}),True)
    def test_preview_geometry(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);(p/'Meshes').mkdir();ini=p/'mod.ini';ini.write_text('[TextureOverrideComponent3]\n; Draw body\ndrawindexed = 3, 0, 0\n');o=np.array([[0,0,0],[1,0,0],[0,1,0]],dtype='<f4');n=o+1
            o.tofile(p/'Meshes/Position.buf');o.tofile(p/'Meshes/Position.buf.orig');np.array([0,1,2],dtype='<u4').tofile(p/'Meshes/Index.buf')
            data=viewer.geometry(d,ini,['body'],mode='Comparison',preview_positions=n);np.testing.assert_array_equal(data[0][1],n);np.testing.assert_array_equal(data[0][3],o);np.testing.assert_array_equal(np.fromfile(p/'Meshes/Position.buf',dtype='<f4').reshape(-1,3),o)
    def test_conditional_diagnostic(self):
        z=np.linspace(0,100,200);p=np.column_stack((np.tile([-2,2],100),np.zeros(200),z));faces={'lower':np.arange(150).reshape(-1,3),'torso':np.arange(150,198).reshape(-1,3)};comp={n:3 for n in faces};ref={'active':list(faces),'uncertain':[],'notes':[]}
        def bones(*args):raise ValueError('no bones')
        ev={n:{'role':'skin','contributions':{'naming':5}} for n in faces}
        out=io.StringIO()
        with contextlib.redirect_stdout(out):a.diagnose(p,faces,comp,'',{},ev,'',bones,ref)
        self.assertIn('Skipped: lower-body coverage present',out.getvalue())
        ev['lower']['role']='ambiguous';out=io.StringIO()
        with contextlib.redirect_stdout(out): recovered=a.diagnose(p,faces,comp,'',{},ev,'',bones,ref)
        self.assertEqual(out.getvalue().count('===== ARF CONDITIONAL RECOVERY'),1);self.assertEqual(recovered,['lower']);self.assertEqual(ev['lower']['role'],'ambiguous')
        with contextlib.redirect_stdout(io.StringIO()): recovered=a.diagnose(p,faces,comp,'',{},ev,'',bones,ref,blocked={'lower'})
        self.assertEqual(recovered,[])
        ev['lower']['contributions']['naming']=-5
        with contextlib.redirect_stdout(io.StringIO()): recovered=a.diagnose(p,faces,comp,'',{},ev,'',bones,ref)
        self.assertEqual(recovered,[])
if __name__=='__main__':unittest.main()
