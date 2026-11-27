"""Read-only overlap interventions; virtual section stitching, not a mesh boolean."""
import contextlib
import sys
import numpy as np
from _surface_overlap_lab import pairs, mesh
from _hip_root_lab import run, view, compare, report_profile
from preview_no_seam_guard import sandbox, geometry, load_cfg

TITLES={64:'VIRTUAL OVERLAP SUBTRACTION',65:'SURFACE STITCHING',66:'UNIFIED GEOMETRY HIPS',67:'CONTROLLED OVERLAP INJECTION',68:'HIP FIELD GRADIENT'}

def choose_pair(p,faces,d):
    # Select the shared band nearest the original hip width landmark, not a named draw.
    candidates=[v for v in pairs(p,faces,d) if v[5]>v[4]]
    if not candidates:return None
    hip=d['L']['hip_z']
    a,b,ta,tb,lo,hi=min(candidates,key=lambda v: abs((v[4]+v[5])/2-hip))
    if p[ta,2].mean()<p[tb,2].mean():a,b,ta,tb=b,a,tb,ta
    print('SELECTED upper/lower',a,b,'shared band',lo,hi,flush=True)
    return a,b,ta,tb,lo,hi

def mapped_faces(sv,t):
    ix=np.searchsorted(sv,t)
    if np.any(ix>=len(sv)) or not np.array_equal(sv[ix],t):raise ValueError('Reference mapping mismatch')
    return ix

def weights(z,lo,hi):
    t=np.clip((z-lo)/(hi-lo),0.,1.)
    return t*t*(3-2*t)

def section_width(p,t,z):
    from morphology.geometry import contour
    xy=contour(p[t],z)
    return np.max(np.abs(xy[:,0])) if len(xy) else np.nan

def stitch_width(a,b,w):
    if not np.isfinite(a):return b
    if not np.isfinite(b):return a
    return w*a+(1-w)*b

@contextlib.contextmanager
def intervention(d,p,pair,mode,amount=0.):
    from morphology import calibration as c
    old=c.fixed_core_outline
    _,_,ta,tb,l,h=pair
    sv=d['sv']; a=mapped_faces(sv,ta); b=mapped_faces(sv,tb)
    sc=d['sc']; lo,hi=sc.zmap(np.array([l,h])); scale=d['scale']
    def factory(ref,tri,zs):
        if len(ref)!=len(sv) or not np.array_equal(tri,d['tri']):raise RuntimeError('Reference order changed between cases')
        base=old(ref,tri,zs)
        live_sc=sys._getframe(1).f_locals.get("sc")
        # A/B omission only where both objects have a section; other faces remain.
        keys_a={tuple(sorted(t)) for t in a}; keys_b={tuple(sorted(t)) for t in b}
        other=tri[np.array([tuple(sorted(t)) not in keys_a|keys_b for t in tri])]
        za=np.array([section_width(ref,a,z) for z in zs]); zb=np.array([section_width(ref,b,z) for z in zs]); hit=(zs>=lo)&(zs<=hi)&np.isfinite(za)&np.isfinite(zb)
        print('Calibration sections inside shared band:',zs[hit].tolist(),'band ref',lo,hi,flush=True)
        # Extend the stitch across a narrow collar so its endpoints can be measured even on coarse calibration sampling.
        collar=(hi-lo); left=lo-collar; right=hi+collar
        if mode=='stitch':
            anchors=np.array([left,right])
            print('Virtual stitch anchors ref Z',anchors.tolist(),'not a triangle mesh union')
        injected=None
        if mode=='inject':
            # Clone real lower triangles intersecting the band and translate their
            # vertices outward. The additional surface is read-only calibration geometry.
            band=b[(ref[b,2].min(1)<hi)&(ref[b,2].max(1)>lo)]
            ids=np.unique(band); injected=ref[ids].copy(); itri=np.searchsorted(ids,band)
            injected[:,0]+=np.sign(injected[:,0])*amount/scale
            print('Injected surface triangles',len(itri),'offset model cm',amount)
        def evaluate(q):
            out=base(q)
            if injected is not None and len(injected):
                ip=injected.copy()
                if q is not ref:
                    if live_sc is None:raise RuntimeError('Calibration field unavailable')
                    observer=getattr(live_sc,'field_observer',None)
                    live_sc.field_observer=None
                    try:ip[:,0]+=live_sc.field_ref(*injected.T)[0]
                    finally:live_sc.field_observer=observer
                for i,z in enumerate(zs):
                    if lo<=z<=hi:
                        v=section_width(ip,itri,z)
                        if np.isfinite(v):out[i]=np.nanmax([out[i],v])
                return out
            if mode=='stitch':
                # Interpolate section widths at the two collar endpoints, before calibration.
                wl=section_width(q,b,left); wr=section_width(q,a,right)
                if np.isfinite(wl) and np.isfinite(wr):
                    inside=(zs>=left)&(zs<=right)
                    out[inside]=(1-weights(zs[inside],left,right))*wl+weights(zs[inside],left,right)*wr
                return out
            if mode=='inject':return out
            for i in np.flatnonzero(hit):
                z=zs[i]; wa=section_width(q,a,z); wb=section_width(q,b,z); wo=section_width(q,other,z) if len(other) else np.nan
                if mode=='subtract_upper': val=wb
                elif mode=='subtract_lower':val=wa
                elif mode=='owner':val=wa if za[i]>=zb[i] else wb
                else:raise ValueError(mode)
                out[i]=np.nanmax([val,wo]) if np.isfinite(val) or np.isfinite(wo) else out[i]
            return out
        return evaluate
    c.fixed_core_outline=factory
    try:yield
    finally:c.fixed_core_outline=old

