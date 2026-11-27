"""Read-only interactive comparison of new Hips fields with independent regional controls."""
EXPERIMENT_INFO={'description':'Interactive direct anatomical Hips editor with four regional sliders.','objective':'Compare direct section and absolute silhouette against Legacy without post smoothing; test combinations.','visual':'Interactive Qt viewer','batch':False,'writes':False,'parameter_source':'protocol','parameters':'Start at zero; Hips 0–5, Glutes/Thighs/Calves 0–2. Legacy comparison on demand.'}
import os,time
from pathlib import Path
import numpy as np
from morphology import PreviewSession
from _direct_anatomical_lab import Lab


def main():
    os.environ.setdefault('QT_API','pyside6')
    from PySide6.QtCore import Qt,QTimer
    from PySide6.QtWidgets import QApplication,QDialog,QHBoxLayout,QVBoxLayout,QFormLayout,QWidget,QDoubleSpinBox,QSlider,QPushButton,QCheckBox,QLabel,QComboBox
    import pyvista as pv
    from pyvistaqt import QtInteractor
    app=QApplication.instance() or QApplication([])
    with PreviewSession(Path(os.environ['THICC_MOD_DIR'])) as s:
        lab=Lab(s); dialog=QDialog(); dialog.setWindowTitle('74 | Direct Anatomical Morphology Lab'); dialog.resize(1500,850)
        outer=QHBoxLayout(dialog); left=QWidget(); panel=QVBoxLayout(left); outer.addWidget(left,0)
        panel.addWidget(QLabel('Experimental — read only'))
        mode=QComboBox(); mode.addItems(['Direct Section','Direct Silhouette']); panel.addWidget(mode)
        form=QFormLayout(); panel.addLayout(form); controls={}
        for name,limit in [('Hips',5),('Glutes',2),('Thighs',2),('Calves',2)]:
            row=QWidget(); line=QHBoxLayout(row); line.setContentsMargins(0,0,0,0)
            sl=QSlider(Qt.Orientation.Horizontal); sl.setRange(0,limit*100); sl.setMinimumWidth(170)
            sp=QDoubleSpinBox(); sp.setRange(0,limit); sp.setDecimals(2); sp.setSingleStep(.01)
            sl.valueChanged.connect(lambda n,w=sp:w.setValue(n/100)); sp.valueChanged.connect(lambda n,w=sl:w.setValue(round(n*100)))
            line.addWidget(sl,1); line.addWidget(sp); form.addRow(name,row); controls[name]=sp
        skin=QCheckBox('Skin only'); skin.setChecked(True); panel.addWidget(skin)
        wire=QCheckBox('Wireframe'); panel.addWidget(wire)
        ref=QComboBox(); ref.addItems(['Original','Legacy (last comparison)']); panel.addWidget(ref)
        status=QLabel('Ready'); status.setWordWrap(True); panel.addWidget(status)
        plot=QtInteractor(parent=dialog,shape=(1,2),auto_update=False); outer.addWidget(plot.interactor,1)
        plot.enable_custom_trackball_style(left='rotate',middle='pan',right='pan')
        state={'q':lab.p.copy(),'legacy':None,'legacy_values':None,'meshes':[]}
        colors=['#a6bcd1','#b3b9a2','#c2a9a0','#a9b3c1','#b9a6c4']
        def values(): return tuple(w.value() for w in controls.values())
        def names(): return lab.skin if skin.isChecked() else lab.visible
        def camera(direction=(0,-1,0),focus=False):
            ids=np.unique(np.concatenate([s.faces[n].ravel() for n in names()])); p=lab.p[ids]; mid=(p.min(0)+p.max(0))/2; extent=max(float(np.ptp(p,axis=0).max()),1.)
            if focus:
                mid[2]=(lab.L['waist']+lab.L['knee'])/2; extent=(lab.L['waist']-lab.L['knee'])*1.3
            d=np.asarray(direction,float); d/=np.linalg.norm(d); plot.subplot(0,0); plot.camera_position=[mid+d*extent*3,mid,(0,0,1)]; plot.camera.parallel_scale=extent*.58; plot.renderer.reset_camera_clipping_range(); plot.render()
        def rebuild(*_):
            plot.subplot(0,0); previous=plot.camera_position if state['meshes'] else None; scale=plot.camera.parallel_scale if previous else None
            plot.clear(); state['meshes']=[]
            legacy=ref.currentIndex()==1 and state['legacy'] is not None
            for col,(label,q) in enumerate([('Legacy '+str(state['legacy_values']) if legacy else 'Original',state['legacy'] if legacy else lab.p),(mode.currentText(),state['q'])]):
                plot.subplot(0,col); plot.set_background('#202733'); plot.enable_parallel_projection()
                for j,n in enumerate(names()):
                    t=s.faces[n]; ids=np.unique(t); cells=np.column_stack((np.full(len(t),3),np.searchsorted(ids,t))).ravel(); mesh=pv.PolyData(q[ids].copy(),cells)
                    plot.add_mesh(mesh,color=colors[j%len(colors)],style='wireframe' if wire.isChecked() else 'surface',smooth_shading=False,reset_camera=False)
                    if col==1: state['meshes'].append((mesh,ids))
                plot.add_text(label,font_size=11,color='white')
            plot.subplot(0,0); plot.link_views()
            if previous: plot.camera_position=previous; plot.camera.parallel_scale=scale; plot.render()
            else: camera()
        timer=QTimer(dialog); timer.setSingleShot(True); timer.setInterval(250)
        def refresh():
            try:
                t=time.perf_counter(); a=values(); q=lab.evaluate(*a,mode.currentText()); state['q']=q
                for mesh,ids in state['meshes']: mesh.points=q[ids].copy(); mesh.Modified()
                plot.render(); status.setText('Ready | %.3f s | %s'%(time.perf_counter()-t,mode.currentText()))
            except Exception as e: status.setText('Error: '+str(e)); print('Preview error:',e,flush=True)
        def change(*_): timer.start()
        for w in controls.values(): w.valueChanged.connect(change)
        timer.timeout.connect(refresh)
        def mode_change(*_): refresh(); rebuild()
        mode.currentIndexChanged.connect(mode_change); skin.toggled.connect(rebuild); wire.toggled.connect(rebuild); ref.currentIndexChanged.connect(rebuild)
        def legacy():
            timer.stop(); refresh(); status.setText('Calculating Legacy…'); app.processEvents()
            try:
                a=values(); state['legacy']=lab.legacy(*a); state['legacy_values']=a; ref.setCurrentIndex(1); rebuild(); status.setText('Legacy comparison ready; frozen at '+str(a))
            except Exception as e: status.setText('Legacy error: '+str(e)); print(e,flush=True)
        def report():
            timer.stop(); refresh(); print('Lab values:',values(),'mode:',mode.currentText(),flush=True); lab.report(state['q']); status.setText('Diagnostics printed to console')
        def reset():
            for w in controls.values(): w.setValue(0.)
        def shot():
            from datetime import datetime
            path=Path.home()/('ThiccDirect_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.png'); plot.screenshot(str(path)); print('Screenshot:',path,flush=True); status.setText(str(path))
        for label,fn in [('Compare Legacy (on demand)',legacy),('Diagnostics',report),('Reset',reset),('Screenshot',shot)]:
            b=QPushButton(label); b.clicked.connect(fn); panel.addWidget(b)
        for label,d in [('Front',(0,1,0)),('Back',(0,-1,0)),('Side',(1,0,0)),('3D',(1,-2,.5))]:
            b=QPushButton(label); b.clicked.connect(lambda checked=False,d=d:camera(d)); panel.addWidget(b)
        b=QPushButton('Focus hips / legs'); b.clicked.connect(lambda:camera((0,-1,0),True)); panel.addWidget(b)
        b=QPushButton('Close'); b.clicked.connect(dialog.accept); panel.addWidget(b); panel.addStretch()
        try: rebuild(); dialog.exec()
        finally: timer.stop(); plot.close()

if __name__=='__main__':
    main(); print('===== EXPERIMENT 74 - DIRECT ANATOMICAL MORPHOLOGY EDITOR FINISHED =====',flush=True)
