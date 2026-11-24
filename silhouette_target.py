"""Experimental relative silhouette targets; no vertex editing."""
import numpy as np


def relative_target(z, base, legacy, hip_z, waist_z, reference_hip, strength=1.0):
    z, base, legacy = map(lambda a: np.asarray(a, dtype=float), (z, base, legacy))
    if not np.isfinite(strength) or not 0 <= strength <= 2:
        raise ValueError('Silhouette strength must be in [0, 2]')
    if not np.isfinite(hip_z + waist_z + reference_hip) or reference_hip <= 0 or waist_z <= hip_z:
        raise ValueError('Invalid silhouette landmarks')
    valid = np.isfinite(base) & (base > 0)
    near = valid & (np.abs(z-hip_z) <= 3)
    if near.sum() < 3:
        raise ValueError('Insufficient hip contour coverage')
    scale = float(np.median(base[near])) / reference_hip
    t = np.clip((z-hip_z)/(waist_z-hip_z), 0, 1)
    fade = 1-t**3*(10+t*(-15+6*t))
    return legacy * scale * strength * fade, scale
