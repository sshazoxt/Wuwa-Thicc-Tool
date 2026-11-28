"""Private, automatic runtime preparation for experiment 78A only."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV = ROOT / '_envs' / 'anny78a'
PACKAGES = {'numpy': 'numpy<2', 'scipy': 'scipy', 'PySide6': 'PySide6',
            'pyvista': 'pyvista', 'pyvistaqt': 'pyvistaqt'}


def log(message):
    print('[78A setup] ' + message, flush=True)


def console_python(exe):
    exe = Path(exe)
    return exe.with_name('python.exe') if exe.name.lower() == 'pythonw.exe' else exe


def missing(exe):
    env = dict(os.environ, QT_API='pyside6', PYTHONUNBUFFERED='1')
    bad = []
    for module, requirement in PACKAGES.items():
        result = subprocess.run([str(exe), '-c', 'import ' + module], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding='utf-8', errors='replace')
        if result.returncode:
            log(module + ' unavailable: ' + result.stdout.strip()[-500:])
            bad.append(requirement)
    return bad


def run(*args):
    log(' '.join(str(a) for a in args))
    subprocess.run([str(a) for a in args], check=True)


def prepare(script):
    """Reuse existing dependencies, otherwise install locally and restart in that env.

    No changes to the director, production interpreter, or original mod.
    The worker remains alive until the child exits; the private snapshot remains valid.
    """
    os.environ.setdefault('QT_API', 'pyside6')
    exe = console_python(sys.executable)
    # Bundled profiles are static: neither torch nor Anny is imported at runtime.
    log('Checking ADS runtime dependencies (bundled Anny profiles).')
    bad = missing(exe)
    if not bad:
        log('All runtime dependencies ready; no installation needed.')
        return
    if os.environ.get('THICC_78A_PRIVATE_RUNTIME') == '1':
        raise RuntimeError('Private runtime still has missing dependencies: ' + ', '.join(bad))
    local = ENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not local.is_file():
        ENV.parent.mkdir(parents=True, exist_ok=True)
        log('Creating private environment: ' + str(ENV))
        run(exe, '-m', 'venv', '--system-site-packages', ENV)
    bad = missing(local)
    if bad:
        run(local, '-m', 'pip', 'install', '--upgrade', '--index-url', 'https://pypi.org/simple', 'pip')
        run(local, '-m', 'pip', 'install', '--index-url', 'https://pypi.org/simple', *bad)
    bad = missing(local)
    if bad:
        raise RuntimeError('Installation incomplete: ' + ', '.join(bad))
    log('Private runtime ready. Launching experiment.')
    env = dict(os.environ, THICC_78A_PRIVATE_RUNTIME='1', PYTHONUNBUFFERED='1', QT_API='pyside6')
    engine = env.get('THICC_ENGINE_DIR')
    if engine:
        env['PYTHONPATH'] = os.pathsep.join(filter(None, [engine, env.get('PYTHONPATH')]))
    result = subprocess.run([str(local), '-u', str(Path(script).resolve())], env=env)
    raise SystemExit(result.returncode)
