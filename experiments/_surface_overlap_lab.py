"""Read-only surface contact diagnostics for open anatomical meshes."""
import numpy as np
from itertools import combinations
from _hip_root_lab import run, visible, view, compare, report_profile
from _overlap_lab import segments, occupancy
from preview_no_seam_guard import sandbox, geometry, load_cfg

TITLES={58:'ADAPTIVE OVERLAP SCAN',59:'SURFACE INTERSECTION',60:'SURFACE OVERLAP AREA',61:'OVERLAP VISUALIZATION',62:'SEAM DISPLACEMENT CONTINUITY',63:'VIRTUAL SURFACE UNION'}

def mesh(p,t):
    import pyvista as pv
    ids=np.unique(t)
    return pv.PolyData(p[ids],np.column_stack((np.full(len(t),3),np.searchsorted(ids,t))).ravel())

def pairs(p,faces,d):
    lo,hi=d['L']['knee'],d['L']['waist']
    allowed={tuple(sorted(t)) for t in d['sv'][d['tri']]}
    ts={n:np.asarray([t for t in faces[n] if tuple(sorted(t)) in allowed],dtype=np.int64).reshape(-1,3) for n in visible(d,faces)}
    for a,b in combinations(ts,2):
        ta,tb=ts[a],ts[b]
        if not len(ta) or not len(tb):continue
        za,zb=p[ta,2],p[tb,2]
        l=max(lo,za.min(),zb.min()); h=min(hi,za.max(),zb.max())
        if h<l:continue
        print('PAIR',a,b,'shared Z range',l,h,flush=True)
        yield a,b,ta,tb,l,h

def area_samples(p,t):
    v=p[t]; area=np.linalg.norm(np.cross(v[:,1]-v[:,0],v[:,2]-v[:,0]),axis=1)/2
    bary=np.array([[1/3,1/3,1/3],[.8,.1,.1],[.1,.8,.1],[.1,.1,.8],[.45,.45,.1],[.45,.1,.45],[.1,.45,.45]])
    return np.einsum('ij,tjk->tik',bary,v).reshape(-1,3),np.repeat(area/len(bary),len(bary)),bary

def contact(p,q,ta,tb,l,h):
    # Seven quadrature points per triangle; directional proximity area, not exact coincident area.
    x,w,bary=area_samples(p,ta); y=np.einsum('ij,tjk->tik',bary,q[ta]).reshape(-1,3)
    ids,near=mesh(p,tb).find_closest_cell(x,return_closest_point=True)
    dist=np.linalg.norm(x-near,axis=1); valid=(x[:,2]>=l)&(x[:,2]<=h)
    # Compare displacements at the same original closest point via barycentric interpolation.
    v=p[tb[ids]]; e=v[:,1]-v[:,0]; f=v[:,2]-v[:,0]; g=near-v[:,0]
    dot=lambda a,b:np.einsum('ij,ij->i',a,b)
    ee,ff,ef=dot(e,e),dot(f,f),dot(e,f); den=ee*ff-ef*ef
    u=np.divide(ff*dot(g,e)-ef*dot(g,f),den,out=np.zeros_like(den),where=den>1e-20)
    z=np.divide(ee*dot(g,f)-ef*dot(g,e),den,out=np.zeros_like(den),where=den>1e-20)
    weights=np.column_stack((1-u-z,u,z)); delta=np.einsum('ij,ijk->ik',weights,(q-p)[tb[ids]])
    mismatch=np.linalg.norm(y-x-delta,axis=1)
    return x,w,dist,valid,mismatch

def scan(p,q,ta,tb,l,h,scale):
    if h<=l:return
    pts=p[np.unique(np.concatenate((ta,tb)))]; step=scale/150
    low=pts[:,:2].min(0); high=pts[:,:2].max(0)
    x=np.arange(low[0]+step/2,high[0],step); y=np.arange(low[1]+step/2,high[1],step)
    for dz0 in (scale/100,scale/400):
        n=max(1,int(np.ceil((h-l)/dz0))); dz=(h-l)/n; total=0.; unknown=0
        print('SCAN dz cm',dz,'XY cell cm',step)
        for z in l+(np.arange(n)+.5)*dz:
            s,t=segments(p[ta],z),segments(p[tb],z); a,ok=occupancy(s,x,y,step*1e-4); b,ok2=occupancy(t,x,y,step*1e-4)
            ar=np.count_nonzero(a&b)*step**2 if ok and ok2 else np.nan
            if np.isfinite(ar):total+=ar*dz
            else:unknown+=1
            def width(seg):return [float(np.max(seg[:,:,0])),float(-np.min(seg[:,:,0]))] if len(seg) else [np.nan,np.nan]
            print('Z',round(z,6),'area cm2',ar,'closed',ok,ok2,'A/B left-right original',width(s),width(t),'final',width(segments(q[ta],z)),width(segments(q[tb],z)))
        print('PARTIAL volume cm3',total,'unknown slices',unknown,'of',n)

