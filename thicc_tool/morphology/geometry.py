"""Shared mesh-plane intersection helper."""
import numpy as np

def contour(tri, z):
    zs = tri[:, :, 2]
    c = (zs.min(1) < z) & (zs.max(1) >= z)
    out = []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        A, B = tri[c, a], tri[c, b]
        za, zb = A[:, 2], B[:, 2]
        m = (za - z) * (zb - z) < 0
        f = (z - za[m]) / (zb[m] - za[m])
        out.append(A[m] + f[:, None] * (B[m] - A[m]))
        out.append(A[za == z])
    return np.concatenate(out)


