"""Prepare and analyze one private library experiment snapshot, never the source mod."""
import json
import sys
from pathlib import Path
from experiment_worker import prepare_snapshot


def prepare(source, target, output):
    import thicc_edit as te
    from detection_cache import diagnose
    source, target, output = map(Path, (source, target, output))
    prepare_snapshot(source, target)
    result = diagnose(str(target), te.run, te.find_ini)
    if not isinstance(result, dict) or not result.get('ready'):
        raise ValueError('Anatomy not ready: ' + '; '.join((result or {}).get('warnings', [])))
    cfg = dict(result['cfg'])
    roles = {row[0]: row[1] for row in result['parts']}
    for key, role in [('skin','skin'),('freeze','frozen'),('move','garment')]:
        cfg[key] = [n for n,r in roles.items() if r == role]
    payload = json.dumps(cfg, ensure_ascii=False, indent=2)
    (target/'thicc.json').write_text(payload, encoding='utf-8')
    (output/'settings.json').write_text(payload, encoding='utf-8')
    print('[Library] Private analysis ready; effective settings archived.', flush=True)

if __name__ == '__main__':
    prepare(*sys.argv[1:4])
