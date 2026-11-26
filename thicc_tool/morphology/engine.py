"""Read-only experimental preview session; no GUI dependency."""
from dataclasses import dataclass
from pathlib import Path
import copy
import json
import shutil
import tempfile
import numpy as np
from analysis_context import AnalysisContext


@dataclass
class MorphologyResult:
    positions: np.ndarray
    regional_data: dict
    vectors: np.ndarray = None


class PreparedGeometry:
    """A snapshot owned by one session. Shared arrays never contain preview data."""
    def __init__(self, root):
        import thicc_edit as te
        self.root = Path(root).resolve()
        self.ini = Path(te.find_ini(str(self.root)))
        metadata = {}; components = {}
        draws = te.parse_draws(str(self.ini), components, metadata)
        mesh = self.root / 'Meshes'
        pos = mesh / 'Position.buf.orig'
        if not pos.is_file(): pos = mesh / 'Position.buf'
        self.positions = np.fromfile(pos, np.float32).reshape(-1, 3).astype(np.float64)
        self.indices = np.fromfile(mesh / 'Index.buf', np.uint32)
        self.positions.setflags(write=False); self.indices.setflags(write=False)
        self.faces = {}
        for name, (start, count) in draws.items():
            fields = metadata[name]['draw'].split(',')
            base = int(fields[2]) if len(fields)>2 else 0
            if start<0 or count<0 or count%3 or start+count>len(self.indices):
                raise ValueError('Invalid DrawIndexed: '+name)
            f = self.indices[start:start+count].astype(np.int64).reshape(-1,3)+base
            if f.size and (f.min()<0 or f.max()>=len(self.positions)):
                raise ValueError('Invalid vertex reference: '+name)
            f.setflags(write=False); self.faces[name] = f
        self.context = AnalysisContext(self.positions,self.faces)


class PreviewSession:
    """Use a single private snapshot for multiple previews. No Apply/Restore API.

    private=False is reserved for callers that already own a disposable copy.
    Skeleton/landmark/calibration computation still runs for each preview.
    """
    def __init__(self, mod, *, private=True):
        self.source = Path(mod).resolve(); self.private = private
        self._temp = None; self.geometry = None; self.root = None

    def __enter__(self):
        import thicc_edit as te
        if self.geometry is not None: raise RuntimeError('Session already open')
        try:
            if self.private:
                self._temp = tempfile.TemporaryDirectory(prefix='thicc-preview-')
                self.root = Path(self._temp.name)
                shutil.copytree(self.source/'Meshes', self.root/'Meshes')
                ini = Path(te.find_ini(str(self.source)))
                for p in (ini, self.source/'thicc.json', self.source/'thicc_detection_cache.json'):
                    if p.is_file(): shutil.copy2(p,self.root/p.name)
            else:
                self.root = self.source
            self.geometry = PreparedGeometry(self.root)
            cfg = self.root/'thicc.json'
            self.saved = json.loads(cfg.read_text(encoding='utf-8')) if cfg.is_file() else {}
            return self
        except BaseException:
            self.__exit__(None,None,None); raise

    def __exit__(self,*args):
        self.geometry = None; self.root = None
        if self._temp is not None:
            self._temp.cleanup(); self._temp = None

    @property
    def original_geometry(self):
        if self.geometry is None: raise RuntimeError("Open PreviewSession first")
        return self.geometry.positions

    @property
    def faces(self):
        if self.geometry is None: raise RuntimeError("Open PreviewSession first")
        return self.geometry.faces

    def preview(self, config=None, *, disable_hip=False):
        import thicc_edit as te
        if self.geometry is None: raise RuntimeError('Open PreviewSession first')
        data = {}
        def observe(event,d):
            if event=='before_waist':
                data.update(L=dict(d['L']), skin=list(d['SKIN']), garments=list(d['GARMENTS']),
                            active=list(d['reference']['active']), allow=d['allow'].copy(), guard=d['guard'].copy(),
                            arm=d['arm_influence'].copy(), H=float(d['H']), before_waist=d['new'].copy())
            elif event=='after_waist': data['after_waist']=d['new'].copy()
            elif event=='after_shading': data['vectors']=d['vectors'].copy()
        cfg=copy.deepcopy(self.saved); cfg.update(copy.deepcopy(config or {}))
        result=te.run(str(self.root),'dry',config_override=cfg,observer=observe,
                      prepared_geometry=self.geometry,disable_hip=disable_hip)
        if not isinstance(result,dict) or 'preview_positions' not in result or not data:
            raise RuntimeError('Preview incomplete; check saved roles and Measurements')
        return MorphologyResult(np.asarray(result['preview_positions'],float),data,data.pop('vectors',None))

    def regional(self, result):
        from .regional import Region
        if self.geometry is None: raise RuntimeError('Open PreviewSession first')
        return Region(self.geometry.positions,self.geometry.faces,result.regional_data)
