import sys
import unittest
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'thicc_tool'))
from morphology_defaults import with_advanced_defaults, active_profile, switch_profile


class MorphologyDefaultsTests(unittest.TestCase):
    def test_fresh_legacy(self):
        p = with_advanced_defaults({}, 'Legacy')
        self.assertTrue(p['coupled_hips'])
        self.assertTrue(p['virtual_inguinal'])
        self.assertTrue(p['surface_rounding'])
        self.assertTrue(p['displacement_smoothing'])
        self.assertEqual(p['hip_profile'], {'upper':1.4,'lower':1.65,'peak':0.0})
        self.assertEqual(p['final_regularization'], {'enabled':True,'strength':.8,'tolerance':.65})
        self.assertEqual(p['deformation_field'], 'Continuous')
        self.assertEqual(p['bounce'], 'normal')
        self.assertEqual(p['surface_shading'], 'Original')
        self.assertEqual(p['silhouette_strength'], 1.0)
        self.assertNotIn('relative_silhouette', p)

    def test_explicit_saved_values_and_nested_gaps(self):
        saved = {'coupled_hips':False, 'displacement_smoothing':False,
                 'virtual_inguinal':False, 'surface_rounding':False,
                 'final_regularization':{'enabled':False,'strength':0.0},
                 'hip_profile':{'upper':1.2,'peak':-.1}, 'silhouette_strength':0,
                 'deformation_field':'Legacy','surface_shading':'Adaptive'}
        p = with_advanced_defaults(saved,'Legacy')
        for key in ('coupled_hips','displacement_smoothing','virtual_inguinal','surface_rounding'):
            self.assertIs(p[key],False)
        self.assertEqual(p['final_regularization'],{'enabled':False,'strength':0.0,'tolerance':.65})
        self.assertEqual(p['hip_profile'],{'upper':1.2,'lower':1.65,'peak':-.1})
        self.assertEqual(p['silhouette_strength'],0)
        self.assertEqual(p['deformation_field'],'Legacy')
        self.assertEqual(p['surface_shading'],'Adaptive')
        self.assertNotIn('tolerance',saved['final_regularization'])

    def test_direct_profile_is_unchanged(self):
        self.assertEqual(with_advanced_defaults({}, 'Direct Section'), {})
        p={'final_regularization':{'enabled':False,'strength':.2},'direct_depth':{'hips':0.0}}
        self.assertEqual(with_advanced_defaults(p,'Direct Section'),p)

    def test_switch_first_time_and_return(self):
        legacy=with_advanced_defaults({'preset':'pear','amounts':{'hips':2}},'Legacy')
        direct=switch_profile({'Legacy':legacy},legacy,'Direct Section')
        self.assertEqual(direct,{'preset':'pear','amounts':{'hips':2}})
        direct['amounts']['hips']=3
        direct['displacement_smoothing']=False
        self.assertEqual(legacy['amounts']['hips'],2)
        self.assertEqual(switch_profile({'Legacy':legacy,'Direct Section':direct},direct,'Legacy'),legacy)
        fresh=with_advanced_defaults(switch_profile({'Direct Section':direct},direct,'Legacy'),'Legacy')
        self.assertTrue(fresh['displacement_smoothing'])
        self.assertEqual(fresh['amounts']['hips'],3)

    def test_active_profile_top_level_wins(self):
        cfg={'engine_profiles':{'Legacy':{'coupled_hips':False,'hip_profile':{'peak':.1}}},'hip_profile':{'upper':1.1},'coupled_hips':True}
        result=with_advanced_defaults(active_profile(cfg,'Legacy'),'Legacy')
        self.assertTrue(result['coupled_hips'])
        self.assertEqual(result['hip_profile'],{'upper':1.1,'lower':1.65,'peak':.1})

    def test_gui_wiring(self):
        src=(ROOT/'thicc_tool'/'thicc_tool_gui.pyw').read_text(encoding='utf-8')
        ast.parse(src)
        for marker in ('QStyle.StandardPixmap.SP_MessageBoxWarning','self.direct_warning.setVisible(not legacy)',
                       'cfg=with_advanced_defaults(cfg,self.morph_engine.get())',
                       'target=switch_profile(self.engine_profiles,self.engine_profiles[old],engine)',
                       'self._load_morphology_values(active_profile(cfg,engine))'):
            self.assertIn(marker,src)

if __name__=='__main__': unittest.main()
