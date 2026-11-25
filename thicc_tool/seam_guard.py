"""Protect coincident moving/frozen interfaces without changing topology."""
import numpy as np
from scipy.spatial import cKDTree

class SeamGuard:
    def __init__(self, points, frozen, allowed, height):
        self.width = float(height) * 0.02
        self.tree = None
        self.count = 0
        frozen = np.unique(np.asarray(frozen, dtype=np.int64))
        ids = np.flatnonzero(allowed > 0)
        if not len(frozen) or not len(ids) or self.width <= 0:
            return
        distance, _ = cKDTree(points[frozen]).query(points[ids], k=1)
        matched = ids[distance <= max(float(height)*1e-6, 1e-8)]
        self.count = len(matched)
        if self.count:
            self.tree = cKDTree(np.unique(points[matched], axis=0))

    def __call__(self, points):
        if self.tree is None:
            return np.ones(len(points))
        d, _ = self.tree.query(points, k=1, distance_upper_bound=self.width)
        t = np.clip(d / self.width, 0., 1.)
        return t*t*t*(10 + t*(-15 + 6*t))
