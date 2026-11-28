"""Interactive reference-guided Direct Section; writes only on explicit Apply."""
EXPERIMENT_INFO={'description':'Anny reference-guided Direct Section (private field clone).','objective':'Compare measured human longitudinal expansion profiles against Direct Section 045 at identical controls.','visual':'Interactive Qt / VTK comparison','batch':False,'writes':True,'parameter_source':'current','parameters':'Current Direct Section basic controls; Anny X/Y reference envelopes; no Advanced Settings UI.'}
import copy,json,os,sys,time,subprocess,traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from morphology import PreviewSession
from morphology.experimental_apply import snapshot,write_buffers
from _anny75_direct import Profiles,experimental_fields


def main():
    os.environ.setdefault('QT_API','pyside6')
    from PySide6.QtCore import Qt,QTimer
    from PySide6.QtWidgets import (QApplication,QDialog,QHBoxLayout,QVBoxLayout,QFormLayout,QWidget,QDoubleSpinBox,QSlider,QPushButton,QCheckBox,QLabel,QComboBox,QMessageBox,QScrollArea)
    import pyvista as pv
    from pyvistaqt import QtInteractor
    import thicc_edit as te
    from morphology.belly import basic_parameters
    app=QApplication.instance() or QApplication([])
    if os.environ.get('THICC_EXPERIMENT_SNAPSHOT') or not os.environ.get('THICC_LIVE_CONFIG'):
        raise RuntimeError('Register writer experiment 75 before running; use Run selected after Analyze, not batch.')
    mod=Path(os.environ['THICC_MOD_DIR']).resolve(); cfg=json.loads(Path(os.environ['THICC_LIVE_CONFIG']).read_text(encoding='utf-8'))
    if cfg.get('morphology_engine')!='Direct Section': raise RuntimeError('Select Direct Section in Morphology before launching experiment 75.')
    expected=snapshot(mod)
    root=Path(__file__).resolve().parent.parent
    refpath=root/'experiment_results'/'anny75'/'profiles.json'
    envpython=os.environ.get('THICC_ANNY_PYTHON',str(root/'.anny75'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')))
    if not refpath.is_file():
        if not Path(envpython).is_file(): raise RuntimeError('Anny reference missing. Run setup_anny75.bat first.')
        subprocess.run([envpython,'-u',str(Path(__file__).with_name('_anny75_reference.py')),str(refpath)],check=True)
    data=json.loads(refpath.read_text(encoding='utf-8')); profiles=Profiles(data)
    print('Anny reference version:',data['anny_version'],'landmarks:',data['landmarks'],flush=True)
    with PreviewSession(mod) as s, ThreadPoolExecutor(max_workers=1) as pool:
        if snapshot(mod)!=expected: raise RuntimeError('Mod changed while preparing session.')
        dialog=QDialog(); dialog.setWindowTitle('75 | Anny Direct Section Lab'); dialog.resize(1500,850)
        outer=QHBoxLayout(dialog); scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setMinimumWidth(350); outer.addWidget(scroll,0)
        pane=QWidget(); scroll.setWidget(pane); panel=QVBoxLayout(pane)
        panel.addWidget(QLabel('Experimental — reference-guided Hips and Thighs'))
        preset=QComboBox(); preset.addItems(list(te.PRESETS)); preset.setCurrentText(cfg.get('preset','pear')); panel.addWidget(QLabel('Base shape')); panel.addWidget(preset)
        form=QFormLayout(); panel.addLayout(form); controls={}; amounts={**te.PRESETS[preset.currentText()],**cfg.get('amounts',{})}; depths=cfg.get('direct_depth',{})
        specs=[('hips','Hips Width (X)',5,amounts['hips']),('hips_y','Hips Depth (Y)',5,depths.get('hips',amounts['hips'])),('butt','Glutes',2,amounts['butt']),('thighs','Thighs Width (X)',2,amounts['thighs']),('thighs_y','Thighs Depth (Y)',2,depths.get('thighs',amounts['thighs'])),('calves','Calves',2,amounts['calves']),('belly','Belly',1,cfg.get('belly_morphology',{}).get('amount',0.))]
        for key,label,limit,val in specs:
            row=QWidget(); line=QHBoxLayout(row); line.setContentsMargins(0,0,0,0)
            sl=QSlider(Qt.Orientation.Horizontal); sl.setRange(0,limit*100); sp=QDoubleSpinBox(); sp.setRange(0,limit); sp.setDecimals(2); sp.setSingleStep(.05 if key!='belly' else .01); sp.setValue(val); sl.setValue(round(sp.value()*100))
            sl.valueChanged.connect(lambda n,w=sp:w.setValue(n/100)); sp.valueChanged.connect(lambda n,w=sl:w.setValue(round(n*100)))
            line.addWidget(sl,1); line.addWidget(sp); form.addRow(label,row); controls[key]=sp
        ref=QComboBox(); ref.addItems(['Direct Section 045','Original']); panel.addWidget(QLabel('Comparison')); panel.addWidget(ref)
        skin=QCheckBox('Skin only'); wire=QCheckBox('Wireframe'); live=QCheckBox('Live Preview'); live.setChecked(True)
        for w in (skin,wire,live): panel.addWidget(w)
        status=QLabel('Ready'); status.setWordWrap(True); panel.addWidget(status)
        preview=QPushButton('Preview (no buffer writes)'); apply=QPushButton('Apply to mod'); restore=QPushButton('Restore original'); reset=QPushButton('Reset'); close=QPushButton('Close')
        apply.setEnabled(False)
        for b in (preview,apply,restore,reset,close): panel.addWidget(b)
        plot=QtInteractor(parent=dialog,shape=(1,2),auto_update=False); outer.addWidget(plot.interactor,1); plot.enable_custom_trackball_style(left='rotate',middle='pan',right='pan')
        state={'future':None,'generation':0,'done':-1,'result':None,'baseline':None,'meshes':[],'closing':False,'active':[],'skin':[],'applied':False}
        colors=['#a6bcd1','#b3b9a2','#c2a9a0','#a9b3c1','#b9a6c4']
        def vals(): return {k:w.value() for k,w in controls.items()}
        def config(a):
            c=copy.deepcopy(cfg); c.update(morphology_engine='Direct Section',amounts={k:a[k] for k in ('hips','butt','thighs','calves')},direct_depth={'hips':a['hips_y'],'thighs':a['thighs_y']},belly_morphology=dict(amount=a['belly'],advanced=False,**basic_parameters(a['belly'])))
            # Freeze common advanced options to the launch configuration for a controlled A/B test.
            return c
        def calculate(g,c):
            start=time.perf_counter(); original=s.preview(c); mid=time.perf_counter()
            with experimental_fields(profiles): result=s.preview(c)
            if result.vectors is None or result.positions.shape!=s.original_geometry.shape or not np.isfinite(result.positions).all(): raise RuntimeError('Invalid preview buffers')
            return g,original,result,mid-start,time.perf_counter()-mid
        def names(): return [n for n in state['active'] if n in s.faces and len(s.faces[n]) and (not skin.isChecked() or n in state['skin'])]
        def rebuild(*_):
            if state['result'] is None:return
            ns=names()
            if not ns:return
            plot.subplot(0,0); previous=plot.camera_position if state['meshes'] else None; scale=plot.camera.parallel_scale if previous else None
            plot.clear(); state['meshes']=[]
            p=s.original_geometry if ref.currentIndex()==1 else state['baseline'].positions
            for col,(label,q) in enumerate([(ref.currentText(),p),('Anny Direct Section',state['result'].positions)]):
                plot.subplot(0,col); plot.set_background('#202733'); plot.enable_parallel_projection()
                for i,n in enumerate(ns):
                    t=s.faces[n]; ids=np.unique(t); cells=np.column_stack((np.full(len(t),3),np.searchsorted(ids,t))).ravel(); mesh=pv.PolyData(q[ids].copy(),cells)
                    plot.add_mesh(mesh,color=colors[i%len(colors)],style='wireframe' if wire.isChecked() else 'surface',smooth_shading=False,reset_camera=False); state['meshes'].append((col,mesh,ids))
                plot.add_text(label,font_size=11,color='white')
            plot.subplot(0,0); plot.link_views()
            if previous: plot.camera_position=previous; plot.camera.parallel_scale=scale; plot.render()
            else: camera((0,1,0))
        def camera(d):
            ns=names()
            if not ns:return
            ids=np.unique(np.concatenate([s.faces[n].ravel() for n in ns])); p=s.original_geometry[ids]; mid=(p.min(0)+p.max(0))/2; extent=max(float(np.ptp(p,axis=0).max()),1.)
            d=np.asarray(d,float); d/=np.linalg.norm(d); plot.subplot(0,0); plot.camera_position=[mid+d*extent*3,mid,(0,0,1)]; plot.camera.parallel_scale=extent*.58; plot.renderer.reset_camera_clipping_range(); plot.render()
        def refresh():
            if state['future'] is not None:return
            apply.setEnabled(False); status.setText('Working…'); state['future']=pool.submit(calculate,state['generation'],config(vals())); poll.start()
        def changed(*_):
            state['generation']+=1; apply.setEnabled(False)
            if live.isChecked(): debounce.start()
        def poll_result():
            f=state['future']
            if f is None or not f.done():return
            poll.stop(); state['future']=None
            try:
                g,base,result,t0,t1=f.result()
                if g!=state['generation']:
                    if live.isChecked(): debounce.start()
                    return
                first=state['result'] is None; state.update(done=g,baseline=base,result=result,active=result.regional_data['active'],skin=result.regional_data['skin'])
                if first: rebuild()
                else:
                    for col,mesh,ids in state['meshes']:
                        q=(s.original_geometry if ref.currentIndex()==1 else base.positions) if col==0 else result.positions
                        mesh.points=q[ids].copy(); mesh.Modified()
                    plot.render()
                diff=float(np.max(np.linalg.norm(result.positions-base.positions,axis=1)))
                status.setText(f'Ready | Direct {t0:.3f}s | Anny {t1:.3f}s | max difference {diff:.3f} cm'); print('Preview:',vals(),'max A/B difference cm:',diff,'times:',t0,t1,flush=True); apply.setEnabled(True)
            except Exception as e: status.setText('Error: '+str(e)); traceback.print_exc(); apply.setEnabled(False)
        debounce=QTimer(dialog); debounce.setSingleShot(True); debounce.setInterval(600); debounce.timeout.connect(refresh)
        poll=QTimer(dialog); poll.setInterval(75); poll.timeout.connect(poll_result)
        for w in controls.values(): w.valueChanged.connect(changed)
        def set_preset(name):
            for k,v in te.PRESETS[name].items():
                controls[k].setValue(v)
                if k+'_y' in controls:controls[k+'_y'].setValue(v)
        preset.currentTextChanged.connect(set_preset)
        preview.clicked.connect(refresh); reset.clicked.connect(lambda:[w.setValue(0.) for w in controls.values()]); skin.toggled.connect(rebuild); wire.toggled.connect(rebuild); ref.currentIndexChanged.connect(rebuild)
        live.toggled.connect(lambda on: debounce.start() if on else debounce.stop())
        def notify():
            marker=os.environ.get('THICC_APPLIED_MARKER')
            if marker: Path(marker).write_text(json.dumps({'experiment':75,'values':vals()}),encoding='utf-8')
        def commit():
            nonlocal expected
            if state['future'] is not None or state['done']!=state['generation'] or state['result'] is None:return
            if QMessageBox.question(dialog,'Apply experimental geometry',f'Write the displayed Anny geometry to:\n{mod}\nClose the game first. Original backups preserved. Continue?')!=QMessageBox.StandardButton.Yes:return
            try:
                r=state['result']; expected=write_buffers(mod,expected,r.positions,r.vectors); notify(); status.setText('Applied — original backups preserved.'); print('APPLIED EXPERIMENT 75:',vals(),flush=True)
            except Exception as e: QMessageBox.critical(dialog,'Apply failed',str(e)); traceback.print_exc()
        def restore_original():
            nonlocal expected
            if state['future'] is not None:return
            if not expected.get('Position.buf.orig') or not expected.get('Vector.buf.orig'): QMessageBox.information(dialog,'Restore','No original backup pair exists.'); return
            if QMessageBox.question(dialog,'Restore',f'Restore original buffers in {mod}? Close the game first.')!=QMessageBox.StandardButton.Yes:return
            try:
                mesh=mod/'Meshes'; p=np.fromfile(mesh/'Position.buf.orig',dtype='<f4').reshape(-1,3); v=np.fromfile(mesh/'Vector.buf.orig',dtype=np.int8).reshape(-1,8); expected=write_buffers(mod,expected,p,v); notify(); status.setText('Original restored.'); print('EXPERIMENT 75 RESTORED ORIGINAL',flush=True)
            except Exception as e: QMessageBox.critical(dialog,'Restore failed',str(e)); traceback.print_exc()
        apply.clicked.connect(commit); restore.clicked.connect(restore_original); close.clicked.connect(dialog.accept)
        for label,d in [('Front',(0,1,0)),('Back',(0,-1,0)),('Side',(1,0,0)),('Perspective',(1,-2,.5))]:
            b=QPushButton(label); b.clicked.connect(lambda checked=False,d=d:camera(d)); panel.addWidget(b)
        def shot():
            from datetime import datetime
            path=refpath.parent/('75_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.png'); plot.screenshot(str(path),scale=2); print('Screenshot:',path,flush=True)
        b=QPushButton('Screenshot'); b.clicked.connect(shot); panel.addWidget(b); panel.addStretch()
        try: QTimer.singleShot(0,refresh); dialog.exec()
        finally: debounce.stop(); poll.stop(); plot.close()

if __name__=='__main__':
    main(); print('===== EXPERIMENT 75 - ANNY DIRECT SECTION LAB FINISHED =====',flush=True)
