"""Gap closure on the final lateral field, without moving the outer contour."""
import numpy as np
from scipy.ndimage import gaussian_filter1d

def q(t):
    t=np.clip(t,0.,1.)
    return t**3*(10+t*(-15+6*t))

def fill_base(P,Q,skin_tri,faces,eligible,mobility,knee,crotch,contour, rounded=True, fill_strength=1.):
    span=crotch-knee
    if not np.isfinite(span) or span<=0:
        print('Inner gap skipped: invalid landmarks'); return Q
    z=np.linspace(knee,crotch,65); tri=Q[skin_tri]
    profiles=[]
    for s in (-1,1):
        gap=np.full(len(z),np.nan); outer=gap.copy()
        for i,h in enumerate(z):
            c=contour(tri,h); x=c[:,0]*s; x=x[x>0]
            if len(x)>=6:
                gap[i]=np.min(x); outer[i]=np.percentile(x,95)
        ok=np.isfinite(gap)&(outer>gap)
        if ok.sum()<20:
            print('Inner gap skipped: insufficient bilateral sections'); return Q
        # Avoid extrapolating beyond supported sections.
        g=gaussian_filter1d(np.interp(z,z[ok],gap[ok]),2)
        o=gaussian_filter1d(np.interp(z,z[ok],outer[ok]),2)
        profiles.append((g,o,z[ok][0],z[ok][-1]))
    # Same fractional closure on both sides; never pull a vertex across the center.
    d=np.zeros(len(P)); ids=np.flatnonzero(eligible & (mobility>0))
    h=P[ids,2]; v=(h-knee)/span
    for s,(g,o,zlo,zhi) in zip((-1,1),profiles):
        j=ids[(P[ids,0]*s>0)&(Q[ids,0]*s>0)]
        h=P[j,2]; v=(h-knee)/span; x=Q[j,0]*s
        gap=np.interp(h,z,g); outer=np.interp(h,z,o)
        limit=gap+.60*(outer-gap)
        # Monotone compression: x -> x*(1-k*w(x)), w non-increasing.
        w=1-q((x-gap)/np.maximum(limit-gap,1e-9))
        if rounded:
            # Start releasing medial volume well above the knee. Blend with
            # the original short taper only near the knee; no knee displacement.
            t=np.clip(v/.55,0.,1.)
            knee_fade=q(t)
        else:
            knee_fade=q(v/.20)
        fade=knee_fade*q((1-v)/.16)*q((h-zlo)/(.08*span))*q((zhi-h)/(.08*span))
        strength=.94*fade*mobility[j]*fill_strength
        d[j]=-s*x*strength*w
    print("Inner gap knee transition: %s" % ("Rounded (55% of knee-crotch span)" if rounded else "Reconstructed (20%)"))
    active=np.flatnonzero(d!=0)
    if not len(active): print('Inner gap: no eligible corrections'); return Q
    t=faces[np.any(d[faces]!=0,axis=1)]
    def normal(A):
        a=A[t]; return np.cross(a[:,1]-a[:,0],a[:,2]-a[:,0])
    n0=normal(P); nb=normal(Q); valid=(np.sum(n0*nb,axis=1)>0)
    for scale in (1.,.5,.25,.125,.0625):
        R=Q.copy(); R[:,0]+=scale*d
        nr=normal(R)
        if np.all(np.sum(n0[valid]*nr[valid],axis=1)>0) and np.all(np.linalg.norm(nr[valid],axis=1)>=.12*np.linalg.norm(nb[valid],axis=1)):
            print('Inner gap: %d vertices; max correction %.4f cm; accepted strength %.3f; no new reversals on valid faces' % (len(active),np.max(np.abs(scale*d)),scale)); return R
    print('Inner gap: rejected by face safety check'); return Q


