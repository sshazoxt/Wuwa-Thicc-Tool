EXPERIMENT_INFO = {'description': 'Compare original envelope with quintic and model-height envelope.', 'objective': 'Compare original envelope with quintic and model-height envelope.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'protocol', 'parameters': 'Hips 2.00; other regions zero; Legacy; no post smoothing; 71 includes separate Thighs 2 positive control'}

from _hip_field_root_isolation import execute

if __name__ == "__main__":
    execute(70)
