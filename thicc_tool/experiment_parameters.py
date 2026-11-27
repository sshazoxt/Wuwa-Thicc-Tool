"""Parameter sources for experiments; never transfer anatomy across models."""
import copy, json
from pathlib import Path

MORPH_KEYS = frozenset("preset amounts direct_depth bounce morphology_engine surface_shading deformation_field displacement_smoothing final_regularization advanced_arm_protection advanced_clothing coupled_hips hip_profile relative_silhouette silhouette_strength directional_enabled directional_values directional_expansion inner_fill inner_gap_mode belly_morphology virtual_inguinal surface_rounding seam_guard waist_morphology".split())

def morphology_only(cfg):
    return copy.deepcopy({k:v for k,v in cfg.items() if k in MORPH_KEYS})

def resolve_amounts(cfg):
    from thicc_edit import PRESETS
    values=dict(PRESETS[cfg.get('preset','pear')]); values.update(cfg.get('amounts',{}))
    return {k:float(v) for k,v in values.items()}

def overlay(cfg, common):
    cfg=copy.deepcopy(cfg)
    if common is not None:
        for k in MORPH_KEYS: cfg.pop(k,None)
        cfg.update(morphology_only(common))
    return cfg

def experiment_amounts(cfg, defaults):
    # The script declares the source; a zero is a real value, never a fallback.
    import os
    if os.environ.get('THICC_PARAMETER_MODE','protocol')=='protocol':
        return dict(defaults)
    actual=resolve_amounts(cfg)
    return {k:actual[k] for k in defaults}

def write_json(path,cfg):
    Path(path).write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
