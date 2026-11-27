EXPERIMENT_INFO = {'description': 'Compare active unique exterior reference against production; no mesh boolean', 'objective': 'Compare active unique exterior reference against production; no mesh boolean', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'protocol', 'parameters': 'Hips 2.00; other regions zero; Legacy; no post smoothing'}

from _surface_overlap_lab import execute

if __name__ == "__main__":
    execute(63)
