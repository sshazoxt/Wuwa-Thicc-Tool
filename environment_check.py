"""Run only during setup/repair, not on a normal cached launch."""
import importlib
import json
import os
import platform
import struct
import sys
from importlib.metadata import version

PACKAGES = ('numpy', 'scipy', 'PySide6', 'pyvista', 'pyvistaqt', 'vtk')


def main():
    if not ((3, 10) <= sys.version_info[:2] <= (3, 12)) or struct.calcsize('P') != 8 or sys.platform != 'win32':
        raise RuntimeError('Expected Windows x64 CPython 3.10, 3.11 or 3.12')
    if platform.machine().lower() not in ('amd64', 'x86_64'):
        raise RuntimeError('Expected x64 Python')
    os.environ['QT_API'] = 'pyside6'
    result = {}
    module_files = {}
    for name in PACKAGES:
        module = importlib.import_module(name)
        result[name] = version(name)
        module_files[name] = os.path.abspath(module.__file__)
    from pyvistaqt import QtInteractor
    from PySide6.QtWidgets import QApplication
    from scipy.spatial import cKDTree
    import thicc_edit
    print(json.dumps({'python': platform.python_version(), 'packages': result, 'module_files': module_files}))


if __name__ == '__main__':
    main()
