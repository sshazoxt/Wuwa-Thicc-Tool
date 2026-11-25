"""Broad-scale anatomical displacement regularization for WWMI meshes.

Fits a smooth longitudinal/angular displacement field rather than performing
vertex-neighbour Laplacian smoothing. Operates on displacement from original.
"""
import numpy as np
from scipy.ndimage import gaussian_filter


def regularize(p, new, faces, allow, guard, strength=0.35, tolerance=0.20, iterations=8):
    p = np.asarray(p, dtype=np.float64)
    new = np.asarray(new, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    n = len(p)
    strength = float(np.clip(strength, 0, 1))
    tolerance = float(np.clip(tolerance, 0, 1))
    if strength <= 0 or n == 0 or not len(f):
        return new
    f = f[(f >= 0).all(1) & (f < n).all(1)]
    if not len(f):
        return new
    d = new - p
    magnitude = np.linalg.norm(d, axis=1)
    mobility = np.clip(np.asarray(allow, dtype=float).reshape(-1), 0, 1) * np.clip(np.asarray(guard, dtype=float).reshape(-1), 0, 1)
    active = (mobility > .02) & (magnitude > 1e-5)
    if active.sum() < 80:
        print('Final profile regularizer: insufficient movable vertices; unchanged')
        return new
    # Work separately on left/right anatomical regions; the midline is never
    # bridged. Coordinates and length scales are learned from each mesh.
    z = p[:, 2]
    mid = float(np.median(p[active, 0]))
    dz = np.zeros_like(d)
    coverage = np.zeros(n, dtype=bool)
    for side in (-1, 1):
        side_mask = active & ((p[:, 0] - mid) * side > 0)
        ids = np.flatnonzero(side_mask)
        if len(ids) < 60:
            continue
        # Only model the anatomical portion carrying the bulk of the change;
        # distant, barely changed vertices are not dragged into the field.
        zs = z[ids]
        lo, hi = np.percentile(zs, [1, 99])
        span = max(float(hi - lo), 1e-4)
        # At each height use a robust centerline from the original mesh.
        # A smoothed centerline prevents angular bins twisting with Z.
        bins_z = 96
        zz = np.linspace(lo, hi, bins_z)
        iz = np.clip(np.rint((zs-lo)/span*(bins_z-1)).astype(int), 0, bins_z-1)
        xc = np.bincount(iz, weights=p[ids,0], minlength=bins_z)
        yc = np.bincount(iz, weights=p[ids,1], minlength=bins_z)
        counts = np.bincount(iz, minlength=bins_z).astype(float)
        sx = gaussian_filter(xc, 5, mode='nearest') / np.maximum(gaussian_filter(counts, 5, mode='nearest'), 1e-8)
        sy = gaussian_filter(yc, 5, mode='nearest') / np.maximum(gaussian_filter(counts, 5, mode='nearest'), 1e-8)
        cx = np.interp(zs, zz, sx)
        cy = np.interp(zs, zz, sy)
        angle = np.mod(np.arctan2(p[ids,1]-cy, p[ids,0]-cx), 2*np.pi)
        bins_a = 64
        ia = np.mod(np.floor(angle/(2*np.pi)*bins_a).astype(int), bins_a)
        # Weighted 2-D field; spatial smoothing extends across broad height
        # intervals and full angular cross-sections, not individual vertices.
        weights = np.maximum(mobility[ids], .05)
        grid_w = np.zeros((bins_z, bins_a))
        np.add.at(grid_w, (iz,ia), weights)
        # ~9% of changed vertical span; stronger settings allow wider curves.
        sigma_z = 5.0 + 5.0*strength
        sigma_a = 2.0 + 2.5*strength
        smooth_w = gaussian_filter(grid_w, (sigma_z,sigma_a), mode=('nearest','wrap'))
        predicted = np.zeros((len(ids),3))
        for axis in range(3):
            grid = np.zeros_like(grid_w)
            np.add.at(grid, (iz,ia), weights*d[ids,axis])
            smooth = gaussian_filter(grid, (sigma_z,sigma_a), mode=('nearest','wrap')) / np.maximum(smooth_w,1e-8)
            # Bilinear interpolation removes bin stair-stepping.
            zf = np.clip((zs-lo)/span*(bins_z-1),0,bins_z-1.000001)
            af = angle/(2*np.pi)*bins_a
            z0 = np.floor(zf).astype(int); z1 = np.minimum(z0+1,bins_z-1)
            a0 = np.floor(af).astype(int)%bins_a; a1=(a0+1)%bins_a
            tz = zf-z0; ta = af-np.floor(af)
            predicted[:,axis] = ((1-tz)*((1-ta)*smooth[z0,a0]+ta*smooth[z0,a1])+
                                    tz*((1-ta)*smooth[z1,a0]+ta*smooth[z1,a1]))
        # Tolerance means retain minor local detail. At zero tolerance, all
        # eligible displacement is attracted toward the broad smooth profile.
        residual = predicted - d[ids]
        rms = np.sqrt(np.mean(np.sum(residual*residual,axis=1)))
        threshold = tolerance*rms
        amplitude = np.linalg.norm(residual,axis=1)
        gate = np.maximum(amplitude-threshold,0)/np.maximum(amplitude,1e-12)
        # Soft protection: avoid hard 0/1 discontinuities near guards.
        dz[ids] = residual * (strength*mobility[ids]*gate)[:,None]
        coverage[ids] = True
    if not coverage.any():
        return new
    # Prevent introducing inverted faces compared with the pre-regularized
    # mesh. Do not claim to repair pre-existing inversions.
    n0 = np.cross(p[f[:,1]]-p[f[:,0]],p[f[:,2]]-p[f[:,0]])
    nb = np.cross(new[f[:,1]]-new[f[:,0]],new[f[:,2]]-new[f[:,0]])
    baseline = np.einsum('ij,ij->i',n0,nb) < 0
    # Local safety backtracking: damp only vertices touching newly inverted
    # faces, instead of shrinking the entire anatomical correction.
    scales = np.ones(n, dtype=float)
    for _ in range(15):
        candidate = new + scales[:,None]*dz
        nc = np.cross(candidate[f[:,1]]-candidate[f[:,0]],candidate[f[:,2]]-candidate[f[:,0]])
        extra = (np.einsum('ij,ij->i',n0,nc)<0) & ~baseline
        if np.isfinite(candidate).all() and not extra.any():
            correction = np.linalg.norm(scales[:,None]*dz,axis=1)
            print('Final profile regularizer: eligible=%d, strength=%.2f, tolerance=%.2f, locally limited=%d, max correction=%.4f, new flips=0' % (coverage.sum(),strength,tolerance,np.count_nonzero(scales[coverage]<.999),correction.max()))
            return candidate
        if not extra.any():
            break
        bad = np.unique(f[extra].ravel())
        scales[bad] *= .5
    # Conservative global fallback if local limits alone are insufficient.
    for k in range(13):
        scale = 0.5 ** k
        candidate = new + scale*scales[:,None]*dz
        nc = np.cross(candidate[f[:,1]]-candidate[f[:,0]],candidate[f[:,2]]-candidate[f[:,0]])
        extra = (np.einsum('ij,ij->i',n0,nc)<0) & ~baseline
        if np.isfinite(candidate).all() and not extra.any():
            correction = np.linalg.norm(scale*scales[:,None]*dz,axis=1)
            print('Final profile regularizer: eligible=%d, strength=%.2f, tolerance=%.2f, fallback scale=%.5f, max correction=%.4f, new flips=0' % (coverage.sum(),strength,tolerance,scale,correction.max()))
            return candidate
    print('Final profile regularizer rejected: new flipped faces cannot be prevented')
    return new
