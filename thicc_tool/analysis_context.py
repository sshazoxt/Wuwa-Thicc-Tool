"""Per-engine-run shared original geometry. Never reuse across buffer revisions.
Arrays are borrowed read-only by convention; no detector may mutate them.
"""
from dataclasses import dataclass
from functools import cached_property
import numpy as np

@dataclass(frozen=True)
class AnalysisOptions:
    # Reserved for future Debug Mode; normal analysis never enables this.
    debug: bool = False

class PartGeometry:
    def __init__(self, context, name):
        self.context, self.name = context, name
    @cached_property
    def triangles(self):
        return self.context._faces(self.name)
    @cached_property
    def vertex_ids(self):
        return np.unique(self.triangles)
    @cached_property
    def local_triangles(self):
        return np.searchsorted(self.vertex_ids, self.triangles)
    @cached_property
    def points(self):
        return self.context.positions[self.vertex_ids]
    @cached_property
    def z_info(self):
        z = self.points[:, 2]
        return float(z.min()), float(z.max()), len(z)

class AnalysisContext:
    def __init__(self, positions, faces, names=None, options=None):
        self.positions = positions
        self.options = options or AnalysisOptions()
        self._faces = faces if callable(faces) else faces.__getitem__
        self._parts = {n: PartGeometry(self, n) for n in (names if names is not None else faces)}
        self._bones = {}
        self._unions = {}
    def part(self, name):
        return self._parts[name]
    def triangles(self, name):
        return self.part(name).triangles
    def vertex_ids(self, name):
        return self.part(name).vertex_ids
    def union(self, names):
        # Unique vertex IDs are independent of draw order and multiplicity.
        key = tuple(sorted(set(names)))
        if key not in self._unions:
            self._unions[key] = np.unique(np.concatenate([self.vertex_ids(n) for n in key])) if key else np.empty(0, dtype=np.int64)
        return self._unions[key]
    def bones(self, path, count, loader):
        key = (path, count, loader)
        if key not in self._bones:
            self._bones[key] = loader(path, count)
        return self._bones[key]
