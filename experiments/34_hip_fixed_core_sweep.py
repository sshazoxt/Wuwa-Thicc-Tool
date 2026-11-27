
EXPERIMENT_INFO = {'description': 'Sweep Fixed Core across hip intensities.', 'objective': 'Locate residual growth and contour changes.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameters': 'Fixed protocol: Hips 3.98, Thighs 2.00, Legacy field; individual cases override these as needed. No post smoothing.', 'parameter_source': 'protocol'}

from _hip_root_lab import execute

if __name__ == "__main__":
    execute(34)
