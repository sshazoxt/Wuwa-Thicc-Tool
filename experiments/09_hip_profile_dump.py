
EXPERIMENT_INFO = {'description': 'Report original and calibrated hip cross sections.', 'objective': 'Locate contour errors and target residuals.', 'visual': 'Console only', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

from _hip_monitor import main

if __name__ == "__main__":
    main('profile')