def execute(num):
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini); saved=load_cfg(root); q,d=run(root,p,faces,saved,hips=2.)
        scale=d['L']['waist']-d['L']['knee']; tol=scale*np.array([.0005,.002,.005]); selected=list(pairs(p,faces,d))
        if not selected:print('No active Skin pairs share the anatomical Z range')
        if num in (59,61):
            import pyvista as pv
            plot=pv.Plotter(shape=(1,2),window_size=(1500,850))
            for col,pos in enumerate((p,q)):
                plot.subplot(0,col); plot.add_text('Original' if col==0 else 'Hips 2.00')
                for n in visible(d,faces):plot.add_mesh(mesh(pos,faces[n]),color='lightgray',opacity=.35)
                for a,b,ta,tb,l,h in selected:
                    if num==59:
                        try:
                            lines,_,_=mesh(pos,ta).intersection(mesh(pos,tb),split_first=False,split_second=False)
                            print('CROSSING',col,a,b,'line cells',lines.n_cells,'length cm',lines.length if lines.n_cells else 0)
                            if lines.n_cells:plot.add_mesh(lines,color='red',line_width=5)
                        except Exception as exc:print('Intersection indeterminate:',repr(exc))
                    else:
                        for t,r,c in ((ta,tb,'orange'),(tb,ta,'cyan')):
                            x,w,dist,valid,_=contact(pos,pos,t,r,l,h); hit=valid&(dist<=tol[1]); print('CONTACT',col,a,b,c,'samples',hit.sum())
                            if hit.any():plot.add_points(x[hit],color=c,point_size=5)
                plot.view_xz(); plot.reset_camera()
            plot.link_views(); plot.show()
        elif num in (58,60,62):
            for a,b,ta,tb,l,h in selected:
                if num==58:scan(p,q,ta,tb,l,h,scale); continue
                for src,dst,t,r in ((a,b,ta,tb),(b,a,tb,ta)):
                    x,w,dist,valid,mismatch=contact(p,q,t,r,l,h)
                    print('DIRECTION',src,dst,'tolerances cm',tol.tolist())
                    for eps in tol:
                        hit=valid&(dist<=eps)
                        print('tol',eps,'estimated near surface area cm2',w[hit].sum(),'samples',hit.sum(),'Z range', (x[hit,2].min(),x[hit,2].max()) if hit.any() else None)
                        if num==62 and hit.any():
                            print('Displacement mismatch cm p50/p95/max',np.percentile(mismatch[hit],[50,95,100]))
                            for lo,hi in zip(np.linspace(l,h,21)[:-1],np.linspace(l,h,21)[1:]):
                                k=hit&(x[:,2]>=lo)&(x[:,2]<=hi)
                                if k.any():print('SEAM BAND',lo,hi,'area',w[k].sum(),'mismatch p95',np.percentile(mismatch[k],95))
            view(p,faces,[('Original',p),('Legacy Hips 2',q)],d,f'{num} | {TITLES[num]}')
        elif num==63:
            # Active exterior reference only: no boolean repair or changes to the source mesh.
            from morphology import calibration as c
            old=c.fixed_core_outline
            def exterior(points,tri,zs):
                from morphology.geometry import contour
                def evaluate(Q):
                    values=[]
                    for z in zs:
                        xy=contour(Q[tri],z)
                        values.append(np.max(np.abs(xy[:,0])) if len(xy) else np.nan)
                    return np.asarray(values)
                return evaluate
            c.fixed_core_outline=exterior
            try:r,e=run(root,p,faces,saved,hips=2.,reference='active_unique')
            finally:c.fixed_core_outline=old
            compare(q,r,'Active unique exterior vs production'); report_profile(p,r,faces,e,'Active unique exterior')
            view(p,faces,[('Original',p),('Legacy Hips 2',q),('Active unique exterior',r)],d,f'{num} | {TITLES[num]}')
    print(f'===== EXPERIMENT {num} - {TITLES[num]} FINISHED =====',flush=True)
