"""GUI defaults for independent morphology profiles (045).

Explicit saved values (including False and 0) always win. The numerical
engines and experiment protocols do not use these GUI-only defaults.
"""
from copy import deepcopy

LEGACY_ADVANCED_DEFAULTS = {
    'coupled_hips': True,
    'hip_profile': {'upper': 1.40, 'lower': 1.65, 'peak': 0.0},
    'silhouette_strength': 1.0,
    'virtual_inguinal': True,
    'surface_rounding': True,
    'bounce': 'normal',
    'surface_shading': 'Original',
    'deformation_field': 'Continuous',
    'displacement_smoothing': True,
    'final_regularization': {'enabled': True, 'strength': 0.80, 'tolerance': 0.65},
}


def _merge(base, overrides):
    """Copy a mapping, recursively filling only absent nested keys."""
    result = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def with_advanced_defaults(cfg, engine):
    defaults = LEGACY_ADVANCED_DEFAULTS if engine == 'Legacy' else {}
    return _merge(defaults, cfg)


def active_profile(cfg, engine):
    """Top-level active values are authoritative; retain saved profile gaps."""
    saved = cfg.get('engine_profiles', {}).get(engine, {})
    return _merge(saved, cfg)


def switch_profile(profiles, previous, engine):
    """Restore a saved profile, or seed only basic sliders on first switch.

    Do not copy advanced settings across engines: a fresh Direct Section
    profile must not inherit the Legacy refinement defaults, or vice versa.
    """
    if engine in profiles:
        return deepcopy(profiles[engine])
    return {key: deepcopy(previous[key]) for key in ('preset', 'amounts', 'belly_morphology') if key in previous}
