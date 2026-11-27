EXPERIMENT_INFO = {'description': 'Color original and deformed contact samples by source surface', 'objective': 'Color original and deformed contact samples by source surface', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'protocol', 'parameters': 'Hips 2.00; other regions zero; Legacy; no post smoothing'}

from _surface_overlap_lab import execute

if __name__ == "__main__":
    execute(61)
