
EXPERIMENT_INFO = {'description': 'Render original, raw hip field and final preview.', 'objective': 'Locate the displacement responsible for visible bulges.', 'visual': 'PNG in batch', 'batch': True, 'writes': False, 'parameter_source': 'saved', 'parameters': 'Saved configuration for this mod; the experiment may override individual values in its own cases.'}

from _hip_monitor import main

if __name__ == "__main__":
    main('visual')
