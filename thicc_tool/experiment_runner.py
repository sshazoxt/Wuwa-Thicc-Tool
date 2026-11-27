"""Discovery and execution contract for trusted local diagnostic scripts."""
from pathlib import Path
import os
import ast
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


def experiment_details(path):
    """Read literal metadata without importing or executing the script."""
    try:
        tree = ast.parse(Path(path).read_text(encoding='utf-8-sig'))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'EXPERIMENT_INFO' for t in node.targets):
                info = ast.literal_eval(node.value)
                if isinstance(info, dict):
                    return info
        return {'description': ast.get_docstring(tree) or 'No description provided.'}
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError, RecursionError):
        return {'description': 'Experiment metadata unavailable.'}

def parameter_source(info):
    """Scripts opt in to current controls; no metadata defaults to own protocol."""
    mode = info.get('parameter_source', 'protocol')
    if mode not in ('protocol', 'saved', 'current'):
        raise ValueError(f'Unknown experiment parameter source: {mode!r}')
    return mode


def experiment_tooltip(path):
    info = experiment_details(path)
    lines = [str(info.get('description', 'No description provided.'))]
    if 'objective' in info: lines.append('Objective: ' + str(info['objective']))
    if 'visual' in info: lines.append('Output: ' + str(info['visual']))
    if 'batch' in info: lines.append('Automated: ' + ('Yes' if info['batch'] else 'No'))
    if 'writes' in info: lines.append('Mod writes: ' + ('Explicit Apply only' if info['writes'] else 'No'))
    try: lines.append('Parameter source: '+parameter_source(info))
    except ValueError as exc: lines.append(str(exc))
    lines.append('Parameters: '+str(info.get('parameters','Script-defined protocol; no live GUI input unless explicitly requested.')))
    return '\n'.join(lines)
