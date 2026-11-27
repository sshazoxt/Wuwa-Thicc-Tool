EXPERIMENT_INFO = {'description': 'Compare legacy leg amplitude with local anatomical-height profile.', 'objective': 'Test replacement of LEG_KNOTS for thighs.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameters': 'Fixed protocol: Hips 3.98, Thighs 2.00, Legacy field; individual cases override these as needed. No post smoothing.', 'parameter_source': 'protocol'}

from _relative_field_lab import execute

if __name__ == "__main__":
    execute(47)
