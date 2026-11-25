"""
Generic WWMI body sculpt ("thicc" / "pear") -- works on any WWMI mod.

Generalisation of rover_thicc_edit.py:
  * the mod's parts are read from the '; Draw <name>' blocks of its ini;
  * skin / frozen (hair, face, head pieces) / garment parts are classified
    automatically (names in English or Chinese + geometry) and can be
    overridden in <mod>/thicc.json;
  * arms are masked from the bone weights (Blend.buf, or the global ids of
    BlendRemapVertexVG.buf when the mod uses blend remapping);
  * anatomical landmarks (ankle, knee, crotch, butt apex, waist, hip width,
    pelvis centre) are measured on the skin, and every field is evaluated in a
    normalised frame that maps the character onto the Rover reference body
    (piecewise-cubic in height, uniform scale laterally).  The fields, tables
    and calibrations are therefore exactly the ones validated on Rover.

Usage:
    python thicc_edit.py "<mod folder>"              dry run + report
    python thicc_edit.py "<mod folder>" --write      write Position.buf / Vector.buf
    python thicc_edit.py "<mod folder>" --restore    copy the .orig files back
    python thicc_edit.py "<mod folder>" --diagnose   parts / landmarks only

The script always starts from Meshes/Position.buf.orig + Vector.buf.orig, so it
can be re-run after editing thicc.json without compounding.
"""
import json
import os
import re
import shutil
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skeleton  # noqa: E402
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------- reference body (Rover)
REF = dict(ankle=16.2, knee=50.1, crotch=82.2, apex=86.9, waist=105.9, hip_half=18.2, cy=-4.6)

PRESETS = {
    # multipliers on the Rover amounts
    "thicc": dict(butt=1.00, hips=1.00, thighs=1.00, calves=1.00),
    "pear":  dict(butt=0.85, hips=1.25, thighs=1.20, calves=1.05),
    "butt":  dict(butt=1.30, hips=0.90, thighs=0.80, calves=0.60),
}

VERSION = "0.2.4-002"
BOUNCE_LEVELS = ("normal", "soft", "medium", "extra")

DEFAULT_CFG = {
    "bounce": "normal",
    "preset": "pear",
    "amounts": {},            # per-key overrides of the preset multipliers
    "inner_fill": False,      # close the thighs (Rover "Closed Thighs" variant)
    "skin": [],               # part names; empty = automatic
    "freeze": [],             # extra part names never moved
    "move": [],               # part names forced to move (overrides auto freeze)
    "landmarks": {},          # overrides, e.g. {"crotch": 80.0}
    "anatomy": [],            # draw parts used to reconstruct the skeleton
}

SKIN_RE = re.compile(r"身体|身體|body|skin|裸|nude|naked|素体", re.I)
NOT_SKIN_RE = re.compile(r"strap|stocking|sock|glove|shoe|boot|bikini|leotard|cloth|dress|skirt|"
                         r"shirt|top|suit|sweater|short|pant|衣|裙|袜|襪|鞋|手套|内裤|內褲|饰|飾", re.I)
FREEZE_RE = re.compile(r"hair|face|head|\beyes?\b|\bears?\b|earring|mask|visor|blindfold|horn|\bhat\b|"
                       r"hood|tail|smile|"
                       r"头|頭|发|髮|脸|臉|面部|眼|耳|帽|角|尾", re.I)

# ---------------------------------------------------------------- Rover tables (reference frame)
BUTT_AMT = 2.45
LEG_KNOTS = [(13.0, 0.00), (16.0, 0.12), (19.0, 0.32), (23.0, 0.62),
             (27.0, 0.95), (31.0, 1.25), (35.0, 1.50), (39.0, 1.55),
             (42.0, 1.42), (45.0, 1.18), (49.0, 1.05), (53.0, 1.32),
             (57.0, 1.72), (61.0, 2.02), (65.0, 2.25), (69.0, 2.40),
             (73.0, 2.40), (76.0, 2.32), (79.0, 2.08), (82.0, 1.55),
             (85.0, 0.82), (88.0, 0.25), (91.0, 0.00)]  # extended upper fade: preserve peak, start transition 3 cm higher
HIP_TARGET = [(64.0, 2.31), (68.0, 2.40), (72.0, 2.48), (76.0, 2.55), (80.0, 2.60),
              (84.0, 2.60), (88.0, 2.50), (92.0, 2.25), (96.0, 1.80), (100.0, 1.20),
              (104.0, 0.60), (108.0, 0.20), (112.0, 0.00)]
HIP_ENV = (62.0, 70.0, 108.0, 114.0)
INNER_KNOTS = [(58.0, 0.00), (62.0, 0.40), (66.0, 0.90), (70.0, 1.40),
               (74.0, 1.80), (77.0, 2.00), (78.5, 1.70), (79.8, 0.70), (80.8, 0.00)]
SKIN_FLOOR, GARMENT_FLOOR, SQUEEZE_SOFT = 0.15, 0.06, 0.25


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def gauss_smooth(z, a, sigma):
    h = np.arange(-4 * sigma, 4 * sigma + 1e-9, z[1] - z[0])
    k = np.exp(-0.5 * (h / sigma) ** 2)
    pad = len(h) // 2
    return np.convolve(np.pad(a, pad, mode="edge"), k / k.sum(), "valid")


def pchip(xk, yk):
    """Monotone piecewise-cubic interpolant (Fritsch-Carlson), linear outside."""
    xk, yk = np.asarray(xk, float), np.asarray(yk, float)
    h = np.diff(xk)
    d = np.diff(yk) / h
    m = np.zeros_like(yk)
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(xk) - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        x = np.asarray(x, float)
        i = np.clip(np.searchsorted(xk, x) - 1, 0, len(xk) - 2)
        t = (x - xk[i]) / h[i]
        h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
        h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        y = h00 * yk[i] + h10 * h[i] * m[i] + h01 * yk[i + 1] + h11 * h[i] * m[i + 1]
        y = np.where(x < xk[0], yk[0] + m[0] * (x - xk[0]), y)
        return np.where(x > xk[-1], yk[-1] + m[-1] * (x - xk[-1]), y)
    return f


