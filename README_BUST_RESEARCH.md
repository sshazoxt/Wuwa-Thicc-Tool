# Bust: research (NOT implemented)

This documents an experiment with a slider to reduce breast size (from the current size to cup A).
**It is not implemented in `thicc_edit.py` or the GUI**; the experiment was reverted. The findings
and prototype code (appendix) are preserved here in case development resumes.

## Idea
A value `amounts["bust"]` from 0 to 1 (1 = current size, 0 = cup A). Only reduces size, never enlarges.

## Measurement (for each breast, using skin vertices)
1. **Apex**: skin vertex with the largest `y` (forward), with `|x| > 2`, `waist-6 < z < 0.88*H`.
2. **Front profile** `y(z)` in a band `|x - xc| < 2.5 cm` around the apex.
3. **Base**: median profile 22–10 cm below the apex.
4. **Edges**: where the profile crosses `base + 25%*(y_apex - base)` — lower fold `zf` and upper edge `zt` (+2 cm).
5. **Chest wall**: plane through the fold and upper edge (including its slope), plus the transverse torso profile measured just below the fold (the sternum projects farther than the sides). Without this transverse profile, the sternum moved 3.45 cm.
6. **Footprint**: ellipse centered at `xm`, radius `rx` based on the lateral extent (where projection exceeds 1 cm), `rlo = zc - zf + 5`, `rhi = zt - zc + 3`.
7. **Projection** = maximum over the ellipse (drooping breasts project farther below the apex).

### Estimated size
Cup A ≈ 4.0 cm of projection on a 165 cm body, +1.5 cm per cup
(AA, A, B, C, D, DD, E, F, G, H, I, J, K), scaled by `H/165`. This is a heuristic, not a real measurement.

### Measurements obtained
| Mod | Apex z | Projection | Approx. cup |
|---|---|---|---|
| Rover (Astral Modulator) | 116.7 | 7.9–9.4 cm | D/DD |
| HiyukiMod | 110–111 | 15.9 / 18.5 cm (asymmetric) | H/J |
| Goth Hiyuki | 122.6 | 9.7 cm | DD |
| Hiyuki_?? | 120.5 | 13.2 cm | ~G |

The last mod name contains unrecoverable characters in the original document.

## Deformation
- Depth: `dy = -k * w * softplus((prot - 1)/0.6) * 0.6` — monotonic, cannot fold the mesh.
- `k = clip((prot - target)/(prot - 1), 0, 0.97) * (1 - slider)`.
- Footprint weight `w` with falloff at normalized radius 1.0–1.5 and an abdominal gate `smoothstep(zf-6, zf+1, z)` to avoid depressing the area below the fold.
- Mild footprint shrinkage: x 0.12 and z 0.06, gradually increasing with projection (0–10 cm).
- Requires 3D displacement (`dz`) and updating row 2 of the Jacobian for normals/tangents.
- When the slider is active, torso garments (bra, shirt, pendants) must **not** be automatically frozen (the `zmin > waist + 4` rule), otherwise they remain floating.

## Results (temporary copies only, never tested in-game)
| Mod | Change | Inverted triangles |
|---|---|---|
| Goth Hiyuki | DD → A | 0 |
| Rover | DD → A | 0 |
| HiyukiMod | H/J → A/B | 0 (apex projection) / 41 (maximum over ellipse) |

- Clothing did not end up inside the skin.
- HiyukiMod is asymmetric: the result differs by 0.8 cm between sides (due to the model, not the tool).

## Issues found
- Linear falloff `max(prot, 0)` and a narrow footprint → 267 inverted triangles in HiyukiMod.
- Greater x/z shrinkage → inverted triangles.
- Fading the chest-wall profile → inverted triangles.
- Very large breasts (HiyukiMod) reach A/B rather than exactly A because `k` is capped at 0.97.

## Pending if development resumes
- In-game testing (shading, normals, torso clothing, breast physics/bones if used by the mod).
- GUI slider displaying the estimated current cup size.
- Review mods with breasts and clothing in the same component.

