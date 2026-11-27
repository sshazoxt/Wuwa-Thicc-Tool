import sys
import unittest
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'experiments'),str(root/'thicc_tool')]
from _overlap_causal_lab import weights, mapped_faces, stitch_width
class OverlapCausalTests(unittest.TestCase):
    def test_weights(self):
        np.testing.assert_allclose(weights(np.array([-1,0,1,2,3]),0,2),[0,0,.5,1,1])
    def test_mapping(self):
        np.testing.assert_array_equal(mapped_faces(np.array([2,4,9]),np.array([[2,4,9]])),[[0,1,2]])
        with self.assertRaises(ValueError):mapped_faces(np.array([2,4,9]),np.array([[2,4,10]]))
    def test_stitch(self):
        self.assertEqual(stitch_width(4,2,.5),3)
        self.assertEqual(stitch_width(np.nan,2,.5),2)
