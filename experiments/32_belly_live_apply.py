"""Live Belly lab on top of the current production morphology; explicit opt-in writes."""

EXPERIMENT_INFO = {'description': 'Interactive live belly lab with explicit Apply.', 'objective': 'Test abdomen controls on the current morphology baseline.', 'visual': 'Interactive viewer', 'batch': False, 'writes': True, 'parameter_source': 'current', 'parameters': 'Snapshot of the current Morphology controls and current mod roles. Interactive only.'}

import os
import json
from pathlib import Path
import numpy as np
from morphology import PreviewSession
from morphology.refinement import RegionalControls, FieldComposer
from morphology.experimental_apply import snapshot, write_buffers, belly_vectors


def main():
    os.environ.setdefault('QT_API','pyside6')
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import (QApplication,QDialog,QHBoxLayout,QVBoxLayout,QFormLayout,
        QWidget,QDoubleSpinBox,QSlider,QPushButton,QCheckBox,QLabel,QMessageBox)
    import pyvista as pv
    from pyvistaqt import QtInteractor
    app=QApplication.instance() or QApplication([])
    mod=Path(os.environ['THICC_MOD_DIR'])
    config_path=os.environ.get('THICC_LIVE_CONFIG')
    if not config_path: raise RuntimeError('Launch experiment 32 from Thicc Tool after Analyze; live GUI configuration required.')
    cfg=json.loads(Path(config_path).read_text(encoding='utf-8'))
    expected=snapshot(mod)
    with PreviewSession(mod) as s:
        if snapshot(mod)!=expected: raise RuntimeError('Source changed while preparing session.')
        base=s.preview({**cfg, "belly_morphology": {"amount":0.}}); r=s.regional(base); center,reliable=r.locate_waist()
        if base.vectors is None: raise RuntimeError('Baseline vectors unavailable; install full patch 025.')
        c=RegionalControls(r,center); composer=FieldComposer(r,base.positions)
        print('Live morphology snapshot:',cfg['amounts'],flush=True)
        print('Belly reference waist:',center,'closed contour confidence:',reliable,flush=True)
        print('Missing skin under garments is not reconstructed.',flush=True)
        dialog=QDialog(); dialog.setWindowTitle('32 | Live Belly Lab'); dialog.resize(1450,850)
        outer=QHBoxLayout(dialog); pane=QWidget(); panel=QVBoxLayout(pane); outer.addWidget(pane,0)
        panel.addWidget(QLabel('Production morphology (current GUI values)'))
        panel.addWidget(QLabel(' | '.join(f'{k}: {v:.2f}' for k,v in cfg['amounts'].items())))
        form=QFormLayout(); panel.addLayout(form); controls={}
        specs=[('Depth',0.,0.,1.),('Width',1.,.5,2.),('Height',1.,.5,1.5),('Offset',0.,-.15,.1)]
        for name,val,lo,hi in specs:
            row=QWidget(); layout=QHBoxLayout(row); layout.setContentsMargins(0,0,0,0)
            slider=QSlider(Qt.Orientation.Horizontal); slider.setRange(round(lo*100),round(hi*100)); slider.setValue(round(val*100))
            spin=QDoubleSpinBox(); spin.setRange(lo,hi); spin.setDecimals(2); spin.setSingleStep(.01); spin.setValue(val)
            slider.valueChanged.connect(lambda n,w=spin:w.setValue(n/100))
            spin.valueChanged.connect(lambda n,w=slider:w.setValue(round(n*100)))
            layout.addWidget(slider,1); layout.addWidget(spin); form.addRow(name,row); controls[name]=spin
        skin=QCheckBox('Skin only (view)'); panel.addWidget(skin)
        status=QLabel('Preparing viewer…'); status.setWordWrap(True); panel.addWidget(status)
        panel.addWidget(QLabel('Apply writes Position.buf and Vector.buf.\nNormal Apply will replace this experimental effect.'))
        reset=QPushButton('Reset Belly'); apply=QPushButton('Apply to mod'); apply.setEnabled(False)
        close=QPushButton('Close'); panel.addWidget(reset); panel.addWidget(apply); panel.addWidget(close); panel.addStretch()
        plot=QtInteractor(parent=dialog,shape=(1,2),auto_update=False); outer.addWidget(plot.interactor,1)
        plot.enable_custom_trackball_style(left='rotate',middle='pan',right='pan')
        state={'q':base.positions.copy(),'factor':1.,'ok':False,'meshes':[], 'camera':None, 'applied':False}
        colors=['#a6bcd1','#b3b9a2','#c2a9a0','#a9b3c1','#b9a6c4']
        directions={'Front':(0,1,0),'Back':(0,-1,0),'Left':(-1,0,0),'Right':(1,0,0),'3D':(1,-2,.55)}
        def names(): return [n for n in r.visible if not skin.isChecked() or n in r.d['skin']]
        def camera(direction='Right',focus=False):
            ids=np.unique(np.concatenate([s.faces[n].ravel() for n in names()]))
            p=base.positions[ids]; mid=(p.min(0)+p.max(0))/2; extent=max(float(np.ptp(p,axis=0).max()),1.)
            if focus:
                mid[0]=float(np.median(r.p[r.skin,0])); mid[1]=float(np.median(r.p[r.skin,1])); mid[2]=(r.L['crotch']+center)/2
                extent=max(1.,(center-r.L['crotch'])*2.5)
            d=np.asarray(directions[direction],float); d/=np.linalg.norm(d)
            plot.subplot(0,0); plot.camera_position=[mid+d*extent*3,mid,(0,0,1)]; plot.camera.parallel_scale=extent*.58
            plot.renderer.reset_camera_clipping_range(); plot.render()
        def rebuild():
            # Rebuild only when the view filter changes, not for slider changes.
            plot.subplot(0,0); previous=plot.camera_position if state['meshes'] else None
            scale=plot.camera.parallel_scale if previous else None
            plot.clear(); state['meshes']=[]
            for col,(label,q) in enumerate([('Morphology baseline',base.positions),('Belly preview',state['q'])]):
                plot.subplot(0,col); plot.set_background('#202733'); plot.enable_parallel_projection()
                for j,n in enumerate(names()):
                    t=s.faces[n]; ids=np.unique(t); cells=np.column_stack((np.full(len(t),3),np.searchsorted(ids,t))).ravel()
                    mesh=pv.PolyData(q[ids].copy(),cells)
                    actor=plot.add_mesh(mesh,color=colors[j%len(colors)],smooth_shading=False,reset_camera=False)
                    if col==1: state['meshes'].append((mesh,ids,actor))
                plot.add_text(label,font_size=12,color='white')
            plot.subplot(0,0); plot.link_views()
            if previous:
                plot.camera_position=previous; plot.camera.parallel_scale=scale; plot.render()
            else: camera()
        buttons=QHBoxLayout(); panel.addLayout(buttons)
        for name in directions:
            b=QPushButton(name); b.clicked.connect(lambda checked=False,n=name:camera(n)); buttons.addWidget(b)
        focus=QPushButton('Focus abdomen (side)'); panel.addWidget(focus); focus.clicked.connect(lambda:camera('Right',True))
        shot=QPushButton('Screenshot'); panel.addWidget(shot)
        def screenshot():
            from datetime import datetime
            path=Path.home()/('ThiccBelly_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.png')
            plot.screenshot(str(path),scale=2); print('Screenshot:',path,flush=True)
        shot.clicked.connect(screenshot)
        timer=QTimer(dialog); timer.setSingleShot(True); timer.setInterval(180)
        def refresh():
            try:
                a={k:w.value() for k,w in controls.items()}
                print("[BELLY_PREVIEW]",a,flush=True)
                q,f,_=composer.compose({'Belly':c.belly(a['Depth'],a['Width'],a['Height'],a['Offset'])})
                # Validate the float32 geometry that will actually be written.
                q=q.astype('<f4').astype(float)
                if len(composer.inspect(q).indices):
                    raise RuntimeError('Float32 output failed final face validation.')
                state.update(q=q,factor=f['Belly'],ok=True)
                for mesh,ids,actor in state['meshes']:
                    mesh.points=q[ids]; mesh.Modified()
                    actor.mapper.Update()
                plot.render(); status.setText(f"Belly accepted: {f['Belly']:.0%} | max added Y: {np.max(np.abs(q[:,1]-base.positions[:,1])):.3f} cm")
                if not reliable: status.setText(status.text()+'\nWaist fallback: open/incomplete skin reference.')
                apply.setEnabled(f['Belly']>0 and (a['Depth']==0 or np.max(np.abs(q-base.positions))>1e-6))
            except Exception as exc:
                state['ok']=False; apply.setEnabled(False); status.setText(str(exc)); print('Belly preview error:',exc,flush=True)
        def changed(*_):
            state['ok']=False; apply.setEnabled(False); timer.start()
        for w in controls.values(): w.valueChanged.connect(changed)
        timer.timeout.connect(refresh); skin.toggled.connect(lambda _:rebuild())
        def restore():
            for name,val,*_ in specs: controls[name].setValue(val)
            changed()
        reset.clicked.connect(restore); close.clicked.connect(dialog.accept)
        def commit():
            nonlocal expected
            timer.stop(); refresh()
            if not state['ok'] or not apply.isEnabled(): return
            a={k:w.value() for k,w in controls.items()}
            text=f'Write the displayed geometry to:\n{mod}\n\nBelly accepted: {state["factor"]:.0%}.\nExisting .orig files will be preserved. Close the game before writing. Continue?'
            if QMessageBox.question(dialog,'Apply experimental Belly',text)!=QMessageBox.StandardButton.Yes: return
            apply.setEnabled(False)
            try:
                shading=cfg.get('surface_shading','Original')
                vec=belly_vectors(base.positions,state['q'],base.vectors,r.allfaces,shading)
                expected=write_buffers(mod,expected,state['q'],vec)
                state['applied']=True
                marker=os.environ.get('THICC_APPLIED_MARKER')
                if marker:
                    try: Path(marker).write_text(json.dumps({'belly':a,'factor':state['factor']}),encoding='utf-8')
                    except OSError as exc: print('Applied successfully; could not notify main viewer:',exc,flush=True)
                print('APPLIED BELLY:',a,'factor:',state['factor'],flush=True)
                status.setText('Applied. Press F10 in game after reopening. Original backups preserved.')
            except Exception as exc:
                QMessageBox.critical(dialog,'Apply failed',str(exc)); print('Apply error:',exc,flush=True)
            finally: apply.setEnabled(state['ok'] and state['factor']>0)
        apply.clicked.connect(commit)
        try:
            rebuild(); refresh(); dialog.exec()
        finally: plot.close()

if __name__=='__main__':
    main()
    print('===== EXPERIMENT 32 - BELLY LIVE APPLY FINISHED =====',flush=True)