## Appendix: prototype code
It was integrated in `thicc_edit.py` after `Sculpt.field` (which returned `dx, dy, dz`, adding
`bust_field(self.bust, ...)` when `self.bust` was defined).

```python
# ================================================================ bust
CUPS = ["AA", "A", "B", "C", "D", "DD", "E", "F", "G", "H", "I", "J", "K"]
A_CUP_PROT = 4.0        # cm of projection from the chest wall for an A cup (165 cm body)
CUP_STEP = 1.5          # cm per cup size


def cup_name(prot, H):
    p = prot * 165.0 / H
    i = int(np.clip(np.round((p - A_CUP_PROT) / CUP_STEP) + 1, 0, len(CUPS) - 1))
    return CUPS[i]


def measure_bust(P, skin, H, waist):
    """Per breast: apex, inframammary fold, upper edge and the chest wall
    behind it (a plane through fold and upper edge + the torso's cross profile
    measured just under the fold).  Returns {sgn: dict} or raises."""
    Q = P[skin]
    out = {}
    for sgn in (1, -1):
        q = Q[(Q[:, 0] * sgn > 2.0) & (Q[:, 2] > waist - 6.0) & (Q[:, 2] < 0.88 * H)]
        if len(q) < 50:
            raise ValueError("no breast skin found")
        a = q[np.argmax(q[:, 1])]
        xc, ya, zc = (float(v) for v in a)
        zs = np.arange(zc - 28.0, zc + 22.0, 0.5)
        f = np.full(len(zs), np.nan)
        near = Q[np.abs(Q[:, 0] - xc) < 2.5]
        for i, z in enumerate(zs):
            m = (near[:, 2] >= z - 0.75) & (near[:, 2] < z + 0.75)
            if m.sum() >= 2:
                f[i] = near[m, 1].max()
        ok = ~np.isnan(f)
        if ok.sum() < 20:
            raise ValueError("incomplete breast profile")
        f = np.interp(zs, zs[ok], f[ok])
        base = float(np.median(f[(zs >= zc - 22) & (zs <= zc - 10)]))
        thr = base + 0.25 * (ya - base)
        ia = int(np.argmin(np.abs(zs - zc)))
        i = ia
        while i > 0 and f[i] > thr:
            i -= 1
        j = ia
        while j < len(zs) - 1 and f[j] > thr:
            j += 1
        if i == 0 or j == len(zs) - 1:
            raise ValueError("breast edges were not found")
        zf = zs[i] + (thr - f[i]) / (f[i + 1] - f[i] + 1e-9) * 0.5
        zt = zs[j - 1] + (f[j - 1] - thr) / (f[j - 1] - f[j] + 1e-9) * 0.5 + 2.0
        yf, yt = float(f[i]), float(np.interp(zt, zs, f))
        slope = (yt - yf) / max(zt - zf, 1.0)
        # torso cross profile just under the fold (sternum higher than the sides)
        band = Q[(Q[:, 2] > zf - 4.0) & (Q[:, 2] < zf - 1.5) & (Q[:, 0] * sgn > -0.5)]
        xb = np.arange(0.0, 26.0, 1.0)
        prof = np.full(len(xb), np.nan)
        for k, x0 in enumerate(xb):
            m = np.abs(band[:, 0] * sgn - x0) < 0.75
            if m.sum() >= 2:
                prof[k] = band[m, 1].max()
        okp = ~np.isnan(prof)
        if okp.sum() >= 3:
            prof = np.interp(xb, xb[okp], prof[okp])
            prof = np.convolve(np.pad(prof, 2, mode="edge"), [.1, .2, .4, .2, .1], "valid")
            prof -= np.interp(abs(xc), xb, prof)
        else:
            prof = np.zeros(len(xb))
        wall_c = yf + slope * (zc - zf)
        prot = ya - wall_c
        # lateral extent at apex height
        m = (np.abs(Q[:, 2] - zc) < 1.5) & (Q[:, 0] * sgn > 0)
        pw = Q[m, 1] - (yf + slope * (Q[m, 2] - zf) + np.interp(np.abs(Q[m, 0]), xb, prof))
        xs = np.abs(Q[m, 0])[pw > 1.0]
        x_in, x_out = (float(xs.min()), float(xs.max())) if len(xs) else (abs(xc) - 6, abs(xc) + 6)
        xm, rx = sgn * 0.5 * (x_in + x_out), 0.5 * (x_out - x_in) * 1.3 + 1.5
        rlo, rhi = zc - zf + 5.0, zt - zc + 3.0
        # largest projection over the whole breast (droopy breasts stick out most below the apex)
        m = (Q[:, 0] * sgn > 1.0) & (np.abs(Q[:, 2] - zc) < 16.0)
        qq = Q[m]
        wq = yf + slope * (qq[:, 2] - zf) + np.interp(np.abs(qq[:, 0]), xb, prof)
        rq = np.where(qq[:, 2] < zc, rlo, rhi)
        inside = np.hypot((qq[:, 0] - xm) / rx, (qq[:, 2] - zc) / rq) < 1.0
        if inside.any():
            prot = max(prot, float((qq[:, 1] - wq)[inside].max()))
        out[sgn] = dict(sgn=sgn, xc=xc, ya=ya, zc=zc, zf=float(zf), yf=yf, zt=float(zt), slope=slope,
                        xb=xb, prof=prof, prot=float(prot), xm=xm, rx=rx, rlo=rlo, rhi=rhi, k=0.0)
    return out


BUST_XS, BUST_ZS = 0.12, 0.06          # footprint shrink (x, z) relative to the depth shrink
BUST_RN = (1.0, 1.5)                    # footprint falloff (normalised radius, generous)
BUST_C, BUST_S = 1.0, 0.6               # softplus knee (cm) of the depth curve
BUST_SG = (0.0, 10.0)                   # x/z shrink ramps in with the projection (cm)


def _deflate(prot):
    """Monotone 'excess projection': ~0 at/behind the chest wall, ~prot-C on the breast."""
    return BUST_S * np.logaddexp(0.0, (prot - BUST_C) / BUST_S)


def bust_k(prot, target):
    """Depth factor so that the apex ends at ``target`` cm of projection."""
    return float(np.clip((prot - target) / max(prot - BUST_C, 1e-3), 0.0, 0.97))


def bust_field(B, px, py, pz):
    """Shrink each breast toward the chest wall.  Depth: y -= k*w*softplus(prot),
    whose derivative along the projection is 1 - k*sigmoid > 0, so the surface
    can never fold; the footprint weight w is wide and only varies where the
    projection is already ~0.  A milder footprint shrink pulls x toward the
    breast centre and z toward the apex."""
    dx, dy, dz = np.zeros(len(px)), np.zeros(len(px)), np.zeros(len(px))
    for b in B.values():
        k = b["k"]
        if k <= 0:
            continue
        sgn = b["sgn"]
        ws = smoothstep(-1.5, 1.5, px * sgn)
        wall = b["yf"] + b["slope"] * (pz - b["zf"]) + np.interp(np.abs(px), b["xb"], b["prof"])
        prot = py - wall
        rz = b["rlo"] + (b["rhi"] - b["rlo"]) * smoothstep(b["zc"] - 2.0, b["zc"] + 2.0, pz)
        rn = np.sqrt(((px - b["xm"]) / b["rx"]) ** 2 + ((pz - b["zc"]) / rz) ** 2)
        below = smoothstep(b["zf"] - 6.0, b["zf"] + 1.0, pz)   # spares the belly under the fold
        w = ws * (1.0 - smoothstep(BUST_RN[0], BUST_RN[1], rn)) * below
        wb = w * smoothstep(BUST_SG[0], BUST_SG[1], prot)
        dy -= k * w * _deflate(prot)
        dx -= k * BUST_XS * wb * (px - b["xm"])
        dz -= k * BUST_ZS * wb * (pz - b["zc"])
    return dx, dy, dz
```
