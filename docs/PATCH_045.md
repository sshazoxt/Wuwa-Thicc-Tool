# Patch 045 — Legacy recommended defaults and Direct Section warning

Install over 044 by extracting the ZIP into the project root. No new dependencies.

## Morphology UI

Direct Section displays a native warning icon and an experimental-engine notice directly below the engine tabs. Legacy does not display this notice.

Legacy initializes missing advanced values as follows:

- Coupled hip-thigh profile: on; upper 1.40, lower 1.65, peak offset 0.00.
- Target strength: 1.00 (Relative silhouette calibration is not newly enabled).
- Morphological groin fold and Thigh rounding: on.
- Bounce: Normal; Surface shading: Original; Deformation field: Continuous.
- Taubin displacement smoothing: on.
- Final morphological regularization: on; strength 0.80, noise tolerance 0.65.

These are GUI defaults, not a forced migration. Every explicit saved setting, including disabled checkboxes and zero values, wins over defaults. Missing nested values are filled individually. Existing configurations cannot distinguish a previously saved default from a deliberate manual choice, so both are preserved. The active top-level configuration takes precedence over the corresponding saved profile, and each engine's profile remains independent. When a profile does not exist, only preset, amounts, and Belly parameters are copied from the previous engine as an initial seed; advanced settings are initialized independently. Switching alone does not write geometry. The normal Preview/Apply workflow saves the active settings.

No numerical engine, Direct Section geometry, Legacy geometry, or experiment protocol was changed. This does not constitute further repair of existing geometric artifacts. CLI and experiment defaults are unchanged.

Validation: 112 unittest cases passed, including six new configuration/default and GUI source wiring tests. Python syntax and archive integrity checked. Qt/VTK window behavior in Windows was not tested because PySide6 and PyVista are unavailable in the validation environment.
