EXPERIMENT_INFO = {'description': 'Visualize virtual side contour joining across the shared band, not mesh welding.', 'objective': 'Visualize virtual side contour joining across the shared band, not mesh welding.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'protocol', 'parameters': 'Hips 2.00; other regions zero; Legacy; no post smoothing'}

from _overlap_causal_lab import execute

if __name__ == "__main__":
    execute(65)
