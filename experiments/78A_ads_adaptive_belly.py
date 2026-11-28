"""Read-only ADS adaptive curves and advanced Belly lab; isolated by Experiments."""
EXPERIMENT_INFO={'description':'ADS adaptive C2 morphological profiles (private field clone).','objective':'Compare adaptive profiles against ADS 75 or DS 045 at identical controls.','visual':'Interactive Qt / VTK comparison','batch':False,'writes':False,'parameter_source':'saved','parameters':'Saved mod roles and morphology, or engine defaults when absent. Direct Section selected internally. Manual Preview by default; advanced Belly; read-only.'}
import copy,json,os,time,traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
if __name__ == "__main__":
    from _anny78a_install import prepare
    prepare(__file__)

import numpy as np
from morphology import PreviewSession
from _anny78_direct import Profiles,experimental_fields
from _anny78_baseline import Profiles as BaselineProfiles


def main():
    os.environ.setdefault('QT_API','pyside6')
    from PySide6.QtCore import Qt,QTimer
    from PySide6.QtWidgets import (QApplication,QDialog,QHBoxLayout,QVBoxLayout,QFormLayout,QWidget,QDoubleSpinBox,QSlider,QPushButton,QCheckBox,QLabel,QComboBox,QScrollArea)
    import pyvista as pv
    from pyvistaqt import QtInteractor
    import thicc_edit as te
    from morphology.belly import basic_parameters, parameters, LIMITS
    app=QApplication.instance() or QApplication([])
    mod=Path(os.environ['THICC_MOD_DIR']).resolve()
    if not (mod/'Meshes'/'Position.buf').is_file():
        raise ValueError('Select a mod with Meshes/Position.buf in Thicc Tool.')
    # Workspace supplies a private snapshot for ordinary experiments. A further
    # private session also protects the source if invoked outside the director.
    outdir=Path(__file__).resolve().parent/'_results'/'anny78a'
    outdir.mkdir(parents=True,exist_ok=True)
    refpath=Path(__file__).with_name('_anny78_profiles.json')
    data=json.loads(refpath.read_text(encoding='utf-8')); profiles=Profiles(data); baseline_profiles=BaselineProfiles(data)
    print('Anny reference version:',data['anny_version'],'landmarks:',data['landmarks'],flush=True)
    with PreviewSession(mod) as s, ThreadPoolExecutor(max_workers=1) as pool:
        cfg=copy.deepcopy(s.saved)
        cfg['morphology_engine']='Direct Section'
        print('[78A] Read-only; Direct Section selected internally; private analysis on first Preview.',flush=True)
        dialog=QDialog(); dialog.setWindowTitle('78A | ADS Adaptive Morphological Curves'); dialog.resize(1500,850)
        outer=QHBoxLayout(dialog); scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setMinimumWidth(350); outer.addWidget(scroll,0)
        pane=QWidget(); scroll.setWidget(pane); panel=QVBoxLayout(pane)
        panel.addWidget(QLabel('Experimental — read only | adaptive C2 Hips and Thighs'))
        preset=QComboBox(); preset.addItems(list(te.PRESETS)); preset.setCurrentText(cfg.get('preset','pear')); panel.addWidget(QLabel('Base shape')); panel.addWidget(preset)
        form=QFormLayout(); panel.addLayout(form); controls={}; basic_belly_row=None; amounts={**te.PRESETS[preset.currentText()],**cfg.get('amounts',{})}; depths=cfg.get('direct_depth',{})
        specs=[('hips','Hips Width (X)',5,amounts['hips']),('hips_y','Hips Depth (Y)',5,depths.get('hips',amounts['hips'])),('butt','Glutes',2,amounts['butt']),('thighs','Thighs Width (X)',2,amounts['thighs']),('thighs_y','Thighs Depth (Y)',2,depths.get('thighs',amounts['thighs'])),('calves','Calves',2,amounts['calves']),('belly','Belly',1,cfg.get('belly_morphology',{}).get('amount',0.))]
        for key,label,limit,val in specs:
            row=QWidget(); line=QHBoxLayout(row); line.setContentsMargins(0,0,0,0)
            sl=QSlider(Qt.Orientation.Horizontal); sl.setRange(0,limit*100); sp=QDoubleSpinBox(); sp.setRange(0,limit); sp.setDecimals(2); sp.setSingleStep(.05 if key!='belly' else .01); sp.setValue(val); sl.setValue(round(sp.value()*100))
            sl.valueChanged.connect(lambda n,w=sp:w.setValue(n/100)); sp.valueChanged.connect(lambda n,w=sl:w.setValue(round(n*100)))
            line.addWidget(sl,1); line.addWidget(sp); form.addRow(label,row); controls[key]=sp
            if key=='belly': basic_belly_row=row
        belly_cfg=cfg.get('belly_morphology',{})
        advanced=QCheckBox('Belly — Advanced Settings'); advanced.setChecked(bool(belly_cfg.get('advanced',False))); panel.addWidget(advanced)
        belly_panel=QWidget(); belly_form=QFormLayout(belly_panel); belly_controls={}
        for key,(lo,hi) in LIMITS.items():
            row=QWidget(); line=QHBoxLayout(row); line.setContentsMargins(0,0,0,0)
            sl=QSlider(Qt.Orientation.Horizontal); sl.setRange(round(lo*100),round(hi*100))
            sp=QDoubleSpinBox(); sp.setRange(lo,hi); sp.setDecimals(2); sp.setSingleStep(.01); sp.setValue(parameters(belly_cfg)[key]); sl.setValue(round(sp.value()*100))
            sl.valueChanged.connect(lambda n,w=sp:w.setValue(n/100)); sp.valueChanged.connect(lambda n,w=sl:w.setValue(round(n*100)))
            line.addWidget(sl,1); line.addWidget(sp); belly_form.addRow(key.title(),row); belly_controls[key]=sp
        panel.addWidget(belly_panel); belly_panel.setVisible(advanced.isChecked()); basic_belly_row.setEnabled(not advanced.isChecked())
        ref=QComboBox(); ref.addItems(['ADS 78A only','ADS 75','Direct Section 045','Original']); panel.addWidget(QLabel('Comparison')); panel.addWidget(ref)
        skin=QCheckBox('Skin only'); wire=QCheckBox('Wireframe'); live=QCheckBox('Live Preview'); live.setChecked(False)
        for w in (skin,wire,live): panel.addWidget(w)
        status=QLabel('Ready'); status.setWordWrap(True); panel.addWidget(status)
        preview=QPushButton('Preview'); reset=QPushButton('Reset controls'); close=QPushButton('Close')
        for b in (preview,reset,close): panel.addWidget(b)
        plot=QtInteractor(parent=dialog,shape=(1,2),auto_update=False); outer.addWidget(plot.interactor,1); plot.enable_custom_trackball_style(left='rotate',middle='pan',right='pan')
        state={'future':None,'generation':0,'done':-1,'result':None,'baseline':None,'meshes':[],'closing':False,'active':[],'skin':[]}
        colors=['#a6bcd1','#b3b9a2','#c2a9a0','#a9b3c1','#b9a6c4']
        def vals(): return {**{k:w.value() for k,w in controls.items()},'belly_advanced':advanced.isChecked(),**{'belly_'+k:w.value() for k,w in belly_controls.items()}}
        def config(a):
            c=copy.deepcopy(cfg); c.update(preset=preset.currentText(),morphology_engine='Direct Section',amounts={k:a[k] for k in ('hips','butt','thighs','calves')},direct_depth={'hips':a['hips_y'],'thighs':a['thighs_y']},belly_morphology=dict(amount=a['belly'],advanced=a['belly_advanced'],**({k:a['belly_'+k] for k in LIMITS} if a['belly_advanced'] else basic_parameters(a['belly']))))
            # Freeze common advanced options to the launch configuration for a controlled A/B test.
            return c
        def calculate(g,c,mode):
            start=time.perf_counter(); profiles.diagnostics.clear()
            with experimental_fields(profiles): result=s.preview(c)
            t1=time.perf_counter()-start; mid=time.perf_counter(); original=None
            if mode==1:
                with experimental_fields(baseline_profiles): original=s.preview(c)
            elif mode==2: original=s.preview(c)
            if result.positions.shape!=s.original_geometry.shape or not np.isfinite(result.positions).all(): raise RuntimeError('Invalid preview geometry')
            # Combined field diagnostic: actual skin section widths, not summed normalized intensities.
            from morphology.geometry import contour
            L=result.regional_data['L']; active=set(result.regional_data['active']); skin_names=[n for n in result.regional_data['skin'] if n in active and n in s.faces]
            if skin_names:
                faces=np.concatenate([s.faces[n] for n in skin_names]); z=np.linspace(L['knee'],L['waist'],241)
                def widths(q):
                    tri=q[faces]; lo=tri[:,:,2].min(1); hi=tri[:,:,2].max(1); rows=[]
                    for h in z:
                        c=contour(tri[(lo<h)&(hi>=h)],h); rows.append([float(c[:,0].max()),float(-c[:,0].min())] if len(c) else [None,None])
                    return rows
                combined=dict(z=z.tolist(),original=widths(s.original_geometry),ads78=widths(result.positions))
                if original is not None: combined['comparison']=widths(original.positions)
            else: combined={}
            (outdir/'latest_curves.json').write_text(json.dumps(dict(mode=mode,amounts=c['amounts'],direct_depth=c['direct_depth'],belly_morphology=c['belly_morphology'],profiles=profiles.diagnostics,combined_sections=combined),indent=2),encoding='utf-8')
            return g,original,result,time.perf_counter()-mid,t1,mode
        def names(): return [n for n in state['active'] if n in s.faces and len(s.faces[n]) and (not skin.isChecked() or n in state['skin'])]
        def rebuild(*_):
            if state['result'] is None:return
            ns=names()
            if not ns:return
            plot.subplot(0,1); previous=plot.camera_position if state['meshes'] else None; scale=plot.camera.parallel_scale if previous else None
            plot.clear(); state['meshes']=[]
            mode=state.get('mode',0); compare=mode!=0
            left=plot.renderers[0]; right=plot.renderers[1]
            left.SetDraw(compare); right.SetDraw(True)
            left.SetViewport(0.,0.,.5,1.); right.SetViewport(.5 if compare else 0.,0.,1.,1.)
            p=s.original_geometry if mode==3 else (state['baseline'].positions if state['baseline'] is not None else s.original_geometry)
            views=[(1,'ADS 78A — Adaptive',state['result'].positions)]
            if compare: views.insert(0,(0,['','ADS 75','Direct Section 045','Original'][mode],p))
            for col,label,q in views:
                plot.subplot(0,col); plot.set_background('#202733'); plot.enable_parallel_projection()
                for i,n in enumerate(ns):
                    t=s.faces[n]; ids=np.unique(t); cells=np.column_stack((np.full(len(t),3),np.searchsorted(ids,t))).ravel(); mesh=pv.PolyData(q[ids].copy(),cells)
                    plot.add_mesh(mesh,color=colors[i%len(colors)],style='wireframe' if wire.isChecked() else 'surface',smooth_shading=False,reset_camera=False); state['meshes'].append((col,mesh,ids))
                plot.add_text(label,font_size=11,color='white')
            plot.subplot(0,1); plot.link_views(views=1)
            if previous: plot.camera_position=previous; plot.camera.parallel_scale=scale; plot.render()
            else: camera((0,1,0))
        def camera(d):
            ns=names()
            if not ns:return
            ids=np.unique(np.concatenate([s.faces[n].ravel() for n in ns])); p=s.original_geometry[ids]; mid=(p.min(0)+p.max(0))/2; extent=max(float(np.ptp(p,axis=0).max()),1.)
            d=np.asarray(d,float); d/=np.linalg.norm(d); plot.subplot(0,1); plot.camera_position=[mid+d*extent*3,mid,(0,0,1)]; plot.camera.parallel_scale=extent*.58; plot.renderer.reset_camera_clipping_range(); plot.render()
        def refresh():
            if state['future'] is not None:return
            debounce.stop(); status.setText('Working…'); state['future']=pool.submit(calculate,state['generation'],config(vals()),ref.currentIndex()); poll.start()
        def changed(*_):
            state['generation']+=1
            status.setText('Parameters changed — press Preview' if not live.isChecked() else 'Parameters changed')
            if live.isChecked(): debounce.start()
        def poll_result():
            f=state['future']
            if f is None or not f.done():return
            poll.stop(); state['future']=None
            try:
                g,base,result,t0,t1,mode=f.result()
                if g!=state['generation']:
                    status.setText('Parameters changed — press Preview')
                    if live.isChecked(): debounce.start()
                    return
                first=state['result'] is None or state.get('mode')!=mode; state.update(done=g,baseline=base,result=result,mode=mode,active=result.regional_data['active'],skin=result.regional_data['skin'])
                if first: rebuild()
                else:
                    for col,mesh,ids in state['meshes']:
                        q=(s.original_geometry if mode==3 else base.positions) if col==0 else result.positions
                        mesh.points=q[ids].copy(); mesh.Modified()
                    plot.render()
                diff=float(np.max(np.linalg.norm(result.positions-(base.positions if base is not None else s.original_geometry),axis=1)))
                status.setText(f'Ready | ADS 78A {t1:.3f}s | comparison/diagnostics {t0:.3f}s | max difference {diff:.3f} cm'); print('Preview:',vals(),'max A/B difference cm:',diff,'times:',t0,t1,flush=True)
            except Exception as e: status.setText('Error: '+str(e)); traceback.print_exc()
        debounce=QTimer(dialog); debounce.setSingleShot(True); debounce.setInterval(600); debounce.timeout.connect(refresh)
        poll=QTimer(dialog); poll.setInterval(75); poll.timeout.connect(poll_result)
        for w in controls.values(): w.valueChanged.connect(changed)
        for w in belly_controls.values(): w.valueChanged.connect(changed)
        def toggle_advanced(on):
            belly_panel.setVisible(on); basic_belly_row.setEnabled(not on); changed()
        advanced.toggled.connect(toggle_advanced)
        def sync_basic(value):
            if not advanced.isChecked():
                for k,v in basic_parameters(value).items(): belly_controls[k].setValue(v)
        controls['belly'].valueChanged.connect(sync_basic)
        def reset_all():
            advanced.setChecked(False)
            for w in controls.values(): w.setValue(0.)
            for k,v in basic_parameters(0.).items(): belly_controls[k].setValue(v)
        def set_preset(name):
            for k,v in te.PRESETS[name].items():
                controls[k].setValue(v)
                if k+'_y' in controls:controls[k+'_y'].setValue(v)
        preset.currentTextChanged.connect(set_preset)
        preview.clicked.connect(refresh); reset.clicked.connect(reset_all); skin.toggled.connect(rebuild); wire.toggled.connect(rebuild); ref.currentIndexChanged.connect(changed)
        live.toggled.connect(lambda on: debounce.start() if on else debounce.stop())
        close.clicked.connect(dialog.accept)
        for label,d in [('Front',(0,1,0)),('Back',(0,-1,0)),('Side',(1,0,0)),('Perspective',(1,-2,.5))]:
            b=QPushButton(label); b.clicked.connect(lambda checked=False,d=d:camera(d)); panel.addWidget(b)
        def shot():
            from datetime import datetime
            path=outdir/('78A_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.png'); plot.screenshot(str(path),scale=2); print('Screenshot:',path,flush=True)
        b=QPushButton('Screenshot'); b.clicked.connect(shot); panel.addWidget(b); panel.addStretch()
        try: QTimer.singleShot(0,refresh); dialog.exec()
        finally: debounce.stop(); poll.stop(); plot.close()

if __name__=='__main__':
    main(); print('===== EXPERIMENT 78A - ADS ADAPTIVE MORPHOLOGICAL CURVES COMPLETED =====',flush=True)
