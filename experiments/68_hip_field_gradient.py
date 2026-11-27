EXPERIMENT_INFO = {'description': 'Measure fixed XY field derivative and actual lateral contour gain derivatives.', 'objective': 'Measure fixed XY field derivative and actual lateral contour gain derivatives.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'protocol', 'parameters': 'Hips 2.00; other regions zero; Legacy; no post smoothing'}

from _overlap_causal_lab import execute

if __name__ == "__main__":
    execute(68)
