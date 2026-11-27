EXPERIMENT_INFO = {'description': 'Compare anatomical gain, lower blend and hip floor separately.', 'objective': 'Determine which target construction term causes contour discontinuities.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameters': 'Fixed protocol: Hips 3.98, Thighs 2.00, Legacy field; individual cases override these as needed. No post smoothing.', 'parameter_source': 'protocol'}

from _hip_target_followup import execute

if __name__ == "__main__":
    execute(49)
