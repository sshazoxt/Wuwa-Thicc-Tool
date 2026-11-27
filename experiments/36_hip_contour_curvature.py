
EXPERIMENT_INFO = {'description': 'Compare all, unique and active skin references; report overlap and contours.', 'objective': 'Test whether segmentation and duplication affect calibration.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameters': 'Fixed protocol: Hips 3.98, Thighs 2.00, Legacy field; individual cases override these as needed. No post smoothing.', 'parameter_source': 'protocol'}

from _hip_root_lab import execute

if __name__ == "__main__":
    execute(36)
