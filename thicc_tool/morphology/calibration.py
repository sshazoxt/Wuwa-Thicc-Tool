import numpy as np

def torso_half(xabs, gap=2.5):
    """Half-width of the body cross-section that is connected to the midline:
    walk outwards over the sorted |x| values and stop at the first gap (arms
    hanging beside the waist or thighs are separated by one)."""
    v = np.sort(xabs)
    if len(v) == 0:
        return np.nan
    d = np.diff(v)
    br = np.nonzero(d > gap)[0]
    return v[br[0]] if len(br) else v[-1]



def fixed_core_outline(original, triangles, zs, contour=None):
    """Keep original section membership throughout X-only hip calibration.

    contour() enumerates intersections in triangle/edge order, determined by Z.
    Calibration changes only X; therefore these sample identities are stable.
    The original cutoff and first-gap filter are applied once, not after growth.
    """
    tri = original[triangles]
    if contour is None:
        from .geometry import contour
    masks = []
    for z in zs:
        x = np.abs(contour(tri, z)[:, 0])
        mask = x < 26.0
        if np.count_nonzero(mask) >= 6:
            mask &= x <= torso_half(x[mask]) + 1e-8
        else:
            mask[:] = False
        masks.append(mask)

    def outline(Q):
        tri = Q[triangles]
        out = np.full(len(zs), np.nan)
        for i, z in enumerate(zs):
            x = np.abs(contour(tri, z)[:, 0])
            mask = masks[i]
            if len(x) != len(mask):
                raise RuntimeError("Hip calibration section correspondence changed")
            # Preserve the legacy baseline even when its core has fewer than
            # six points: the six-point gate applies to the original section.
            if np.any(mask):
                out[i] = np.max(x[mask])
        return out

    return outline


def update_correction(Hc, env, err):
    return np.clip(Hc + 1.3 * env * err, -1.0, 6.0)

def smooth_correction(Hc, g, env):
    return np.convolve(np.pad(Hc, 3, mode="edge"), g, "valid") * env


