EXPERIMENT_INFO = {'description': 'Measure per-component cross sections and overlap', 'objective': 'Measure per-component cross sections and overlap', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'protocol', 'parameters': 'Hips 2.00; all other regions zero; Legacy, no post smoothing'}

from _overlap_lab import execute

if __name__ == "__main__":
    execute(52)
