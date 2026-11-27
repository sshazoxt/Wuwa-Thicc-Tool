EXPERIMENT_INFO = {'description': 'Compare legacy, relative hip, relative leg and combined fields.', 'objective': 'Evaluate combined field construction without post smoothing.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameters': 'Fixed protocol: Hips 3.98, Thighs 2.00, Legacy field; individual cases override these as needed. No post smoothing.', 'parameter_source': 'protocol'}

from _relative_field_lab import execute

if __name__ == "__main__":
    execute(48)
