"""Shared experimental viewer. PyVista is imported only when a window opens."""
from pathlib import Path
from datetime import datetime
import numpy as np


class ExperimentViewer:
    def __init__(self, original, faces, cases, names, title='Morphology comparison'):
        self.original=original; self.faces=faces; self.cases=list(cases)
        self.names=[n for n in names if n in faces and len(faces[n])]
        self.title=title
        if not self.names or not self.cases: raise ValueError('No visible geometry or cases')

    def show(self, view='back', columns=3, focus=None, overlays=None):
        import pyvista as pv
        cols=min(columns,len(self.cases)); rows=(len(self.cases)+cols-1)//cols
        plot=pv.Plotter(shape=(rows,cols),window_size=(1500,900),title=self.title)
        colors=['#a6bcd1','#b3b9a2','#c2a9a0','#a9b3c1','#b9a6c4']
        actors=[]
        for i,(label,q) in enumerate(self.cases):
            plot.subplot(i//cols,i%cols)
            for j,n in enumerate(self.names):
                t=self.faces[n]; ids=np.unique(t)
                cells=np.column_stack((np.full(len(t),3),np.searchsorted(ids,t))).ravel()
                actors.append(plot.add_mesh(pv.PolyData(q[ids],cells),color=colors[j%len(colors)],smooth_shading=True))
            if overlays and label in overlays and len(overlays[label]):
                t=overlays[label]; ids=np.unique(t); cells=np.column_stack((np.full(len(t),3),np.searchsorted(ids,t))).ravel()
                plot.add_mesh(pv.PolyData(q[ids],cells),color="red",show_edges=True,line_width=3,lighting=False)
            plot.add_text(label,font_size=11)
            plot.enable_parallel_projection()
        plot.subplot(0,0); plot.link_views()
        # Explicit camera directions: WWMI front +Y, back -Y, height +Z.
        directions={'front':(0,1,0),'back':(0,-1,0),'left':(-1,0,0),'right':(1,0,0),'perspective':(1,-2,.55)}
        all_ids=np.unique(np.concatenate([self.faces[n].ravel() for n in self.names]))
        bounds=np.stack([q[all_ids].min(0) for _,q in self.cases]+[q[all_ids].max(0) for _,q in self.cases])
        center=(bounds.min(0)+bounds.max(0))*.5
        extent=max(float(np.ptp(bounds,axis=0).max()),1.)
        if focus is not None:
            lo,hi=focus; center[2]=(lo+hi)/2; extent=max(hi-lo,1.)
        current=[view]
        def set_view(name):
            current[0]=name
            direction=np.asarray(directions[name],float); direction/=np.linalg.norm(direction)
            plot.camera_position=[center+direction*3*extent,center,(0,0,1)]
            plot.camera.parallel_scale=extent*.57
            plot.renderer.reset_camera_clipping_range(); plot.render()
        for key,name in [('1','front'),('2','back'),('3','left'),('4','right'),('5','perspective')]:
            plot.add_key_event(key,lambda n=name:set_view(n))
        def screenshot():
            path=Path.home()/('ThiccExperiment_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.png')
            plot.screenshot(str(path),scale=2); print('Screenshot:',path,flush=True)
        wire=[False]
        def toggle_wire():
            wire[0]=not wire[0]
            for actor in actors:
                if wire[0]: actor.GetProperty().SetRepresentationToWireframe()
                else: actor.GetProperty().SetRepresentationToSurface()
            plot.render()
        plot.add_key_event('s',screenshot); plot.add_key_event('w',toggle_wire)
        plot.add_key_event('f',lambda:set_view(current[0]))
        plot.add_text('1 Front | 2 Back | 3 Left | 4 Right | 5 3D | F Fit | W Wire | S PNG',position='lower_left',font_size=9)
        print('Viewer: 1 Front, 2 Back, 3 Left, 4 Right, 5 Perspective, F Fit, W Wireframe, S Screenshot',flush=True)
        set_view(view); plot.show()