def stitch_preview(p,q,pair):
    # Draw two independent side profiles, not an invented watertight mesh.
    import pyvista as pv
    from morphology.geometry import contour
    _,_,a,b,lo,hi=pair
    collar=hi-lo; zs=np.linspace(lo-collar,hi+collar,121)
    plot=pv.Plotter(shape=(1,2),window_size=(1500,850))
    for col,pos in enumerate((p,q)):
        plot.subplot(0,col);plot.add_text('Original' if col==0 else 'Hips 2.00')
        for t,color in ((a,'steelblue'),(b,'orange')):plot.add_mesh(mesh(pos,t),color=color,opacity=.45)
        for sign in (-1,1):
            lines=[]
            for z in zs:
                xy1=contour(pos[a],z);xy2=contour(pos[b],z)
                vals=[]
                for xy in (xy1,xy2):
                    side=xy[xy[:,0]*sign>0]; vals.append(side[np.argmax(side[:,0]*sign)] if len(side) else None)
                u,v=vals; w=weights(z,lo,hi)
                if u is None and v is None:continue
                pt=v if u is None else u if v is None else w*u+(1-w)*v
                lines.append(pt)
            if len(lines)>1:plot.add_mesh(pv.lines_from_points(np.array(lines)),color='lime',line_width=5)
        plot.view_xz();plot.reset_camera()
    plot.link_views();plot.show()

def gradient(p,q,faces,d,pair):
    from morphology.geometry import contour
    sc=d['sc']; sc.field_observer=None
    tri=d['sv'][d['tri']]; lo,hi=d['L']['knee'],d['L']['waist']; z=np.linspace(lo,hi,501)
    print('GRADIENT Z | side | x | actual surface gain | fixed XY derivative | gain derivative | gain second derivative')
    for sign in (-1,1):
        rows=[]
        for h in z:
            xy=contour(p[tri],h); final=contour(q[tri],h)
            xy=xy[xy[:,0]*sign>0]; final=final[final[:,0]*sign>0]
            if not len(xy) or not len(final):continue
            pt=xy[np.argmax(sign*xy[:,0])]; gain=np.max(sign*final[:,0])-sign*pt[0]
            eps=(hi-lo)/10000
            x=np.repeat(pt[0],2); y=np.repeat(pt[1],2); zz=np.array([h-eps,h+eps]); dx,_=sc.field(x,y,zz)
            rows.append([h,pt[0],gain,sign*(dx[1]-dx[0])/(2*eps)])
        r=np.asarray(rows)
        if len(r)<3:continue
        g=np.gradient(r[:,2],r[:,0]); gg=np.gradient(g,r[:,0])
        for row,j,k in zip(r,g,gg):print('%.5f %d %.5f %.5f %.5f %.5f %.5f'%(row[0],sign,*row[1:],j,k))
        ix=np.argmax(np.abs(gg[1:-1]))+1;print('PEAK surface gain second derivative',gg[ix],'Z',r[ix,0],'side',sign,'distance to overlap',max(pair[4]-r[ix,0],r[ix,0]-pair[5],0.))

def execute(num):
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini); saved=load_cfg(root); q,d=run(root,p,faces,saved,hips=2.)
        pair=choose_pair(p,faces,d); cases=[('Original',p),('Legacy Hips 2',q)]
        if pair is None:print('SKIP: no active overlapping Z band'); view(p,faces,cases,d,TITLES[num])
        elif num==65:stitch_preview(p,q,pair)
        elif num==68:gradient(p,q,faces,d,pair);view(p,faces,cases,d,TITLES[num])
        else:
            modes={64:[('subtract_upper',0),('subtract_lower',0)],66:[('owner',0),('stitch',0)],67:[('inject',v*(pair[5]-pair[4])) for v in (.25,.5,1.)]}[num]
            for mode,amount in modes:
                label=f'{mode} {amount:.3f} cm' if amount else mode
                with intervention(d,p,pair,mode,amount):r,e=run(root,p,faces,saved,hips=2.)
                compare(q,r,label);report_profile(p,r,faces,e,label);cases.append((label,r))
            view(p,faces,cases,d,f'{num} | {TITLES[num]}')
    print(f'===== EXPERIMENT {num} - {TITLES[num]} FINISHED =====',flush=True)
