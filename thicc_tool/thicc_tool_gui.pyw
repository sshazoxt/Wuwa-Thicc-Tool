#! python3.10
from html import escape
import codecs,os,sys,json,subprocess,tempfile,pickle,time,shutil,traceback,struct,importlib
from pathlib import Path
os.environ['QT_API']='pyside6'
from PySide6.QtCore import Qt,QTimer,QUrl,QItemSelectionModel
from PySide6.QtGui import QDesktopServices,QColor,QTextCursor
from PySide6.QtWidgets import *
HERE=os.path.dirname(os.path.abspath(__file__))
from anatomical_reconstruction import FULL_BODY
sys.path.insert(0,HERE)
class FocusWheelCombo(QComboBox):
    def wheelEvent(self, event):
        if self.hasFocus(): super().wheelEvent(event)
        else: event.ignore()

class FocusWheelSlider(QSlider):
    def wheelEvent(self, event):
        if self.hasFocus(): super().wheelEvent(event)
        else: event.ignore()

class FocusWheelSpin(QDoubleSpinBox):
    def wheelEvent(self, event):
        if self.hasFocus(): super().wheelEvent(event)
        else: event.ignore()

class Messages:
    def showwarning(self,t,m): QMessageBox.warning(QApplication.activeWindow(),t,m)
    def showinfo(self,t,m): QMessageBox.information(QApplication.activeWindow(),t,m)
    def showerror(self,t,m): QMessageBox.critical(QApplication.activeWindow(),t,m)
    def askyesno(self,t,m): return QMessageBox.question(QApplication.activeWindow(),t,m)==QMessageBox.StandardButton.Yes
messagebox=Messages()
class Var:
    def __init__(self,w): self.w=w
    def get(self):
        w=self.w
        if isinstance(w,QLineEdit): return w.text()
        if isinstance(w,QComboBox): return w.currentText()
        if isinstance(w,QCheckBox): return w.isChecked()
        return w.value()
    def set(self,v):
        w=self.w
        if isinstance(w,QLineEdit): w.setText(str(v))
        elif isinstance(w,QComboBox): w.setCurrentText(str(v))
        elif isinstance(w,QCheckBox): w.setChecked(bool(v))
        else: w.setValue(float(v))
class Label(QLabel):
    def config(self,**kw):
        if 'text' in kw: self.setText(kw['text'])
        if 'foreground' in kw: self.setStyleSheet('color:'+kw['foreground'])
class Table(QTableWidget):
    keys=['name','label','visibility','role','anatomy','region','zmin','zmax','verts']
    def __init__(self):
        super().__init__(0,9); self.setHorizontalHeaderLabels(['Part','Label','Status','Role','Anatomy','Region','Z min','Z max','Vertices']); self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.verticalHeader().hide(); self.setAlternatingRowColors(True); self.setShowGrid(False); self.verticalHeader().setDefaultSectionSize(34); self.setColumnWidth(0,230); self.setColumnWidth(1,130); self.setColumnWidth(2,86); self.setColumnWidth(3,92); self.setColumnWidth(4,78); self.dark=True; self.setMouseTracking(True)
    def mousePressEvent(self, event):
        # Explicit Ctrl+click toggle; leave Shift and ordinary selection to Qt.
        if (event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() == Qt.KeyboardModifier.ControlModifier):
            index = self.indexAt(event.position().toPoint())
            if index.isValid():
                self._ctrl_row_press = True
                model = self.selectionModel()
                flags = QItemSelectionModel.SelectionFlag
                model.setCurrentIndex(index, flags.NoUpdate)
                model.select(index, flags.Toggle | flags.Rows)
                event.accept()
                return
        self._ctrl_row_press = False
        super().mousePressEvent(event)
    def mouseReleaseEvent(self, event):
        if getattr(self, '_ctrl_row_press', False) and event.button() == Qt.MouseButton.LeftButton:
            self._ctrl_row_press = False
            event.accept()
            return
        super().mouseReleaseEvent(event)
    def mouseDoubleClickEvent(self, event):
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
    def selection(self): return sorted({i.row() for i in self.selectedIndexes()})
    def get_children(self): return list(range(self.rowCount()))
    def delete(self,*a): self.setRowCount(0)
    def insert(self,*a,text,values,tags):
        r=self.rowCount(); self.insertRow(r)
        for c,v in enumerate((text,*values)): self.setItem(r,c,QTableWidgetItem(str(v)))
        self.item(r,tags=tags)
    def item(self,r,which=None,tags=None):
        if which=='text': return super().item(r,0).text()
        if tags:
            color=({'skin':'#a8d5aa','garment':'#a9c7ec','frozen':'#b1b1b8'} if self.dark else {'skin':'#237047','garment':'#315f91','frozen':'#66666f'})[tags[0]]; item=super().item(r,3); item.setForeground(QColor(color)); font=item.font(); font.setBold(True); item.setFont(font); return
        return super().item(r,which)
    def set(self,r,key,*value):
        i=super().item(r,self.keys.index(key))
        if value: i.setText(str(value[0]))
        return i.text()
ROLES = {"skin": "Skin", "garment": "Clothing", "frozen": "Frozen"}
ROLE_KEYS = {v: k for k, v in ROLES.items()}
SLIDERS = [("butt", "Glutes"), ("hips", "Hips"), ("thighs", "Thighs"), ("calves", "Calves")]
LANDMARKS = [("ankle", "Ankle"), ("knee", "Knee"), ("crotch", "Crotch"),
             ("apex", "Glute apex"), ("waist", "Waist"), ("hip_half", "Hip half-width"),
             ("cy", "Pelvis center (y)")]
BOUNCE_LABELS = {"normal": "Normal", "soft": "Soft", "medium": "Medium", "extra": "Extra"}
SETTINGS = os.path.join(HERE, "thicc_tool_settings.json")


ABOUT = """Author: sshazoxt
Indirect co-author / original script: Voidflaq

Geometry editor for Wuthering Waves mods.
Automatic classification is experimental; manual corrections take priority."""
MANUAL = """THICC TOOL — USER MANUAL

Select a mod folder containing its INI and Meshes. Click Analyze.
Skin deforms; Clothing follows the body; Frozen remains unchanged.
Anatomy is independent of role and visibility. Correct roles manually, then Save and analyze.
Double-click Part to view its geometry; double-click Label to rename a part. Show / hide changes the INI; refresh the game with F10.
Select parts and click View 3D geometry to inspect them. Ctrl+click toggles individual rows; Shift+click selects a range. Left drag rotates, right drag pans, and the wheel zooms. Screenshot saves a high-resolution PNG.
Preview computes deformation without replacing geometry buffers. Apply writes buffers; Restore recovers .orig geometry, not the INI.
1.0 is the base contribution; 0 disables that contribution. Blank measurements are automatic. Only Normal bounce is implemented.
Library stores folder references, not copies. Analyze library runs diagnostics sequentially with each mod's saved settings. Cancel stops the batch; completed logs remain.
Keep backups of your mods."""