# ================================================================ the sculpt
class Sculpt:
    def __init__(self, amounts, inner_fill):
        self.a = amounts
        self.direction = {k: (1.0, 1.0) for k in ("butt", "hips", "thighs", "calves")}
        self.continuous = False
        self.coupled_hips = False
        self._curves = {}
        z = np.arange(0.0, 130.001, 0.1)
        base = np.interp(z, [k[0] for k in LEG_KNOTS], [k[1] for k in LEG_KNOTS])
        mult = amounts["calves"] + (amounts["thighs"] - amounts["calves"]) * smoothstep(47.0, 55.0, z)
        self.leg = (z, gauss_smooth(z, base * mult, 1.2))
        self.axis = None
        self.hip = None
        self.inner = None
        self.root = None
        self.rounding = None
        
        if inner_fill:
            m = np.interp(z, [k[0] for k in INNER_KNOTS], [k[1] for k in INNER_KNOTS])
            self.inner = (z, gauss_smooth(z, m * amounts["thighs"], 0.8))
        self.s = 1.0
        self.zmap = None
        self.cyc = REF["cy"]

    def set_frame(self, L):
        self.s = L["hip_half"] / REF["hip_half"]
        zc = [0.0, L["ankle"], L["knee"], L["crotch"], L["apex"], L["waist"], L["waist"] + 40.0]
        zr = [0.0, REF["ankle"], REF["knee"], REF["crotch"], REF["apex"], REF["waist"], REF["waist"] + 40.0]
        if not (zc[3] < zc[4] < zc[5]):
            print("INFO: apex omitted from vertical mapping to preserve monotonicity.")
            zc.pop(4)
            zr.pop(4)
        if not np.all(np.diff(zc) > 0):
            raise ValueError("Vertical landmarks are not increasing; deformation cannot proceed.")
        self.zmap = pchip(zc, zr)
        self.cyc = L["cy"]

    def to_ref(self, x, y, z):
        return x / self.s, (y - self.cyc) / self.s + REF["cy"], self.zmap(z)
    
    def curve(self, x, y, z):
        if not self.continuous:
            return np.interp(z, x, y)
        from continuous_field import profile
        key = (id(x), id(y))
        if key not in self._curves:
            self._curves[key] = (x, y, profile(x, y))
        return self._curves[key][2](z)

    def field_ref(self, px, py, pz):
        if self.continuous:
            from continuous_field import quintic as step
        else:
            step = smoothstep
        dx = np.zeros(len(px))
        dy = np.zeros(len(px))
        cyb = REF["cy"]

        # ---- buttocks
        _ = np.hypot(px, py - cyb)
        ux = px / np.sqrt(_ * _ + 4.0)
        uy = (py - cyb) / np.sqrt(_ * _ + 4.0)
        ang = np.degrees(np.arccos(np.clip(
            -uy / np.maximum(np.hypot(ux, uy), 1e-9),
            -1.0, 1.0
        )))

        w = (
            (1.0 - step(55.0, 100.0, ang))
            * step(75.0, 85.0, pz)
            * (1.0 - step(93.0, 103.0, pz))
            * (1.0 - step(16.0, 26.0, _))
            * step(1.0, 7.0, _)
            * BUTT_AMT * self.a["butt"]
        )

        soft = np.sqrt(px * px + (py - cyb) ** 2 + 9.0)
        dx += w * px / soft * self.direction["butt"][0]
        dy += w * (py - cyb) / soft * self.direction["butt"][1]

        # ---- calibrated multidirectional hip field
        if self.hip is not None:
            wr_hip = (
                step(4.0, 9.0, _)
                * (1.0 - step(21.0, 27.0, _))
            )
            hip_amount = (np.interp(pz, *self.hip) if not self.coupled_hips else self._hip_spline(pz)) * wr_hip
            # Broad, smooth lateral response (odd in X).
            lateral = ux * (0.55 + 0.45 * ux * ux)
            # Smaller depth response; greater toward the posterior.
            posterior = step(-0.75, 0.75, -uy)
            depth = (0.20 + 0.15 * posterior) * uy * (0.65 + 0.35 * ux * ux)
            dx += hip_amount * lateral * self.direction["hips"][0]
            dy += hip_amount * depth * self.direction["hips"][1]

        # ---- legs (+ optional inner-thigh fill)
        for sgn in (1, -1):
            zk, xk, yk = self.axis[sgn]

            ax = self.curve(zk, xk, pz)
            ay = self.curve(zk, yk, pz)

            ex, ey = px - ax, py - ay
            r = np.hypot(ex, ey)

            soft = np.sqrt(r * r + 1.5 ** 2)
            exu, eyu = ex / soft, ey / soft

            med = np.clip(
                -exu / np.maximum(np.hypot(exu, eyu), 1e-9) * sgn,
                0.0, 1.0
            )

            w_med = (
                1.0 - med * med
                * (0.12 + 0.80 * step(50.0, 70.0, pz))
            )

                        # ---- anatomical thigh deformation
            leg_amount = self.curve(*self.leg, pz)
            root_fade = 1.0
            effective_amount = leg_amount

            if self.root is not None and sgn in self.root:
                angles, root_z = self.root[sgn]

                theta = np.arctan2(ey, sgn * ex)

                # Provisional anatomical landmarks.
                thigh_outer = np.interp(
                    0.0, angles, root_z,
                    period=2.0 * np.pi
                )

                thigh_inner = np.interp(
                    np.pi, angles, root_z,
                    period=2.0 * np.pi
                )

                # Continuous anatomical boundary.
                boundary = np.interp(
                    theta, angles, root_z,
                    period=2.0 * np.pi
                )

                if self.continuous:
                    from continuous_field import angular_profile
                    key = (id(angles), id(root_z))
                    if key not in self._curves:
                        self._curves[key] = (angles, root_z, angular_profile(angles, root_z))
                    boundary = self._curves[key][2](theta)

                # One continuous upper profile for the anterior thigh.
                # Broad angular transition, with a continuous second derivative.
                # Preserve full anterior strength and zero posterior strength.
                angular = np.clip((eyu + 0.20) / 1.10, 0.0, 1.0)
                anterior = angular**3 * (10.0 + angular * (-15.0 + 6.0 * angular))
                peak_z = self.leg[0][np.argmax(self.leg[1])]
                peak_amount = np.max(self.leg[1])
                front_root = np.interp(np.pi / 2, angles, root_z,
                                       period=2.0 * np.pi)
                upper_end = np.maximum(
                    peak_z + 1.0,
                    LEG_KNOTS[-1][0] + boundary - front_root
                )
                t = np.clip((pz - peak_z) / (upper_end - peak_z), 0.0, 1.0)
                q = t**3 * (10.0 + t * (-15.0 + 6.0 * t))
                upper_amount = peak_amount * (1.0 - q)

                root_fade = 1.0 - step(
                    boundary + 6.0 + 12.0 * step(0.35, 0.95, eyu),
                    boundary + 18.0 + 12.0 * step(0.35, 0.95, eyu),
                    pz
                )
                if self.continuous:
                    # Single full-length amplitude with anatomical root fade.
                    effective_amount = leg_amount * root_fade
                # Blend the combined influence, not two separate fades.
                mix = anterior * step(peak_z - 3.0, peak_z, pz)
                target = np.where(pz >= peak_z, upper_amount, leg_amount)
                if not self.continuous:
                    effective_amount = (1.0 - mix) * leg_amount * root_fade + mix * target

            w = (
                effective_amount
                * (1.0 - step(9.5, 16.0, r))
                * w_med
            )

            # Main leg displacement (applied only once).
            blend = step(47.0, 55.0, pz)
            gx = self.direction["calves"][0] + blend * (self.direction["thighs"][0] - self.direction["calves"][0])
            gy = self.direction["calves"][1] + blend * (self.direction["thighs"][1] - self.direction["calves"][1])
            dx += w * exu * gx
            dy += w * eyu * gy

            # ---- optional inner-thigh fill
            if self.inner is not None:
                own = step(0.0, 1.0, px * sgn)

                fill = (
                    self.curve(*self.inner, pz)
                    * med * med
                    * (1.0 - step(9.5, 16.0, r))
                    * own
                    * root_fade
                )

                dx -= sgn * fill

        if self.rounding is not None:
            zz, aa, table = self.rounding
            for sign in (1, -1):
                zk, xk, yk = self.axis[sign]
                ex = px + dx - self.curve(zk, xk, pz)
                ey = py + dy - self.curve(zk, yk, pz)
                theta = np.arctan2(ey, sign * ex)
                radius = np.hypot(ex, ey)
                iz = np.clip(np.searchsorted(zz, pz)-1, 0, len(zz)-2)
                ia = np.clip(np.searchsorted(aa, theta)-1, 0, len(aa)-2)
                u = np.clip((pz-zz[iz])/(zz[iz+1]-zz[iz]),0,1)
                v = np.clip((theta-aa[ia])/(aa[ia+1]-aa[ia]),0,1)
                # Cubic interpolation with shared slopes, not a stop at each grid node.
                def weights(t):
                    return (-.5*t+t*t-.5*t**3, 1-2.5*t*t+1.5*t**3,
                            .5*t+2*t*t-1.5*t**3, -.5*t*t+.5*t**3)
                dr = np.zeros_like(radius)
                for i, wi in enumerate(weights(u)):
                    for j, wj in enumerate(weights(v)):
                        dr += wi*wj*table[np.clip(iz+i-1,0,len(zz)-1),
                                          np.clip(ia+j-1,0,len(aa)-1)]
                dr *= (px*sign > 0) * (pz >= zz[0]) * (pz <= zz[-1]) * (theta > 0) * (theta < np.pi/2)
                if self.continuous:
                    dr *= step(zz[0],zz[2],pz)*(1-step(zz[-3],zz[-1],pz))
                    dr *= step(0,np.pi/12,theta)*(1-step(5*np.pi/12,np.pi/2,theta))
                dr *= step(1.0,3.0,radius)*(1-step(13.,19.,radius))
                dx += dr*ex/np.maximum(radius,1e-9)
                dy += dr*ey/np.maximum(radius,1e-9)
        return dx, dy

    
    def field(self, px, py, pz):
        X, Y, Z = self.to_ref(px, py, pz)
        dX, dY = self.field_ref(X, Y, Z)
        return dX * self.s, dY * self.s


# ================================================================ geometry helpers
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


def fit_axis(tri_ref):
    out = {}
    for sgn in (1, -1):
        zz, xx, yy = [], [], []
        for z in np.arange(14.0, 78.01, 1.0):
            q = contour(tri_ref, z)
            q = q[(q[:, 0] * sgn > 0.3) & (np.abs(q[:, 0]) < 22.0)]
            if len(q) < 12:
                continue
            zz.append(z)
            xx.append(0.5 * (q[:, 0].min() + q[:, 0].max()))
            yy.append(0.5 * (q[:, 1].min() + q[:, 1].max()))
        out[sgn] = (np.array(zz), np.array(xx), np.array(yy))
    zr, xr, yr = out[1]
    zl, xl, yl = out[-1]
    if len(zr) < 5 or len(zl) < 5 or np.isin(zr, zl).sum() < 5:
        sys.exit("could not trace the legs on the skin parts: check which parts are 'skin' "
                 "(they must include both legs) or correct the landmarks")
    zc = zr[np.isin(zr, zl)]
    xc = 0.5 * (xr[np.isin(zr, zl)] - xl[np.isin(zl, zr)])
    yc = 0.5 * (yr[np.isin(zr, zl)] + yl[np.isin(zl, zr)])
    for _ in range(3):
        xc = np.convolve(np.pad(xc, 1, mode="edge"), [0.15, 0.70, 0.15], "valid")
        yc = np.convolve(np.pad(yc, 1, mode="edge"), [0.15, 0.70, 0.15], "valid")
    return {1: (zc, xc, yc), -1: (zc, -xc, yc)}


def radial_section(tri, z, center, angles, sign):
    """Ray/segment crossings on actual triangle sections, not vertex bins."""
    t = tri[(tri[:,:,2].min(1)<z)&(tri[:,:,2].max(1)>z)]
    if not len(t):
        return np.full(len(angles),np.nan)
    pts = np.full((len(t),3,2),np.nan)
    for k,(a,b) in enumerate(((0,1),(1,2),(2,0))):
        A,B=t[:,a],t[:,b]
        m=(A[:,2]-z)*(B[:,2]-z)<0
        f=(z-A[m,2])/(B[m,2]-A[m,2])
        pts[m,k]=A[m,:2]+f[:,None]*(B[m,:2]-A[m,:2])
    good=np.isfinite(pts[:,:,0]); pts=pts[good.sum(1)==2]; good=good[good.sum(1)==2]
    if not len(pts): return np.full(len(angles),np.nan)
    seg=pts[good].reshape(-1,2,2)-center
    A=seg[:,0]; E=seg[:,1]-A
    out=[]
    for a in angles:
        d=np.array([sign*np.cos(a),np.sin(a)])
        den=d[0]*E[:,1]-d[1]*E[:,0]
        ok=np.abs(den)>1e-9
        r=(A[ok,0]*E[ok,1]-A[ok,1]*E[ok,0])/den[ok]
        u=(A[ok,0]*d[1]-A[ok,1]*d[0])/den[ok]
        r=r[(u>=0)&(u<=1)&(r>1)&(r<19)]
        out.append(np.max(r) if len(r) else np.nan)
    return np.array(out)


def fit_rounding(sc, PR, part_tris, L):
    """Smooth only growth relative to the original shell; per-part sampling."""
    if sc.a['thighs'] <= 0: return
    span=L['crotch']-L['knee']
    if span<=0: return
    zz=sc.zmap(np.linspace(L['crotch']-.42*span,L['crotch']+.35*span,23))
    aa=np.linspace(-np.pi,np.pi,73)
    dx,dy=sc.field_ref(*PR.T); Q=PR+np.stack([dx,dy,np.zeros(len(dx))],1)
    rows=[]
    for ids in part_tris:
        if len(ids)<100: continue
        t0,t1=PR[ids],Q[ids]
        for sign in (1,-1):
            zk,xk,yk=sc.axis[sign]; r0=[]; r1=[]
            for z in zz:
                c=np.array([np.interp(z,zk,xk),np.interp(z,zk,yk)])
                r0.append(radial_section(t0,z,c,aa,sign)); r1.append(radial_section(t1,z,c,aa,sign))
            r0,r1=np.array(r0),np.array(r1)
            # Only accept a band with coherent angular samples in both meshes.
            sector=(aa>=0)&(aa<=np.pi/2)
            if np.isfinite(r0[:,sector]).mean()<.8 or np.isfinite(r1[:,sector]).mean()<.8: continue
            # Smooth excessive local curvature variation of the deformed contour,
            # while retaining the broad original shape and growth extrema.
            from numpy.lib.stride_tricks import sliding_window_view
            k=np.exp(-0.5*(np.arange(-8,9)/4.0)**2); k/=k.sum()
            growth = r1 - r0
            smooth=sliding_window_view(np.pad(growth,((0,0),(8,8)),mode='edge'),17,axis=1)@k
            residual=smooth-growth
            rows.append(np.where(np.isfinite(residual),residual,np.nan))
    if not rows:
        print('rounding: insufficient independent contour coverage; skipped'); return
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        table=np.nanmedian(rows,axis=0)
    table=np.nan_to_num(table)
    # Suppress unsupported angular sectors and maintain the lateral/front extrema.
    w=np.sin(np.clip(aa,0,np.pi/2)*2)**2
    v=np.sin(np.linspace(0,np.pi,len(zz)))**2
    for _ in range(2):
        table=(np.pad(table,((1,1),(0,0)),mode='edge')[:-2]+2*table+np.pad(table,((1,1),(0,0)),mode='edge')[2:])/4
    table=np.clip(table*1.4,-.30,.30)*v[:,None]*w[None,:]
    sc.rounding=(zz,aa,table)
    print(f'rounding: {len(rows)} independent side/part samples; max radial correction={np.abs(table).max()*sc.s:.4f} cm')


