
EXPERIMENT_INFO = {'description': 'Compare isolated thigh and hip fields, with and without hip calibration.', 'objective': 'Identify contributions to thigh bulges.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameters': 'Fixed protocol: Hips 3.98, Thighs 2.00, Legacy field; individual cases override these as needed. No post smoothing.', 'parameter_source': 'protocol'}

from _hip_root_lab import execute

if __name__ == "__main__":
    execute(39)
