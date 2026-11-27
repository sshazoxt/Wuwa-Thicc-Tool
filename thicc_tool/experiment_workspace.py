"""Independent experiment process and ordered batch workspace."""
import codecs, json, os, shutil, subprocess, tempfile, time, traceback, sys
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem,QPushButton,QLabel,QMessageBox,QApplication,QAbstractItemView,QToolButton,QMenu,QDialog)
from experiment_runner import discover, invocation, completion_message, experiment_tooltip, experiment_details, parameter_source
from experiment_parameters import morphology_only, write_json

INTERACTIVE={'31_regional_morphology_editor.py','32_belly_live_apply.py'}
WRITER='32_belly_live_apply.py'

class ExperimentWorkspace(QWidget):
    def __init__(self, app, engine, find_ini):
        super().__init__(app); self.app=app; self.engine=Path(engine); self.root=self.engine.parent/'experiments'; self.find_ini=find_ini
        self.run=None; self.job=None; self.last_output=None
        layout=QVBoxLayout(self); layout.addWidget(QLabel('Experiments · trusted local Python scripts'))
        layout.addWidget(QLabel('Select one script for interactive execution, or check scripts and arrange their batch order.'))
        self.items=QListWidget(); self.items.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); layout.addWidget(self.items,1)
        row=QHBoxLayout(); layout.addLayout(row)
        for text,fn in [('Refresh',self.refresh),('Up',lambda:self.move(-1)),('Down',lambda:self.move(1)),('Uncheck all',self.uncheck)]:
            b=QPushButton(text); b.clicked.connect(fn); row.addWidget(b)
        row=QHBoxLayout(); layout.addLayout(row)
        self.single=QPushButton('Run selected'); self.batch=QToolButton(); self.batch.setText('Run automated'); self.batch.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup); menu=QMenu(self.batch); menu.addAction('Current mod',lambda:self.start(True)); menu.addAction('Library mods…',self.select_library); self.batch.setMenu(menu); self.cancel=QPushButton('Cancel'); self.open=QPushButton('Open results')
        for b,fn in [(self.single,lambda:self.start(False)),(self.batch,lambda:self.start(True)),(self.cancel,self.stop),(self.open,self.open_results)]:
            row.addWidget(b); b.clicked.connect(fn)
        self.info=QLabel('Ready'); self.info.setWordWrap(True); layout.addWidget(self.info)
        self.timer=QTimer(self); self.timer.setInterval(100); self.timer.timeout.connect(self.poll)
        self.refresh(); self.controls()
    def refresh(self):
        if self.run:return
        self.items.clear()
        for p in discover(self.root):
            name=str(p.relative_to(self.root)); item=QListWidgetItem(name+(' [interactive only]' if p.name in INTERACTIVE else ''))
            item.setToolTip(experiment_tooltip(p)); item.setData(Qt.ItemDataRole.UserRole,name); item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Unchecked); self.items.addItem(item)
    def move(self,d):
        if self.run:return
        i=self.items.currentRow(); j=i+d
        if i>=0 and 0<=j<self.items.count(): self.items.insertItem(j,self.items.takeItem(i)); self.items.setCurrentRow(j)
    def uncheck(self):
        if not self.run:
            for i in range(self.items.count()): self.items.item(i).setCheckState(Qt.CheckState.Unchecked)
    def controls(self):
        active=self.run is not None; self.single.setEnabled(not active); self.batch.setEnabled(not active); self.items.setEnabled(not active); self.cancel.setEnabled(active and not self.writer_active()); self.open.setEnabled(self.last_output is not None)
    def writer_active(self): return bool(self.run and self.run['writer'])
    def blocks_write(self,mod): return self.writer_active() and os.path.normcase(os.path.abspath(mod))==os.path.normcase(self.run['mod'])
    def status(self,text):
        self.info.setText(text); self.app.experiment_status.setText(text)
    def open_results(self):
        if self.last_output: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output)))
    def select_library(self):
        if self.run or self.app.busy:return
        paths=list(dict.fromkeys(os.path.abspath(p) for p in self.app.library))
        if not paths:
            QMessageBox.information(self,'Experiments','The mod library is empty.'); return
        d=QDialog(self); d.setWindowTitle('Select library mods'); d.resize(700,400)
        layout=QVBoxLayout(d); layout.addWidget(QLabel('Select mods in library order. Each mod is analyzed privately.'))
        layout.addWidget(QLabel('Parameter source is declared by each experiment. Current controls, when requested, are captured once.'))
        items=QListWidget(); layout.addWidget(items)
        for p in paths:
            item=QListWidgetItem(p); item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Checked); items.addItem(item)
        row=QHBoxLayout(); layout.addLayout(row)
        for label,fn in [('Select all',lambda:[items.item(i).setCheckState(Qt.CheckState.Checked) for i in range(items.count())]),('Uncheck all',lambda:[items.item(i).setCheckState(Qt.CheckState.Unchecked) for i in range(items.count())]),('Run',d.accept),('Cancel',d.reject)]:
            b=QPushButton(label); b.clicked.connect(fn); row.addWidget(b)
        if d.exec():
            selected=[paths[i] for i in range(len(paths)) if items.item(i).checkState()==Qt.CheckState.Checked]
            if selected:self.start(True,selected)
    def start(self,batch,library=None):
        if self.run or self.app.busy:return
        if batch: items=[self.items.item(i) for i in range(self.items.count()) if self.items.item(i).checkState()==Qt.CheckState.Checked]
        else: items=[self.items.currentItem()] if self.items.currentItem() else []
        names=[i.data(Qt.ItemDataRole.UserRole) for i in items]
        if not names:return
        if batch and any(Path(n).name in INTERACTIVE or experiment_details(self.root/n).get('batch') is False or experiment_details(self.root/n).get('writes') is True for n in names):
            QMessageBox.warning(self,'Experiments','Interactive-only or mod-writing scripts must be run individually.'); return
        m=self.app.mod.get().strip(); m=os.path.abspath(m) if m else ''; ini=''; writer=not batch and Path(names[0]).name==WRITER
        work=None
        try:
            if m and library is None:
                try: ini=os.path.abspath(self.find_ini(m))
                except SystemExit as exc: raise ValueError(str(exc)) from exc
            sources={n:parameter_source(experiment_details(self.root/n)) for n in names}
            cfg=None
            if writer or 'current' in sources.values():
                if not m or not self.app.analysis or self.app.analyzed_mod!=m or not self.app.analysis.get('ready'):
                    raise ValueError('An experiment requests current Morphology controls. Analyze the current mod first.')
                cfg=self.app.write_cfg(m,dry=True)
                cfg['amounts']={k:float(v.get()) for k,v in self.app.amount.items()}
            work=Path(tempfile.mkdtemp(prefix='thicc-exp-'))
            out=None
            if batch:
                out=self.root.parent/'experiment_results'/(datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')+' - Experiment Results'); out.mkdir(parents=True); self.last_output=out
                (out/'run.json').write_text(json.dumps({'mod':m,'ini':ini,'scripts':names,'settings':'script-declared','library':library,'parameter_sources':sources,'current_morphology':morphology_only(cfg) if cfg is not None else None},ensure_ascii=False,indent=2),encoding='utf-8')
            self.run=dict(names=names,index=0,mod=m,ini=ini,writer=writer,batch=batch,work=work,out=out,stop=False,results=[],start=time.monotonic(),cfg=cfg,sources=sources)
            self.controls()
            if library is not None:
                self.run.update(library=library,mod_index=0,root_out=out,root_work=work,mod_results=[])
                self.next_mod()
            else:self.next()
        except Exception:
            if work: shutil.rmtree(work,ignore_errors=True)
            self.run=None; self.controls(); self.status('Experiment error'); self.app.say(traceback.format_exc())
    def record(self,s):
        self.app.say(s)
        if self.run['out']:
            with (self.run['out']/'console.txt').open('a',encoding='utf-8') as f:f.write(s)
            root=self.run.get('root_out')
            if root and root!=self.run['out']:
                with (root/'console.txt').open('a',encoding='utf-8') as f:f.write(s)
    def next_mod(self):
        r=self.run
        if r['stop'] or r['mod_index']>=len(r['library']):
            self.finish(); return
        r['mod']=r['library'][r['mod_index']]; r['index']=0; r['results']=[]
        folder=f"{r['mod_index']+1:02d}_{Path(r['mod']).name or 'mod'}"
        r['out']=r['root_out']/folder; r['out'].mkdir()
        r['work']=r['root_work']/folder; r['work'].mkdir()
        r['ini']=''
        try:
            r['ini']=os.path.abspath(self.find_ini(r['mod']))
            (r['out']/'run.json').write_text(json.dumps(dict(mod=r['mod'],ini=r['ini'],scripts=r['names'],parameter_sources=r['sources']),ensure_ascii=False,indent=2),encoding='utf-8')
            log=r['work']/'analysis.log'; exe=Path(sys.executable)
            if exe.name.lower()=='pythonw.exe':exe=exe.with_name('python.exe')
            cmd=[str(exe),'-u',str(self.engine/'library_experiment_analysis.py'),r['mod'],str(r['work']/'model'),str(r['out'])]
            with log.open('wb') as f: proc=subprocess.Popen(cmd,cwd=str(self.engine),env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONUNBUFFERED':'1'},stdout=f,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.job=dict(proc=proc,log=log,offset=0,decoder=codecs.getincrementaldecoder('utf-8')(errors='replace'),start=time.monotonic(),name='Analyze',analysis=True)
            self.record(f"\n===== LIBRARY MOD {r['mod_index']+1}/{len(r['library'])}: {r['mod']} =====\n")
            self.status(f"{folder} — Analyzing — 0 s"); self.timer.start()
        except (Exception,SystemExit):
            self.record(traceback.format_exc()); r['results'].append(dict(name='Analyze',status='Error')); self.complete_mod()
    def complete_mod(self):
        r=self.run
        status='Cancelled' if r['stop'] else ('Error' if any(x['status']=='Error' for x in r['results']) else 'Finished')
        (r['out']/'summary.json').write_text(json.dumps(r['results'],indent=2),encoding='utf-8')
        r['mod_results'].append(dict(mod=r['mod'],folder=r['out'].name,status=status,results=r['results']))
        shutil.rmtree(r['work'],ignore_errors=True); r['mod_index']+=1
        r['out']=r['root_out']; r['work']=r['root_work']; r['results']=[]
        QTimer.singleShot(0,self.next_mod)
    def next(self):
        r=self.run
        if r['stop'] or r['index']>=len(r['names']):
            if 'library' in r:self.complete_mod()
            else:self.finish()
            return
        name=r['names'][r['index']]; log=r['work']/f"{r['index']:03d}.log"
        try:
            cmd,env=invocation(self.root/name,self.root,self.engine,r['mod'],r['ini'])
            env['THICC_EXPERIMENT_MODE']='batch' if r['batch'] else 'legacy'
            source=r['sources'][name]
            env['THICC_PARAMETER_MODE']=source
            for key in ('THICC_EXPERIMENT_CONFIG','THICC_EXPERIMENT_CONFIG_KIND','THICC_EXPERIMENT_BASE_CONFIG','THICC_EXPERIMENT_SNAPSHOT','THICC_LIVE_CONFIG','THICC_APPLIED_MARKER','THICC_EXPERIMENT_OUTPUT','THICC_EXPERIMENT_STEM'):
                env.pop(key,None)
            if source=='current' and not r['writer']:
                config=r['work']/'current_config.json'
                write_json(config,morphology_only(r['cfg']) if 'library' in r else r['cfg'])
                env['THICC_EXPERIMENT_CONFIG']=str(config)
                env['THICC_EXPERIMENT_CONFIG_KIND']='morphology' if 'library' in r else 'full'
            if r['mod'] and not r['writer']:
                env['THICC_EXPERIMENT_BASE_CONFIG']=str(r['work']/'base_config.json')
            if 'library' in r:
                snapshot=r['work']/'model'
                env['THICC_MOD_DIR']=str(snapshot); env['THICC_INI']=str(snapshot/Path(r['ini']).name)
                env.pop('THICC_EXPERIMENT_SNAPSHOT',None)
            elif r['mod'] and not r['writer']: env['THICC_EXPERIMENT_SNAPSHOT']=str(r['work']/'model')
            if r['out']:
                env['THICC_EXPERIMENT_OUTPUT']=str(r['out']); env['THICC_EXPERIMENT_STEM']=f"{r['index']+1:02d}_{Path(name).stem}"
            if r['writer']:
                config=r['work']/'live_config.json'; config.write_text(json.dumps(r['cfg'],ensure_ascii=False),encoding='utf-8'); env['THICC_LIVE_CONFIG']=str(config); env['THICC_APPLIED_MARKER']=str(r['work']/'applied.json')
            cmd=[*cmd[:-1],str(self.engine/'experiment_worker.py'),cmd[-1]]
            with log.open('wb') as f: proc=subprocess.Popen(cmd,cwd=str(self.root),env=env,stdout=f,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.job=dict(proc=proc,log=log,offset=0,decoder=codecs.getincrementaldecoder('utf-8')(errors='replace'),start=time.monotonic(),name=name,source=source)
            self.record(f'\n===== EXPERIMENT: {name} =====\nMod: {r["mod"]}\nParameter source: {source}\n'); self.timer.start(); self.status(f'{name} — Running — 0 s')
        except Exception:
            self.record(traceback.format_exc()); r['results'].append(dict(name=name,status='Error')); r['index']+=1; self.next()
    def poll(self):
        j=self.job; r=self.run
        if not j or not r:return
        done=j['proc'].poll() is not None
        with j['log'].open('rb') as f:f.seek(j['offset']); data=f.read(); j['offset']=f.tell()
        chunk=j['decoder'].decode(data,final=done)
        if chunk:self.record(chunk)
        elapsed=time.monotonic()-j['start']; prefix=f"Mod {r['mod_index']+1}/{len(r['library'])} · {Path(r['mod']).name} · " if 'library' in r else ''; self.status(prefix+(f"Analyzing — {elapsed:.1f} s" if j.get('analysis') else f"{r['index']+1}/{len(r['names'])} · {j['name']} — Running — {elapsed:.1f} s"))
        if not done:return
        self.timer.stop(); code=j['proc'].returncode; status='Cancelled' if r['stop'] else ('Finished' if code==0 else 'Error')
        self.record(completion_message(j['name'],status,elapsed,code)); r['results'].append(dict(name=j['name'],status=status,seconds=elapsed,exit=code,parameter_source=j.get('source')))
        if j.get('analysis'):
            self.job=None
            if status=='Finished':self.next()
            else:self.complete_mod()
            return
        if r['writer'] and (r['work']/'applied.json').is_file() and self.app.analyzed_mod==r['mod']:
            self.app.preview_positions=None; self.app.viewer_mode.set('Current')
            if not self.app.busy and os.path.abspath(self.app.mod.get())==r['mod']: self.app.show_full_body()
        self.job=None; r['index']+=1
        if r['batch'] and not r['stop'] and r['index']<len(r['names']) and 'library' not in r: QApplication.beep()
        # Continue after an individual script error; stop if explicitly cancelled.
        self.next()
    def stop(self):
        if not self.run or self.writer_active():return
        self.run['stop']=True
        if self.job and self.job['proc'].poll() is None:self.job['proc'].terminate()
    def finish(self):
        r=self.run; elapsed=time.monotonic()-r['start']; errors=sum(x['status']=='Error' for x in r.get('mod_results',r['results'])); status='Cancelled' if r['stop'] else ('Finished with errors' if errors else 'Finished')
        self.record(f'\n===== EXPERIMENT RUN {status.upper()} | {elapsed:.2f}s =====\n')
        if r['out']:(r['out']/'summary.json').write_text(json.dumps(r.get('mod_results',r['results']),indent=2),encoding='utf-8')
        shutil.rmtree(r['work'],ignore_errors=True); self.run=None; self.controls(); self.status(f'Experiments — {status} — {elapsed:.1f} s'); QApplication.beep()
