"""Native Anny shape laboratory, independent of WWMI and Thicc Tool engines."""
EXPERIMENT_INFO={'description':'Standalone native Anny full body editor','objective':'Inspect native morphology without transfer or WWMI constraints','visual':'Interactive Qt / VTK','batch':False,'writes':False,'parameter_source':'current'}
import os,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def main():
    env=ROOT/'.anny77'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not env.exists(): raise RuntimeError('Run setup_anny77.bat first.')
    if Path(sys.prefix).resolve()!=env.parent.parent.resolve():
        return subprocess.call([str(env),str(Path(__file__).resolve())])
    os.environ.setdefault('QT_API','pyside6')
    import json,time,traceback
    import numpy as np
    import torch,anny,pyvista as pv
    from PySide6.QtCore import Qt,QTimer
    from PySide6.QtWidgets import (QApplication,QDialog,QHBoxLayout,QVBoxLayout,QFormLayout,QWidget,QDoubleSpinBox,QSlider,QPushButton,QCheckBox,QLabel,QComboBox,QMessageBox,QScrollArea,QLineEdit,QFileDialog)
    from pyvistaqt import QtInteractor
    from concurrent.futures import ThreadPoolExecutor
    app=QApplication.instance() or QApplication([])
    model=anny.Anny(topology='anny',rig='anny',phenotypes='all',local_changes='default').to(device='cpu',dtype=torch.float32).eval()
    phen=list(model.phenotype_labels); local=list(model.local_change_labels)
    defaults={k:.5 for k in phen}; defaults.update({k:v for k,v in {'age':.67,'gender':1.}.items() if k in phen})
    faces=model.faces.detach().cpu().numpy().astype(np.int64)
    cells=np.column_stack((np.full(len(faces),faces.shape[1]),faces)).ravel()
    def generate(p,l):
        with torch.no_grad():
            out=model(phenotype_kwargs={k:torch.tensor([v],dtype=torch.float32) for k,v in p.items()},local_changes_kwargs={k:torch.tensor([v],dtype=torch.float32) for k,v in l.items() if v!=0})
            q=out['vertices'].detach().cpu().numpy().reshape(-1,3)
        if not np.isfinite(q).all() or faces.max()>=len(q): raise ValueError('Anny returned invalid geometry')
        return q.copy()
    baseline=generate(defaults,{})
    d=QDialog(); d.setWindowTitle('77 | Anny Standalone — Native Full Body'); d.resize(1500,850)
    outer=QHBoxLayout(d); left=QWidget(); left.setMinimumWidth(420); outer.addWidget(left,0); panel=QVBoxLayout(left)
    panel.addWidget(QLabel(f'Native Anny | {len(phen)} global + {len(local)} local controls'))
    search=QLineEdit(); search.setPlaceholderText('Filter by exact target or region...'); panel.addWidget(search)
    group=QComboBox(); group.addItems(['All','Global','Torso / Waist','Hips / Glutes','Legs / Feet','Arms / Hands','Head / Neck','Other']); panel.addWidget(group)
    scroll=QScrollArea(); scroll.setWidgetResizable(True); panel.addWidget(scroll,1); body=QWidget(); scroll.setWidget(body); form=QFormLayout(body)
    controls={}; rows={}; sliders={}
    def category(k):
        if k in phen:return 'Global'
        if any(x in k for x in ('hip','buttocks','pelvis','bulge')):return 'Hips / Glutes'
        if any(x in k for x in ('leg','thigh','calf','knee','ankle','foot')):return 'Legs / Feet'
        if any(x in k for x in ('arm','hand','finger','wrist','shoulder')):return 'Arms / Hands'
        if any(x in k for x in ('torso','waist','breast','bust','stomach','chest')):return 'Torso / Waist'
        if any(x in k for x in ('head','neck','eye','nose','mouth','ear','chin','cheek','forehead','lip')):return 'Head / Neck'
        return 'Other'
    for k in phen+local:
        row=QWidget(); h=QHBoxLayout(row); h.setContentsMargins(0,0,0,0); sl=QSlider(Qt.Orientation.Horizontal); sp=QDoubleSpinBox(); sp.setDecimals(3); sp.setSingleStep(.05)
        sl.setRange(0,1000) if k in phen else sl.setRange(-5000,5000)
        sp.setRange(0,1) if k in phen else sp.setRange(-100,100)
        sp.setValue(defaults.get(k,0)); sl.setValue(round(sp.value()*1000)); h.addWidget(sl,1); h.addWidget(sp)
        def sync(v,s=sl):
            s.blockSignals(True); s.setValue(round(v*1000)); s.blockSignals(False)
        sp.valueChanged.connect(sync); sl.valueChanged.connect(lambda v,s=sp:s.setValue(v/1000))
        label=QLabel(k); label.setWordWrap(True); form.addRow(label,row); controls[k]=sp; rows[k]=(label,row); sliders[k]=sl
    def filter_rows(*_):
        for k,(label,row) in rows.items():
            show=(group.currentText()=='All' or group.currentText()==category(k)) and search.text().lower() in k.lower(); label.setVisible(show); row.setVisible(show)
    group.currentTextChanged.connect(filter_rows); search.textChanged.connect(filter_rows)
    compare=QCheckBox('Compare neutral reference'); wire=QCheckBox('Wireframe'); live=QCheckBox('Live Preview'); live.setChecked(True)
    for w in (compare,wire,live):panel.addWidget(w)
    status=QLabel('Ready'); status.setWordWrap(True); panel.addWidget(status)
    plot=QtInteractor(parent=d,shape=(1,2),auto_update=False); outer.addWidget(plot.interactor,1)
    pool=ThreadPoolExecutor(max_workers=1); state={'q':baseline,'future':None,'dirty':False,'revision':0,'shown':-1,'params':None,'closing':False,'camera':None}
    def values():return ({k:controls[k].value() for k in phen},{k:controls[k].value() for k in local})
    def render(*_):
        plot.subplot(0,1); cam=plot.camera_position if state['camera'] else None; scale=plot.camera.parallel_scale if cam else None
        plot.clear(); c=compare.isChecked()
        for i,q,title in ([(0,baseline,'Neutral Anny'),(1,state['q'],'Native Anny')] if c else [(1,state['q'],'Native Anny')]):
            plot.subplot(0,i); plot.renderer.SetDraw(True); plot.renderer.SetViewport((i*.5 if c else 0),0,((i+1)*.5 if c else 1),1); plot.set_background('#202733'); plot.enable_parallel_projection(); plot.add_mesh(pv.PolyData(q,cells),color='#a6bcd1',style='wireframe' if wire.isChecked() else 'surface',smooth_shading=False); plot.add_text(title,font_size=12)
            if cam:plot.camera_position=cam; plot.camera.parallel_scale=scale
            else:plot.view_xz(); plot.reset_camera()
        if not c:plot.subplot(0,0); plot.renderer.SetDraw(False)
        else:plot.link_views()
        plot.subplot(0,1); state['camera']=True; plot.render()
    def calculate(p,l,rev):
        t=time.perf_counter(); q=generate(p,l); return q,p,l,rev,time.perf_counter()-t
    def start():
        if state['closing']:return
        if state['future'] is not None:state['dirty']=True;return
        p,l=values(); state['dirty']=False; state['future']=pool.submit(calculate,p,l,state['revision']); status.setText('Working...')
    debounce=QTimer(d); debounce.setSingleShot(True); debounce.timeout.connect(start)
    def changed(*_):
        state['revision']+=1
        if live.isChecked():debounce.start(600)
        else:status.setText('Parameters changed — Preview required')
    for sp in controls.values():sp.valueChanged.connect(changed)
    def poll():
        f=state['future']
        if f is None or not f.done():return
        state['future']=None
        try:
            q,p,l,rev,elapsed=f.result()
            if rev==state['revision']:
                state.update(q=q,params=(p,l),shown=rev); render(); status.setText(f'Finished | {elapsed:.3f}s | {len(q)} vertices'); print(f'Experiment 77 native preview: {elapsed:.3f}s',flush=True)
        except Exception as e:traceback.print_exc(); status.setText('Error: '+str(e))
        if state['dirty'] or (live.isChecked() and state['shown']!=state['revision'] and debounce.isActive()):
            if not debounce.isActive():start()
    timer=QTimer(d); timer.timeout.connect(poll); timer.start(100)
    def button(label,fn):
        b=QPushButton(label); b.clicked.connect(lambda _:fn()); panel.addWidget(b)
    def reset():
        for k,sp in controls.items():sp.setValue(defaults.get(k,0))
        debounce.stop();start()
    def export():
        if state['shown']!=state['revision'] or state['params'] is None: QMessageBox.warning(d,'Preview required','Preview current parameters before exporting.');return
        path,_=QFileDialog.getSaveFileName(d,'Export native Anny mesh',str(ROOT/'anny77.obj'),'OBJ (*.obj)')
        if not path:return
        path=Path(path).with_suffix('.obj'); p,l=state['params']; pv.PolyData(state['q'],cells).save(str(path)); path.with_suffix('.json').write_text(json.dumps({'phenotypes':p,'local_changes':l},indent=2),encoding='utf-8'); status.setText('Exported '+str(path))
    def load():
        path,_=QFileDialog.getOpenFileName(d,'Load parameters','','JSON (*.json)')
        if not path:return
        try:
            data=json.loads(Path(path).read_text()); v={**data['phenotypes'],**data['local_changes']}
            for k,sp in controls.items():sp.setValue(float(v.get(k,defaults.get(k,0))))
            debounce.stop();start()
        except Exception as e:QMessageBox.warning(d,'Load failed',str(e))
    def view(name):
        plot.subplot(0,1); getattr(plot,name)(); plot.render()
    def screenshot():
        path,_=QFileDialog.getSaveFileName(d,'Screenshot','','PNG (*.png)')
        if path:plot.screenshot(path)
    button('Preview',start); button('Reset all',reset); button('Load parameters',load); button('Export native OBJ + parameters',export)
    for label,method in [('Front','view_xz'),('Back','view_xz'),('Side','view_yz'),('Perspective','view_isometric')]:
        if label=='Back':button(label,lambda: (plot.subplot(0,1),plot.view_xz(negative=True),plot.render()))
        else:button(label,lambda m=method:view(m))
    button('Screenshot',screenshot); button('Close',d.accept)
    compare.toggled.connect(render); wire.toggled.connect(render); live.toggled.connect(lambda v: debounce.start(600) if v else debounce.stop())
    render(); start()
    try:d.exec()
    finally:
        state['closing']=True; timer.stop(); debounce.stop(); pool.shutdown(wait=True,cancel_futures=True); plot.close()
    print('EXPERIMENT 77 - ANNY STANDALONE COMPLETED',flush=True)
    return 0
if __name__=='__main__':sys.exit(main())
