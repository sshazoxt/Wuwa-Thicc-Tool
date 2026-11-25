"""Independent geometric/WWMI evidence consumed by Thicc Tool auto roles.

Conservative guard: fragmented draws are NOT automatically promoted to skin.
A veto is applied only to weak automatic guesses, never manual settings.
"""
from __future__ import annotations
import numpy as np


def _island_evidence(triangles, local_geometry=None):
    """Return connected triangle island count and dominant area fraction.

    Uses shared vertex indices, not vertex coordinates, so coincident but
    disconnected garment pieces are not merged. Iterative union-find.
    """
    triangles=np.asarray(triangles,dtype=np.int64).reshape(-1,3)
    if not len(triangles): return 0,0.0
    vertices, inv=np.unique(triangles,return_inverse=True) if local_geometry is None else local_geometry
    faces=inv.reshape(-1,3)
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    a=faces.ravel(); b=faces[:,[1,2,0]].ravel()
    _,labels=connected_components(coo_matrix((np.ones(len(a),dtype=np.int32),(a,b)),shape=(len(vertices),len(vertices))).tocsr(),directed=False)
    _,counts=np.unique(labels[faces[:,0]],return_counts=True)
    return len(counts),float(counts.max()/len(faces))



def welded_island_evidence(P, triangles, relative_tolerance=1e-7, local_geometry=None, points=None):
    """Diagnostic-only connectivity after welding coincident vertex positions.

    Does not modify buffers, triangle indices, or role decisions. The tiny
    model-relative tolerance avoids joining distinct nearby garment layers.
    """
    faces = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
    if not len(faces):
        return 0, 0.0
    vertex_ids, inverse = np.unique(faces, return_inverse=True) if local_geometry is None else local_geometry
    points = np.asarray(P)[vertex_ids] if points is None else points
    extent = np.ptp(points, axis=0)
    scale = max(float(np.max(extent)), 1e-9)
    tolerance = max(scale * relative_tolerance, 1e-10)
    # Local origin reduces quantization errors for meshes far from (0, 0, 0).
    coords = np.rint((points - points.min(axis=0)) / tolerance).astype(np.int64)
    _, welded_ids = np.unique(coords, axis=0, return_inverse=True)
    welded_faces = welded_ids[inverse].reshape(-1, 3)
    # _island_evidence accepts arbitrary vertex IDs, including welded IDs.
    return _island_evidence(welded_faces)

def assess_auto_skin(P, draws, verts, tris, suggestions, manual_roles,
                     draw_meta=None, structure=None):
    """Conservative 1.9C automatic role validation.

    Fragmentation by indices alone cannot veto skin when exact geometric
    welding establishes a continuous surface. Conversely, welding never
    creates an automatic skin suggestion. A contradictory case remains
    undecided unless independently supported by a skin-like name and a
    body-spanning geometry; manually configured roles are always immutable.
    """
    out = {}
    suggestions = set(suggestions)
    manual_roles = set(manual_roles)
    for name in draws:
        faces = tris(name)
        islands, dominant = _island_evidence(faces)
        fragmented = bool(islands >= 12 and dominant < .35 and len(faces) >= 100)
        welded_islands, welded_dominant = None, None
        if fragmented and name in suggestions:
            try:
                welded_islands, welded_dominant = welded_island_evidence(P, faces)
            except (ValueError, IndexError, FloatingPointError, OverflowError):
                pass
        welded_continuous = bool(welded_islands is not None and
                                 welded_islands <= 2 and welded_dominant >= .90)
        # Name evidence is intentionally required for the contradictory case:
        # garment layers can also be welded into a single continuous surface.
        # Generic height-based suggestions must remain vetoed.
        import re
        named_skin = bool(re.search(r'(?:skin|body|nude|basebody)', name, re.I))
        can_rescue = bool(fragmented and welded_continuous and named_skin)
        veto = bool(name in suggestions and name not in manual_roles and
                    fragmented and not can_rescue)
        out[name] = dict(
            islands=islands, dominant_fraction=dominant,
            fragmented=fragmented, veto_auto_skin=veto,
            welded_islands=welded_islands,
            welded_dominant_fraction=welded_dominant,
            welded_continuous=welded_continuous,
            index_fragmentation_rescued=can_rescue,
            evidence=('index fragmentation contradicted by welded continuity + skin name'
                      if can_rescue else 'fragmented topology' if fragmented
                      else 'not decisive'),
            manually_configured=name in manual_roles)
    return out
