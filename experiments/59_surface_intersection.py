EXPERIMENT_INFO = {'description': 'VTK triangle crossing lines on original and deformed surfaces', 'objective': 'VTK triangle crossing lines on original and deformed surfaces', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'protocol', 'parameters': 'Hips 2.00; other regions zero; Legacy; no post smoothing'}

from _surface_overlap_lab import execute

if __name__ == "__main__":
    execute(59)
