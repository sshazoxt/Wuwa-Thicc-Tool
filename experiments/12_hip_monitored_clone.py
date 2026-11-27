
EXPERIMENT_INFO = {'description': 'Trace the monitored hip calculation and iterations.', 'objective': 'Locate abrupt changes in calibration.', 'visual': 'Console only', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

from _hip_monitor import main

if __name__ == "__main__":
    main('trace')
