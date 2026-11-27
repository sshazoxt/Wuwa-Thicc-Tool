EXPERIMENT_INFO = {'description': 'Compare section ownership and virtual stitched contour calibration.', 'objective': 'Compare section ownership and virtual stitched contour calibration.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'protocol', 'parameters': 'Hips 2.00; other regions zero; Legacy; no post smoothing'}

from _overlap_causal_lab import execute

if __name__ == "__main__":
    execute(66)
