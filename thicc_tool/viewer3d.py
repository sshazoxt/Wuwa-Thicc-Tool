"""Read-only WWMI geometry viewer, including displacement diagnostics."""
import os
import numpy as np

def load_positions(path):
    a=np.fromfile(path,dtype='<f4')
    if not a.size or a.size%3 or not np.isfinite(a).all():
        raise ValueError('Invalid Position.buf: '+path)
    return a.reshape(-1,3)

def geometry(mod,ini,names,original=False,mode=None,preview_positions=None):
    import thicc_edit as te
    meta={}; draws=te.parse_draws(ini,metadata=meta)
    folder=os.path.join(mod,'Meshes'); path=os.path.join(folder,'Position.buf')
    p=load_positions(path); o=None
    if preview_positions is not None:
        preview_positions=np.asarray(preview_positions)
        if preview_positions.shape!=p.shape or not np.isfinite(preview_positions).all(): raise ValueError('Invalid preview geometry.')
        p=preview_positions
    mode=mode or ('Original' if original else 'Current')
    if mode in ('Original','Comparison','Displacement'):
        if not os.path.isfile(path+'.orig'): raise ValueError('Position.buf.orig is missing; original geometry cannot be verified.')
        o=load_positions(path+'.orig')
        if o.shape!=p.shape: raise ValueError('Original and current buffers differ in size.')
    idx=np.fromfile(os.path.join(folder,'Index.buf'),dtype='<u4'); out=[]
    for name in names:
        s,c=draws[name]; fields=meta[name]['draw'].split(','); base=int(fields[2]) if len(fields)>2 else 0
        if s<0 or c<=0 or c%3 or s+c>len(idx): raise ValueError('Invalid index range: '+name)
        t=idx[s:s+c].astype(np.int64)+base
        if t.min()<0 or t.max()>=len(p): raise ValueError('Index outside Position.buf: '+name)
        ids,local=np.unique(t,return_inverse=True)
        out.append((name,p[ids],local.reshape(-1,3),None if o is None else o[ids]))
    return out

def displacement(p,o):
    return np.linalg.norm(p.astype(np.float64)-o.astype(np.float64),axis=1)

def populate(plot,mod,ini,names,wire=False,original=False,mode=None,preview_positions=None):
    import pyvista as pv
    mode=mode or ('Original' if original else 'Current')
    data=geometry(mod,ini,names,mode=mode,preview_positions=preview_positions)
    if not data: raise ValueError("No resolved geometry in the default configuration.")
    plot.clear(); plot.set_background('#202733')
    style='wireframe' if wire else 'surface'
    maximum=max((float(displacement(p,o).max()) for _,p,_,o in data),default=0) if mode=='Displacement' else 0
    for i,(name,p,t,o) in enumerate(data):
        faces=np.column_stack((np.full(len(t),3),t)).ravel()
        def mesh(points): return pv.PolyData(points,faces)
        if mode=='Comparison':
            plot.add_mesh(mesh(p),color='#ed6a62',opacity=.55,style=style,label=('Preview' if preview_positions is not None else 'Current') if i==0 else None)
            plot.add_mesh(mesh(o),color='#69a5ee',opacity=.40,style='wireframe',label='Original' if i==0 else None)
        elif mode=='Displacement':
            d=displacement(p,o); m=mesh(p); m['Displacement']=d
            plot.add_mesh(m,scalars='Displacement',cmap='inferno',clim=(0,maximum or 1),style=style,show_scalar_bar=i==0,scalar_bar_args={'title':'Displacement (model units)'})
        else:
            plot.add_mesh(mesh(o if mode=='Original' else p),color=['#b7c9dd','#e6af85','#8dcbb5','#c4a7e7'][i%4],style=style,label=name)
    if mode=='Displacement': plot.add_text(f'Maximum: {maximum:.4f} model units',font_size=10)
    elif mode=='Comparison' or len(data)<=12: plot.add_legend()
    else: plot.add_text(f'{len(data)} resolved parts',font_size=10)
    plot.add_axes(); plot.view_isometric(); plot.reset_camera()

def show(mod,ini,names,wire=False,original=False,mode=None):
    import pyvista as pv
    plot=pv.Plotter(title="Thicc Tool")
    populate(plot,mod,ini,names,wire,original,mode)
    plot.show()

if __name__=='__main__':
    import sys,json,traceback,faulthandler
    faulthandler.enable()
    try:
        print("Python:",sys.executable,flush=True)
        show(**json.loads(sys.argv[1]))
    except Exception:
        traceback.print_exc()
        sys.exit(1)
