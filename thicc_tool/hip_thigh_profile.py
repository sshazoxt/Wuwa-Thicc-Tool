"""Experimental broad hip target, in the existing anatomical reference frame."""
import numpy as np
from scipy.interpolate import CubicSpline


def quintic(t):
    t = np.clip(t, 0., 1.)
    return t**3 * (10 + t*(-15 + 6*t))


def coupled_target(z, base, legacy, hip, waist, knee, amplitude, upper, lower, shift):
    z, base, legacy = (np.asarray(a, float) for a in (z, base, legacy))
    if not np.all(np.isfinite([hip, waist, knee, amplitude, upper, lower, shift])) or not knee < hip < waist:
        raise ValueError('Invalid hip profile landmarks')
    if not (.5 <= upper <= 2.5 and .5 <= lower <= 2.5 and -.3 <= shift <= .3 and amplitude >= 0):
        raise ValueError('Invalid hip profile controls')
    peak = hip + shift*(waist-hip if shift >= 0 else hip-knee)
    # Leave the waist and knee as hard target endpoints. Spread adjusts the
    # interior shape, not those anchors. Broad defaults avoid a narrow bump.
    lo, hi = knee, waist
    t = np.where(z >= peak, (z-peak)/(hi-peak), (peak-z)/(peak-lo))
    spread = np.where(z >= peak, upper, lower)
    # Rational remapping has finite derivatives at both ends.
    t = np.clip(t, 0, 1)
    u = t/(spread+(1-spread)*t)
    weight = 1-quintic(u)
    valid = np.isfinite(base) & (base > 0)
    if valid.sum() < 5 or not z[valid][0] <= peak <= z[valid][-1]:
        raise ValueError('Insufficient contour coverage for hip profile')
    # The existing no-hip field supplies the lower-leg baseline. Blend toward
    # a broad total growth target, not a second additive thigh expansion.
    baseline = CubicSpline(z[valid], legacy[valid], bc_type='natural')(np.clip(z,z[valid][0],z[valid][-1]))
    baseline = np.maximum(baseline, 0)
    # Upper endpoint fades to zero; low endpoint retains the leg field.
    baseline *= 1-quintic((z-peak)/(hi-peak))
    target = baseline*(1-weight) + amplitude*weight
    target = np.where(z >= hi, 0., target)
    return target, peak
