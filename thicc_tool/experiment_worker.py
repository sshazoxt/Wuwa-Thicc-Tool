"""Execute trusted experiment scripts, with optional centralized PyVista capture."""
import os
import json
from contextlib import contextmanager
import runpy
import shutil
import sys
from pathlib import Path


def signature(root):
    files = [p for p in (root/'Meshes').rglob('*') if p.is_file()]
    files += [p for p in root.glob('*.ini') if p.is_file()]
    files += [p for p in (root/'thicc.json', root/'thicc_detection_cache.json') if p.is_file()]
    return {str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns) for p in files}


def prepare_snapshot(source, target):
    if target.exists(): return
    before = signature(source)
    staging = target.with_name(target.name+'.partial')
    shutil.copytree(source/'Meshes', staging/'Meshes')
    for name in before:
        if not name.startswith('Meshes'+os.sep):
            shutil.copy2(source/name, staging/name)
    if signature(source) != before:
        raise RuntimeError('Mod changed during experiment snapshot; restart the run.')
    staging.rename(target)


def install_capture(output, stem):
    import pyvista as pv
    original_init, original_show = pv.Plotter.__init__, pv.Plotter.show
    count = 0
    def init(self,*args,**kwargs):
        kwargs['off_screen'] = True
        original_init(self,*args,**kwargs)
    def show(self,*args,**kwargs):
        nonlocal count
        count += 1
        path = output / f'{stem}_{count:02d}.png'
        try:
            w,h = self.window_size
            original_show(self, interactive=False, auto_close=False, screenshot=str(path), window_size=(w*2,h*2))
            if not path.is_file(): raise RuntimeError('Screenshot was not created')
            print(f'[Batch] Screenshot: {path}',flush=True)
        finally:
            self.close()
    pv.Plotter.__init__, pv.Plotter.show = init, show


@contextmanager
def script_config(mod, base, override=None, kind='morphology'):
    """Private snapshot only. Preserve the baseline across independent scripts."""
    path=Path(mod)/'thicc.json'; base=Path(base)
    missing=base.with_suffix('.missing')
    if not base.exists() and not missing.exists():
        if path.exists(): shutil.copy2(path,base)
        else: missing.touch()
    def restore():
        if base.exists(): shutil.copy2(base,path)
        else: path.unlink(missing_ok=True)
    restore()
    try:
        if override:
            from experiment_parameters import overlay
            cfg=json.loads(Path(override).read_text(encoding='utf-8'))
            if kind=='morphology':
                saved=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
                cfg=overlay(saved,cfg)
            elif kind!='full': raise ValueError('Unknown configuration override kind')
            path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
        yield path
    finally: restore()


def execute_script(script, cfgpath=None):
    source=os.environ.get('THICC_PARAMETER_MODE','protocol')
    print('[Experiment] Parameter source:',source,flush=True)
    output=os.environ.get('THICC_EXPERIMENT_OUTPUT')
    stem=os.environ.get('THICC_EXPERIMENT_STEM')
    if output and stem:
        from experiment_runner import experiment_details
        input_cfg=json.loads(cfgpath.read_text(encoding='utf-8')) if cfgpath and cfgpath.is_file() else None
        path=Path(output)/f'{stem}_input.json'
        path.write_text(json.dumps({'parameter_source':source,'experiment_info':experiment_details(script),'input_configuration':input_cfg,'note':'Input snapshot; script-defined case overrides are logged separately.'},ensure_ascii=False,indent=2),encoding='utf-8')
    if os.environ.get('THICC_EXPERIMENT_MODE')=='batch':
        install_capture(Path(output),stem)
    sys.path.insert(0,str(script.parent))
    sys.argv=[str(script)]
    runpy.run_path(str(script),run_name='__main__')

def main():
    script=Path(sys.argv[1]).resolve()
    source=os.environ.get('THICC_MOD_DIR','')
    target=os.environ.get('THICC_EXPERIMENT_SNAPSHOT','')
    if source and target:
        src=Path(source); dst=Path(target)
        prepare_snapshot(src,dst)
        ini=os.environ.get('THICC_INI','')
        os.environ['THICC_MOD_DIR']=str(dst)
        if ini: os.environ['THICC_INI']=str(dst/Path(ini).name)
        print('[Experiment] Private model snapshot:',dst,flush=True)
    config=os.environ.get('THICC_EXPERIMENT_CONFIG')
    base=os.environ.get('THICC_EXPERIMENT_BASE_CONFIG')
    mod=os.environ.get('THICC_MOD_DIR')
    output=os.environ.get('THICC_EXPERIMENT_OUTPUT')
    if config and (not base or not mod): raise RuntimeError('Current control override requires a private snapshot')
    if base and mod:
        with script_config(mod,base,config,os.environ.get('THICC_EXPERIMENT_CONFIG_KIND','morphology')) as path:
            if output and Path(base).is_file():
                archived=Path(output)/'settings.json'
                if not archived.exists(): shutil.copy2(base,archived)
            execute_script(script,path)
    else:
        execute_script(script,Path(mod)/'thicc.json' if mod else None)

if __name__=='__main__': main()