class App(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Thicc Tool — WWMI | 2.2.6 · ARF diagnostic'); self.resize(1500,900); self.setMinimumSize(1000,650)
        self.preview_positions=None; self.busy=False; self.job=None; self.analysis=None; self.analyzed_mod=None; self.anatomy=set(); self.auto_lm={}; self.pending_mod=None; self.plot=None; self._populate_viewer=None; self._viewer_has_geometry=False; self._closing=False; self.library=[]; self.batch=None; self.library_last_dir=""
        self._build(); self._load_settings()
    def _build(self):
        root=QWidget(); self.setCentralWidget(root); self.main=root; l=QVBoxLayout(root); l.setContentsMargins(16,12,16,12); l.setSpacing(10)
        def button(layout,text,fn):
            b=QPushButton(text); b.clicked.connect(lambda checked=False:fn()); layout.addWidget(b); return b
        def combo(items):
            w=FocusWheelCombo(); w.setFocusPolicy(Qt.FocusPolicy.StrongFocus); w.addItems(list(items)); return Var(w)
        def check(text,value=False):
            w=QCheckBox(text); w.setChecked(value); return Var(w)
        header=QHBoxLayout(); l.addLayout(header); title=QLabel('Thicc Tool'); title.setObjectName('heading'); header.addWidget(title); header.addWidget(QLabel('Morphology editor · WWMI')); header.addStretch(); self.theme=combo(['Dark','Light']); header.addWidget(self.theme.w); self.theme.w.currentTextChanged.connect(self.set_theme)
        bar=QHBoxLayout(); l.addLayout(bar); self.mod=Var(QLineEdit()); self.mod.w.setPlaceholderText('Mod folder'); bar.addWidget(self.mod.w,1); button(bar,'Browse…',self.pick); self.analyze_btn=QToolButton(); self.analyze_btn.setText('Analyze'); self.analyze_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup); self.analyze_btn.clicked.connect(lambda checked=False:self.analyze()); am=QMenu(self.analyze_btn); am.addAction('Force analyze',lambda:self.analyze(force=True)); am.addSeparator(); am.addAction('Analyze library',lambda:self.analyze_library()); am.addAction('Force analyze library',lambda:self.analyze_library(force=True)); self.analyze_btn.setMenu(am); bar.addWidget(self.analyze_btn); button(bar,'Library',self.manage_library); button(bar,'Open folder',self.open_folder)
        vertical=QSplitter(Qt.Orientation.Vertical); l.addWidget(vertical,1); split=QSplitter(Qt.Orientation.Horizontal); vertical.addWidget(split)
        left=QWidget(); left.setObjectName("workspacePanel"); ll=QVBoxLayout(left); ll.setContentsMargins(12,12,12,12); ll.setSpacing(8); split.addWidget(left); wardrobe_title=QLabel("Wardrobe"); wardrobe_title.setObjectName("sectionHeading"); ll.addWidget(wardrobe_title)
        warning=QLabel('Weighted automatic classification (002). Hover over Role for score and evidence; review in 3D.'); warning.setWordWrap(True); warning.setObjectName('warning'); ll.addWidget(warning)
        self.cache_note=QLabel(''); self.cache_note.setWordWrap(True); self.cache_note.hide(); ll.addWidget(self.cache_note); self.mod.w.textChanged.connect(lambda _:self.cache_note.hide())
        self.tree=Table(); ll.addWidget(self.tree,1); self.tree.cellDoubleClicked.connect(self.part_double_clicked); self.tree.horizontalHeaderItem(0).setToolTip("Double-click a Part to view its geometry"); self.tree.horizontalHeaderItem(1).setToolTip("Double-click a Label to rename it")
        row=QHBoxLayout(); ll.addLayout(row)
        for k in ROLES: button(row,ROLES[k],lambda k=k:self.set_role(k))
        button(row,'Show / hide',self.toggle_visibility)
        row=QHBoxLayout(); ll.addLayout(row); button(row,'+ Anatomy',lambda:self.set_anatomy(True)); button(row,'− Anatomy',lambda:self.set_anatomy(False)); button(row,'Save and analyze',self.save_anatomy); button(row,'Reset automatic',self.reset_auto)
        center=QWidget(); center.setObjectName("workspacePanel"); cl=QVBoxLayout(center); cl.setContentsMargins(12,12,12,12); split.addWidget(center); viewer_title=QLabel("3D Viewer · Selected parts"); viewer_title.setObjectName("sectionHeading"); cl.addWidget(viewer_title)
        row=QHBoxLayout(); cl.addLayout(row); self.viewer_mode=combo(['Current','Original','Preview','Comparison','Displacement']); row.addWidget(self.viewer_mode.w); self.wire=check('Wireframe'); row.addWidget(self.wire.w); button(row,'View 3D geometry',self.view3d).setObjectName('primary')
        self.viewer_status=QLabel("3D engine: starting…"); self.viewer_status.setWordWrap(True); cl.addWidget(self.viewer_status)
        self.viewhost=QFrame(); self.viewhost.setObjectName("viewerHost"); self.viewlayout=QVBoxLayout(self.viewhost); self.viewlayout.setContentsMargins(0,0,0,0); self.placeholder=QLabel('Analyze a mod and select one or more parts.'); self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter); self.placeholder.setWordWrap(True); self.viewlayout.addWidget(self.placeholder,1); cl.addWidget(self.viewhost,1)
        row=QHBoxLayout(); cl.addLayout(row); button(row,'Front',lambda:self.camera('xz')); button(row,'Side',lambda:self.camera('yz')); button(row,'Perspective',lambda:self.camera('iso')); button(row,'Fit',lambda:self.camera('fit')); button(row,'Screenshot',self.viewer_screenshot).setToolTip('Save a high-resolution PNG of the current 3D view.')
        right=QTabWidget(); right.setObjectName("inspector"); split.addWidget(right); shape=QWidget(); sh=QVBoxLayout(shape); sh.setContentsMargins(12,12,12,12); sh.setSpacing(8); scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame); scroll.setWidget(shape); right.addTab(scroll,'Morphology'); self.preset=combo(te.PRESETS); self.preset.set('pear'); sh.addWidget(QLabel('Base shape')); sh.addWidget(self.preset.w); self.preset.w.currentTextChanged.connect(lambda _:self.apply_preset()); self.amount={}
        for k,t in SLIDERS:
            sh.addWidget(QLabel(t)); row=QHBoxLayout(); sh.addLayout(row); slider=FocusWheelSlider(Qt.Orientation.Horizontal); slider.setFocusPolicy(Qt.FocusPolicy.StrongFocus); slider.setRange(0,500 if k=='hips' else 200); spin=FocusWheelSpin(); spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus); spin.setRange(0,5 if k=='hips' else 2); spin.setDecimals(2); spin.setSingleStep(.05); spin.setValue(1); slider.setValue(100); slider.valueChanged.connect(lambda v,s=spin:s.setValue(v/100)); spin.valueChanged.connect(lambda v,s=slider:s.setValue(round(v*100))); row.addWidget(slider,1); row.addWidget(spin); self.amount[k]=Var(spin)
        self.waist_group=QGroupBox('Waist morphology (experimental)'); self.waist_group.setCheckable(True); self.waist_group.setChecked(False)
        wl=QFormLayout(self.waist_group); self.waist_controls={}
        for key,label in [('width','Waist width'),('depth','Waist depth')]:
            spin=FocusWheelSpin(); spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus); spin.setRange(.60,1.50); spin.setDecimals(2); spin.setSingleStep(.05); spin.setValue(1.); wl.addRow(label,spin); self.waist_controls[key]=Var(spin)
        sh.addWidget(self.waist_group)
        self.relative_silhouette=check('Relative silhouette calibration (experimental)'); sh.addWidget(self.relative_silhouette.w)
        row=QHBoxLayout(); sh.addLayout(row); row.addWidget(QLabel('Target strength')); spin=FocusWheelSpin(); spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus); spin.setRange(0,2); spin.setDecimals(2); spin.setSingleStep(.1); spin.setValue(1); row.addWidget(spin); self.silhouette_strength=Var(spin)
        profile=QGroupBox('Coupled hip-thigh profile (experimental)'); profile.setCheckable(True); profile.setChecked(False)
        self.hip_profile_group=profile; self.hip_profile={}; pl=QFormLayout(profile)
        for key,label,lo,hi,default in [('upper','Upper spread',.5,2.5,1.4),('lower','Lower spread',.5,2.5,1.65),('peak','Peak height offset',-.3,.3,0.)]:
            spin=FocusWheelSpin(); spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus); spin.setRange(lo,hi); spin.setDecimals(2); spin.setSingleStep(.05); spin.setValue(default); pl.addRow(label,spin); self.hip_profile[key]=Var(spin)
        sh.addWidget(profile)
        self.direction = {}
        directional = QGroupBox('Directional expansion (experimental)'); directional.setCheckable(True); directional.setChecked(False)
        dl=QGridLayout(directional); dl.addWidget(QLabel('Region'),0,0); dl.addWidget(QLabel('X · Width'),0,1); dl.addWidget(QLabel('Y · Depth'),0,2)
        for i,(key,label) in enumerate(SLIDERS,1):
            dl.addWidget(QLabel(label),i,0); pair=[]
            for j in (1,2):
                spin=FocusWheelSpin(); spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus); spin.setRange(0,2); spin.setDecimals(2); spin.setSingleStep(.1); spin.setValue(1); dl.addWidget(spin,i,j); pair.append(Var(spin))
            self.direction[key]=pair
        self.direction_group=directional; sh.addWidget(directional)
        note=QLabel('1 = unchanged; 0 = no contribution on that axis. Groin fill remains independent. Non-neutral settings skip thigh rounding.'); note.setWordWrap(True); sh.addWidget(note)
        self.arm_protection=check("Advanced arm protection (experimental)"); sh.addWidget(self.arm_protection.w)
        self.advanced_clothing=check("Advanced clothing adaptation (experimental)"); sh.addWidget(self.advanced_clothing.w)
        self.inner=check('Fill inner thigh gap'); self.virtual=check('Morphological groin fold',True); self.rounding=check('Thigh rounding',True)
        sh.addWidget(self.inner.w); self.inner.w.setToolTip("Uses the rounded inner-knee transition.")
        for v in (self.virtual,self.rounding): sh.addWidget(v.w)
        sh.addWidget(QLabel('1.0 = base contribution · 0 = no contribution')); self.bounce=combo(BOUNCE_LABELS.values()); sh.addWidget(QLabel('Bounce · only Normal available')); sh.addWidget(self.bounce.w); self.shading=combo(['Original','Adaptive','Legacy','Geometric']); sh.addWidget(QLabel('Surface shading')); sh.addWidget(self.shading.w); self.field_mode=combo(['Legacy','Continuous']); sh.addWidget(QLabel('Deformation field')); sh.addWidget(self.field_mode.w); self.taubin=check("Taubin displacement smoothing (experimental)"); sh.addWidget(self.taubin.w)
        self.final_reg_group=QGroupBox('Final morphological regularization (experimental)'); self.final_reg_group.setCheckable(True); self.final_reg_group.setChecked(False)
        rl=QFormLayout(self.final_reg_group); self.final_reg_controls={}
        for key,label,default in [('strength','Strength',0.35),('tolerance','Noise tolerance',0.20)]:
            spin=FocusWheelSpin(); spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus); spin.setRange(0,1); spin.setDecimals(2); spin.setSingleStep(.05); spin.setValue(default)
            rl.addRow(label,spin); self.final_reg_controls[key]=Var(spin)
        sh.addWidget(self.final_reg_group); sh.addStretch(); actions=QWidget(); al=QVBoxLayout(actions); al.setContentsMargins(0,0,0,0); al.setSpacing(5); sh.addWidget(actions); button(al,'Preview (no buffer writes)',self.preview); button(al,'Apply to mod',self.apply).setObjectName('primary'); button(al,'Restore original',self.restore);
        for b in actions.findChildren(QPushButton): b.setMinimumHeight(32); b.setStyleSheet('font-size: 12px; padding: 4px 6px;')
        measures=QWidget(); ml=QFormLayout(measures); right.addTab(measures,'Measurements'); self.lm={}
        for k,t in LANDMARKS: self.lm[k]=Var(QLineEdit()); self.lm[k].w.setPlaceholderText('Automatic'); ml.addRow(t,self.lm[k].w)
        self.warn=Label(''); self.warn.setWordWrap(True); ml.addRow(self.warn); split.setSizes([520,590,330]); right.setMinimumWidth(275)
        logbox=QWidget(); logbox.setObjectName("workspacePanel"); logl=QVBoxLayout(logbox); logl.setContentsMargins(12,8,12,10); row=QHBoxLayout(); logl.addLayout(row); log_title=QLabel('Diagnostic log'); log_title.setObjectName('sectionHeading'); row.addWidget(log_title); row.addStretch(); button(row,'Copy',lambda:QApplication.clipboard().setText(self.log.toPlainText())); button(row,'Clear',lambda:self.log.clear()); button(row,'Experiments',self.run_experiment); self.log=QPlainTextEdit(); self.log.setObjectName('diagnosticLog'); self.log.setReadOnly(True); logl.addWidget(self.log); vertical.addWidget(logbox); vertical.setSizes([650,180]); self.status=Label('Select a WWMI mod folder.'); self.status.setObjectName('footer'); l.addWidget(self.status)
        for title,items in [('File',[('Browse folder',self.pick),('Open folder',self.open_folder),('Exit',self.close)]),('Tools',[('Analyze',self.analyze),('Show / hide',self.toggle_visibility)]),('Help',[('Manual',self.manual),('About',self.about)])]:
            menu=self.menuBar().addMenu(title)
            for text,fn in items: menu.addAction(text,fn)
        self.set_theme('Dark')
    def set_theme(self,mode):
        dark=mode=='Dark'
        bg,panel,field,alt,edge,fg,muted,hover,selected,accent = (
            ('#171717','#222222','#292929','#252525','#3c3c3c','#ededed','#a7a7a7','#343434','#37475a','#8db7e8') if dark else
            ('#f0f1f3','#ffffff','#f7f7f8','#fafafa','#d5d8dd','#24262a','#666b73','#e9edf2','#dce9fa','#3069a6'))
        self.tree.dark=dark
        self.setStyleSheet(f"""
            QWidget {{background:{bg};color:{fg};font-family:'Segoe UI';font-size:13px;}}
            QWidget#workspacePanel,QTabWidget::pane {{background:{panel};border:1px solid {edge};border-radius:10px;}}
            QLabel,QCheckBox {{background:transparent;}}
            QLabel#heading {{font-size:28px;font-weight:700;}}
            QLabel#sectionHeading {{font-size:15px;font-weight:700;padding:2px 0 5px;}}
            QLabel#warning {{color:{'#dfb77c' if dark else '#80531b'};font-size:12px;padding:3px 0;}}
            QLabel#footer {{color:{muted};font-size:12px;padding:5px 2px;}}
            QLineEdit,QPlainTextEdit,QComboBox,QDoubleSpinBox {{background:{field};border:1px solid {edge};border-radius:6px;padding:5px 8px;}}
            QLineEdit:focus,QComboBox:focus,QDoubleSpinBox:focus {{border-color:{accent};}}
            QTableWidget {{background:{panel};alternate-background-color:{alt};border:1px solid {edge};border-radius:7px;selection-background-color:{selected};selection-color:{fg};outline:0;}}
            QTableWidget::item {{padding:5px 8px;border-bottom:1px solid {edge};}}
            QTableWidget::item:hover:!selected {{background:{hover};}}
            QHeaderView::section {{background:{hover};color:{muted};font-weight:600;padding:9px 8px;border:0;border-bottom:1px solid {edge};}}
            QPushButton,QToolButton {{background:{field};border:1px solid {edge};border-radius:7px;padding:7px 10px;}}
            QPushButton:hover,QToolButton:hover {{background:{hover};border-color:{accent};}}
            QPushButton:pressed,QToolButton:pressed {{background:{selected};border-color:{accent};}}
            QPushButton#primary {{background:#396ca5;color:white;border-color:#507eaf;font-weight:600;}}
            QPushButton#primary:hover {{background:#487eb9;}}
            QPushButton#primary:pressed {{background:#2d537f;}}
            QPushButton:disabled,QToolButton:disabled {{color:{muted};background:{panel};border-color:{edge};}}
            QToolButton {{padding-right:24px;}}
            QToolButton::menu-button {{width:18px;border-left:1px solid {edge};}}
            QToolButton::menu-arrow {{width:8px;height:8px;}}
            QTabBar::tab {{background:{panel};color:{muted};padding:10px 12px;border-bottom:2px solid transparent;}}
            QTabBar::tab:selected {{color:{fg};border-bottom:2px solid {accent};font-weight:600;}}
            QGroupBox {{border:1px solid {edge};border-radius:7px;margin-top:15px;padding:12px 8px 8px;}}
            QGroupBox::title {{subcontrol-origin:margin;subcontrol-position:top left;left:9px;padding:0 4px;color:{fg};}}
            QSplitter::handle {{background:{bg};width:7px;height:7px;}}
            QFrame#viewerHost {{background:{panel};border:1px solid {edge};border-radius:7px;}}
            QPlainTextEdit#diagnosticLog {{font-family:Consolas,monospace;font-size:12px;background:{field};}}
            QScrollBar:vertical {{background:{panel};width:11px;margin:0;}}
            QScrollBar:horizontal {{background:{panel};height:11px;margin:0;}}
            QScrollBar::handle {{background:{edge};border-radius:5px;min-height:24px;min-width:24px;}}
            QScrollBar::handle:hover {{background:{muted};}}
            QScrollBar::add-line,QScrollBar::sub-line {{width:0;height:0;}}
            QScrollBar::add-page,QScrollBar::sub-page {{background:transparent;}}
            QSlider::groove:horizontal {{height:5px;background:{edge};border-radius:2px;}}
            QSlider::handle:horizontal {{background:{accent};width:14px;margin:-5px 0;border-radius:7px;}}
            QSlider::sub-page:horizontal {{background:{accent};border-radius:2px;}}
            QProgressBar {{border:1px solid {edge};border-radius:5px;}}
            QProgressBar::chunk {{background:{accent};}}
            QToolTip {{background:{hover};color:{fg};border:1px solid {edge};padding:9px;}}
            QMenu {{background:{panel};border:1px solid {edge};padding:4px;}}
            QMenu::item:selected {{background:{selected};}}
        """)
        for row in self.tree.get_children():
            role=ROLE_KEYS.get(self.tree.set(row,'role'))
            if role: self.tree.item(row,tags=(role,))
            self.refresh_role_tooltip(row)

    def refresh_role_tooltip(self,row):
        if not self.analysis: return
        name=self.tree.item(row,'text')
        ev=self.analysis.get('role_evidence',{}).get(name,{})
        if not ev: return
        dark=self.tree.dark
        fg='#eeeeee' if dark else '#24262a'
        muted='#b7b7b7' if dark else '#666b73'
        good='#b4d9b6' if dark else '#237047'
        bad='#e8a5a5' if dark else '#a32d2d'
        effective=ROLE_KEYS.get(self.tree.set(row,'role'),self.tree.set(row,'role'))
        parts=[f'<b>{escape(name)}</b>', f'Auto: {escape(str(ev.get("role")))} &nbsp; | &nbsp; Effective: {escape(effective)}']
        if name in self.analysis.get('arf_recovered', []):
            parts.append('ARF: lower-body recovery (original weighted score unchanged).')
        score=ev.get('score')
        if score is not None:
            parts.append(f'<b>Score: {score:+.1f} / 100</b> &nbsp; | &nbsp; Coverage: {100*ev.get("coverage",0):.0f}%')
            rows=[]
            labels={'surface':'Surface','stickman':'Stickman','welded':'Welded','shape':'Shape','height':'Height','naming':'Naming','topology':'Topology','vertices':'Vertices'}
            for k,v in ev.get('contributions',{}).items():
                color=muted if v is None or v==0 else good if v>0 else bad
                value='N/D' if v is None else f'{v:+.1f}'
                rows.append(f'<tr><td width="155" style="color:{muted}">{escape(labels.get(k,k))}</td><td align="right" width="65" style="color:{color}">{value}</td></tr>')
            parts.append('<hr><table cellspacing="4" cellpadding="1">'+''.join(rows)+'</table>')
            parts.append(f'<span style="color:{muted}">Surface reference: {escape(str(ev.get("surface_source")))}</span>')
        elif ev.get('fixed'):
            parts.append('Fixed component rule (manual role still overrides).')
        self.tree.item(row,3).setToolTip(f'<div style="color:{fg};white-space:pre-wrap">'+ '<br>'.join(parts)+'</div>')

    def part_double_clicked(self,row,col):
        if self.busy: return
        if col == 1:
            self.edit_label(row,col)
        elif col == 0 and 0 <= row < self.tree.rowCount():
            self.tree.clearSelection()
            self.tree.selectRow(row)
            self.view3d()

    def say(self,s): self.log.moveCursor(QTextCursor.MoveOperation.End); self.log.insertPlainText(s); self.log.moveCursor(QTextCursor.MoveOperation.End)
    def camera(self,mode):
        if self.plot is None:return
        if mode=='iso':self.plot.view_isometric()
        elif mode=='fit':self.plot.reset_camera()
        elif mode=='xz':self.plot.view_xz()
        else:self.plot.view_yz()
        self.plot.render()
    def viewer_screenshot(self):
        if self.busy: return
        if self.plot is None or not self._viewer_has_geometry:
            return messagebox.showinfo('Screenshot','Display geometry first.')
        name = Path(self.analyzed_mod or 'Thicc Tool').name
        default = str(Path.home() / (name + '_' + self.viewer_mode.get() + '_' + time.strftime('%Y%m%d_%H%M%S') + '.png'))
        path, _ = QFileDialog.getSaveFileName(self, 'Save 3D screenshot', default, 'PNG image (*.png)')
        if not path: return
        if not path.lower().endswith('.png'): path += '.png'
        try:
            # Preserve the viewport aspect ratio and camera; no window resize.
            import math
            w, h = self.plot.window_size
            scale = max(1, math.ceil(2400 / max(1, int(w), int(h))))
            self.plot.render()
            image = self.plot.screenshot(path, scale=scale, return_img=True)
            self.say(f'[Viewer] Screenshot saved: {path} ({image.shape[1]} x {image.shape[0]})\n')
        except Exception:
            self.say('[Viewer] Screenshot failed:\n' + traceback.format_exc())
            messagebox.showerror('Screenshot','Could not save the image. Check the log.')

    def initialize_viewer(self):
        """Create and warm the embedded graphics context once, on the Qt thread."""
        if self.plot is not None:return
        from pyvistaqt import QtInteractor
        import pyvista as pv
        from viewer3d import populate
        plot=None; widget=None
        try:
            plot=QtInteractor(parent=self.viewhost, auto_update=False)
            # PyVista's custom trackball maps right drag to pan, wheel to zoom.
            plot.enable_custom_trackball_style(left='rotate', middle='pan', right='pan')
            widget=plot.interactor
            # Keep the native rendering widget embedded, never a top-level window.
            if widget.parentWidget() is not self.viewhost:
                widget.setParent(self.viewhost)
            if widget.isWindow():
                widget.setWindowFlags(Qt.WindowType.Widget)
            self.viewlayout.addWidget(widget,1)
            self.placeholder.hide()
            widget.show()
            self.viewlayout.activate()
            # Warm the OpenGL context and mesh rendering path before any mod view.
            plot.set_background('#202733')
            actor=plot.add_mesh(pv.Sphere(theta_resolution=8, phi_resolution=8),
                                color='#202733', reset_camera=True, render=False)
            plot.render()
            plot.remove_actor(actor, reset_camera=False, render=False)
            plot.clear()
            plot.render()
            self.plot=plot
            self._populate_viewer=populate
        except Exception:
            if widget is not None:
                self.viewlayout.removeWidget(widget)
            if plot is not None:
                try:plot.close()
                except Exception:pass
            if widget is not None:widget.deleteLater()
            self.placeholder.show()
            raise

    def warmup_viewer(self):
        """Synchronously prepare the native viewer before the main window is revealed."""
        if self._closing or self.plot is not None:return
        self.busy=True
        self.viewer_status.setText('3D engine: initializing graphics…')
        self.say('\n[Viewer] Startup warm-up: initializing before window display…\n')
        started=time.monotonic()
        try:
            self.initialize_viewer()
            self.viewer_status.setText('3D engine: ready — select a part to view.')
            self.say(f'[Viewer] Startup warm-up ready in {time.monotonic()-started:.2f} s.\n')
        except Exception:
            self.viewer_status.setText('3D engine unavailable — View 3D geometry to retry.')
            self.say('\n[Viewer] Startup warm-up failed:\n'+traceback.format_exc())
        finally:self.busy=False

    def show_full_body(self):
        if not self.analysis or not self.tree.rowCount():return
        if self.tree.item(0,'text')!=FULL_BODY:return
        self.tree.clearSelection(); self.tree.selectRow(0); self.view3d()

    def view3d(self):
        if self.busy:return
        if not self.analysis or self.analyzed_mod!=os.path.abspath(self.mod.get()): return messagebox.showinfo('Viewer','Analyze the mod first.')
        names=[self.tree.item(i,'text') for i in self.tree.selection()]
        if FULL_BODY in names:
            from anatomical_reconstruction import reconstruct
            try:
                meta={}; te.parse_draws(self.analysis['ini'],metadata=meta)
                reference=reconstruct(self.analysis['ini'],meta)
                names=reference['active']
                self.say('[Full Body] %d resolved default draws; %d unknown.\n'%(len(names),len(reference['uncertain'])))
            except Exception as e:
                self.say('[Full Body] '+str(e)+'\n'); return
        if not names:return messagebox.showinfo('Viewer','Select one or more parts.')
        self.busy=True
        mod=self.analyzed_mod; ini=self.analysis['ini']; wire=self.wire.get(); mode=self.viewer_mode.get(); preview=self.preview_positions if mode in ('Preview','Comparison','Displacement') else None
        if mode=='Preview' and preview is None:
            self.busy=False; return messagebox.showinfo('Viewer','Run Preview first.')
        self.viewer_status.setText('3D engine: loading geometry…')
        self.say('\n[Viewer] Loading geometry…\n')
        started=time.monotonic()
        def load():
            try:
                # Retry initialization only if startup warm-up failed.
                self.initialize_viewer()
                self._viewer_has_geometry=False
                self._populate_viewer(self.plot,mod,ini,names,wire=wire,mode=mode,preview_positions=preview)
                self._viewer_has_geometry=True
                self.plot.render()
                elapsed=time.monotonic()-started
                self.viewer_status.setText(f'3D engine: ready | {elapsed:.2f} s')
                self.say(f'[Viewer] Ready in {elapsed:.2f} s.\n')
            except Exception:
                self.viewer_status.setText('3D engine: error — check diagnostic log.')
                self.say('\n[Viewer] '+traceback.format_exc())
                messagebox.showerror('Viewer','Could not display geometry. Check the log.')
            finally:self.busy=False
        QTimer.singleShot(50,load)
    def run_experiment(self):
        if self.busy:return
        from experiment_runner import discover, invocation
        root=Path(HERE).parent/'experiments'
        try: scripts=discover(root)
        except Exception:return messagebox.showerror('Experiments',traceback.format_exc())
        if not scripts:return messagebox.showinfo('Experiments',f'Place Python scripts in {root}')
        names=[str(p.relative_to(root)) for p in scripts]
        name,ok=QInputDialog.getItem(self,'Experiments','Select a trusted local diagnostic script:',names,0,False)
        if not ok:return
        script=scripts[names.index(name)]
        m=self.mod.get().strip()
        m=os.path.abspath(m) if m else ''
        ini=''
        if m and os.path.isdir(m):
            try:ini=os.path.abspath(te.find_ini(m))
            except (Exception,SystemExit):pass
        work=tempfile.mkdtemp(prefix='thicc-experiment-'); log=os.path.join(work,'experiment.log')
        try:
            cmd,env=invocation(script,root,HERE,m,ini)
            with open(log,'wb') as f:
                proc=subprocess.Popen(cmd,cwd=str(root),env=env,stdout=f,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except Exception:
            shutil.rmtree(work,ignore_errors=True); return messagebox.showerror('Experiments',traceback.format_exc())
        self.busy=True; self.main.setEnabled(False); self.menuBar().setEnabled(False)
        self.status.setText('Experiment working…'); self.say(f'\n===== EXPERIMENT: {name} =====\nMod: {m or "(none)"}\n')
        self.job=dict(proc=proc,work=work,log=log,start=time.monotonic(),offset=0,decoder=codecs.getincrementaldecoder('utf-8')(errors='replace'),cancelled=False,mode='experiment',name=name)
        self.overlay=QDialog(self); self.overlay.setWindowTitle('Experiments'); self.overlay.setWindowModality(Qt.WindowModality.ApplicationModal)
        layout=QVBoxLayout(self.overlay); layout.addWidget(QLabel(name)); self.elapsed=QLabel('0 s'); layout.addWidget(self.elapsed)
        cancel=QPushButton('Cancel experiment'); layout.addWidget(cancel)
        def stop():
            j=self.job
            if j and j['mode']=='experiment' and j['proc'].poll() is None:
                j['cancelled']=True; j['proc'].terminate(); cancel.setEnabled(False)
        cancel.clicked.connect(stop); self.overlay.reject=stop; self.overlay.show()
        self.timer=QTimer(self); self.timer.timeout.connect(self.poll_experiment); self.timer.start(100)

    def poll_experiment(self):
        j=self.job; finished=j['proc'].poll() is not None
        with open(j['log'],'rb') as stream:
            stream.seek(j['offset']); data=stream.read(); j['offset']=stream.tell()
        chunk=j['decoder'].decode(data,final=finished)
        if chunk:self.say(chunk)
        elapsed=time.monotonic()-j['start']; self.elapsed.setText(f'{elapsed:.1f} s elapsed')
        if not finished:return
        self.timer.stop(); self.overlay.hide(); self.overlay.deleteLater()
        self.main.setEnabled(True); self.menuBar().setEnabled(True); self.job=None; self.busy=False
        status='Cancelled' if j['cancelled'] else ('Finished' if j['proc'].returncode==0 else 'Error')
        from experiment_runner import completion_message
        self.say(completion_message(j['name'], status, elapsed, j['proc'].returncode))
        self.status.setText(f'{j["name"]} — {status.lower()} — {elapsed:.2f} s')
        shutil.rmtree(j['work'],ignore_errors=True)

    def start_analysis(self,m,done,force=False): self.launch(m,'diagnose',done,force=force)
    def run_task(self,mode,done=None,save=True):
        if self.busy:return
        m=self._check_mod()
        if not m:return
        if save:
            if not self.analysis or self.analyzed_mod!=os.path.abspath(m):return messagebox.showwarning('Thicc Tool','Analyze the mod before continuing.')
            if not self.analysis.get('ready'):return messagebox.showwarning('Thicc Tool','Analysis incomplete or Anatomy changed. Review and save/analyze.\n\n'+'\n'.join(self.analysis.get('warnings',[])))
            try:
                candidate=self.write_cfg(m,dry=True)
                if candidate != getattr(self,"analysis_ui_baseline",None): self.write_cfg(m)
            except ValueError as e:return messagebox.showerror('Thicc Tool',str(e))
        self.launch(m,mode,done)
    def launch(self,m,mode,done,force=False):
        self._save_settings(); work=tempfile.mkdtemp(prefix='thicc-qt-'); result=os.path.join(work,'result.pkl'); log=os.path.join(work,'analysis.log'); exe=sys.executable
        if os.path.basename(exe).lower()=='pythonw.exe':exe=os.path.join(os.path.dirname(exe),'python.exe')
        try:
            with open(log,'wb') as f: proc=subprocess.Popen([exe,'-u',os.path.join(HERE,'analysis_worker.py'),m,result,mode]+(['--force'] if force else []),stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONIOENCODING':'utf-8'},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except Exception:
            shutil.rmtree(work,ignore_errors=True);return messagebox.showerror('Process',traceback.format_exc())
        self.cache_note.hide(); self.status.setStyleSheet(''); self.status.setText('Working…'); self.busy=True; self.job=dict(mod=m,proc=proc,work=work,result=result,log=log,done=done,mode=mode,start=time.monotonic(),cancelled=False,offset=0,decoder=codecs.getincrementaldecoder('utf-8')(errors='replace'),tail=''); self.say('\n'); self.main.setEnabled(False); self.menuBar().setEnabled(False)
        self.overlay=QDialog(self); self.overlay.setWindowTitle('Thicc Tool'); self.overlay.setWindowModality(Qt.WindowModality.ApplicationModal); self.overlay.setWindowFlags(Qt.WindowType.Dialog|Qt.WindowType.CustomizeWindowHint|Qt.WindowType.WindowTitleHint); p=QVBoxLayout(self.overlay); p.setContentsMargins(28,25,28,25); p.addWidget(QLabel('Analyzing mod…' if mode=='diagnose' else 'Processing geometry…')); self.elapsed=QLabel('0 s'); p.addWidget(QLabel(f"Mod {self.batch['index']}/{self.batch['total']} — {os.path.basename(m)}") if self.batch else QLabel(os.path.basename(m))); p.addWidget(self.elapsed); progress=QProgressBar(); progress.setRange(0,0); p.addWidget(progress); self.cancel_button=QPushButton('Cancel analysis'); self.cancel_button.clicked.connect(self.cancel_analysis); p.addWidget(self.cancel_button); self.cancel_button.setVisible(mode=='diagnose'); self.overlay.reject=lambda:None; self.overlay.resize(380,150); self.overlay.show(); self.timer=QTimer(self); self.timer.timeout.connect(self.poll_analysis); self.timer.start(100)
    def cancel_analysis(self):
        j=self.job
        if not j or j['mode']!='diagnose' or j['cancelled']:return
        j['cancelled']=True; self.cancel_button.setEnabled(False); self.elapsed.setText('Cancelling…')
        if j['proc'].poll() is None:j['proc'].terminate()
    def poll_analysis(self):
        j=self.job
        finished=j['proc'].poll() is not None
        with open(j['log'],'rb') as stream:
            stream.seek(j['offset']); data=stream.read(); j['offset']=stream.tell()
        chunk=j['decoder'].decode(data,final=finished)
        if chunk:
            self.say(chunk); j['tail']=(j['tail']+chunk)[-1500:]
        if not finished:
            if not j['cancelled']:self.elapsed.setText(f"{int(time.monotonic()-j['start'])} s elapsed")
            return
        self.timer.stop(); self.overlay.hide(); self.overlay.deleteLater(); self.main.setEnabled(True); self.menuBar().setEnabled(True); self.job=None; self.busy=False
        try:
            if j['cancelled']:self.say('\nAnalysis cancelled by user.\n'); self.status.setText('Analysis cancelled.');return
            if j['proc'].returncode:raise RuntimeError(j['tail'])
            with open(j['result'],'rb') as f:res=pickle.load(f)
            if j['done']:
                accepted=j['done'](res)
                if j['mode']=='diagnose' and accepted is not False: self.analysis_completed(res,j['mod'])
            else:
                self.status.setText({'dry':'Preview ready. Check the log.','write':'Applied. Press F10 in game.','restore':'Original restored.'}[j['mode']])
                if j['mode']=='dry':
                    self.preview_positions=res.get('preview_positions') if isinstance(res,dict) else None
                    if self.preview_positions is None:
                        self.status.setText('Preview unavailable. Check the log.'); return
                else: self.preview_positions=None
                if self.analysis and self.analyzed_mod==os.path.abspath(j['mod']):
                    self.viewer_mode.set('Current' if j['mode']=='restore' else 'Comparison')
                    self.show_full_body()
        except Exception:
            self.say(traceback.format_exc()); self.status.setText('Error: check the log.');
            if self.batch is None: messagebox.showerror('Thicc Tool','Process error. Check the log.')
        finally:
            shutil.rmtree(j['work'],ignore_errors=True)
            if self.batch is not None:
                if j['cancelled']: self.finish_batch(True)
                else: self.next_library()
    def completion_popup(self,title,body):
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            QApplication.beep()
        QApplication.alert(self, 5000)
        if getattr(self,'completion_box',None) is not None:
            try: self.completion_box.close()
            except RuntimeError: pass
        box=QMessageBox(self); box.setWindowTitle(title); box.setIcon(QMessageBox.Icon.Information)
        box.setTextFormat(Qt.TextFormat.RichText); box.setText(body); box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,True); box.setWindowModality(Qt.WindowModality.NonModal)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose,True); box.show()
        self.completion_box=box

    def analysis_completed(self,res,mod):
        c=res.get('_cache',{}); source=c.get('source','real'); seconds=c.get('seconds',0)
        labels={'real':'Real analysis','full_cache':'FULL CACHE','detection_cache':'DETECTION CACHE + new morphology','reclassified':'CACHED DETECTORS + new classification'}
        label=labels.get(source,source); cached=source!='real'; color='#2e9d70' if cached else '#748ec7'
        status='Ready' if res.get('ready') else 'Incomplete — review parts'
        self.cache_note.setText(label + (' — Analyze → Force analyze to rebuild.' if cached else ' — detection recalculated.')); self.cache_note.setStyleSheet('color:#2e9d70' if cached else 'color:#748ec7'); self.cache_note.show()
        self.status.setStyleSheet('color:#2e9d70' if cached else '')
        self.status.setText(f'{label} | {seconds:.2f} s | {status}'+(' | Analyze > Force analyze to rebuild' if cached else ''))
        if self.batch is not None:
            self.batch['sources'].append(source); return
        self.completion_popup('Analysis finished',f'<b>Analysis finished</b><br><br>{escape(os.path.basename(mod))}<br><br><b style="color:{color}">{label}</b><br>Time: {seconds:.2f} s<br>{escape(status)}'+('<br><br>Use Analyze → Force analyze to rebuild.' if cached else ''))

    def manage_library(self):
        if self.busy: return
        d=QDialog(self); d.setWindowTitle('Mod library'); d.resize(760,380)
        l=QVBoxLayout(d); l.addWidget(QLabel('Saved mod folders. Removing an entry does not delete files.'))
        w=QListWidget(); w.addItems(self.library); l.addWidget(w)
        row=QHBoxLayout(); l.addLayout(row)
        def add(path=None):
            start=self.library_last_dir or os.path.dirname(self.mod.get()) or os.path.expanduser('~')
            if not os.path.isdir(start): start=os.path.expanduser('~')
            path=path or QFileDialog.getExistingDirectory(d,'Add mod folder',start)
            if not path:return
            path=os.path.abspath(path)
            if not self.valid_folder(path):return QMessageBox.warning(d,'Library','Select a valid mod folder containing Meshes/Position.buf.')
            self.library_last_dir=os.path.dirname(path)
            if not any(os.path.normcase(x)==os.path.normcase(path) for x in self.library):
                self.library.append(path); w.addItem(path)
            self._save_settings()
        def remove():
            i=w.currentRow()
            if i>=0:self.library.pop(i); w.takeItem(i); self._save_settings()
        def load():
            i=w.currentRow()
            if i>=0: self.mod.set(self.library[i]); d.accept(); self.analyze(False)
        for name,fn in [('Add folder',lambda:add()),('Add current',lambda:add(self.mod.get())),('Remove',remove),('Open and analyze',load),('Close',d.accept)]:
            b=QPushButton(name); b.clicked.connect(fn); row.addWidget(b)
        w.itemDoubleClicked.connect(lambda _:load()); d.exec()
    def valid_folder(self,m):
        return any(os.path.isfile(os.path.join(m,'Meshes',n)) for n in ('Position.buf','Position.buf.orig'))
    def analyze_library(self,force=False):
        if self.busy:return
        if not self.library:return self.manage_library()
        self.batch={'paths':list(self.library),'total':len(self.library),'index':0,'original':self.mod.get(),'force':force,'sources':[]}
        self.say('\n=== LIBRARY ANALYSIS ===\n'); self.next_library()
    def next_library(self):
        b=self.batch
        if b is None:return
        while b['paths']:
            m=b['paths'].pop(0); b['index']+=1
            self.say(f"\n=== Mod {b['index']}/{b['total']}: {m} ===\n")
            if not self.valid_folder(m): self.say('Skipped: missing geometry buffers.\n'); continue
            self.mod.set(m); self.analyze(False,force=b['force'])
            if self.busy:return
            self.say('Could not start analysis.\n')
        self.finish_batch(False)
    def finish_batch(self,cancelled):
        original=self.batch["original"] if self.batch else ""
        sources=self.batch.get("sources",[]) if self.batch else []
        total=self.batch.get('total',0) if self.batch else 0
        self.batch=None
        if self.analyzed_mod:self.mod.set(self.analyzed_mod)
        elif original:self.mod.set(original)
        msg='Library analysis cancelled.' if cancelled else 'Library analysis finished. Review the diagnostic log.'
        self.say('\n'+msg+'\n'); self.status.setText(msg); self._save_settings()
        if not cancelled:
            real=sources.count('real'); cached=len(sources)-real
            self.completion_popup('Library analysis finished',f'<b>Library analysis finished</b><br>Completed: {len(sources)} / {total}<br>Failed or skipped: {total-len(sources)}<br>Real: {real}<br><b style="color:#2e9d70">Cached: {cached}</b>')
    def analyze_saved(self):
        old=self.analysis; self.analysis=None
        try:self.analyze()
        finally:self.analysis=old
    def manual(self): self.show_text('Manual',MANUAL)
    def about(self):
        info='Thicc Tool 008 ARF test / engine '+te.VERSION+'\nPython: '+sys.version+'\nExecutable: '+sys.executable
        for name in ('numpy','scipy','PySide6','pyvista','pyvistaqt','vtk'):
            try:info+='\n'+name+': '+str(getattr(importlib.import_module(name),'__version__','Available'))
            except Exception as e:info+='\n'+name+': '+str(e)
        try:
            env_cache=json.loads(Path(HERE,'thicc_environment_cache.json').read_text(encoding='utf-8'))
            info+='\nEnvironment cache: '+str(env_cache.get('status','unknown'))+' | '+str(env_cache.get('validated_utc',''))
        except Exception:
            info+='\nEnvironment cache: not available (direct launch or not yet validated)'
        info+='\nVirtual environment: '+str(sys.prefix!=sys.base_prefix)
        self.show_text('About',info+'\n\n'+ABOUT)
    def show_text(self,title,text):
        d=QDialog(self); d.setWindowTitle(title); l=QVBoxLayout(d); box=QPlainTextEdit(text); box.setReadOnly(True); l.addWidget(box); d.resize(760,540); d.exec()
    def closeEvent(self,event):
        if self.busy:event.ignore();return
        self._closing=True
        if self.plot is not None:self.plot.close()
        event.accept()
    def _load_settings(self):
        try:
            s = json.load(open(SETTINGS, encoding="utf-8"))
            self.library_last_dir=s.get("library_last_dir", ""); self.mod.set(s.get("last_mod", "")); self.library=list(dict.fromkeys(x for x in s.get("library",[]) if isinstance(x,str)))
        except Exception:
            pass
        self.apply_preset()

    def _save_settings(self):
        try:
            json.dump({"last_mod": self.mod.get(), "library": self.library, "library_last_dir": self.library_last_dir}, open(SETTINGS, "w", encoding="utf-8"))
        except Exception:
            pass

    def apply_preset(self):
        for k, v in te.PRESETS[self.preset.get()].items():
            self.amount[k].set(v)

    def pick(self):
        if self.busy:
            return
        d = QFileDialog.getExistingDirectory(self, "Select the mod folder", self.mod.get() or os.path.expanduser("~"))
        if d:
            self.mod.set(os.path.normpath(d))
            self.analyze()

    def open_folder(self):
        if os.path.isdir(self.mod.get()):
            os.startfile(self.mod.get())

    def _check_mod(self):
        m = self.mod.get().strip()
        if not os.path.isfile(os.path.join(m, "Meshes", "Position.buf")) and \
                not os.path.isfile(os.path.join(m, "Meshes", "Position.buf.orig")):
            messagebox.showwarning("Thicc Tool", "This folder does not contain Meshes\\Position.buf.\n"
                                   "Select the mod folder containing the INI and Meshes folder.")
            return None
        return m

    def cfg_path(self, m):
        return os.path.join(m, "thicc.json")

    def read_cfg(self, m):
        try:
            cfg = json.load(open(self.cfg_path(m), encoding="utf-8"))
            try:
                te.normalize_legacy_part_names(cfg, te.parse_draws(te.find_ini(m)))
            except (OSError, ValueError, SystemExit):
                pass
            return cfg
        except Exception:
            return {}

    def write_cfg(self, m, dry=False):
        cfg = self.read_cfg(m)
        cfg["bounce"] = next(k for k, v in BOUNCE_LABELS.items() if v == self.bounce.get())
        cfg["surface_shading"] = self.shading.get()
        cfg["deformation_field"] = self.field_mode.get()
        cfg["displacement_smoothing"] = self.taubin.get()
        cfg["final_regularization"] = dict(enabled=self.final_reg_group.isChecked(), **{k:v.get() for k,v in self.final_reg_controls.items()})
        cfg["advanced_arm_protection"] = bool(self.arm_protection.get())
        cfg["advanced_clothing"] = bool(self.advanced_clothing.get())
        cfg["coupled_hips"] = self.hip_profile_group.isChecked()
        cfg["hip_profile"] = {k:v.get() for k,v in self.hip_profile.items()}
        cfg["relative_silhouette"] = bool(self.relative_silhouette.get())
        cfg["silhouette_strength"] = self.silhouette_strength.get()
        cfg["directional_enabled"] = self.direction_group.isChecked()
        cfg["directional_values"] = {k:[v.get() for v in pair] for k,pair in self.direction.items()}
        cfg["directional_expansion"] = cfg["directional_values"] if cfg["directional_enabled"] else {}
        cfg["preset"] = self.preset.get()
        base = te.PRESETS[self.preset.get()]
        cfg["amounts"] = {k: round(self.amount[k].get(), 2) for k, _ in SLIDERS
                          if abs(self.amount[k].get() - base[k]) > 1e-6}
        cfg["inner_fill"] = bool(self.inner.get())
        cfg["inner_gap_mode"] = "Rounded transition"
        cfg["waist_morphology"] = dict(enabled=self.waist_group.isChecked(), **{k:v.get() for k,v in self.waist_controls.items()})
        cfg["virtual_inguinal"] = bool(self.virtual.get())
        cfg["surface_rounding"] = bool(self.rounding.get())
        if self.analysis and self.analyzed_mod == os.path.abspath(m):
            roles = {self.tree.item(i, "text"): ROLE_KEYS[self.tree.set(i, "role")]
                     for i in self.tree.get_children() if self.tree.item(i,"text")!=FULL_BODY}
            cfg["anatomy"] = [n for n in roles if n in self.anatomy]
            cfg["skin"] = [n for n, r in roles.items() if r == "skin"]
            cfg["freeze"] = [n for n, r in roles.items() if r == "frozen"]
            cfg["move"] = [n for n, r in roles.items() if r == "garment"]
        lm = {}
        for k, _ in LANDMARKS:
            s = self.lm[k].get().strip().replace(",", ".")
            if not s:
                continue
            try:
                v = float(s)
            except ValueError:
                raise ValueError("Invalid measurement in '%s': %s" % (k, s))
            if k not in self.auto_lm or abs(v - self.auto_lm[k]) > 0.05:
                lm[k] = v
        cfg["landmarks"] = {**{k: v for k, v in cfg.get("landmarks", {}).items() if k not in self.lm}, **lm}
        if dry: return cfg
        json.dump(cfg, open(self.cfg_path(m), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    def analyze(self, save_current=True, force=False):
        if self.busy:
            return
        m = self._check_mod()
        if not m:
            return
        if not force and save_current and self.analysis and self.analyzed_mod == os.path.abspath(m):
            try:
                candidate=self.write_cfg(m,dry=True)
                if candidate != getattr(self,"analysis_ui_baseline",None): self.write_cfg(m)
            except ValueError as e:
                messagebox.showerror("Thicc Tool", str(e)); return
        self.pending_mod = None
        def done(res):
            if not res:
                return False
            if force:
                from detection_cache import accept_proposal
                saved=self.read_cfg(m)
                old_roles={n:r for k,r in (('skin','skin'),('freeze','frozen'),('move','garment')) for n in saved.get(k,[])}
                old_anatomy=set(saved.get('anatomy',[])); new_anatomy=set(res['cfg']['anatomy'])
                changes=[]
                for n,role,*_ in res['parts']:
                    old=old_roles.get(n,'automatic')
                    if old!=role or (n in old_anatomy)!=(n in new_anatomy):
                        changes.append((n,old,role,'Yes' if n in old_anatomy else 'No','Yes' if n in new_anatomy else 'No','ARF' if n in res.get('arf_recovered',[]) else 'Weighted / automatic'))
                current_names={row[0] for row in res['parts']}
                for n in sorted((set(old_roles)|old_anatomy)-current_names):
                    changes.append((n,old_roles.get(n,'automatic'),'Removed','Yes' if n in old_anatomy else 'No','No','Missing draw'))
                if not res.get('ready'):
                    self.say('\n[Force analyze] Proposed anatomy is incomplete: '+ '; '.join(res.get('warnings',[]))+'\n')
                if os.path.isfile(self.cfg_path(m)) and changes and not self.confirm_detection_changes(changes,res):
                    self.say('\n[Force analyze] Saved configuration retained.\n'); self.status.setText('Automatic proposal rejected — saved configuration unchanged.'); return False
                accept_proposal(m,res,te.find_ini)
                self.say('\n[Force analyze] Accepted configuration saved; analysis reused.\n')
            if self.plot is not None:self.plot.clear(); self.plot.render()
            self.analysis = res
            self.preview_positions=None
            self.analyzed_mod = os.path.abspath(m)
            self.anatomy = set(res["cfg"].get("anatomy", []))
            self.tree.delete(*self.tree.get_children())
            self.tree.insert('', 'end', text=FULL_BODY, values=('Default INI assembly','Virtual','View only','—','—','—','—','—'),tags=('frozen',))
            self.tree.item(0,0).setToolTip('Read-only assembled default configuration; not saved as a real part.')
            for n, role, z0, z1, nv, reg in res["parts"]:
                self.tree.insert("", "end", text=n,
                                 values=(res["cfg"].get("labels", {}).get(n, ""), "Visible" if res["draw_meta"][n]["visible"] else "Hidden", ROLES[role], "Yes" if n in self.anatomy else "No", reg or "-", "%.1f" % z0, "%.1f" % z1, nv),
                                 tags=(role,))
                self.refresh_role_tooltip(self.tree.rowCount()-1)
            cfg = res["cfg"]
            self.shading.set(cfg.get("surface_shading", "Original"))
            self.field_mode.set(cfg.get("deformation_field", "Legacy"))
            self.taubin.set(bool(cfg.get("displacement_smoothing", False)))
            reg=cfg.get("final_regularization", {})
            self.final_reg_group.setChecked(bool(reg.get("enabled", False)))
            for k,v in self.final_reg_controls.items(): v.set(reg.get(k, {"strength":0.35,"tolerance":0.20}[k]))
            self.arm_protection.set(bool(cfg.get("advanced_arm_protection", False)))
            self.advanced_clothing.set(bool(cfg.get("advanced_clothing", False)))
            self.hip_profile_group.setChecked(bool(cfg.get("coupled_hips",False)))
            for k,v in self.hip_profile.items(): v.set(cfg.get("hip_profile",{}).get(k,{"upper":1.4,"lower":1.65,"peak":0.}[k]))
            self.relative_silhouette.set(bool(cfg.get("relative_silhouette", False)))
            self.silhouette_strength.set(cfg.get("silhouette_strength", 1.0))
            self.direction_group.setChecked(bool(cfg.get("directional_enabled", False)))
            for key,pair in self.direction.items():
                for control,value in zip(pair,cfg.get("directional_values", {}).get(key,[1,1])): control.set(value)
            self.bounce.set(BOUNCE_LABELS.get(cfg.get("bounce", "normal"), "Normal"))
            if cfg.get("preset") in te.PRESETS:
                self.preset.set(cfg["preset"])
            self.apply_preset()
            for k, v in cfg.get("amounts", {}).items():
                if k in self.amount:
                    self.amount[k].set(v)
            self.inner.set(bool(cfg.get("inner_fill", False)))
            waist=cfg.get("waist_morphology", {})
            self.waist_group.setChecked(bool(waist.get("enabled",False)))
            for k,v in self.waist_controls.items(): v.set(waist.get(k,1.0))
            self.virtual.set(bool(cfg.get("virtual_inguinal", True)))
            self.rounding.set(bool(cfg.get("surface_rounding", True)))
            over = cfg.get("landmarks", {})
            L = res["landmarks"]
            self.auto_lm = res.get("natural", L)
            for k, _ in LANDMARKS:
                value = over.get(k, L.get(k))
                self.lm[k].set(str(value) if value is not None else "")
            status = {"complete":"Skeleton reconstructed", "old_format":"Legacy format: local bone indices", "incomplete":"Unified skeleton incomplete", "failed":"Could not reconstruct unified skeleton", "pending":"Anatomy pending"}.get(res.get("skeleton_status"), "Unknown status")
            self.warn.config(foreground="#18733c" if res.get("ready") else "#b00000", text=status + "\n" + "\n".join("Warning: " + w for w in res["warnings"]))
            self.status.config(text="Analysis ready." if res.get("ready") else "Analysis incomplete: review parts and analyze again.")
            self.analysis_ui_baseline=self.write_cfg(m,dry=True)
            if self.batch is None:
                self.viewer_mode.set("Current"); QTimer.singleShot(0,self.show_full_body)
            return True
        self.start_analysis(m, done, force=force)

    def confirm_detection_changes(self,changes,res):
        dlg=QDialog(self); dlg.setWindowTitle('Automatic detection changes'); layout=QVBoxLayout(dlg)
        label=QLabel('Force analyze found %d changed parts. Replace saved classification and Anatomy?' % len(changes)); label.setWordWrap(True); layout.addWidget(label)
        if not res.get('ready'):
            warning=QLabel('New analysis is incomplete: '+ '; '.join(res.get('warnings',[]))); warning.setWordWrap(True); layout.addWidget(warning)
        table=QTableWidget(len(changes),6); table.setHorizontalHeaderLabels(['Part','Saved role','Detected role','Saved anatomy','Detected anatomy','Source']); table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for i,row in enumerate(changes):
            for j,value in enumerate(row): table.setItem(i,j,QTableWidgetItem(str(value)))
        table.resizeColumnsToContents(); table.horizontalHeader().setStretchLastSection(True); layout.addWidget(table)
        buttons=QDialogButtonBox(); accept=buttons.addButton('Accept changes',QDialogButtonBox.ButtonRole.AcceptRole); reject=buttons.addButton('Keep saved',QDialogButtonBox.ButtonRole.RejectRole); reject.setDefault(True); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); layout.addWidget(buttons); dlg.resize(880,420)
        return dlg.exec()==QDialog.DialogCode.Accepted

    def toggle_visibility(self):
        if self.busy or not self.analysis or not self.analyzed_mod:
            return
        if os.path.abspath(self.mod.get()) != self.analyzed_mod:
            messagebox.showwarning("Wardrobe", "Analyze this folder first.")
            return
        rows = [i for i in self.tree.selection() if self.tree.item(i,"text")!=FULL_BODY]
        if not rows:
            messagebox.showinfo("Wardrobe", "Select one or more parts.")
            return
        meta = self.analysis['draw_meta']
        selected = {self.tree.item(i, 'text'): meta[self.tree.item(i, 'text')] for i in rows}
        visible = not any(v['visible'] for v in selected.values())
        try:
            new = te.set_visibility(self.analysis['ini'], selected, visible)
        except (ValueError, OSError) as e:
            messagebox.showerror('Wardrobe', str(e)); return
        self.analysis['draw_meta'] = new
        for i in self.tree.get_children():
            n = self.tree.item(i, 'text')
            if n==FULL_BODY:continue
            self.tree.set(i, 'visibility', 'Visible' if new[n]['visible'] else 'Hidden')
        self.say('Wardrobe: '+ ('shown' if visible else 'hidden') + ': '+ ', '.join(selected) + '\n')
        self.status.config(text='Visibility saved in INI. Press F10 in game.')

    def edit_label(self, row, col):
        if self.busy or col != 1 or not self.analyzed_mod: return
        if self.analyzed_mod != os.path.abspath(self.mod.get()): return
        if self.tree.item(row,"text")==FULL_BODY:return
        value, ok = QInputDialog.getText(self, "Label", "Custom name:", text=self.tree.set(row,"label"))
        if not ok: return
        cfg=self.read_cfg(self.analyzed_mod); labels=cfg.setdefault("labels",{}); name=self.tree.item(row,"text")
        if value.strip(): labels[name]=value.strip()
        else: labels.pop(name,None)
        with open(self.cfg_path(self.analyzed_mod),"w",encoding="utf-8") as f: json.dump(cfg,f,ensure_ascii=False,indent=2)
        self.tree.set(row,"label",value.strip())

    def set_role(self, role):
        if self.busy or self.analyzed_mod != os.path.abspath(self.mod.get()): return
        sel = [i for i in self.tree.selection() if self.tree.item(i,"text")!=FULL_BODY]
        if not sel:
            messagebox.showinfo("Thicc Tool", "Select one or more parts in the table.")
            return
        if self.analysis: self.analysis["ready"] = False
        for i in sel:
            self.tree.set(i, "role", ROLES[role])
            self.tree.item(i, tags=(role,))
            self.refresh_role_tooltip(i)

    def set_anatomy(self, include):
        if self.busy or self.analyzed_mod != os.path.abspath(self.mod.get()):
            return
        rows=[i for i in self.tree.selection() if self.tree.item(i,"text")!=FULL_BODY]
        if not rows:return
        if self.analysis: self.analysis["ready"] = False
        for i in rows:
            n = self.tree.item(i, "text")
            if include:
                self.anatomy.add(n)
            else:
                self.anatomy.discard(n)
            self.tree.set(i, "anatomy", "Yes" if include else "No")

    def save_anatomy(self):
        if self.busy:
            return
        m = self._check_mod()
        if not m or os.path.abspath(m) not in (self.analyzed_mod, getattr(self, "pending_mod", None)):
            return
        if not self.anatomy:
            messagebox.showwarning("Thicc Tool", "Select at least one anatomical part.")
            return
        cfg = self.read_cfg(m)
        cfg["anatomy"] = [self.tree.item(i, "text") for i in self.tree.get_children()
                          if self.tree.item(i, "text") in self.anatomy]
        if self.analysis:
            try:
                self.write_cfg(m)
                cfg = self.read_cfg(m)
            except ValueError as e:
                messagebox.showerror("Thicc Tool", str(e))
                return
        json.dump(cfg, open(self.cfg_path(m), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        self.analyze_saved()

    def reset_auto(self):
        if self.busy:
            return
        m = self._check_mod()
        if not m:
            return
        cfg = self.read_cfg(m)
        for k in ("skin", "freeze", "move", "anatomy"):
            cfg[k] = []
        cfg["landmarks"] = {}
        json.dump(cfg, open(self.cfg_path(m), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        self.analyze_saved()

    def preview(self):
        self.run_task("dry")

    def apply(self):
        if messagebox.askyesno("Thicc Tool", "Will modify Meshes\\Position.buf y Vector.buf de:\n\n%s\n\n"
                               "Original is backed up (.orig). Continue?" % self.mod.get()):
            self.run_task("write")

    def restore(self):
        m = self._check_mod()
        if not m:
            return
        if not os.path.isfile(os.path.join(m, "Meshes", "Position.buf.orig")):
            messagebox.showinfo("Thicc Tool", "This mod has no .orig backup.")
            return
        if messagebox.askyesno("Thicc Tool", "Restore original Position.buf and Vector.buf?"):
            self.run_task("restore", save=False)

def notify_launcher(status, **details):
    path=os.environ.get('THICC_READY_FILE')
    if not path:
        return
    try:
        target=Path(path)
        temp=target.with_suffix('.tmp')
        temp.write_text(json.dumps({'status':status, **details}),encoding='utf-8')
        os.replace(temp,target)
    except OSError:
        pass

if __name__=='__main__':
    app=QApplication(sys.argv)
    try:
        import thicc_edit as te
        window=App()
        # Build and embed VTK while the top-level window is not visible.
        # WA_DontShowOnScreen permits Qt to prepare the widget hierarchy without
        # mapping the main window to the desktop during the initial render.
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        try:
            window.warmup_viewer()
            window.show()
            app.processEvents()
            if window.plot is not None:
                try:
                    window.plot.render()
                    app.processEvents()
                except Exception:
                    window.say('\n[Viewer] Pre-display render warning:\n'+traceback.format_exc())
        finally:
            window.hide()
            window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
        window.show()
        QTimer.singleShot(0, lambda: notify_launcher('ready', viewer='ready' if window.plot is not None else 'unavailable; retry in tool'))
        sys.exit(app.exec())
    except Exception:
        error=traceback.format_exc(); notify_launcher('error',message=error); Path(HERE,'gui_error.log').write_text(error,encoding='utf-8'); QMessageBox.critical(None,'Thicc Tool',error); sys.exit(1)
