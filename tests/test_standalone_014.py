import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'thicc_tool'))
from anatomical_reconstruction import reconstruct

class StandaloneTests(unittest.TestCase):
    def run_ini(self, text):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'mod.ini'; p.write_text(text)
            meta={str(i):{'line':i} for i,s in enumerate(text.splitlines(),1) if s.strip().startswith('drawindexed')}
            return reconstruct(p,meta)
    def test_external_gate(self):
        r=self.run_ini('[Constants]\nglobal persist $shoe = 1\n[TextureOverrideComponent4]\nif $\\Other\\Master\\selector == 3\nif $shoe == 1\ndrawindexed = 3,0,0\nelse\ndrawindexed = 3,3,0\nendif\nendif\n')
        self.assertEqual(len(r['active']),1); self.assertFalse(r['uncertain'])
    def test_key_bound_external(self):
        r=self.run_ini('[KeySwap]\nkey = K\n$\\Other\\selector = 0,1\n[TextureOverrideComponent4]\nif $\\Other\\selector == 1\ndrawindexed = 3,0,0\nendif\n')
        self.assertFalse(r['active']); self.assertEqual(len(r['uncertain']),1)
    def test_partial_gate(self):
        r=self.run_ini('[TextureOverrideComponent4]\ndrawindexed = 3,0,0\nif $\\Other\\selector == 1\ndrawindexed = 3,3,0\nendif\n')
        self.assertEqual(len(r['active']),1); self.assertEqual(len(r['uncertain']),1)
    def test_alternative_gate(self):
        r=self.run_ini('[TextureOverrideComponent4]\nif $\\Other\\selector == 1\ndrawindexed = 3,0,0\nelse\ndrawindexed = 3,3,0\nendif\n')
        self.assertFalse(r['active']); self.assertEqual(len(r['uncertain']),2)
    def test_local_condition(self):
        r=self.run_ini('[Constants]\nglobal $switch = 0\n[TextureOverrideComponent4]\nif $switch == 1\ndrawindexed = 3,0,0\nendif\n')
        self.assertFalse(r['active']); self.assertFalse(r['uncertain'])
if __name__=='__main__': unittest.main()
