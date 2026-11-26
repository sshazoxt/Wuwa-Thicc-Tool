import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'thicc_tool'))
from morphology.experimental_apply import snapshot,write_buffers,belly_vectors
import morphology.experimental_apply as ea

class BellyWrites(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.mod=Path(self.temp.name); self.m=self.mod/'Meshes'; self.m.mkdir()
        self.p=np.array([[0,0,0],[1,0,0],[0,1,0]],dtype='<f4')
        self.v=np.zeros((3,8),dtype=np.int8); self.v[:,0]=127; self.v[:,6]=127; self.v[:,3]=42; self.v[:,7]=13
        self.p.tofile(self.m/'Position.buf'); self.v.tofile(self.m/'Vector.buf')
        np.array([0,1,2],dtype='<u4').tofile(self.m/'Index.buf')
    def test_apply_twice_preserves_original(self):
        s=snapshot(self.mod); q=self.p+1; v=self.v.copy(); v[:,1]=5
        s=write_buffers(self.mod,s,q,v)
        self.assertEqual((self.m/'Position.buf.orig').read_bytes(),self.p.tobytes())
        self.assertEqual((self.m/'Vector.buf.orig').read_bytes(),self.v.tobytes())
        write_buffers(self.mod,s,self.p+2,v)
        self.assertEqual((self.m/'Position.buf.orig').read_bytes(),self.p.tobytes())
        self.assertEqual((self.m/'Vector.buf.orig').read_bytes(),self.v.tobytes())
        self.assertEqual((self.m/'Position.buf').read_bytes(),(self.p+2).tobytes())
    def test_changed_source_rejected(self):
        s=snapshot(self.mod); (self.m/'Index.buf').write_bytes(b'changed')
        with self.assertRaises(RuntimeError): write_buffers(self.mod,s,self.p+1,self.v)
        self.assertFalse((self.m/'Position.buf.orig').exists())
    def test_incomplete_backup_rejected(self):
        self.p.tofile(self.m/'Position.buf.orig')
        with self.assertRaises(RuntimeError): snapshot(self.mod)
    def test_write_failure_rollback(self):
        s=snapshot(self.mod); real=ea.os.replace
        def fail_second(src,dst):
            if Path(dst).name=='Vector.buf': raise OSError('simulated locked file')
            return real(src,dst)
        with patch.object(ea.os,'replace',side_effect=fail_second):
            with self.assertRaises(OSError): write_buffers(self.mod,s,self.p+1,self.v)
        self.assertEqual(snapshot(self.mod),s)
        self.assertFalse(list(self.m.glob('.thicc-belly-*')))
    def test_vector_modes(self):
        q=self.p.copy(); q[2,2]=.2; faces=np.array([[0,1,2]])
        np.testing.assert_array_equal(belly_vectors(self.p,q,self.v,faces,'Original'),self.v)
        v=belly_vectors(self.p,q,self.v,faces,'Adaptive')
        np.testing.assert_array_equal(v[:2],self.v[:2]); np.testing.assert_array_equal(v[:,[3,7]],self.v[:,[3,7]])
        self.assertFalse(np.array_equal(v[2,4:7],self.v[2,4:7]))
if __name__=='__main__': main()
