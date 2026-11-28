"""Anny Full Body morphology; writes only on explicit Apply."""
EXPERIMENT_INFO={'description':'Independent native Anny morphology transfer.','objective':'Evaluate native combined Anny local changes without DS fields or envelopes.','visual':'Interactive Qt / VTK','batch':False,'writes':True,'parameter_source':'current','parameters':'Native Anny target strengths; no Advanced Settings UI.'}
import copy,json,os,sys,time,subprocess,traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from morphology import PreviewSession
from morphology.experimental_apply import snapshot,write_buffers
from _anny77_transfer import NativeAnny, Transfer
from _anny77_controls import SPECS
from morphology.engine import MorphologyResult
from morphology.experimental_apply import belly_vectors


def main():
    os.environ.setdefault('QT_API','pyside6')
    from PySide6.QtCore import Qt,QTimer
    from PySide6.QtWidgets import (QApplication,QDialog,QHBoxLayout,QVBoxLayout,QFormLayout,QWidget,QDoubleSpinBox,QSlider,QPushButton,QCheckBox,QLabel,QComboBox,QMessageBox,QScrollArea)
    import pyvista as pv
    from pyvistaqt import QtInteractor
    import thicc_edit as te
    app=QApplication.instance() or QApplication([])
    if os.environ.get('THICC_EXPERIMENT_SNAPSHOT') or not os.environ.get('THICC_LIVE_CONFIG'):
        raise RuntimeError('Register writer experiment 77 before running; use Run selected after Analyze, not batch.')
    mod=Path(os.environ['THICC_MOD_DIR']).resolve(); cfg=json.loads(Path(os.environ['THICC_LIVE_CONFIG']).read_text(encoding='utf-8'))
    expected=snapshot(mod)
    root=Path(__file__).resolve().parent.parent
    refpath=root/'experiment_results'/'anny77'/'reference.json'
    refpath.parent.mkdir(parents=True,exist_ok=True)
    reference={'knee': -0.3073733150959015, 'crotch': 0.018759595304727594, 'waist': 0.2647896856069565, 'half_width': 0.1974008398368322, 'half_depth': 0.09857251266035744}
    envpython=os.environ.get('THICC_ANNY_PYTHON',str(root/'.anny75'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')))
    if not Path(envpython).is_file(): envpython=str(root/'.anny77'/('Scripts/python.exe' if os.name=='nt' else 'bin/python'))
    if not Path(envpython).is_file(): raise RuntimeError('Run setup_anny77_full_body.bat first.')
    native=NativeAnny(envpython)
    with PreviewSession(mod) as s, ThreadPoolExecutor(max_workers=1) as pool:
        if snapshot(mod)!=expected: raise RuntimeError('Mod changed while preparing session.')
        dialog=QDialog(); dialog.setWindowTitle('77 | Anny Full Body WWMI'); dialog.resize(1500,850)
        outer=QHBoxLayout(dialog); scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setMinimumWidth(350); left=QWidget(); left.setMinimumWidth(400); left_layout=QVBoxLayout(left); outer.addWidget(left,0); left_layout.addWidget(scroll,1)
        pane=QWidget(); scroll.setWidget(pane); panel=QVBoxLayout(pane)
        panel.addWidget(QLabel('Experimental — native Anny target strengths'))
        panel.addWidget(QLabel(str(mod.name)))
        preset=QComboBox(); preset.addItems(['Neutral',*te.PRESETS]); preset.setCurrentText('Neutral'); panel.addWidget(QLabel('Optional lower-body preset (starts neutral)')); panel.addWidget(preset)
        form=QFormLayout(); panel.addLayout(form); controls={}; amounts={}; depths={}
        specs=[(k,label,lo,hi,0.) for k,label,lo,hi,_ in SPECS]
        for key,label,lo,limit,val in specs:
            if key in {'build','waist','breast','shoulders','neck_x','hips','thighs','calves','belly'}:
                form.addRow(QLabel({'build':'GLOBAL','waist':'TORSO / WAIST','breast':'CHEST','shoulders':'ARMS / HANDS','neck_x':'NECK','hips':'PELVIS','thighs':'THIGHS','calves':'LOWER LEGS / FEET','belly':'ABDOMEN'}[key]))
            row=QWidget(); line=QHBoxLayout(row); line.setContentsMargins(0,0,0,0)
            sl=QSlider(Qt.Orientation.Horizontal); sl.setRange(lo*100,limit*100); sp=QDoubleSpinBox(); sp.setRange(lo,limit); sp.setDecimals(2); sp.setSingleStep(.05 if key!='belly' else .01); sp.setValue(val); sl.setValue(round(sp.value()*100))
            sl.valueChanged.connect(lambda n,w=sp:w.setValue(n/100)); sp.valueChanged.connect(lambda n,w=sl:w.setValue(round(n*100)))
            line.addWidget(sl,1); line.addWidget(sp); form.addRow(label,row); controls[key]=sp
        ref=QComboBox(); ref.addItems(['Anny only','Compare original']); panel.addWidget(QLabel('Comparison')); panel.addWidget(ref)
        skin=QCheckBox('Skin only'); wire=QCheckBox('Wireframe'); live=QCheckBox('Live Preview'); live.setChecked(False)
        for w in (skin,wire,live): left_layout.addWidget(w)
        status=QLabel('Ready'); status.setWordWrap(True); left_layout.addWidget(status)
        preview=QPushButton('Preview (no buffer writes)'); apply=QPushButton('Apply to mod'); restore=QPushButton('Restore original'); reset=QPushButton('Reset'); close=QPushButton('Close')
        apply.setEnabled(False)
        for b in (preview,apply,restore,reset,close): left_layout.addWidget(b)
        plot=QtInteractor(parent=dialog,shape=(1,2),auto_update=False); outer.addWidget(plot.interactor,1); plot.enable_custom_trackball_style(left='rotate',middle='pan',right='pan')
        state={'future':None,'generation':0,'done':-1,'result':None,'baseline':None,'meshes':[],'closing':False,'active':[],'skin':[],'applied':False}; cached={}
        colors=['#a6bcd1','#b3b9a2','#c2a9a0','#a9b3c1','#b9a6c4']
        def vals(): return {k:w.value() for k,w in controls.items()}
        def config(a): return dict(a)
        def calculate(g,c):
            start=time.perf_counter()
            if 'neutral' not in cached:
                neutral=copy.deepcopy(cfg)
                neutral.update(morphology_engine='Direct Section',amounts=dict(hips=0.,butt=0.,thighs=0.,calves=0.),direct_depth=dict(hips=0.,thighs=0.),belly_morphology=dict(amount=0.,advanced=False),waist_morphology=dict(enabled=False),inner_fill=False,surface_rounding=False,displacement_smoothing=False,advanced_clothing=False,final_regularization=dict(enabled=False),coupled_hips=False,relative_silhouette=False,legacy_hip_repair=False,surface_shading='Original')
                # Stop before any production deformation field is evaluated.
                class AnalysisComplete(Exception): pass
                data={}
                def observe(event,d):
                    if event=='before_field':
                        data.update(L=dict(d['L']),skin=list(d['SKIN']),garments=list(d['GARMENTS']),active=list(d['reference']['active']), H=float(d['H']))
                        raise AnalysisComplete()
                try: te.run(str(s.root),'dry',config_override=neutral,prepared_geometry=s.geometry,observer=observe,zero_calibration=True,positions_only=True)
                except AnalysisComplete: pass
                if not data: raise RuntimeError('Analysis did not reach before_field')
                mesh=s.root/'Meshes'; vp=mesh/'Vector.buf.orig'
                if not vp.exists(): vp=mesh/'Vector.buf'
                r=MorphologyResult(s.original_geometry.copy(),data,np.fromfile(vp,dtype=np.int8).reshape(-1,8))
                cached['neutral']=r
            original=cached['neutral']; d=original.regional_data
            mid=time.perf_counter(); base,target,ref_faces=native.generate(c)
            if 'transfer' not in cached:
                skin_ids=np.unique(np.concatenate([s.faces[n].ravel() for n in d['skin'] if n in s.faces]))
                # Only explicit roles govern eligibility. No arm protection, seam guard or height fade.
                mobility=np.zeros(len(s.original_geometry),float)
                for n in d['skin']+d['garments']:
                    if n in s.faces: mobility[s.faces[n].ravel()]=1.
                for n in s.faces:
                    if n not in d['skin']+d['garments']: mobility[s.faces[n].ravel()]=0.
                cached['transfer']=Transfer(s.original_geometry,base,d['L'],reference,skin_ids,mobility,anatomical_top=d['H'])
            elif not np.array_equal(base,cached['transfer'].base):raise RuntimeError('Neutral Anny reference changed')
            q=cached['transfer'].apply(target)
            faces=np.concatenate(list(s.faces.values()))
            a,b,e=s.original_geometry[faces].transpose(1,0,2); na=np.cross(b-a,e-a)
            a,b,e=q[faces].transpose(1,0,2); nb=np.cross(b-a,e-a)
            flipped=int(np.count_nonzero(np.einsum('ij,ij->i',na,nb)<0))
            print('Anny77 diagnostic: changed triangle orientation:',flipped,'max vertical displacement:',float(np.max(np.abs(q[:,2]-s.original_geometry[:,2]))),flush=True)
            vectors=belly_vectors(s.original_geometry,q,original.vectors,faces,'Geometric')
            result=MorphologyResult(q,d,vectors)
            if not np.isfinite(q).all():raise RuntimeError('Invalid preview')
            np.savez_compressed(refpath.parent/'latest_native_reference.npz',base=base,target=target,faces=ref_faces,values_json=json.dumps(c))
            print('Native Anny max displacement:',float(np.max(np.linalg.norm(target-base,axis=1))),flush=True)
            return g,original,result,mid-start,time.perf_counter()-mid
        def names(): return [n for n in state['active'] if n in s.faces and len(s.faces[n]) and (not skin.isChecked() or n in state['skin'])]
        def rebuild(*_):
            if state['result'] is None:return
            ns=names()
            if not ns:return
            plot.subplot(0,1); previous=plot.camera_position if state['meshes'] else None; scale=plot.camera.parallel_scale if previous else None
            plot.clear(); state['meshes']=[]
            compare=ref.currentIndex()==1
            plot.subplot(0,0); plot.renderer.SetDraw(compare); plot.renderer.SetViewport(0,0,.5,1)
            plot.subplot(0,1); plot.renderer.SetDraw(True); plot.renderer.SetViewport(.5 if compare else 0,0,1,1)
            pairs=[(0,'Original',s.original_geometry),(1,'Anny Full Body',state['result'].positions)] if compare else [(1,'Anny Full Body',state['result'].positions)]
            for col,label,q in pairs:
                plot.subplot(0,col); plot.set_background('#202733'); plot.enable_parallel_projection()
                for i,n in enumerate(ns):
                    t=s.faces[n]; ids=np.unique(t); cells=np.column_stack((np.full(len(t),3),np.searchsorted(ids,t))).ravel(); mesh=pv.PolyData(q[ids].copy(),cells)
                    plot.add_mesh(mesh,color=colors[i%len(colors)],style='wireframe' if wire.isChecked() else 'surface',smooth_shading=False,reset_camera=False); state['meshes'].append((col,mesh,ids))
                plot.add_text(label,font_size=11,color='white')
            plot.link_views(1); plot.subplot(0,1)
            if previous: plot.camera_position=previous; plot.camera.parallel_scale=scale; plot.render()
            else: camera((0,1,0))
        def camera(d):
            ns=names()
            if not ns:return
            ids=np.unique(np.concatenate([s.faces[n].ravel() for n in ns])); p=s.original_geometry[ids]; mid=(p.min(0)+p.max(0))/2; extent=max(float(np.ptp(p,axis=0).max()),1.)
            d=np.asarray(d,float); d/=np.linalg.norm(d); plot.subplot(0,1); plot.camera_position=[mid+d*extent*3,mid,(0,0,1)]; plot.camera.parallel_scale=extent*.58; plot.renderer.reset_camera_clipping_range(); plot.render()
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
                        q=s.original_geometry if col==0 else result.positions
                        mesh.points=q[ids].copy(); mesh.Modified()
                    plot.render()
                diff=float(np.max(np.linalg.norm(result.positions-base.positions,axis=1)))
                status.setText(f'Ready | Analysis {t0:.3f}s | Anny {t1:.3f}s | max movement {diff:.3f} cm'); print('Preview:',vals(),'max displacement cm:',diff,'times:',t0,t1,flush=True); apply.setEnabled(True)
            except Exception as e: status.setText('Error: '+str(e)); traceback.print_exc(); apply.setEnabled(False)
        debounce=QTimer(dialog); debounce.setSingleShot(True); debounce.setInterval(600); debounce.timeout.connect(refresh)
        poll=QTimer(dialog); poll.setInterval(75); poll.timeout.connect(poll_result)
        for w in controls.values(): w.valueChanged.connect(changed)
        def set_preset(name):
            if name=='Neutral':
                for w in controls.values(): w.setValue(0.)
                return
            for k,v in te.PRESETS[name].items():
                controls[k].setValue(v)
                if k+'_y' in controls:controls[k+'_y'].setValue(v)
        preset.currentTextChanged.connect(set_preset)
        preview.clicked.connect(refresh); reset.clicked.connect(lambda:[w.setValue(0.) for w in controls.values()]); skin.toggled.connect(rebuild); wire.toggled.connect(rebuild); ref.currentIndexChanged.connect(rebuild)
        live.toggled.connect(lambda on: debounce.start() if on else debounce.stop())
        def notify():
            marker=os.environ.get('THICC_APPLIED_MARKER')
            if marker: Path(marker).write_text(json.dumps({'experiment':77,'values':vals()}),encoding='utf-8')
        def commit():
            nonlocal expected
            if state['future'] is not None or state['done']!=state['generation'] or state['result'] is None:return
            if QMessageBox.question(dialog,'Apply experimental geometry',f'Write the displayed Anny geometry to:\n{mod}\nClose the game first. Original backups preserved. Continue?')!=QMessageBox.StandardButton.Yes:return
            try:
                r=state['result']; expected=write_buffers(mod,expected,r.positions,r.vectors); notify(); status.setText('Applied — original backups preserved.'); print('APPLIED EXPERIMENT 77:',vals(),flush=True)
            except Exception as e: QMessageBox.critical(dialog,'Apply failed',str(e)); traceback.print_exc()
        def restore_original():
            nonlocal expected
            if state['future'] is not None:return
            if not expected.get('Position.buf.orig') or not expected.get('Vector.buf.orig'): QMessageBox.information(dialog,'Restore','No original backup pair exists.'); return
            if QMessageBox.question(dialog,'Restore',f'Restore original buffers in {mod}? Close the game first.')!=QMessageBox.StandardButton.Yes:return
            try:
                mesh=mod/'Meshes'; p=np.fromfile(mesh/'Position.buf.orig',dtype='<f4').reshape(-1,3); v=np.fromfile(mesh/'Vector.buf.orig',dtype=np.int8).reshape(-1,8); expected=write_buffers(mod,expected,p,v); notify(); status.setText('Original restored.'); print('EXPERIMENT 77 RESTORED ORIGINAL',flush=True)
            except Exception as e: QMessageBox.critical(dialog,'Restore failed',str(e)); traceback.print_exc()
        apply.clicked.connect(commit); restore.clicked.connect(restore_original); close.clicked.connect(dialog.accept)
        for label,d in [('Front',(0,1,0)),('Back',(0,-1,0)),('Side',(1,0,0)),('Perspective',(1,-2,.5))]:
            b=QPushButton(label); b.clicked.connect(lambda checked=False,d=d:camera(d)); panel.addWidget(b)
        def shot():
            from datetime import datetime
            path=refpath.parent/('77_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.png'); plot.screenshot(str(path),scale=2); print('Screenshot:',path,flush=True)
        b=QPushButton('Screenshot'); b.clicked.connect(shot); panel.addWidget(b); panel.addStretch()
        try: QTimer.singleShot(0,refresh); dialog.exec()
        finally:
            debounce.stop(); poll.stop(); pool.shutdown(wait=True); native.close(); plot.close()

if __name__=='__main__':
    main(); print('===== EXPERIMENT 77 - ANNY FULL BODY WWMI COMPLETED =====',flush=True)
