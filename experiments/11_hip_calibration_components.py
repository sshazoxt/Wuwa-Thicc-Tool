
EXPERIMENT_INFO = {'description': 'Break down the contributions to hip calibration.', 'objective': 'Identify which field terms produce excessive expansion.', 'visual': 'Console only', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

from _hip_monitor import main

if __name__ == "__main__":
    main('components')
