import unittest, tempfile, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'thicc_tool'))
from experiment_runner import experiment_details, experiment_tooltip, discover
class ExperimentDetails(unittest.TestCase):
    def test_all_scripts_have_metadata(self):
        for p in discover(Path(__file__).resolve().parents[1]/'experiments'):
            with self.subTest(script=p.name):
                self.assertTrue({'description','objective','visual','batch','writes'} <= experiment_details(p).keys())
    def test_no_execution(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.py'; p.write_text("EXPERIMENT_INFO={'description':'hello','objective':'test'}\nraise RuntimeError('must not execute')")
            self.assertIn('Objective: test',experiment_tooltip(p))
    def test_bad_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.py'; p.write_text('EXPERIMENT_INFO = dangerous()')
            self.assertIn('unavailable',experiment_tooltip(p))