def calibrate(sc, PR, skin_tri, L, amounts, cfg, REF, HIP_ENV, HIP_TARGET, smoothstep, *, observer=None, outline_factory=None, zero_calibration=False):
    """Calibrate the production hip field using fixed original contour membership.

    An optional outline factory and observer support read-only experiments.
    """
    sc.legacy_hip_spline = None
    N = len(PR)
    # hip outline calibration (reference frame): silhouette growth -> target
    coupled = bool(cfg.get("coupled_hips", False)) and amounts["hips"] > 0
    zs = np.arange(REF["knee"] if coupled else 56.0, 118.001, 1.0)
    a, b, c, d = HIP_ENV
    env = smoothstep(a, b, zs) * (1.0 - smoothstep(c, d, zs))
    T0 = np.interp(zs, [k[0] for k in HIP_TARGET], [k[1] for k in HIP_TARGET])
    wt = smoothstep(72.0, 82.0, zs)
    lower_amount = max(amounts["thighs"], 0.35 * amounts["hips"])
    tgt = T0 * ((1 - wt) * lower_amount + wt * amounts["hips"])
    Hc = np.zeros_like(zs)
    sv = np.unique(skin_tri)
    remap = np.full(N, -1, np.int64)
    remap[sv] = np.arange(len(sv))
    tri_l = remap[skin_tri]
    PRs = PR[sv]
    g = np.exp(-0.5 * (np.arange(-3, 4) / 1.5) ** 2)
    g /= g.sum()

    outline = (outline_factory or fixed_core_outline)(PRs, tri_l, zs)
    print("Hip contour calibration: Fixed Core (original section membership)" if outline_factory is None else "Hip contour calibration: experimental outline override")
    original_outline = outline(PRs)
    if observer is not None: observer("hip_target_initial", locals())
    relative = bool(cfg.get("relative_silhouette", False))
    if coupled:
        from hip_thigh_profile import coupled_target, quintic
        from scipy.interpolate import PchipInterpolator
        hip_ref = float(sc.zmap(np.asarray([L["hip_z"]]))[0])
        Q = PRs.copy()
        Q[:,0] += sc.field_ref(*PRs.T)[0]
        natural = np.nan_to_num(outline(Q)-original_outline, nan=0.)
        ctrl = cfg.get("hip_profile", {})
        amp = float(np.interp(hip_ref, zs, tgt))
        tgt, peak = coupled_target(zs, original_outline, natural, hip_ref, REF["waist"], REF["knee"], amp, float(ctrl.get("upper",1.4)), float(ctrl.get("lower",1.65)), float(ctrl.get("peak",0.)))
        env = quintic((zs-REF["knee"])/5.) * (1-quintic((zs-(REF["waist"]-5.))/5.))
        print("\n===== DEFORMATION PHASE 2.7 / COUPLED HIP-THIGH PROFILE =====")
        print("Hip center %.2f; expansion center %.2f; peak target %.2f; controls %s" % (hip_ref,peak,amp,ctrl))
        print("Coupled profile replaces relative silhouette target when enabled.")
        relative = False
    if relative:
        from silhouette_target import relative_target
        hip_ref = float(sc.zmap(np.asarray([L["hip_z"]]))[0])
        tgt, scale = relative_target(zs, original_outline, tgt, hip_ref, REF["waist"], REF["hip_half"], float(cfg.get("silhouette_strength", 1.0)))
        print("\n===== DEFORMATION PHASE 2.6 / RELATIVE SILHOUETTE =====")
        print("Hip reference Z %.2f; local scale %.3f; waist target growth zero" % (hip_ref, scale))
    if observer is not None: observer("hip_target_final", locals())
    if cfg.get("legacy_hip_repair", False) and amounts["hips"] > 0 and not zero_calibration:
        from .legacy_hip_repair import fit
        Hc, env, tgt, err = fit(sc, PRs, tri_l, zs, original_outline, outline, tgt, REF, amounts,
                                coupled=coupled, relative=relative, ctrl=cfg.get("hip_profile"),
                                hip_ref=locals().get("hip_ref"), factory=outline_factory)
        valid = (env > .5) & np.isfinite(err)
        print("hip calibration: residual %.3f cm (ref frame; constrained profile)" % (np.max(np.abs(err[valid])) if valid.any() else np.nan))
        return dict(zs=zs, env=env, tgt=tgt, T0=T0, Hc=Hc, sv=sv, tri_l=tri_l,
                    PRs=PRs, outline=outline, original_outline=original_outline,
                    relative=relative, coupled=coupled, hip_ref=locals().get("hip_ref"), err=err)
    for it in range(1 if zero_calibration else 8):
        sc.hip = (zs, Hc)
        if coupled:
            sc.coupled_hips = True
            spline = PchipInterpolator(zs, Hc, extrapolate=False)
            sc._hip_spline = lambda z, f=spline: np.nan_to_num(f(z), nan=0.0)
        dxr, _ = sc.field_ref(PRs[:, 0], PRs[:, 1], PRs[:, 2])
        Q = PRs.copy()
        Q[:, 0] += dxr
        grow = outline(Q) - original_outline
        err = np.where(np.isnan(grow), 0.0, tgt - grow)
        if observer is not None: observer("hip_iteration_before", locals())
        Hc = np.zeros_like(Hc) if zero_calibration else update_correction(Hc, env, err)
        if observer is not None: observer("hip_iteration_clipped", locals())
        Hc = smooth_correction(Hc, g, env)
        if observer is not None: observer("hip_iteration_smoothed", locals())
    sc.hip = (zs, Hc)
    if coupled:
        spline = PchipInterpolator(zs, Hc, extrapolate=False)
        sc._hip_spline = lambda z, f=spline: np.nan_to_num(f(z), nan=0.0)
    if relative or coupled:
        # Report the actual post-iteration residual, not the previous iteration.
        Q = PRs.copy()
        Q[:, 0] += sc.field_ref(PRs[:,0], PRs[:,1], PRs[:,2])[0]
        err = np.where(np.isfinite(original_outline) & np.isfinite(outline(Q)), tgt - (outline(Q)-original_outline), np.nan)
    bad_z = zs[(env > 0.5) & (np.abs(err) > 0.4)]
    print("hip calibration: residual %.3f cm (ref frame)%s" % (
        np.nanmax(np.abs(err[env > 0.5])),
        ("   off-target at ref z " + ", ".join("%.0f" % z for z in bad_z)) if len(bad_z) else ""))

    return dict(zs=zs, env=env, tgt=tgt, T0=T0, Hc=Hc, sv=sv, tri_l=tri_l,
                PRs=PRs, outline=outline, original_outline=original_outline,
                relative=relative, coupled=coupled, hip_ref=locals().get("hip_ref"), err=err)
