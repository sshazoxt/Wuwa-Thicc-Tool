# Regional morphology experiments 022

Requires production patch 021 and the existing experiment helpers from 017–021. Extract to repository root; no production modules are replaced. Run from Experiments with a selected, analyzed mod and saved roles/measurements. The scripts copy geometry and settings into a temporary directory, use dry-run only, and display untextured active Full Body draws. Close the preview window to finish the script. All script names and success messages are numbered; the runner also reports the actual exit status.

| Script | Purpose |
| --- | --- |
| 16_waist_legacy_diagnostic.py | Compare actual production waist OFF, width 0.75, depth 1.35; report measured torso section candidates, actual stage displacement and support. |
| 17_waist_belly_preview.py | Compare localized waist, lower-center trial, anterior-only belly, and their combination. |
| 18_glutes_xyz_preview.py | Compare posterior width, depth, vertical extension and combined deformation independently. |
| 19_thigh_hip_isolation.py | Compare production thighs 2, the same field without calibrated hip correction, and independent local-axis prototype. |
| 20_pear_shape_combinations.py | Compare production Fixed Core hips 2.5 against three experimental combinations. |

Prototypes use original active Skin slices (excluding arm-weighted faces), compact quintic vertical support, posterior-only glute influence, local thigh axes, and an independent anterior abdominal field. They retain saved Seam Guard, original role/mobility masks, and production arm transition. Other optional postprocesses are disabled for isolation; the regional prototypes are post-preview geometry candidates, not a production pipeline integration. Clothing receives the same spatial field with a distance fade for remote garments. The safety backtracking reports any reduction or rejection explicitly. No exact intersection/collision solver, animation, or vector-buffer validation is provided. Z deformation is experimental geometry only; the production engine assumes primarily XY displacement. The waist search is heuristic; if no supported closed minimum is found, it reports this and uses the engine landmark for comparison only. Use side and rear views to inspect the results; all cameras are linked.

Validation: syntax compilation, anchor checks against patch 021, and synthetic geometry checks for support, axis isolation, side preservation, and anterior/posterior gating. Real mod execution and Windows viewer are not validated here.