def morphological_roots(P, skin, L, sc):
    """Experimental virtual landmarks; all measurements in original mesh units."""
    g = float(L['crotch'])
    knee = float(L['knee'])
    # Use the groin-to-knee span as a scale independent of head geometry.
    span = g - knee
    if not np.isfinite(span) or span <= 0:
        return None
    prior_hip = g + 0.22 * span
    prior_waist = g + 0.85 * span
    q = P[skin]
    zs = np.linspace(g - 0.40 * span, g + 1.45 * span, 96)
    widths = np.full(len(zs), np.nan)
    for i, z in enumerate(zs):
        band = q[np.abs(q[:, 2] - z) <= 0.045 * span]
        left = -band[band[:, 0] < 0, 0]
        right = band[band[:, 0] > 0, 0]
        if min(len(left), len(right)) >= 12:
            widths[i] = torso_half(np.abs(band[:, 0]))
    good = np.isfinite(widths)
    if good.sum() >= 5:
        widths = np.interp(zs, zs[good], widths[good])
        widths = np.convolve(np.pad(widths, 2, mode='edge'), [1/9,2/9,3/9,2/9,1/9], mode='valid')
    def estimate(prior, lo, hi, maximum):
        ids = np.flatnonzero((zs >= lo) & (zs <= hi) & np.isfinite(widths))
        if len(ids) < 5:
            return prior, 0.0, np.nan
        v = widths[ids]
        j = int(np.argmax(v) if maximum else np.argmin(v))
        k = ids[j]
        prominence = min(abs(v[j]-v[0]), abs(v[j]-v[-1])) / max(v[j], 1e-9)
        confidence = float(np.clip(prominence / 0.12, 0, 1)) if 0 < j < len(ids)-1 else 0.0
        confidence *= float(good[ids].mean())
        z = prior + confidence * (zs[k]-prior)
        return z, confidence, float(np.interp(z, zs, widths))
    hip, hc, hw = estimate(prior_hip, g-0.35*span, g+0.55*span, True)
    waist, wc, ww = estimate(prior_waist, g+0.56*span, g+1.40*span, False)
    outer = 0.5 * (hip + waist)
    print('\n===== VIRTUAL ANATOMY (experimental) =====')
    print(f'groin={g:.2f} knee={knee:.2f} scale={span:.2f}')
    print(f'hip={hip:.2f} confidence={hc:.3f} half_width={hw:.2f}')
    print(f'waist={waist:.2f} confidence={wc:.3f} half_width={ww:.2f}')
    print(f'inguinal outer={outer:.2f} inner={g:.2f} (mesh)')
    # Smooth periodic diagonal: lateral high, medial low, front intermediate.
    angles = np.linspace(-np.pi, np.pi, 72, endpoint=False)
    # Four cardinal landmarks: preserve outer/inner, front slightly higher
    # than the symmetric midpoint, posterior slightly lower. Experimental.
    u = np.sin(angles)
    physical = g + (outer-g) * (
        0.5 + 0.5*np.cos(angles) + 0.08*u**3
    )
    roots = sc.zmap(physical)
    return {sign: (angles.copy(), roots.copy()) for sign in (1,-1)}


def fit_leg_roots(PR, skin_core, rw, axis):
    """
    Estimate the upper anatomical root of each leg from skinning weights.

    Returns:
        {sgn: (angle_centers, root_z)}

    Angles are measured around each leg axis:
      0       = outer side
      +/- pi  = inner side
      +/- pi/2 = front/back
    """
    n_angles = 24
    z_min, z_max = 45.0, 82.0
    dz = 1.5
    z_centers = np.arange(z_min + dz / 2, z_max, dz)
    angle_centers = -np.pi + (np.arange(n_angles) + 0.5) * (2 * np.pi / n_angles)

    result = {}

    for sgn, leg_name in ((1, "leg_r"), (-1, "leg_l")):
        lw = rw[leg_name]
        tw = rw["torso"]
        ratio = lw / np.maximum(lw + tw, 1e-9)

        ids = skin_core
        zk, xk, yk = axis[sgn]

        ax = np.interp(PR[ids, 2], zk, xk)
        ay = np.interp(PR[ids, 2], zk, yk)

        ex = PR[ids, 0] - ax
        ey = PR[ids, 1] - ay

        outward = sgn * ex
        radius = np.hypot(ex, ey)
        angle = np.arctan2(ey, outward)

        eligible = (
            ((lw[ids] + tw[ids]) > 0.10)
            & (radius >= 3.5)
            & (radius <= 15.5)
            & (PR[ids, 2] >= z_min)
            & (PR[ids, 2] < z_max)
        )

        ids = ids[eligible]
        angle = angle[eligible]
        ratio_local = ratio[ids]
        z_local = PR[ids, 2]

        ai = np.floor((angle + np.pi) / (2 * np.pi) * n_angles).astype(int)
        ai = np.clip(ai, 0, n_angles - 1)
        zi = np.floor((z_local - z_min) / dz).astype(int)
        zi = np.clip(zi, 0, len(z_centers) - 1)

        grid = np.full((n_angles, len(z_centers)), np.nan)

        for a in range(n_angles):
            for z in range(len(z_centers)):
                m = (ai == a) & (zi == z)
                if m.sum() >= 3:
                    grid[a, z] = np.median(ratio_local[m])

        root = np.full(n_angles, np.nan)

        for a in range(n_angles):
            profile = grid[a]
            good = np.isfinite(profile)

            if good.sum() < 4:
                continue

            # Fill sparse height gaps before smoothing.
            profile = np.interp(
                np.arange(len(z_centers)),
                np.flatnonzero(good),
                profile[good]
            )

            profile = np.convolve(
                np.pad(profile, 1, mode="edge"),
                [0.25, 0.50, 0.25],
                mode="valid"
            )

            # Find the transition from leg-dominant to torso-dominant.
            crossings = np.flatnonzero(
                (profile[:-1] >= 0.5) & (profile[1:] < 0.5)
            )

            if len(crossings):
                k = crossings[0]
                v0, v1 = profile[k], profile[k + 1]
                den = v1 - v0
                if abs(den) > 1e-9:
                    f = (0.5 - v0) / den
                    root[a] = z_centers[k] + f * dz
            else:
                k = int(np.argmin(np.abs(profile - 0.5)))
                if abs(profile[k] - 0.5) < 0.20:
                    root[a] = z_centers[k]

        valid = np.isfinite(root)

        if valid.sum() < 8:
            print(
                f"WARNING: insufficient leg-root samples for {leg_name} "
                f"({valid.sum()}/{n_angles}); using no root mask"
            )
            continue

        # Fill missing angular sectors periodically.
        x = np.arange(n_angles)
        xp = np.concatenate([
            x[valid] - n_angles,
            x[valid],
            x[valid] + n_angles
        ])
        yp = np.tile(root[valid], 3)
        root = np.interp(x, xp, yp)

        # Smooth around the circumference without a seam at +/- pi.
        kernel = np.array([1, 2, 3, 2, 1], dtype=float)
        kernel /= kernel.sum()
        root = sum(
            kernel[k] * np.roll(root, k - 2)
            for k in range(5)
        )

        result[sgn] = (angle_centers, root)

        print(
            f"leg root {leg_name}: "
            f"Z p10={np.percentile(root, 10):.1f} "
            f"median={np.median(root):.1f} "
            f"p90={np.percentile(root, 90):.1f}"
        )

    return result


def vnormals(P, T):
    tri = P[T]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    g = np.zeros_like(P)
    for k in range(3):
        np.add.at(g, T[:, k], fn)
    return g / np.maximum(np.linalg.norm(g, axis=1), 1e-12)[:, None]


def tri_clear(p, A, B, C):
    ab, ac, ap = B - A, C - A, p - A
    d1, d2 = (ab * ap).sum(1), (ac * ap).sum(1)
    bp = p - B
    d3, d4 = (ab * bp).sum(1), (ac * bp).sum(1)
    cp = p - C
    d5, d6 = (ab * cp).sum(1), (ac * cp).sum(1)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    den = va + vb + vc
    safe = np.where(np.abs(den) < 1e-12, 1.0, den)
    q = A + ab * (vb / safe)[:, None] + ac * (vc / safe)[:, None]
    m = (d1 <= 0) & (d2 <= 0)
    q[m] = A[m]
    m = (d3 >= 0) & (d4 <= d3)
    q[m] = B[m]
    t = d1 / np.where(np.abs(d1 - d3) < 1e-12, 1.0, d1 - d3)
    m = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
    q[m] = (A + ab * t[:, None])[m]
    m = (d6 >= 0) & (d5 <= d6)
    q[m] = C[m]
    w = d2 / np.where(np.abs(d2 - d6) < 1e-12, 1.0, d2 - d6)
    m = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
    q[m] = (A + ac * w[:, None])[m]
    t2 = (d4 - d3) / np.where(np.abs((d4 - d3) + (d5 - d6)) < 1e-12, 1.0, (d4 - d3) + (d5 - d6))
    m = (va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0)
    q[m] = (B + (C - B) * t2[:, None])[m]
    n = np.cross(ab, ac)
    nn = np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    dv = p - q
    return (dv * (n / nn)).sum(1), np.linalg.norm(dv, axis=1), q


