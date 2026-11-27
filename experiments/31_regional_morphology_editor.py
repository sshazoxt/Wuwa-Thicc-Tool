
EXPERIMENT_INFO = {'description': 'Interactive regional morphology editor.', 'objective': 'Adjust experimental fields and inspect previews.', 'visual': 'Interactive viewer', 'batch': False, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

from _refinement_lab import *

def main():
    from PySide6.QtWidgets import QApplication,QDialog,QFormLayout,QDoubleSpinBox,QPushButton,QComboBox,QLabel,QCheckBox
    app=QApplication.instance() or QApplication([])
    with PreviewSession(os.environ['THICC_MOD_DIR']) as s:
        base,r,c,v=setup(s,2.5); dialog=QDialog(); dialog.setWindowTitle('31 | Regional Morphology Lab'); layout=QFormLayout(dialog); controls={}
        specs=[('Waist width',.82,.5,1.5),('Waist depth',.95,.5,1.5),('Waist height',1,.4,1.6),('Waist offset',0,-.18,.08),('Belly depth',.35,0,1),('Belly width',1,.5,2),('Belly height',1,.5,1.5),('Belly offset',0,-.15,.1),('Glutes X',.3,0,.8),('Glutes Y',.4,0,.8),('Glutes Z',0,0,.8),('Volume height',1,.6,1.6),('Thighs X',.3,0,.7),('Thighs Y',.2,0,.7)]
        for name,val,lo,hi in specs:
            w=QDoubleSpinBox(); w.setRange(lo,hi); w.setDecimals(2); w.setSingleStep(.05); w.setValue(val); controls[name]=w; layout.addRow(name,w)
        mode=QComboBox(); mode.addItems(['Volume height','Vertex height']); layout.addRow('Glute method',mode)
        focus=QComboBox(); focus.addItems(['torso','pelvis','legs','full']); layout.addRow('Focus',focus)
        skin=QCheckBox('Skin only'); skin.setChecked(True); layout.addRow(skin)
        status=QLabel('Read-only preview; Hips baseline 2.5'); status.setWordWrap(True); layout.addRow(status)
        preview=QPushButton('Preview'); reset=QPushButton('Reset'); layout.addRow(preview,reset)
        def run():
            a=lambda k:controls[k].value()
            try:
                fields={'Waist':c.waist(a('Waist width'),a('Waist depth'),a('Waist height'),a('Waist offset')),'Belly':c.belly(a('Belly depth'),a('Belly width'),a('Belly height'),a('Belly offset')),'Thighs':r.thighs(a('Thighs X'),a('Thighs Y'))}
                if mode.currentIndex()==0:
                    fields['Glutes X']=c.glute_volume(a('Glutes X'),0,a('Volume height')); fields['Glutes Y']=c.glute_volume(0,a('Glutes Y'),a('Volume height'))
                else:
                    for key,xyz in [('X',(a('Glutes X'),0,0)),('Y',(0,a('Glutes Y'),0)),('Z',(0,0,a('Glutes Z')))]: fields['Glutes '+key]=r.glutes(*xyz)
                q,f,_=v.compose(fields); status.setText('Accepted: '+str(f)); show(s,r,[('Hips baseline',base.positions),('Edited',q)],'31 | Regional Morphology Lab',focus=focus.currentText(),skin=skin.isChecked())
            except Exception as exc:
                status.setText(str(exc)); print('Preview error:',exc,flush=True)
        def restore():
            for name,val,*_ in specs: controls[name].setValue(val)
        preview.clicked.connect(run); reset.clicked.connect(restore); dialog.exec()
if __name__=='__main__':
    main(); print('===== EXPERIMENT 31 - REGIONAL MORPHOLOGY EDITOR FINISHED =====',flush=True)