def close_gap(P,Q,skin_tri,faces,eligible,mobility,knee,crotch,contour, rounded=True, upper_gap=0., fill_strength=1.):
    upper_gap=float(np.clip(upper_gap,0.,1.))
    fill_strength=float(np.clip(fill_strength,0.,1.))
    span=crotch-knee
    if not np.isfinite(span) or span<=0:
        print('Inner gap skipped: invalid landmarks'); return Q
    Q=fill_base(P,Q,skin_tri,faces,eligible,mobility,knee,crotch,contour,rounded,fill_strength)
    if upper_gap==0 or fill_strength==0: return Q
    z=np.linspace(knee,crotch,65); tri=Q[skin_tri]
    # One amplitude per horizontal cut, not one target per Y ray.
    # Angular coordinates are normalized by the section's own radii.
    depth=np.linspace(np.percentile(tri[:,:,1],1),np.percentile(tri[:,:,1],99),81)
    d=np.zeros(len(P)); ids=np.flatnonzero(eligible & (mobility>0))
    clearance=.0005*span
    def angular(x,y,cx,cy,rx,ry):
        u=(cx-x)/np.maximum(rx,1e-9)
        w=(y-cy)/np.maximum(ry,1e-9)
        return np.clip(u/np.maximum(np.hypot(u,w),1e-9),0.,1.)**4
    for side in (-1,1):
        profile=np.full((len(z),5),np.nan)
        for i,h in enumerate(z):
            c=contour(tri,h); c=c[c[:,0]*side>0]
            if len(c)<6: continue
            x=c[:,0]*side; y=c[:,1]
            lo,hi=x.min(),x.max(); yl,yh=y.min(),y.max()
            rx=(hi-lo)/2; ry=(yh-yl)/2
            if min(rx,ry)<=1e-9: continue
            cx=(hi+lo)/2; cy=(yl+yh)/2
            w=angular(x,y,cx,cy,rx,ry)
            m=w>1e-6
            if not m.any(): continue
            # Bound the single amplitude using every sampled medial point.
            # The closest point need not lie at the middle of the Y range.
            amp=np.min(np.maximum(x[m]-clearance,0.)/w[m])
            profile[i]=cx,cy,rx,ry,amp
        ok=np.isfinite(profile).all(axis=1)
        if ok.sum()<20:
            print('Angular contact skipped: insufficient sections'); return Q
        j=ids[(P[ids,0]*side>0)&(Q[ids,0]*side>0)]
        h=P[j,2]; v=(h-knee)/span; x=Q[j,0]*side
        vals=[np.interp(h,z[ok],profile[ok,k]) for k in range(5)]
        cx,cy,rx,ry,amp=vals
        w=angular(x,Q[j,1],cx,cy,rx,ry)
        # Preserve the established vertical envelope and the groin itself.
        fade=q((v-.72)/.24)*q((1-v)/.015)
        # No interpolation across unsupported sections.
        fade*=q(np.interp(h,z,ok.astype(float),left=0.,right=0.))
        shift=amp*w*fade*mobility[j]*fill_strength*upper_gap
        # Last-resort vertex bound; the main amplitude already has a
        # section-wide clearance bound, so no full-depth planar target.
        d[j]=-side*np.minimum(shift,np.maximum(x-clearance,0.))
        print(f'Angular medial contact side {side:+d}: supported cuts {ok.sum()}/{len(z)}; peak section amplitude {np.nanmax(profile[:,4]):.4f} cm')
    print("Inner gap knee transition: %s" % ("Rounded (55% of knee-crotch span)" if rounded else "Reconstructed (20%)"))
    print(f"Inner gap: fill={fill_strength:.2f}; Upper Y contact={upper_gap:.2f} (Angular Medial Contact)")
    active=np.flatnonzero(d!=0)
    if not len(active): print('Inner gap: no eligible corrections'); return Q
    R, fraction = adaptive_contact(P,Q,faces,d)
    if not np.any(fraction>0):
        print('Inner gap: rejected by face safety check'); return Q
    print('Inner gap: %d vertices; max correction %.4f cm; weighted accepted strength %.3f' % (len(active),np.max(np.abs(R[:,0]-Q[:,0])),np.sum(np.abs(d)*fraction)/np.sum(np.abs(d))))
    print('Y residual: Z | nominal gap | baseline fill | achieved (cm; frontal sections)')
    for v0 in (.25,.40,.55,.65,.75,.85,.90,.95,.98):
        h0=knee+v0*span
        def gap_at(A):
            x=contour(A[skin_tri],h0)[:,0]
            l=x[x<0]; r=x[x>0]
            return float(r.min()-l.max()) if len(l) and len(r) else np.nan
        before=gap_at(Q); after=gap_at(R)
        k=q((v0-.72)/.24)*q((1-v0)/.015)*upper_gap
        target=before-max(before-2*clearance,0)*k*fill_strength
        print(f'  {h0:7.3f} | {target:7.3f} | {before:7.3f} | {after:7.3f}')
    print('Y contact depth diagnostic: Z | paired rays | median gap baseline/after (sampled)')
    # Ray intersections at matching Y and Z for the final surface.
    for v0 in (.65,.85,.95,.98):
        h0=knee+v0*span
        def sampled(A):
            B=A[skin_tri]; B=B[(B[:,:,2].min(1)<h0)&(B[:,:,2].max(1)>h0)]
            out=[]
            for yy in depth[::4]:
                # Barycentric intersection in the YZ projection.
                a=B[:,0]; e=B[:,1]-a; f=B[:,2]-a
                det=e[:,1]*f[:,2]-e[:,2]*f[:,1]
                u=np.divide((yy-a[:,1])*f[:,2]-(h0-a[:,2])*f[:,1],det,out=np.full(len(a),np.nan),where=abs(det)>1e-12)
                v=np.divide(e[:,1]*(h0-a[:,2])-e[:,2]*(yy-a[:,1]),det,out=np.full(len(a),np.nan),where=abs(det)>1e-12)
                x=(a[:,0]+u*e[:,0]+v*f[:,0])[(u>=0)&(v>=0)&(u+v<=1)]
                l=x[x<=0]; r=x[x>=0]; out.append(r.min()-l.max() if len(l) and len(r) else np.nan)
            return np.array(out)
        a,b=sampled(Q),sampled(R); ok=np.isfinite(a)&np.isfinite(b)
        if ok.any(): print(f'  {h0:.3f} | {ok.sum()} | {np.median(a[ok]):.4f} -> {np.median(b[ok]):.4f}')
    return R