def penetration(name, A0, A1, B0, B1, tri, sc, allow_s, zlim, cell=3.0):
    """Garment vertex vs skin surface: signed clearance before/after, measured
    at the same material point of the skin (q0 -> q0 + u(q0))."""
    tab = defaultdict(list)
    for i in range(len(B0)):
        p = B0[i]
        tab[(int(p[0] // cell), int(p[1] // cell), int(p[2] // cell))].append(i)
    vt = defaultdict(list)
    for k, (a, b, c) in enumerate(tri):
        vt[a].append(k)
        vt[b].append(k)
        vt[c].append(k)
    inside, worst, worst0, tested = 0, 1e9, 1e9, 0
    for i in range(len(A0)):
        if not (zlim[0] < A0[i, 2] < zlim[1]) or np.linalg.norm(A1[i] - A0[i]) < 0.02:
            continue
        p = A0[i]
        k = (int(p[0] // cell), int(p[1] // cell), int(p[2] // cell))
        cand = []
        for a in (-1, 0, 1):
            for b in (-1, 0, 1):
                for c in (-1, 0, 1):
                    cand.extend(tab.get((k[0] + a, k[1] + b, k[2] + c), []))
        if not cand:
            continue
        cand = np.array(cand)
        if ((B0[cand] - p) ** 2).sum(1).min() > 2.25:
            continue
        tset = sorted({t for v in cand for t in vt[v]})
        if not tset:
            continue
        t = tri[tset]
        dc0, du0, q0 = tri_clear(p, B0[t[:, 0]], B0[t[:, 1]], B0[t[:, 2]])
        kk = int(np.argmin(du0))
        d0 = float(dc0[kk])
        if d0 < -0.02:
            continue
        tested += 1
        q = q0[kk]
        fdx, fdy = sc.field(q[0:1], q[1:2], q[2:3])
        q1 = q + float(allow_s[t[kk]].mean()) * np.array([fdx[0], fdy[0], 0.0])
        a1, b1, c1 = B1[t[kk, 0]], B1[t[kk, 1]], B1[t[kk, 2]]
        n1 = np.cross(b1 - a1, c1 - a1)
        n1 /= max(np.linalg.norm(n1), 1e-12)
        d1 = float((A1[i] - q1) @ n1)
        inside += d1 < -0.02
        worst, worst0 = min(worst, d1), min(worst0, d0)
    if tested:
        print("    %-34s pairs %5d   min clearance %+6.3f -> %+6.3f cm   inside %d"
              % (name[:34], tested, worst0, worst, inside))
    return inside


# ================================================================ mod loading
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
            name = "Component %s - Line %d" % (comp, i + 1)
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


def set_visibility(ini, expected, visible):
    """Only change comment markers, preserving bytes, BOM and line endings."""
    import tempfile
    raw = open(ini, 'rb').read()
    lines = raw.splitlines(keepends=True)
    current = {}
    parse_draws(ini, metadata=current)
    for name, old in expected.items():
        now = current.get(name)
        if now != old:
            raise ValueError('The INI has changed: analyze again before changing visibility.')
        i = now['line'] - 1
        line = lines[i]
        match = re.match(rb'^([ \t]*)(;[ \t]*)?(drawindexed[ \t]*=)', line, re.I)
        if not match:
            raise ValueError('The expected DrawIndexed entry was not found.')
        if visible and match.group(2):
            lines[i] = line[:match.start(2)] + line[match.end(2):]
        elif not visible and not match.group(2):
            lines[i] = line[:match.end(1)] + b'; ' + line[match.end(1):]
    updated = b''.join(lines)
    if updated != raw:
        backup = ini + '.wardrobe.bak'
        if not os.path.exists(backup):
            with open(backup, 'xb') as f: f.write(raw)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(ini)))
        try:
            with os.fdopen(fd, 'wb') as f: f.write(updated)
            if open(ini, 'rb').read() != raw:
                raise ValueError('The INI changed during the operation.')
            os.replace(tmp, ini)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
    result = {}
    parse_draws(ini, metadata=result)
    return result


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

    print("\n--- COORDINATE DIAGNOSTIC ---")
    print("Vertices in Z band:", len(z_band))

    if len(z_band):
        xyz = P[z_band]

        for i, axis in enumerate(["X", "Y", "Z"]):
            values = xyz[:, i]
            print(
                f"{axis}: range {values.min():.3f} to {values.max():.3f} "
                f"| minimum absolute value: {np.abs(values).min():.3f}"
            )

        nearest = z_band[np.argsort(np.abs(P[z_band, 0]))[:10]]

        print("\n10 vertices closest to the X centerline:")
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
            "No skin vertices were found in the crotch region.\n"
            f"Skin vertices: {len(skin)}\n"
            f"Height H: {H:.4f}\n"
            f"X range: {skin_xyz[:, 0].min():.4f} to {skin_xyz[:, 0].max():.4f}\n"
            f"Z range: {skin_xyz[:, 2].min():.4f} to {skin_xyz[:, 2].max():.4f}\n"
            "Check the Skin part selection or the model position."
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


def normalize_legacy_part_names(cfg, draws):
    """Migrate only generated legacy part IDs; preserve real mod names and labels."""
    def resolve(name):
        if not isinstance(name, str) or name in draws:
            return name
        # Historical non-English spelling, encoded to keep source text English.
        match = re.fullmatch(r"Component (\d+) - L\u00ednea (\d+)( \(\d+\))?", name)
        if match:
            candidate = "Component %s - Line %s%s" % (match[1], match[2], match[3] or "")
            if candidate in draws:
                return candidate
        return name
    for key in ("skin", "freeze", "move", "anatomy", "_auto_skin"):
        if isinstance(cfg.get(key), list):
            cfg[key] = [resolve(name) for name in cfg[key]]
    if isinstance(cfg.get("labels"), dict):
        labels = cfg["labels"]
        cfg["labels"] = {resolve(name): value for name, value in labels.items()}
        # If both names are present, the current ID takes precedence.
        cfg["labels"].update({name: value for name, value in labels.items() if name in draws})
    return cfg


# ================================================================ main
def run(mod, mode, bounce=None):
    M = os.path.join(mod, "Meshes")
    POS, VEC = os.path.join(M, "Position.buf"), os.path.join(M, "Vector.buf")
    if mode == "restore":
        shutil.copy2(POS + ".orig", POS)
        shutil.copy2(VEC + ".orig", VEC)
        print("restored Position.buf / Vector.buf from .orig")
        return
    cfg_path = os.path.join(mod, "thicc.json")
    cfg = json.loads(json.dumps(DEFAULT_CFG))
    if os.path.exists(cfg_path):
        cfg.update(json.load(open(cfg_path, encoding="utf-8")))
    if bounce is not None:
        cfg["bounce"] = bounce
    level = cfg.get("bounce", "normal")
    if level not in BOUNCE_LEVELS:
        raise ValueError("Invalid bounce level: %s" % level)
    if mode != "diagnose" and level != "normal":
        raise ValueError("Bounce %s is not available yet: WWMI dynamic physics still needs validation. Select Normal. No buffers were modified." % level)
    for f in (POS, VEC):
        if mode != "diagnose" and not os.path.exists(f + ".orig"):
            shutil.copy2(f, f + ".orig")
            print("backup %s -> .orig" % os.path.basename(f))

    amounts = dict(PRESETS[cfg["preset"]])
    amounts.update(cfg.get("amounts", {}))

    ini = find_ini(mod)
    COMP = {}
    draw_meta = {}
    DRAWS = parse_draws(ini, COMP, draw_meta)
    normalize_legacy_part_names(cfg, DRAWS)
    # Phase 1.9B: internal, read-only structural evidence. The user does not
    # launch a second script. Never change Wardrobe roles or morph masks here.
    wwmi_structure_summary = None
    if mode == "diagnose":
        try:
            from wwmi_structure import analyze as analyze_wwmi_structure
            structural = analyze_wwmi_structure(ini)
            structural_draws = structural.get("draws", [])
            wwmi_structure_summary = {
                "schema": structural.get("schema"),
                "sections": structural.get("sections", 0),
                "resources": len(structural.get("resources", {})),
                "draws": len(structural_draws),
                "wardrobe_draws": len(DRAWS),
                "potential_shared_geometry": len(structural.get("potential_shared_geometry", [])),
                "warnings": structural.get("warnings", []),
                "limitations": structural.get("limitations", []),
            }
            print("\n--- WWMI STRUCTURE (diagnostic, no automatic classification) ---")
            print("sections=%d resources=%d structural_draws=%d wardrobe_draws=%d potential_shared=%d" % (
                wwmi_structure_summary["sections"], wwmi_structure_summary["resources"],
                wwmi_structure_summary["draws"], wwmi_structure_summary["wardrobe_draws"],
                wwmi_structure_summary["potential_shared_geometry"]))
            for warning in wwmi_structure_summary["warnings"]:
                print("WWMI structural note:", warning)
            if wwmi_structure_summary["draws"] != len(DRAWS):
                print("WWMI structural note: draw counts may differ because of inactive draws or CommandLists")
        except Exception as exc:
            # Structural diagnostics must never block a working mod analysis.
            wwmi_structure_summary = {"error": "%s: %s" % (type(exc).__name__, exc)}
            print("WWMI structure unavailable (diagnostic only):", exc)
    P0 = np.fromfile(POS + ".orig" if os.path.exists(POS + ".orig") else POS, np.float32).reshape(-1, 3).astype(np.float64)
    N = len(P0)
    idx = np.fromfile(os.path.join(M, "Index.buf"), np.uint32)
    T = idx[:len(idx) // 3 * 3].reshape(-1, 3)
    # Validate the actual index ranges and base-vertex offsets before any
    # component is measured or any mesh buffer is modified. This uses the
    # DrawIndexed metadata already collected by Wardrobe (including hidden
    # pieces), not a second list from an independent parser.
    for part_name, (first_index, index_count) in DRAWS.items():
        meta = draw_meta[part_name]
        fields = [x.strip() for x in meta["draw"].split(",")]
        base_vertex = int(fields[2]) if len(fields) > 2 else 0
        if first_index < 0 or index_count < 0 or first_index + index_count > len(idx):
            raise ValueError(
                "WWMI: %s has a DrawIndexed range outside Index.buf "
                "(start=%d, count=%d, indices=%d). "
                "No buffers were modified."
                % (part_name, first_index, index_count, len(idx)))
        if index_count % 3:
            raise ValueError(
                "WWMI: %s contains %d indices, not divisible by 3. "
                "No buffers were modified."
                % (part_name, index_count))
        if index_count:
            raw_indices = idx[first_index:first_index + index_count].astype(np.int64)
            actual_min = int(raw_indices.min()) + base_vertex
            actual_max = int(raw_indices.max()) + base_vertex
            if actual_min < 0 or actual_max >= N:
                raise ValueError(
                    "WWMI: %s references nonexistent vertices "
                    "(range=%d..%d, vertices=%d, base=%d). "
                    "No buffers were modified."
                    % (part_name, actual_min, actual_max, N, base_vertex))
    print("WWMI: DrawIndexed ranges and vertex references validated (%d parts)." % len(DRAWS))
    print("ini %s   verts %d   tris %d   parts %d"
          % (os.path.basename(ini), N, len(T), len(DRAWS)))
    if not DRAWS:
        sys.exit("no drawindexed found in the TextureOverrideComponent sections of " + ini)

    def verts(n):
        s, c = DRAWS[n]
        fields = draw_meta[n]["draw"].split(",")
        base = int(fields[2]) if len(fields) > 2 else 0
        return np.unique(idx[s:s + c].astype(np.int64) + base)

    def tris(n):
        s, c = DRAWS[n]
        fields = draw_meta[n]["draw"].split(",")
        base = int(fields[2]) if len(fields) > 2 else 0
        return (idx[s:s+c].astype(np.int64) + base).reshape(-1, 3)
    
    # 002: independent read-only evidence, before effective roles or anatomy.
    info = {n: (float(P0[verts(n),2].min()), float(P0[verts(n),2].max()), len(verts(n))) for n in DRAWS}
    from detection_cache import detection
    automatic_evidence = detection(P0, {n: tris(n) for n in DRAWS}, COMP,
                                  ini, draw_meta, M, load_bones)
    suggested = [n for n in DRAWS if automatic_evidence[n]['role'] == 'skin']
    explicit_skin = set(cfg.get('skin', []))
    explicit_roles = explicit_skin | set(cfg.get('freeze', [])) | set(cfg.get('move', []))
    def role_for(n):
        if n in explicit_skin: return 'skin'
        if n in cfg.get('freeze', []): return 'frozen'
        if n in cfg.get('move', []): return 'garment'
        if COMP[n] in (0,1,2): return 'frozen'
        if n in suggested: return 'skin'
        return 'frozen' if FREEZE_RE.search(n) else 'garment'
    # A saved anatomy selection is authoritative. Otherwise use effective skin
    # (manual overrides included) plus known face; no topology veto.
    saved_anatomy = cfg.get('anatomy', [])
    anatomy_names = list(saved_anatomy) if saved_anatomy else [n for n in DRAWS if role_for(n)=='skin' or COMP[n]==2]
    unknown = [n for n in anatomy_names if n not in DRAWS]
    anatomy_names = [n for n in dict.fromkeys(anatomy_names) if n in DRAWS]
    cfg['anatomy'] = anatomy_names
    state = 'pending'
    partial_regions = {}
    skeleton_warnings = []
    H = None
    rw = None
    print('\n===== WEIGHTED AUTO VS EFFECTIVE ROLES =====')
    for n in DRAWS:
        f = automatic_evidence[n]
        print('%s | auto=%s score=%s | effective=%s | manual=%s | anatomy=%s' %
              (n,f['role'],f['score'],role_for(n),n in explicit_roles,n in anatomy_names))
    print('===== END WEIGHTED AUTO VS EFFECTIVE ROLES =====\n')
    def result(warnings, landmarks=None, roles=None, regions=None, ready=False, natural=None):
        warnings = list(dict.fromkeys(skeleton_warnings + warnings))
        for w in warnings: print('WARNING: '+w)
        return dict(parts=[(n, (roles or {}).get(n, role_for(n)), *info[n], (regions if regions is not None else partial_regions).get(n,'')) for n in DRAWS],
                    landmarks=landmarks or {}, natural=natural or {}, warnings=warnings, cfg=cfg, height=H,
                    stickman=rw is not None, skeleton_status=state, ready=ready, ini=ini, draw_meta=draw_meta,
                    wwmi_structure=wwmi_structure_summary, role_evidence=automatic_evidence)
    if unknown or not anatomy_names:
        msg = 'Unknown anatomical parts: '+', '.join(unknown) if unknown else 'No anatomical parts were identified. Select them and save the anatomy.'
        if mode == 'diagnose': return result([msg])
        raise ValueError(msg)
    if not explicit_skin and not cfg.get('skin'):
        print('Automatic anatomy/roles are suggestions; check all body parts.')

    anatomy_v = np.unique(
        np.concatenate([verts(n) for n in anatomy_names])
    )

    anatomy_mask = np.zeros(N, dtype=bool)
    anatomy_mask[anatomy_v] = True

    H = float(P0[anatomy_v, 2].max())

    print("\n--- ANATOMICAL GEOMETRY ---")
    print("Parts:", anatomy_names)
    print("Anatomical vertices:", len(anatomy_v))
    print("Anatomical height:", round(H, 3), "cm")

    # ---- bones: unified skeleton or per-component ids ------------------------
    try:
        bi, bw = load_bones(M, N)
    except (OSError, ValueError, IndexError) as exc:
        if mode == 'diagnose':
            return result(['Could not read bones for deformation: '+str(exc)])
        raise
    ini_txt = open(ini, encoding="utf-8", errors="replace").read()
    unified = os.path.exists(os.path.join(M, "BlendRemapVertexVG.buf")) or "vg_offset" in ini_txt
    if not unified:
        # old WWMI format: every component numbers its own bones from 0
        vcomp = np.full(N, -1, np.int64)
        for n in DRAWS:
            vcomp[verts(n)] = COMP[n]
        bi = (vcomp[:, None] + 1) * 1024 + bi
        print("bones: per-component numbering (old format) -> stickman disabled")

    # ---- stickman (skeleton regions) ----------------------------------------
    rw = None
    state = "old_format" if not unified else "failed"
    if unified:
        try:
            region, sinfo = skeleton.label_bones(
                P0,
                bi,
                bw,
                H,
                vertex_mask=anatomy_mask,
                triangles=T
            )
            rw = skeleton.region_weights(bi, bw, region)
            for n in DRAWS:
                v = verts(n)
                f = {'head':rw['head'][v].mean(), 'torso':rw['torso'][v].mean(),
                     'arms':(rw['arm_l'][v]+rw['arm_r'][v]).mean(), 'legs':(rw['leg_l'][v]+rw['leg_r'][v]).mean()}
                k = max(f,key=f.get)
                partial_regions[n] = '%s %d%%'%(k,round(100*f[k])) if f[k] > 0 else 'Unidentified'
            s = sinfo["seeds"]
            C = sinfo["centroid"]
            good = all(s[k] is not None for k in ("foot_r", "foot_l", "head", "hand_r", "hand_l"))
            if good:
                good = (C[s["foot_r"], 2] < 0.2 * H and C[s["foot_l"], 2] < 0.2 * H
                        and C[s["head"], 2] > 0.75 * H
                        and min(abs(C[s["hand_r"], 0]), abs(C[s["hand_l"], 0])) > 0.08 * H
                        and rw["leg_l"].sum() > 100 and rw["leg_r"].sum() > 100
                        and rw["arm_l"].sum() > 100 and rw["arm_r"].sum() > 100)
            if not good:
                print("stickman: incomplete skeleton -> falling back to geometric rules")
                missing = [label for key,label in [('foot_r','right foot'),('foot_l','left foot'),('head','head'),('hand_r','right hand'),('hand_l','left hand')] if s[key] is None]
                skeleton_warnings.append(('Not identified: '+', '.join(missing)+'. ' if missing else 'The detected body branches did not pass validation. ')+'Include the missing body parts in Anatomy, even if they are clothing or frozen.')
                partial_regions = {n: ('~ '+v if v != 'Unidentified' else v) for n,v in partial_regions.items()}
                rw = None
                state = "incomplete"
            else:
                state = "complete"
                cnt = {
                    r: sum(1 for v in region.values() if v == r)
                    for r in rw
                }

                print(
                    "stickman: "
                    + "  ".join("%s %d bones" % kv for kv in cnt.items())
                )

                skeleton.print_anatomy_report(sinfo, region)
        except Exception as e:  # never block the sculpt because of the labeller
            print("stickman failed (%s) -> falling back to geometric rules" % e)
            skeleton_warnings.append("Error reconstructing the skeleton: "+str(e))
            rw = None
    # ---- diagnostic: 3D leg root distribution -----------------------------
    if rw is not None:
        print("\n===== LEG ROOT 3D DIAGNOSTIC =====")

        for leg, sgn in (("leg_r", 1), ("leg_l", -1)):
            lw = rw[leg]
            tw = rw["torso"]

            shared = (lw > 0.05) & (tw > 0.05)
            dominant = lw > tw

            print(f"\n{leg}:")

            for z0 in range(35, 66, 5):
                z1 = z0 + 5

                mask = (
                    shared
                    & (P0[:, 2] >= z0)
                    & (P0[:, 2] < z1)
                )

                ids = np.where(mask)[0]

                if len(ids) == 0:
                    continue

                # Positive X means outward, negative means toward the center
                outward = sgn * P0[ids, 0]

                print(
                    f"  Z {z0:02d}-{z1:02d}: "
                    f"n={len(ids):4d} "
                    f"Xout=[{np.percentile(outward, 10):6.2f}, "
                    f"{np.percentile(outward, 50):6.2f}, "
                    f"{np.percentile(outward, 90):6.2f}] "
                    f"Y=[{np.percentile(P0[ids, 1], 10):6.2f}, "
                    f"{np.percentile(P0[ids, 1], 50):6.2f}, "
                    f"{np.percentile(P0[ids, 1], 90):6.2f}]"
                )

            # Show where leg influence becomes dominant
            ids = np.where(dominant & (P0[:, 2] >= 35) & (P0[:, 2] < 65))[0]

            if len(ids):
                print(
                    "  Leg-dominant vertices:"
                    f" Z={np.percentile(P0[ids, 2], [10, 50, 90]).round(2)}"
                    f" Xout={np.percentile(sgn * P0[ids, 0], [10, 50, 90]).round(2)}"
                )

        print("===== END 3D DIAGNOSTIC =====\n")
    headw = rw["head"] if rw is not None else np.zeros(N)

    # ---- classification ----------------------------------------------------
    info = {n: (P0[verts(n), 2].min(), P0[verts(n), 2].max(), len(verts(n))) for n in DRAWS}
    head_of = {n: float(headw[verts(n)].mean()) for n in DRAWS}
    SKIN = [n for n in DRAWS if role_for(n) == 'skin']
    if not SKIN:
        msg = 'No skin parts found. Manually mark the body parts.'
        if mode == 'diagnose': return result([msg])
        raise ValueError(msg)
    skin_v = np.unique(np.concatenate([verts(n) for n in SKIN]))
    print("\n--- COMPONENT DIAGNOSTIC ---")

    for name in DRAWS:
        v = verts(name)

        band = v[
            (P0[v, 2] > 0.3 * H) &
            (P0[v, 2] < 0.7 * H)
        ]

        if len(band):
            x = np.abs(P0[band, 0])

            print(
                f"{name}: "
                f"verts={len(v)}, "
                f"band={len(band)}, "
                f"min_abs_X={x.min():.3f}, "
                f"X<0.8={np.sum(x < 0.8)}, "
                f"X<3={np.sum(x < 3)}"
            )
        else:
            print(f"{name}: verts={len(v)}, no vertices in band")

    thigh_widths = [(band_stats(P0, skin_v, z - 1, z + 1) or (np.nan,))[0]
                    for z in np.arange(0.35 * H, 0.47 * H, 1.0)]
    if not np.isfinite(thigh_widths).any():
        msg = "No Skin surface in the thigh band (Z %.1f–%.1f cm). Mark the body parts covering that region as Skin and analyze again. Current Skin: %s." % (.35*H,.47*H,", ".join(SKIN))
        if mode == "diagnose": return result([msg])
        raise ValueError(msg)
    thigh_half = np.nanmax(thigh_widths)
    if rw is not None:
        armw = np.clip(rw["arm_l"] + rw["arm_r"], 0.0, 1.0)
        arm_note = "stickman arms"
    else:
        # arm bones: most of their skin weight lies outside the thigh/hip outline
        nb = int(bi.max()) + 1
        wsum, wout, cz = np.zeros(nb), np.zeros(nb), np.zeros(nb)
        outside = (np.abs(P0[skin_v, 0]) > 1.05 * thigh_half).astype(np.float64)
        for k in range(bi.shape[1]):
            bs, ws = bi[skin_v, k], bw[skin_v, k]
            np.add.at(wsum, bs, ws)
            np.add.at(wout, bs, ws * outside)
            np.add.at(cz, bs, ws * P0[skin_v, 2])
        ok = wsum > 1.0
        wout[ok] /= wsum[ok]
        cz[ok] /= wsum[ok]
        arm_bone = ok & (wout > 0.5) & (cz > 0.45 * H) & (cz < 0.88 * H)
        armw = np.zeros(N)
        for k in range(bi.shape[1]):
            armw += np.where(arm_bone[bi[:, k]], bw[:, k], 0.0)
        arm_note = "%d arm bones (skin weight mostly at |x| > %.1f cm)" % (arm_bone.sum(), 1.05 * thigh_half)

    skin_core = skin_v[armw[skin_v] < 0.01]
    print("\n--- FILTER DIAGNOSTIC ---")
    print("SKIN parts:", SKIN)
    print("Vertices skin_v:", len(skin_v))
    print("Vertices skin_core:", len(skin_core))

    for name, vertices in [
        ("BEFORE filtering", skin_v),
        ("AFTER filtering", skin_core)
    ]:
        band = vertices[
            (P0[vertices, 2] > 0.3 * H) &
            (P0[vertices, 2] < 0.7 * H)
        ]

        if len(band):
            x = np.abs(P0[band, 0])
            print(f"\n{name}:")
            print("Vertices in band:", len(band))
            print("Minimum |X|:", x.min())
            print("Vertices with |X| < 0.8:", np.sum(x < 0.8))
            print("Vertices with |X| < 3:", np.sum(x < 3))
            print("Vertices with |X| < 5:", np.sum(x < 5))
            print("Vertices with |X| < 11:", np.sum(x < 11))
    skin_tri = np.concatenate([tris(n) for n in SKIN])
    skin_tri = skin_tri[(armw[skin_tri] < 0.01).all(1)]
    if len(skin_core) < 500:
        if mode == "diagnose": return result(["Insufficient skin after filtering out the arms."])
        raise ValueError("Insufficient skin after filtering out the arms.")
    try:
        L = measure(P0, skin_core, H, skin_tri)
    except (ValueError, IndexError) as e:
        if mode == 'diagnose': return result(['Could not measure the landmarks: '+str(e)])
        raise
    natural = dict(L)
    if mode == "diagnose":
        try:
            import torso_profile
            torso_profile.report(P0, skin_tri, natural, [
                (n, t[(armw[t] < 0.01).all(1)]) for n in SKIN
                for t in [tris(n)] if len(t) and (armw[t] < 0.01).all(1).any()
            ])
            refs = None
            if rw is not None:
                refs = {k: round(float(sinfo['centroid'][v, 2]), 3)
                        for k, v in sinfo['seeds'].items() if v is not None}
            torso_profile.report_continuity(
                P0, np.concatenate([tris(n) for n in SKIN]), skin_tri,
                natural, np.concatenate([tris(n) for n in anatomy_names]), refs)
            torso_profile.report_regions(
                P0, np.concatenate([tris(n) for n in SKIN]), skin_tri, natural, refs)
        except Exception as e:
            print("Torso profile unavailable (diagnostic only):", e)
    if mode == "diagnose":
        try:
            import joint_profile
            joint_profile.report(P0, np.concatenate([tris(n) for n in SKIN]),
                                 natural, sinfo if rw is not None else None)
        except Exception as e:
            print("Joint profile unavailable (diagnostic only):", e)
    if mode == "diagnose":
        try:
            import surface_evidence
            surface_evidence.report(P0, [(n, tris(n), role_for(n)) for n in DRAWS], natural, bi, bw, unified, mod, ini, draw_meta)
        except Exception as e:
            print("Independent surfaces unavailable (diagnostic only):", e)
    L.update(cfg.get("landmarks", {}))
    warn = []
    if not (2.0 <= L["apex"] - L["crotch"] <= 14.0):
        print("INFO: vertical difference between crotch and gluteal apex: %.2f cm (non-blocking)." % (L["apex"] - L["crotch"]))
    if not (L["ankle"] < L["knee"] < L["crotch"] < L["waist"]):
        warn.append("landmark order ankle < knee < crotch < waist is broken")

    skin_top = float(P0[skin_core,2].max())
    if not all(np.isfinite(v) for v in L.values()) or L['waist'] >= min(skin_top,H) or not (L['knee'] < L['apex'] < L['waist'] and L['knee'] < L['hip_z'] < L['waist']) or L['hip_z'] > L['apex'] + .55*(L['crotch']-L['knee']):
        warn.append('Incompatible measurements: waist %.2f, hip Z %.2f, crotch %.2f, gluteal apex %.2f, skin limit %.2f cm. Check the Skin selection or correct the displayed measurements.' % (L['waist'],L['hip_z'],L['crotch'],L['apex'],skin_top))
    if state in ('incomplete','failed'):
        warn.append('Unified skeleton incomplete or not reconstructed; include the head, arms and legs in anatomy.')
    freeze = set(cfg["freeze"]) | {n for n in DRAWS if COMP[n] in (0,1,2) and n not in explicit_roles}
    auto_frozen = []
    for n in DRAWS:
        if n in SKIN or n in explicit_roles:
            continue
        zmin, zmax, _ = info[n]
        if rw is not None:
            hit = head_of[n] > 0.6 or FREEZE_RE.search(n) or zmin > L["waist"] + 4
        else:
            hit = (FREEZE_RE.search(n) or zmin > L["waist"] + 4
                   or (zmax > 0.90 * H and zmin > 0.40 * H))
        if hit:
            freeze.add(n)
            auto_frozen.append(n)
    GARMENTS = [n for n in DRAWS if n not in SKIN and n not in freeze]

    print("\nparts:")
    for n in DRAWS:
        role = "SKIN" if n in SKIN else ("frozen" if n in freeze else "garment")
        print("  %-8s z %6.1f..%6.1f  verts %6d   %s" % (role, info[n][0], info[n][1], info[n][2], n))
    print("\narms: %s   arm-weighted verts %d" % (arm_note, (armw > 0.01).sum()))
    print("landmarks: " + "  ".join("%s %.1f" % (k, v) for k, v in L.items()))
    for w in warn:
        print("WARNING: %s -> check the model and set \"landmarks\" in thicc.json" % w)
    print("amounts (%s): %s   inner_fill %s" % (cfg["preset"], amounts, cfg["inner_fill"]))

    if mode == 'diagnose':
        roles = {n: 'skin' if n in SKIN else 'frozen' if n in freeze else 'garment' for n in DRAWS}
        regions = dict(partial_regions)
        if rw is not None:
            for n in DRAWS:
                v = verts(n)
                f = {'head':rw['head'][v].mean(), 'torso':rw['torso'][v].mean(),
                     'arms':(rw['arm_l'][v]+rw['arm_r'][v]).mean(), 'legs':(rw['leg_l'][v]+rw['leg_r'][v]).mean()}
                k = max(f,key=f.get); regions[n] = '%s %d%%'%(k,round(100*f[k])) if round(100*f[k]) > 0 else 'Unidentified'
        return result(warn, L, roles, regions, ready=not (warn or skeleton_warnings), natural=natural)
    if warn:
        raise ValueError('Apply blocked: '+ '; '.join(warn))
    if not os.path.exists(cfg_path):
        out = dict(DEFAULT_CFG)
        out["_auto_skin"] = SKIN
        out["_auto_frozen"] = auto_frozen
        out["_landmarks"] = {k: round(v, 2) for k, v in L.items()}
        json.dump(out, open(cfg_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("wrote %s (edit it to override the automatic choices)" % cfg_path)
    # ---- frame + calibrations ----------------------------------------------
    reconstructed_fill = bool(cfg["inner_fill"])
    sc = Sculpt(amounts, cfg["inner_fill"] and not reconstructed_fill)
    sc.continuous = cfg.get("deformation_field", "Legacy") == "Continuous"
    print("\n===== DEFORMATION PHASE 2.3 / CONTINUOUS FIELD =====")
    print("Field mode: " + ("Continuous" if sc.continuous else "Legacy"))
    sc.set_frame(L)
    print("\nframe: lateral scale %.3f   z map ankle %.1f->%.1f knee %.1f->%.1f crotch %.1f->%.1f "
          "apex %.1f->%.1f waist %.1f->%.1f"
          % (sc.s, L["ankle"], REF["ankle"], L["knee"], REF["knee"], L["crotch"], REF["crotch"],
             L["apex"], REF["apex"], L["waist"], REF["waist"]))

    # Strict anatomical arm exclusion.  A weak bone weight must not allow
    # a leg/hip morph to leak into the shoulder or arm surface.
    # The small transition is on bone influence, not a global XYZ box.
    arm_influence = np.clip(armw, 0.0, 1.0)
    arm_exclusion = 1.0 - smoothstep(0.001, 0.01, arm_influence)
    allow = arm_exclusion.copy()
    print("Arm exclusion: fully protected=%d, transition=%d" % (
        np.count_nonzero(arm_exclusion == 0),
        np.count_nonzero((arm_exclusion > 0) & (arm_exclusion < 1))))
    if cfg.get("advanced_arm_protection", False):
        from arm_protection import mobility
        previous_allow = allow.copy()
        # Advanced protection may only further restrict, never reopen arms.
        allow = np.minimum(allow, mobility(armw))
        print("\n===== DEFORMATION PHASE 2.8 / ARM PROTECTION =====")
        print("Arm evidence: %s; additionally attenuated: %d; newly pinned: %d" % (
            arm_note, np.count_nonzero(allow < previous_allow - 1e-8),
            np.count_nonzero((allow == 0) & (previous_allow > 0))))
        if not np.any(armw > .01):
            print("No arm evidence found; protection unchanged.")

    for n in freeze:
        if n in DRAWS:
            allow[verts(n)] = 0.0

    X, Y, Z = sc.to_ref(P0[:, 0], P0[:, 1], P0[:, 2])
    PR = np.stack([X, Y, Z], 1)
    sc.axis = fit_axis(PR[skin_tri])
    
    # Build continuous anatomical root profiles from skin vertices only.
    if rw is not None:
        sc.root = fit_leg_roots(PR, skin_core, rw, sc.axis)
        
    old_root = sc.root
    virtual_root = morphological_roots(P0, skin_core, L, sc)
    if virtual_root is not None:
        for sign, (angles, roots) in virtual_root.items():
            for angle in (0.0, np.pi/2, np.pi, -np.pi/2):
                old = np.interp(angle, *old_root[sign], period=2*np.pi) if old_root and sign in old_root else np.nan
                new = np.interp(angle, angles, roots, period=2*np.pi)
                print(f'root compare side={sign:+d} angle={np.degrees(angle):.0f}: skinning={old:.2f} virtual={new:.2f} (ref)')
        if cfg.get('virtual_inguinal', True):
            sc.root = virtual_root

    if sc.root is not None:
        print("\n===== LEG ROOT ANGULAR PROFILE =====")

        for sgn, name in ((1, "leg_r"), (-1, "leg_l")):
            if sgn not in sc.root:
                continue

            angles, roots = sc.root[sgn]
            print(f"\n{name}:")

            thigh_outer = np.interp(
                0.0, angles, roots,
                period=2.0 * np.pi
            )

            thigh_inner = np.interp(
                np.pi, angles, roots,
                period=2.0 * np.pi
            )

            print(f"  Thigh outer Z: {thigh_outer:.2f}")
            print(f"  Thigh inner Z: {thigh_inner:.2f}")
            print(f"  Diagonal delta: {thigh_outer - thigh_inner:.2f}")
            
            for angle, z in zip(angles, roots):
                print(
                    f"  angle={np.degrees(angle):7.1f}°"
                    f"   root_z={z:6.2f}"
                )
    
    # ---- diagnostic: anatomical leg root in 3D ---------------------------
    if rw is not None:
        print("\n===== LEG ROOT 3D BY SIDE =====")

        # Coordinates in the same reference frame as sc.axis
        for leg, sgn in (("leg_r", 1), ("leg_l", -1)):
            lw = rw[leg]
            tw = rw["torso"]

            # Relative leg influence: 0 = torso, 1 = leg
            ratio = lw / np.maximum(lw + tw, 1e-9)

            # Leg centerline
            zk, xk, yk = sc.axis[sgn]
            ax = np.interp(PR[:, 2], zk, xk)
            ay = np.interp(PR[:, 2], zk, yk)

            dx = PR[:, 0] - ax
            dy = PR[:, 1] - ay
            outward = sgn * dx

            # Only vertices with meaningful torso/leg influence
            valid = np.zeros(len(PR), dtype=bool)
            valid[skin_core] = (lw[skin_core] + tw[skin_core]) > 0.10

            print(f"\n--- {leg} ---")

            # Analyze the transition at different heights
            for z0, z1 in [
                (45, 50), (50, 55), (55, 60),
                (60, 65), (65, 70), (70, 75),
                (75, 80), (80, 85), (85, 90)
            ]:
                mask = (
                    valid
                    & (PR[:, 2] >= z0)
                    & (PR[:, 2] < z1)
                )

                ids = np.flatnonzero(mask)

                if len(ids) == 0:
                    continue

                # Split around the leg circumference
                sectors = {
                    "outer": outward[ids] > 3.0,
                    "inner": outward[ids] < -3.0,
                    "front": (np.abs(outward[ids]) <= 3.0) & (dy[ids] < 0),
                    "back":  (np.abs(outward[ids]) <= 3.0) & (dy[ids] >= 0),
                }

                print(f"z {z0:5.1f}-{z1:5.1f}:")

                for name, sector in sectors.items():
                    vi = ids[sector]

                    if len(vi) == 0:
                        continue

                    r = ratio[vi]
                    print(
                        f"  {name:5s}: "
                        f"n={len(vi):5d} "
                        f"leg={np.mean(r):.3f} "
                        f"p10={np.percentile(r, 10):.3f} "
                        f"p50={np.percentile(r, 50):.3f} "
                        f"p90={np.percentile(r, 90):.3f}"
                    )

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

    def outline(Q):
        # exact cross-section contour (independent of the vertex density)
        tri = Q[tri_l]
        o = np.full(len(zs), np.nan)
        for i, z in enumerate(zs):
            c = contour(tri, z)
            c = np.abs(c[:, 0])
            c = c[c < 26.0]
            if len(c) >= 6:
                o[i] = torso_half(c)
        return o
    original_outline = outline(PRs)
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
    for it in range(8):
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
        Hc = np.clip(Hc + 1.3 * env * err, -1.0, 6.0)
        Hc = np.convolve(np.pad(Hc, 3, mode="edge"), g, "valid") * env
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

    # Calibrate the baseline first; otherwise calibration cancels the X control.
    directional = cfg.get("directional_expansion", {})
    for key in sc.direction:
        pair = directional.get(key, [1.0, 1.0])
        if len(pair) != 2 or not np.all(np.isfinite(pair)) or not np.all((np.asarray(pair) >= 0) & (np.asarray(pair) <= 2)):
            raise ValueError("Directional multipliers must be finite and between 0 and 2")
        sc.direction[key] = tuple(map(float, pair))
    directional_active = any(pair != (1.0, 1.0) for pair in sc.direction.values())
    print("\n===== DEFORMATION PHASE 2.5 / DIRECTIONAL EXPANSION =====")
    print("X/Y multipliers: " + str(sc.direction))
    if directional_active and cfg.get('surface_rounding', True):
        print("Thigh rounding skipped: radial correction can reintroduce disabled directions.")
    if cfg.get('surface_rounding', True) and not directional_active:
        fit_rounding(sc, PR, [tris(n) for n in SKIN], L)

    # ---- apply -------------------------------------------------------------
    fdx, fdy = sc.field(P0[:, 0], P0[:, 1], P0[:, 2])
    from seam_guard import SeamGuard
    frozen_ids = np.unique(np.concatenate([verts(n) for n in freeze if n in DRAWS])) if any(n in DRAWS for n in freeze) else np.empty(0, dtype=np.int64)
    seam = SeamGuard(P0, frozen_ids, allow, H) if cfg.get("seam_guard", True) else SeamGuard(P0, [], allow, H)
    guard = seam(P0)
    print("\n===== DEFORMATION PHASE 2.1 / SEAM GUARD =====")
    print("Coincident moving/frozen vertices: %d; transition width %.3f cm; protected moving vertices: %d" % (seam.count, seam.width, np.count_nonzero((guard < 1) & (allow > 0))))
    dx, dy = fdx * allow * guard, fdy * allow * guard
    new = P0 + np.stack([dx, dy, np.zeros(N)], 1)
    sqd = np.ones(N)
    if cfg["inner_fill"] and not reconstructed_fill:
        # flatten the meeting thighs against the midline (soft floor)
        layer = np.zeros(N, np.int8)
        for n in GARMENTS:
            layer[verts(n)] = 2
        layer[skin_v] = 1
        lo, hi = L["knee"] - 10, L["crotch"] + 0.3
        cand = np.nonzero((layer > 0) & (P0[:, 2] > lo) & (P0[:, 2] < hi) & (allow > 0))[0]
        side = np.sign(P0[cand, 0])
        xx = new[cand, 0] * side
        k = xx < 2.0
        cand, side, xx = cand[k], side[k], xx[k]
        floor = np.where(layer[cand] == 1, SKIN_FLOOR, GARMENT_FLOOR)
        bb = smoothstep(0.1, 0.6, np.abs(P0[cand, 0])) * (1.0 - smoothstep(hi - 1.5, hi, P0[cand, 2]))
        bb *= guard[cand]
        u = (xx - floor) / SQUEEZE_SOFT
        f = floor + SQUEEZE_SOFT * np.logaddexp(0.0, u)
        new[cand, 0] = side * (xx + bb * (f - xx))
        sqd[cand] = 1.0 - bb + bb / (1.0 + np.exp(-u))
        dx = new[:, 0] - P0[:, 0]
    waist = cfg.get("waist_morphology", {})
    if waist.get("enabled", False) and (waist.get("width",1)!=1 or waist.get("depth",1)!=1):
        print("\n===== DEFORMATION PHASE 3.2 / WAIST MORPHOLOGY =====")
        if cfg.get("surface_shading", "Original") == "Legacy":
            raise ValueError("Waist morphology requires Original, Adaptive or Geometric shading.")
        from waist_morphology import deform
        eligible = np.zeros(N, dtype=bool)
        eligible[skin_v] = True
        for name in GARMENTS: eligible[verts(name)] = True
        raw_skin = np.concatenate([tris(n) for n in SKIN])
        new = deform(P0, new, raw_skin, T, eligible, allow*guard, L,
                     float(waist.get("width",1)), float(waist.get("depth",1)), contour,
                     manual="waist" in cfg.get("landmarks", {}))
        dx, dy = (new-P0)[:,0], (new-P0)[:,1]
    if cfg.get("displacement_smoothing", False):
        print("\n===== DEFORMATION PHASE 2.4 / TAUBIN DISPLACEMENT =====")
        if cfg.get("surface_shading", "Original") == "Legacy":
            raise ValueError("Taubin requires Original, Adaptive or Geometric shading; Legacy derivatives exclude smoothing.")
        from displacement_smoothing import smooth_displacement
        faces = []
        for name, (start, count) in DRAWS.items():
            fields = draw_meta[name]["draw"].split(",")
            base_vertex = int(fields[2]) if len(fields)>2 else 0
            raw = idx[start:start+count].astype(np.int64)+base_vertex
            faces.append(raw[:len(raw)//3*3].reshape(-1,3))
        new = smooth_displacement(P0, new, np.concatenate(faces), allow, guard)
        dx, dy = (new-P0)[:,0], (new-P0)[:,1]
    if cfg.get("advanced_clothing", False):
        print("\n===== DEFORMATION PHASE 2.9 / CLOTHING ADAPTATION =====")
        if cfg.get("surface_shading", "Original") == "Legacy":
            raise ValueError("Clothing adaptation requires Original, Adaptive or Geometric shading.")
        from clothing_adaptation import adapt
        garment_ids = np.unique(np.concatenate([verts(n) for n in GARMENTS])) if GARMENTS else np.empty(0, dtype=np.int64)
        new = adapt(P0, new, skin_core, garment_ids, T, allow*guard, H) if len(garment_ids) else new
        dx, dy = (new-P0)[:,0], (new-P0)[:,1]
    if reconstructed_fill:
        print("\n===== DEFORMATION PHASE 3.1 / INNER THIGH RECONSTRUCTION =====")
        if cfg.get("surface_shading", "Original") == "Legacy":
            raise ValueError("Reconstructed inner gap requires Original, Adaptive or Geometric shading.")
        from inner_thigh import close_gap
        eligible = np.zeros(N, dtype=bool)
        eligible[skin_core] = True
        for name in GARMENTS:
            eligible[verts(name)] = True
        new = close_gap(P0, new, skin_tri, T, eligible, allow*guard, L["knee"], L["crotch"], contour, rounded=True)
        dx, dy = (new-P0)[:,0], (new-P0)[:,1]
    # Last geometry operation: optional morphology-wide displacement regularization.
    reg = cfg.get("final_regularization", {})
    if isinstance(reg, dict) and reg.get("enabled", False):
        if cfg.get("surface_shading", "Original") == "Legacy":
            raise ValueError("Final regularization requires Original, Adaptive or Geometric shading.")
        from final_regularization import regularize
        faces = []
        for name, (start, count) in DRAWS.items():
            fields = draw_meta[name]["draw"].split(",")
            base_vertex = int(fields[2]) if len(fields) > 2 else 0
            raw = idx[start:start+count].astype(np.int64) + base_vertex
            faces.append(raw[:len(raw)//3*3].reshape(-1,3))
        print("\n===== FINAL MORPHOLOGICAL REGULARIZATION =====")
        # Regularization is a lower-body operation, not a whole-character
        # smoother.  Restrict it below the inferred waist and exclude arms.
        # The height ramp is derived from the model's own landmarks.
        reg_allow = allow.copy()
        upper = L["waist"]
        fade = max(1.0, 0.08 * (L["waist"] - L["crotch"]))
        reg_allow *= 1.0 - smoothstep(upper - fade, upper, P0[:, 2])
        reg_allow[arm_influence >= 0.001] = 0.0
        print("Regularizer lower-body restriction: waist=%.2f, fade=%.2f, eligible=%d" % (
            upper, fade, np.count_nonzero(reg_allow > .02)))
        new = regularize(P0, new, np.concatenate(faces), reg_allow, guard,
                         strength=float(reg.get("strength", 0.35)),
                         tolerance=float(reg.get("tolerance", 0.20)))
        dx, dy = (new-P0)[:,0], (new-P0)[:,1]
    # Final anatomical boundary normalization: a hard arm lock alone can
    # create a visible ridge where moving torso vertices meet fixed arms.
    # Fade the entire displacement field into the protected arm surface.
    from anatomical_transition import blend_at_arm_boundary
    new = blend_at_arm_boundary(P0, new, arm_influence, allow, H)
    # Last-resort safety: arm-dominant vertices must remain bit-identical to
    # their source, even if an optional post-process bypasses mobility masks.
    arm_locked = arm_influence >= 0.01
    arm_leak = np.linalg.norm(new[arm_locked] - P0[arm_locked], axis=1)
    print("Arm final safety: locked=%d, pre-clamp max=%.5f cm" % (
        np.count_nonzero(arm_locked), arm_leak.max() if len(arm_leak) else 0.0))
    new[arm_locked] = P0[arm_locked]
    dx, dy = (new-P0)[:,0], (new-P0)[:,1]
    if relative or coupled:
        print("\n--- FINAL SILHOUETTE / after masks, directional controls and smoothing ---")
        X, Y, Z = sc.to_ref(new[sv,0], new[sv,1], new[sv,2])
        final_width = outline(np.column_stack((X,Y,Z)))
        for z, orig, target, actual in zip(zs, original_outline, tgt, final_width):
            if np.isfinite(orig) and np.isfinite(actual) and (coupled or z >= hip_ref-2):
                print("ref Z %5.1f | target full-width delta %+6.2f cm | actual %+6.2f cm" % (z,2*target*sc.s,2*(actual-orig)*sc.s))
    disp = np.hypot(dx, dy)

    # ---- report ------------------------------------------------------------
    print("\nmoved>0.02cm %d   max %.2f cm   mean %.3f" % ((disp > 0.02).sum(), disp.max(), disp.mean()))
    tri0, tri1 = P0[T], new[T]
    n0 = np.cross(tri0[:, 1] - tri0[:, 0], tri0[:, 2] - tri0[:, 0])
    n1 = np.cross(tri1[:, 1] - tri1[:, 0], tri1[:, 2] - tri1[:, 0])
    flip = (n0 * n1).sum(1) < 0
    e0 = np.linalg.norm(tri0[:, 1] - tri0[:, 0], axis=1)
    e1 = np.linalg.norm(tri1[:, 1] - tri1[:, 0], axis=1)
    r = e1 / np.maximum(e0, 1e-9)
    print("triangles flipped %d / %d   stretch %.2f..%.2f"
          % (flip.sum(), len(T), r[e0 > 1e-4].max(), r[e0 > 1e-4].min()))
    g0, g1 = vnormals(P0, T), vnormals(new, T)
    mv = disp > 0.1
    turn = np.degrees(np.arccos(np.clip((g0 * g1).sum(1), -1, 1)))
    if mv.any():
        print("geometric normal turn (moved): mean %.1f  p95 %.1f  max %.1f deg   >60deg %d"
              % (turn[mv].mean(), np.percentile(turn[mv], 95), turn[mv].max(), (turn[mv] > 60).sum()))
    parts = ["%s %.2f" % (n, disp[verts(n)].max()) for n in DRAWS if (disp[verts(n)] > 0.02).any()]
    print("per part max |d|: " + ", ".join(parts))
    if freeze:
        fr = np.unique(np.concatenate([verts(n) for n in freeze if n in DRAWS]))
        print("field on frozen parts before masking: max %.2f cm (masked to 0)" % np.hypot(fdx, fdy)[fr].max())
    if (armw > 0.01).any():
        print("field on arm-weighted verts before masking: max %.2f cm" % np.hypot(fdx, fdy)[armw > 0.01].max())

    key = {}
    for i in np.nonzero(disp > 0.02)[0]:
        key[(round(P0[i, 0], 2), round(P0[i, 1], 2), round(P0[i, 2], 2))] = i
    dif, cnt = 0.0, 0
    for (kx, ky, kz), i in key.items():
        j = key.get((round(-kx, 2), ky, kz))
        if j is not None:
            dif = max(dif, abs(dx[i] + dx[j]), abs(dy[i] - dy[j]))
            cnt += 1
    print("mirror symmetry: %d paired verts, max |d - mirrored d| %.4f cm" % (cnt, dif))


    print("\nsilhouette (skin, arms excluded, exact cross-sections):")
    print("    z     Xhalf before/after     Ymin before/after    Ymax before/after    thigh gap")
    t0s, t1s = P0[skin_tri], new[skin_tri]

    def cut(tri, z):
        c = contour(tri, z)
        c = c[np.abs(c[:, 0]) < 26.0]
        if len(c) < 6:
            return None
        xh = torso_half(np.abs(c[:, 0]))
        body = c[np.abs(c[:, 0]) <= xh + 1e-6]
        rt, lt = body[body[:, 0] > 0.0, 0], body[body[:, 0] < 0.0, 0]
        gap = (rt.min() - lt.max()) if len(rt) and len(lt) else np.nan
        return xh, body[:, 1].min(), body[:, 1].max(), gap
    for z0 in np.arange(np.floor(L["ankle"]), L["waist"] + 8, 4):
        sa, sb = cut(t0s, z0 + 2.0), cut(t1s, z0 + 2.0)
        if sa is None or sb is None:
            continue
        tags = [k for k in ("knee", "crotch", "apex", "hip_z", "waist") if z0 <= L[k] < z0 + 4]
        print("  %5.1f   %6.2f -> %6.2f      %6.2f -> %6.2f     %6.2f -> %6.2f    %5.2f -> %5.2f%s"
              % (z0 + 2.0, sa[0], sb[0], sa[1], sb[1], sa[2], sb[2], sa[3], sb[3],
                 ("   <- " + ", ".join(tags)) if tags else ""))

    low = (P0[:, 2] < L["crotch"] - 1) & (P0[:, 2] > L["knee"] - 10)
    cross = low & (np.sign(P0[:, 0]) != np.sign(new[:, 0])) & (np.abs(P0[:, 0]) > 0.02) & (disp > 0.02)
    print("vertices that crossed the midline below the crotch: %d" % cross.sum())

    # print("\nclipping tests (garment vs skin):")
    # sidx = np.full(N, -1, np.int64)
    # sidx[skin_core] = np.arange(len(skin_core))
    # st = sidx[skin_tri]
    # stri = st[(st >= 0).all(1)]
    # bad = 0
    # zlim = (L["ankle"] - 3, L["waist"] + 4)
    # for gname in GARMENTS:
        # gv = verts(gname)
        # bad += penetration(gname, P0[gv], new[gv], P0[skin_core], new[skin_core], stri, sc,
                           # allow[skin_core], zlim)
    # print("  garment verts newly inside the skin: %d" % bad)

    vec = np.fromfile(VEC + ".orig", np.int8).reshape(-1, 8).copy()
    t_old = vec[:, 0:3].astype(np.float64)
    n_old = vec[:, 4:7].astype(np.float64)
    t_old /= np.maximum(np.linalg.norm(t_old, axis=1), 1e-9)[:, None]
    n_old /= np.maximum(np.linalg.norm(n_old, axis=1), 1e-9)[:, None]
    shading = cfg.get("surface_shading", "Original")
    if shading not in ("Legacy", "Original", "Geometric", "Adaptive"):
        raise ValueError("Unknown surface shading mode: " + str(shading))
    print("\n===== DEFORMATION PHASE 2.2 / SURFACE SHADING =====")
    print("Mode: " + shading)
    if len(vec) != N:
        raise ValueError("Vector.buf vertex count does not match Position.buf")
    moved = disp > (0.02 if shading == "Legacy" else 1e-6)
    if shading == "Legacy":
        F = np.tile(np.eye(3), (N, 1, 1))
        Hh = 0.05
        pts = P0[moved]
        am = allow[moved]
        for j in range(3):
            o = np.zeros(3)
            o[j] = Hh
            dpx, dpy = sc.field(pts[:, 0] + o[0], pts[:, 1] + o[1], pts[:, 2] + o[2])
            dmx, dmy = sc.field(pts[:, 0] - o[0], pts[:, 1] - o[1], pts[:, 2] - o[2])
            gp, gm = seam(pts + o), seam(pts - o)
            dpx, dpy, dmx, dmy = dpx * gp, dpy * gp, dmx * gm, dmy * gm
            F[moved, 0, j] += am * (dpx - dmx) / (2 * Hh)
            F[moved, 1, j] += am * (dpy - dmy) / (2 * Hh)
        F[moved, 0, :] *= sqd[moved][:, None]
        det = np.linalg.det(F[moved])
        if det.size: print("field det(F): min %.4f max %.4f" % (det.min(), det.max()))
        Fit = np.linalg.inv(F).transpose(0, 2, 1)
        t_new = np.einsum("nij,nj->ni", F, t_old)
        n_new = np.einsum("nij,nj->ni", Fit, n_old)
        t_new /= np.maximum(np.linalg.norm(t_new, axis=1), 1e-9)[:, None]
        n_new /= np.maximum(np.linalg.norm(n_new, axis=1), 1e-9)[:, None]
        wb = smoothstep(0.02, 0.55, disp)
        t_b = (1.0 - wb)[:, None] * t_old + wb[:, None] * t_new
        n_b = (1.0 - wb)[:, None] * n_old + wb[:, None] * n_new
        n_b /= np.maximum(np.linalg.norm(n_b, axis=1), 1e-9)[:, None]
        t_b -= (t_b * n_b).sum(1)[:, None] * n_b
        t_b /= np.maximum(np.linalg.norm(t_b, axis=1), 1e-9)[:, None]

    elif shading == "Original":
        t_b, n_b = t_old, n_old
        moved = np.zeros(N, dtype=bool)
    else:
        from adaptive_normals import surface_frames
        faces = []
        for name, (start, count) in DRAWS.items():
            fields = draw_meta[name]["draw"].split(",")
            base = int(fields[2]) if len(fields) > 2 else 0
            raw = idx[start:start+count].astype(np.int64) + base
            faces.append(raw[:len(raw)//3*3].reshape(-1,3))
        t_b, n_b, moved = surface_frames(P0, new.astype(np.float32).astype(np.float64), np.concatenate(faces), t_old, n_old, moved, shading)

    def pack(V):
        return np.clip(np.rint(V * 127.0), -127, 127).astype(np.int8)
    tan_ok = np.abs((t_old * n_old).sum(1)) < 0.2
    vec[:, 0:3] = np.where((moved & tan_ok)[:, None], pack(t_b), vec[:, 0:3])
    vec[:, 4:7] = np.where(moved[:, None], pack(n_b), vec[:, 4:7])
    nn = vec[:, 4:7].astype(np.float64)
    nn /= np.maximum(np.linalg.norm(nn, axis=1), 1e-9)[:, None]
    tv = np.degrees(np.arccos(np.clip((n_old * nn).sum(1), -1, 1)))
    orig = np.fromfile(VEC + ".orig", np.int8).reshape(-1, 8)
    print("vectors: %d re-framed   normal turn mean %.1f max %.1f deg   untouched bit-exact: %s"
          % (moved.sum(), tv[moved].mean() if moved.any() else 0., tv[moved].max() if moved.any() else 0., np.array_equal(vec[~moved], orig[~moved])))
    if mode != "write":
        print("\n[DRY RUN] Nothing written. Re-run with --write to apply.")
        return
    new.astype(np.float32).tofile(POS)
    print("Position.buf written")
    vec.tofile(VEC)
    print("Vector.buf written")



if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args and "--version" not in sys.argv:
        sys.exit(__doc__ + "\n--bounce=normal|soft|medium|extra (solo normal disponible)\n--version")
    mode = ("write" if "--write" in sys.argv else "restore" if "--restore" in sys.argv
            else "diagnose" if "--diagnose" in sys.argv else "dry")
    if "--version" in sys.argv:
        print(VERSION)
    else:
        run(os.path.abspath(args[0]), mode, next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--bounce=")), None))
