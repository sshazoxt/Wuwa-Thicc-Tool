import sys
from pathlib import Path
import unittest
import numpy as np
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'thicc_tool'),str(ROOT/'experiments')]
import _hip_root_lab as lab
from morphology.calibration import fixed_core_outline
from morphology import calibration
import thicc_edit as te

class HipRootTests(unittest.TestCase):
    def test_dedup_by_coordinates_not_ids_or_orientation(self):
        p=np.array([[0,0,0],[1,0,0],[0,1,1],[0,0,0],[1,0,0],[0,1,1],[1,1,1]],float)
        t=np.array([[0,1,2],[5,4,3],[0,1,6]])
        np.testing.assert_array_equal(lab.unique_faces(p,t),t[[0,2]])
        np.testing.assert_array_equal(t,[[0,1,2],[5,4,3],[0,1,6]])
    def test_partition_identical_geometry(self):
        p=[]
        for x in range(11): p.extend([[x,0,0],[x,1,0],[x,0,2]])
        p=np.asarray(p,float); t=np.arange(len(p)).reshape(-1,3); z=[1.]
        a=fixed_core_outline(p,t,z); b=fixed_core_outline(p,np.concatenate([t[1::2],t[::2]]),z)
        q=p.copy(); q[:,0]*=1.2
        np.testing.assert_allclose(a(p),b(p)); np.testing.assert_allclose(a(q),b(q))
    def test_experiment_config_preserves_roles_and_disables_post_smoothing(self):
        old={'skin':['pelvis','legs'],'anatomy':['face','pelvis'],'freeze':['hair'],'coupled_hips':True,'final_regularization':{'enabled':True},'belly_morphology':{'advanced':True,'depth':.7}}
        c=lab.isolated(old,hips=3.98)
        self.assertEqual(c['skin'],old['skin']); self.assertEqual(c['anatomy'],old['anatomy']); self.assertEqual(c['freeze'],old['freeze'])
        self.assertFalse(c['coupled_hips']); self.assertFalse(c['final_regularization']['enabled']); self.assertEqual(c['belly_morphology']['amount'],0.)
        self.assertEqual(c['amounts'],dict(hips=3.98,thighs=0.,butt=0.,calves=0.)); self.assertTrue(old['coupled_hips'])
    def test_calibration_override_restores_on_exception(self):
        old=calibration.update_correction
        with self.assertRaises(RuntimeError):
            with lab.calibration_trial(12.):
                self.assertEqual(calibration.update_correction(np.array([6.]),np.ones(1),np.array([10.]))[0],12.)
                raise RuntimeError('trial error')
        self.assertIs(calibration.update_correction,old)
    def test_response_probes_restore_field(self):
        class Sculpt:
            hip=None
            def field_ref(self,x,y,z): return np.ones(len(x))*self.hip[1][0]*.5,np.zeros(len(x))
        sc=Sculpt(); p=np.array([[2.,0.,1.],[3.,0.,1.]])
        response=lab.estimate_response(sc,p,np.array([1.]),lambda q:np.array([q[:,0].max()]),np.array([3.]),np.array([8.]))
        self.assertIsNone(sc.hip); np.testing.assert_allclose(response['required'],[16.]); np.testing.assert_allclose(response['cap'],[20.])
    def test_measurement_reference_clone_restores(self):
        original=te.run
        with lab.measurement_reference(te,'active'):
            self.assertIsNot(te.run,original)
            self.assertEqual(te.run.__code__.co_filename,'<experimental measurement reference>')
        self.assertIs(te.run,original)
    def test_021_archive_compiles(self):
        p=ROOT/'experiments'/'_engine_021.txt'; compile(p.read_bytes(),str(p),'exec')
    def test_active_face_membership(self):
        t=np.array([[0,1,2],[1,2,3],[3,4,5]])
        np.testing.assert_array_equal(lab.subset_indices(t,np.array([[3,2,1]])),[False,True,False])
if __name__=='__main__': unittest.main()
