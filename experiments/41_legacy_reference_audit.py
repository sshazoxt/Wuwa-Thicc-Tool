EXPERIMENT_INFO = {'description': 'Compare actual landmarks and section radii with Rover reference.', 'objective': 'Locate scale and fixed-mask mismatches.', 'visual': 'Console only', 'batch': True, 'writes': False, 'parameters': 'Fixed protocol: Hips 3.98, Thighs 2.00, Legacy field; individual cases override these as needed. No post smoothing.', 'parameter_source': 'protocol'}

from _relative_field_lab import execute

if __name__ == "__main__":
    execute(41)
