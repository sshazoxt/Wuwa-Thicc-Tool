import os, sys, re
import numpy as np


SKIN_RE = re.compile(r"身体|身體|body|skin|裸|nude|naked|素体", re.I)

NOT_SKIN_RE = re.compile(r"strap|stocking|sock|glove|shoe|boot|bikini|leotard|cloth|dress|skirt|"
                         r"shirt|top|suit|sweater|short|pant|衣|裙|袜|襪|鞋|手套|内裤|內褲|饰|飾", re.I)

FREEZE_RE = re.compile(r"hair|face|head|\beyes?\b|\bears?\b|earring|mask|visor|blindfold|horn|\bhat\b|"
                       r"hood|tail|smile|"
                       r"头|頭|发|髮|脸|臉|面部|眼|耳|帽|角|尾", re.I)

def vnormals(P, T):
    tri = P[T]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    g = np.zeros_like(P)
    for k in range(3):
        np.add.at(g, T[:, k], fn)
    return g / np.maximum(np.linalg.norm(g, axis=1), 1e-12)[:, None]

def find_ini(mod):
    best, n = None, -1
    for f in os.listdir(mod):
        if not f.lower().endswith(".ini") or f.upper().startswith("DISABLED"):
            continue
        t = open(os.path.join(mod, f), encoding="utf-8", errors="replace").read()
        c = t.count("drawindexed")
        if c > n and "Meshes/Position.buf" in t.replace("\\", "/"):
            best, n = f, c
    if not best:
        sys.exit("no WWMI ini with drawindexed + Meshes/Position.buf in " + mod)
    return os.path.join(mod, best)

DRAW_RE = re.compile(r"^(\s*)(;[ \t]*)?(drawindexed\s*=\s*(\d+),\s*(\d+)(?:,\s*(-?\d+))?)(?=\s|;|$)", re.I)

def parse_draws(ini, comps=None, metadata=None):
    """part name -> (first index, index count) for every drawindexed of the
    TextureOverrideComponent sections.  The name comes from a '; Draw <name>'
    comment, else from the toggle variable guarding the draw
    ('if $draw_component_3_xxx'), else 'Component N #k'."""
    lines = open(ini, encoding="utf-8", errors="replace").read().splitlines()
    out = {}
    comp, k = None, 0
    for i, l in enumerate(lines):
        h = re.match(r"\s*\[TextureOverrideComponent(\d+)\]", l, re.I)
        if h:
            comp, k = h.group(1), 0
            continue
        if re.match(r"\s*\[", l):
            comp = None
            continue
        d = DRAW_RE.match(l)
        if not d or comp is None or int(d.group(4)) == 0:
            continue
        k += 1
        name = None
        back = []
        for b in lines[max(i - 4, 0):i][::-1]:
            if DRAW_RE.match(b) or re.match(r"\s*(endif|\[)", b, re.I):
                break
            back.append(b)
        for b in back:
            m = re.match(r"\s*;\s*Draw (.+)$", b)
            if m:
                name = m.group(1).strip()
                break
        if name is None:
            name = "Component %s - Línea %d" % (comp, i + 1)
        base, n = name, 2
        while name in out:
            name = "%s (%d)" % (base, n)
            n += 1
        out[name] = (int(d.group(5)), int(d.group(4)))
        if metadata is not None:
            metadata[name] = dict(line=i+1, visible=d.group(2) is None, draw=d.group(3), component=int(comp))
        if comps is not None:
            comps[name] = int(comp)
    return out

def load_bones(M, N):
    bl = np.fromfile(os.path.join(M, "Blend.buf"), np.uint8)
    per = bl.size // N
    bl = bl.reshape(N, per)
    k = per // 2
    bi, bw = bl[:, :k].astype(np.int64), bl[:, k:].astype(np.float64) / 255.0
    vg = os.path.join(M, "BlendRemapVertexVG.buf")
    if os.path.exists(vg):
        g = np.fromfile(vg, np.uint16)
        if g.size == N * k:
            print("bones: BlendRemapVertexVG (global ids), %d influences" % k)
            return g.reshape(N, k).astype(np.int64), bw
    print("bones: Blend.buf, %d influences" % k)
    return bi, bw

