"""Spatially continuous displacement fade around protected arm geometry.

The fade is applied to *displacements*, never to source positions.  It is
computed from the source mesh so it is invariant under morph strength.
"""
import numpy as np
from scipy.spatial import cKDTree


def blend_at_arm_boundary(original, modified, arm_influence, allowed, height,
                          *, span_fraction=0.035):
    original = np.asarray(original)
    modified = np.asarray(modified)
    influence = np.asarray(arm_influence)
    allowed = np.asarray(allowed)
    locked = influence >= 0.01
    out = modified.copy()
    if not np.any(locked):
        print('Anatomical transition: no arm evidence; unchanged')
        return out

    # Exclude the whole upper arm region from sculpting, including separate
    # garments without useful blend weights. Spatial proximity alone is not
    # used as a permanent lock: it is a continuous transition into the torso.
    span = float(np.clip(height * span_fraction, 1.0, 6.0))
    tree = cKDTree(original[locked])
    distance = tree.query(original, k=1, workers=-1)[0]
    t = np.clip(distance / span, 0., 1.)
    ramp = t*t*(3.-2.*t)
    # Honor existing restrictions, but do not double-fade those already
    # applied by the field. Reapply a final safety envelope to every optional
    # postprocess (including garment adaptation and final regularization).
    final_factor = ramp
    final_factor[locked] = 0.
    delta = modified - original
    before = np.linalg.norm(delta, axis=1)
    out = original + delta * final_factor[:, None]
    changed = np.count_nonzero((before > 1e-5) & (final_factor < 0.999))
    print('Anatomical transition: width=%.3f cm, affected=%d, locked=%d, max before=%.4f cm' % (
        span, changed, np.count_nonzero(locked), before[locked].max(initial=0.)))
    return out
