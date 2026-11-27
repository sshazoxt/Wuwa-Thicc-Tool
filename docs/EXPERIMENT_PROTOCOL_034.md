# Experiment protocol and hip-target follow-up (034)

Each public experiment declares `parameter_source` in its literal `EXPERIMENT_INFO` metadata:

- `protocol` (default for new scripts without a declaration): the experiment supplies its own test values; current UI values are not captured. The script owns any overrides. The shared `experiment_amounts(saved, defaults)` helper returns its protocol defaults.
- `current`: explicitly requests the current Morphology controls. Capture once at launch, not per model or per case. A library run copies only morphological settings into each analyzed private snapshot, not anatomy, landmarks or roles. For a single current-mod experiment the full private configuration is available; interactive experiment 32 continues using its explicit live config and Apply behavior.
- `saved`: use the individual mod's saved configuration as the input, with any script-specific test overrides. Older experiments retain this behavior. This mode is useful for reproducing user-specific configurations, not inherently a standardized comparison.

The runner decides neither the test levels nor the mathematical formula. It reads metadata without importing the script, provides the declared source, and manages execution, isolation and reporting. Different sources can coexist in one automated queue. If a script requests current controls, the selected source mod must have completed analysis; do not silently fall back to saved values. The input configuration is restored before each new script, including after an interrupted preceding worker. The private copy is independent of the actual mod. The original source mod is never written by automated experiments.

`run.json` records sources; each script gets an `*_input.json` describing its input snapshot and metadata. For 34–51, the per-case console log records the actual settings and numeric overrides. `settings.json` is the base per-mod input, not the effective configuration of every case.

## Controlled follow-up

Experiments 34–51 use the same default protocol: Hips 3.98, Thighs 2.00, Legacy field mode; cases may isolate one region or run a fixed sweep. Other fields are zero, optional post smoothing and regularization are disabled, and the anatomical arm exclusion remains. Native landmarks/roles remain per model. These are research settings, not changes to production defaults. Some non-morphological settings and anatomical differences remain model-specific.

49: split anatomical target gain, relative lower blend and the hip-derived lower floor.
50: isolate linear lateral response and removal of the hip-depth term, including combinations with the anatomical target.
51: test hip/thigh target coupling with combined Hips/Thighs. All alternatives use temporary experiment-local functions; no production formulas changed.

Run 45, 49, 50 and 51 in one library batch on Suoming, Rover, and Danjin (or another complete body). Compare contours, desired vs achieved outlines, residual and curvature, and images at equivalent settings. A lower residual or curvature metric alone is not evidence of correct morphology. No further smoothing is introduced.
