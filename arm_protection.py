"""Optional conservative arm mask; uses existing arm evidence only."""
import numpy as np

def mobility(arm_weight):
    w = np.clip(np.asarray(arm_weight, dtype=float), 0., 1.)
    if not np.isfinite(w).all():
        raise ValueError('Non-finite arm weights')
    t = np.clip(w / .65, 0., 1.)
    q = t**3 * (10. + t * (-15. + 6.*t))
    # Never weaken existing protection, including at low evidence.
    return np.minimum(1.-w, 1.-q)
