"""Read-only check of the experiment runner environment."""
import os
import sys
from pathlib import Path

print('Python:', sys.version)
for key in ('THICC_MOD_DIR', 'THICC_INI', 'THICC_ENGINE_DIR', 'THICC_EXPERIMENT_DIR'):
    print(key + ':', os.environ.get(key, ''))
mod = os.environ.get('THICC_MOD_DIR')
if mod:
    for name in ('Position.buf', 'Position.buf.orig', 'Index.buf', 'Blend.buf'):
        p = Path(mod) / 'Meshes' / name
        print(name, p.stat().st_size if p.is_file() else 'missing')
