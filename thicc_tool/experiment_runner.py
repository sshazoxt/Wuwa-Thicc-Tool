"""Discovery and execution contract for trusted local diagnostic scripts."""
from pathlib import Path
import os
import sys


def discover(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return sorted((p for p in root.rglob('*.py') if p.is_file() and not p.name.startswith('_')
                   and '__pycache__' not in p.relative_to(root).parts
                   and p.resolve().is_relative_to(root)),
                  key=lambda p: str(p.relative_to(root)).casefold())


def invocation(script, root, engine, mod='', ini='', executable=None):
    root, script = Path(root).resolve(), Path(script).resolve()
    if not script.is_relative_to(root) or script.suffix.lower() != '.py' or not script.is_file():
        raise ValueError('Select a Python script inside the experiments folder.')
    engine = Path(engine).resolve()
    exe = Path(executable or sys.executable)
    if exe.name.lower() == 'pythonw.exe':
        exe = exe.with_name('python.exe')
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1',
               THICC_MOD_DIR=mod, THICC_INI=ini, THICC_ENGINE_DIR=str(engine),
               THICC_EXPERIMENT_DIR=str(root), THICC_TEST_DIR=str(root))
    env['PYTHONPATH'] = os.pathsep.join(filter(None, [str(engine), env.get('PYTHONPATH')]))
    return [str(exe), '-u', str(script)], env


def completion_message(name, status, elapsed, returncode):
    """Identify the actual script, including its numeric prefix, on every exit."""
    return (f'\n===== EXPERIMENT {name} | {status.upper()} | '
            f'{elapsed:.3f}s | exit {returncode} =====\n')