def band_stats(P, sel, z0, z1):
    m = (P[sel, 2] >= z0) & (P[sel, 2] < z1)
    if m.sum() < 10:
        return None
    q = P[sel][m]
    rt, lt = q[q[:, 0] > 0.3, 0], q[q[:, 0] < -0.3, 0]
    gap = (rt.min() - lt.max()) if len(rt) and len(lt) else np.nan
    return torso_half(np.abs(q[:, 0])), q[:, 1].min(), q[:, 1].max(), gap

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

def measure(P, skin, H, skin_tri):
    def xh(z0, z1):
        zs = np.arange(z0, z1, 1.0)
        v = []
        for z in zs:
            m = (P[skin, 2] >= z - 1) & (P[skin, 2] < z + 1)
            v.append(torso_half(np.abs(P[skin][m, 0])) if m.sum() >= 10 else np.nan)
        return zs, np.array(v)
    L = {}
    # crotch = lowest point of the perineum: skin on the midline whose surface
    # faces up/down.  Inner thighs that touch the midline face sideways, so
    # they are not mistaken for the crotch (thick-thigh mods).
    n = vnormals(P, skin_tri)
    z_band = skin[
        (P[skin, 2] > 0.3 * H) &
        (P[skin, 2] < 0.7 * H)
    ]

    print("\n--- DIAGNOSTICO DE COORDENADAS ---")
    print("Vertices en franja Z:", len(z_band))

    if len(z_band):
        xyz = P[z_band]

        for i, axis in enumerate(["X", "Y", "Z"]):
            values = xyz[:, i]
            print(
                f"{axis}: rango {values.min():.3f} a {values.max():.3f} "
                f"| minimo valor absoluto: {np.abs(values).min():.3f}"
            )

        nearest = z_band[np.argsort(np.abs(P[z_band, 0]))[:10]]

        print("\n10 vertices mas cercanos al centro X:")
        for v in nearest:
            print(
                f"X={P[v,0]:.3f} "
                f"Y={P[v,1]:.3f} "
                f"Z={P[v,2]:.3f}"
            )

    near = z_band[np.abs(P[z_band, 0]) < 0.8]
    down = near[np.abs(n[near, 2]) > 0.5]
    
    if len(near) == 0:
        skin_xyz = P[skin]

        raise ValueError(
            "No se encontraron vertices de piel en la zona de la entrepierna.\n"
            f"Vertices Skin: {len(skin)}\n"
            f"Altura H: {H:.4f}\n"
            f"Rango X: {skin_xyz[:, 0].min():.4f} a {skin_xyz[:, 0].max():.4f}\n"
            f"Rango Z: {skin_xyz[:, 2].min():.4f} a {skin_xyz[:, 2].max():.4f}\n"
            "Revisa la seleccion de partes Skin o la posicion del modelo."
        )

    L["crotch"] = float(P[down, 2].min() if len(down) else P[near, 2].min())
    zs, v = xh(0.22 * H, 0.72 * L["crotch"])
    L["knee"] = float(zs[np.nanargmin(v)])
    zs, v = xh(0.04 * H, 0.6 * L["knee"])
    L["ankle"] = float(zs[np.nanargmin(v)])
    m = (P[skin, 2] > L["crotch"] - 6) & (P[skin, 2] < L["crotch"] + 18)
    i = np.argmin(P[skin][m, 1])
    L["apex"] = float(P[skin][m][i, 2])
    L["apex_y"] = float(P[skin][m][i, 1])
    span = L["crotch"] - L["knee"]
    # Limit waist search to the local pelvis-to-torso transition, not the neck.
    zs, v = xh(L["apex"] + .35*span, min(L["apex"] + 1.05*span, float(P[skin,2].max())))
    L["waist"] = float(zs[np.nanargmin(v)])
    zs, v = xh(max(L["knee"], L["crotch"] - .35*span), min(L["waist"], L["apex"] + .45*span))
    L["hip_half"] = float(np.nanmax(v))
    L["hip_z"] = float(zs[np.nanargmax(v)])
    st = band_stats(P, skin, L["apex"] - 2, L["apex"] + 2)
    L["cy"] = float(0.5 * (st[1] + st[2]))
    return L
