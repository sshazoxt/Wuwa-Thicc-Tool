# 041 — Direct Anatomical Thighs

Incremental patch for 040. Morphology > Direct Section now selects a native-coordinate thigh field in addition to the unchanged Direct Hips field. Legacy is unmodified.

- Each side is measured independently from active Skin triangle/plane intersections, with PCHIP interpolation of its section extents. The gain is a quintic profile between the knee and crotch, peaking at 62% of their span. The width unit is 32% of the median original half-width in the central thigh. These are provisional dimensionless shape parameters, not Rover dimensions.
- The field is evaluated from original positions, separately for each leg. Normalized lateral and depth coordinates determine the displacement. Medial growth is weaker and additionally limited by clearance to the midline, with a smooth per-point cap. A relative radial mask limits influence away from the measured section. No post-deformation smoothing is introduced.
- Hips is unchanged. The new thigh contribution is added to the existing direct hip field, not applied to already-deformed vertices. The old leg field is rebuilt with thigh amount zero when Direct Thighs is active, retaining the existing calf contribution. Glutes and Belly are unchanged. This does not certify compatibility of every slider combination.
- The original Legacy thigh rounding option is retained but skipped when Direct Thighs is active because its sampling only understands the reference-space field. Final regularization, Taubin, inner-gap reconstruction and other optional processing are retained. The historical read-only experiment 74 remains unchanged.
- Preview and Apply use the same production path. The mod's existing engine selector and saved settings are reused. Backups remain managed by the original export path.
- Missing or insufficient Skin section coverage raises an error rather than inventing body radii. No new dependencies.

Test Hips 1.99 / Thighs 1.01 with all other amounts zero and optional smoothing disabled, then higher intensities. Check front, side, back, and in-game animation/clothing. The field is not a collision solver; no midline crossing in the tested mesh is not proof that garments or animated surfaces cannot intersect.
