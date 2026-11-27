EXPERIMENT_INFO = {'description': 'Exclude upper or lower section contribution in shared band.', 'objective': 'Exclude upper or lower section contribution in shared band.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'protocol', 'parameters': 'Hips 2.00; other regions zero; Legacy; no post smoothing'}

from _overlap_causal_lab import execute

if __name__ == "__main__":
    execute(64)
