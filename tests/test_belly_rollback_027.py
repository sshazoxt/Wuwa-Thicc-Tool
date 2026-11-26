import sys, unittest
from pathlib import Path
from unittest.mock import Mock
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'thicc_tool'))
from morphology.belly import field, basic_parameters

class BellyRollbackTests(unittest.TestCase):
    def test_production_delegates_to_experiment_32(self):
        ctrl=Mock(); expected=np.arange(9).reshape(3,3); ctrl.belly.return_value=expected
        for u in (0,.25,.5,.75,1):
            params=basic_parameters(u)
            self.assertIs(field(ctrl,**params),expected)
            ctrl.belly.assert_called_with(**params)
    def test_basic_monotonic(self):
        rows=np.array([list(basic_parameters(u).values()) for u in np.linspace(0,1,101)])
        self.assertTrue(np.all(np.diff(rows,axis=0)>=0))
        np.testing.assert_allclose(rows[-1],[.66,2.5,1.5,.1])
