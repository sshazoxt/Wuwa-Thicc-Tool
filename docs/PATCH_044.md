# Patch 044 — Legacy hip calibration repair (release candidate)

Install over patch 043. The Direct Section branch, GUI, regional leg/glute/calf/belly algorithms and optional refinement passes are unchanged.

Legacy Hips now uses a broad C2 profile in its existing Rover reference frame. The old fixed-core outline is still measured and the amplitude is iteratively calibrated against the observed response. The correction cap depends on the requested target and measured response, rather than the old hard ceiling of 6. The radial masks, angular response, X/Y direction and depth formula are unchanged. The hip profile is constructed before deformation; no new mesh smoothing is introduced. Coupled/relative controls retain a separate profile and target calculation, but have not been validated across the full range on real mods.

A neutral Hips slider uses the original calibration exactly. An advanced rollback for the old calibration is `"legacy_hip_repair": false` in a configuration read by the engine (when preserved by the GUI); reinstalling the original 043 files is the reliable rollback. Existing experiments directly invoking calibrate without the new flag still use the historical implementation; experiments that invoke the production run can use the new calibration and are not necessarily comparable to historical iterations.

## Validation

Real geometry: Suoming 422324 vertices, Rover 259910. Both used the original position buffers and saved anatomical roles. Continuous field, no seam guard, no optional smoothing, no coupled/relative profile, no rounding or inner fill, Original shading for export.

- Hips 0 through 5 in increments of 0.5, plus Hips/Thighs 2/2, 5/2 and Hips/Thighs/Glutes/Calves 2/1/1/1. No >90 degree geometric face-normal rotations in the measured active Skin, excluding arm-weighted faces. This is a diagnostic, not a general proof of mesh validity.
- Both modes of field interpolation tested on 101 equally spaced amplitudes between zero and the calibrated Hips 5 field. At 201 cross sections from knee to waist, neither side had multiple lateral maxima with prominence >=0.12 cm in either mod. This measures the outer contour; does not certify every surface or animation.
- Max observed outward half-width growth (cm), Hips only: Suoming H2 3.390, H5 8.474; Rover H2 5.246, H5 13.052. Old H5: Suoming 3.849; Rover 5.916. Old H2: Suoming 3.377; Rover 5.193.
- Real dry vs write Hips/Thighs 2/2: exact position equality and original position backup SHA256 unchanged in both private model copies.
- Full export revealed normal rotations in existing accessory/garment issues: Suoming inactive lower chain 2250 old vs 2342 new; Rover inactive Dress 34 vs 31 and active Original Hanging Cloths 5 vs 6. These counts are >90-degree geometric normal changes, not definitive evidence of topological inversion. The old counts use the captured pre-final field with the same masks. Do not declare public stability before checking clothing variants and gameplay. Existing isolated Thighs shape is deliberately not changed; optional coupled/relative, rounding, Belly combination, all clothing, all slider combinations and Windows/game animation remain to be validated.
