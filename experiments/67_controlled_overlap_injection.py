EXPERIMENT_INFO = {'description': 'Inject translated copies of shared-band triangles into calibration; test reference sensitivity, not source mesh changes.', 'objective': 'Inject translated copies of shared-band triangles into calibration; test reference sensitivity, not source mesh changes.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'protocol', 'parameters': 'Hips 2.00; other regions zero; Legacy; no post smoothing'}

from _overlap_causal_lab import execute

if __name__ == "__main__":
    execute(67)
