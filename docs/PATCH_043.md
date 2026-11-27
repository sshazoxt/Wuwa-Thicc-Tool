# 043 — Direct Section axes and longitudinal thigh profile

Incremental patch for 042. Extract into the project root. No new dependencies.

- Morphology contains Legacy and Direct Section tabs. Their controls are stored independently per mod (`engine_profiles`); the active values remain at the top level for the existing worker. The first visit to an unconfigured engine copies the current controls as a starting point. Old Direct Section configurations without a depth value initialize depth from their existing width amount in the GUI.
- Direct Section has independent Hips Width/Depth (0–5) and Thighs Width/Depth (0–2). Depth is measured from actual transverse sections. Width and depth multiply separate fields; existing directional multipliers are still optional. Other sliders remain unchanged. The new profile moves the thigh peak to 72% of the knee-to-crotch span and extends the top by 26% of the crotch-to-waist span, with a broad lower falloff. These coefficients remain experimental and do not impose fixed model dimensions.
- The Legacy deformation branch is not altered; the new depth settings are used only in Direct Section. Existing refinement options are retained (Legacy thigh rounding remains skipped for Direct Thighs as in 042).
- Preview and Apply use the existing worker and export pipeline. The active engine and new depth settings are included in the preview cache key.

## Validation of reconstructed patch

102 unit tests passed, including separate X/Y field tests. Python syntax and archive integrity checked. On original buffers of Suoming (422,324 vertices) and Rover (259,910 vertices), dry Preview with Hips Width/Depth and Thighs Width/Depth all 2.00, other sliders zero and post-smoothing disabled, finished successfully. No >90-degree normal changes in the evaluated active Skin faces (39,144 and 105,636 respectively); no Z displacement. The independent base fields were verified on the real vertices. The complete Windows GUI, in-game animation/clothing collision, Apply export, full intensity range and numerical Legacy regression have not been revalidated in this session. Use as experimental patch, retain 042 as rollback.