def adaptive_contact(P,Q,faces,d):
    """Incremental local backtracking, preserving fixed vertices and X sign.

    Propagate local constraints along the indexed surface and coincident
    movable vertices. No displacement outside the original medial field.
    """
    active=d!=0
    t=faces[np.any(active[faces],axis=1)]
    if not len(t): return Q.copy(),np.zeros(len(Q))
    def normals(A):
        a=A[t]; return np.cross(a[:,1]-a[:,0],a[:,2]-a[:,0])
    n0=normals(P); nb=normals(Q)
    area=np.linalg.norm(nb,axis=1)
    valid=(np.sum(n0*nb,axis=1)>0)&(area>1e-12)
    # Exact coincident vertices are constrained together without welding mesh.
    ids=np.flatnonzero(active)
    _,groups=np.unique(Q[ids],axis=0,return_inverse=True)
    edges=np.concatenate((t[:,[0,1]],t[:,[1,2]],t[:,[2,0]]))
    edges=edges[active[edges].all(axis=1)]
    u,v=edges.T
    fraction=np.zeros(len(Q)); R=Q.copy()
    def bad_faces(A):
        n=normals(A)
        return valid & ((np.sum(n0*n,axis=1)<=0)|(np.linalg.norm(n,axis=1)<.12*area))
    for iteration in range(32):
        remaining=np.maximum(0.,1-fraction)
        step=np.where(active,np.minimum(.125,remaining),0.)
        if np.max(step)<1e-7: break
        for attempt in range(18):
            trial=Q.copy(); trial[:,0]+=d*(fraction+step)
            bad=bad_faces(trial)
            if not bad.any(): break
            blocked=np.unique(t[bad]); blocked=blocked[active[blocked]]
            step[blocked]*=.5
            # Spread the restriction across two edge rings, softly.
            for _ in range(2):
                lim=step.copy()
                np.minimum.at(lim,u,step[v]+.025)
                np.minimum.at(lim,v,step[u]+.025)
                step=np.minimum(step,lim)
            g=np.full(groups.max()+1,np.inf)
            np.minimum.at(g,groups,step[ids]); step[ids]=g[groups]
        else:
            print('Adaptive contact: could not find safe local increment'); break
        if np.max(step)<1e-6: break
        fraction+=step; R=trial
        mean=np.sum(np.abs(d)*fraction)/np.sum(np.abs(d))
        print(f'Adaptive contact {iteration+1:02d}: weighted progress {mean:.3f}; fully reached {np.count_nonzero(fraction[ids]>=.999)/len(ids):.1%}',flush=True)
        if mean>=.999: break
    return R,fraction
