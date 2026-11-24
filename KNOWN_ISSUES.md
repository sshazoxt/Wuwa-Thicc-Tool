# ROVER-001 — Surface shading degradation
Status: deferred, non-blocking (2026-11-19).
Rover's original muscular shading becomes discontinuous after morphology. Original Vector.buf reduces the issue; Legacy, Adaptive, Geometric and Continuous have not resolved it. The two leg straps have independent geometry, with no shared vertex IDs with skin in the earlier inspection. Root cause remains unknown: geometry curvature, UV stretching, authored normals/tangents and runtime shaders remain candidates. No character-specific fix. Revisit after deformation improvements; compare original buffers, identical poses and lighting.

# VIEWER-001 — First-use window flicker
Reported first invocation pauses ~4 seconds then window disappears/reappears. QtInteractor was initialized lazily. Version 2.0.5 keeps lazy initialization and shows a modal loading message before initialization. Root cause unconfirmed; Windows validation pending. The progress animation may pause during synchronous VTK initialization.

# Phase 2.4
Opt-in Taubin displacement filter (4 cycles, +0.45/-0.48) inspired by Voidflaq's Fleur method as previously reviewed. Indexed adjacency, pinned coincident positions and protected vertices, reject newly flipped triangles. Default off. Legacy shading incompatible with smoothing. Not validated on real mods or Windows. No changes to anatomical analysis/slider curves. Other remaining techniques: independent directional expansion, target silhouette calibration refinements, clothing adaptation, arm protection review.

# HSIN-002 — Visible ankle deformation
Status: manual workaround confirmed by user (2026-11-19); root cause deferred.
Set Component 3身体 and Component 3身体裸.002 (upper-body variants, one with long drapes) to Frozen + Anatomy; retain Component 7腿 as Skin + Anatomy. Log confirms skin selection drops from three draws to one; anatomy still includes both upper variants and Component 6. Component 3身体 spans Z=26.21..143.10, so its geometry is not confined to upper-body elevations. Role changes also alter skin-based landmarks (waist 104.6 -> 107.6; pelvis Y 0.3 -> -2.7); exact cause not established. Do not hard-code character-specific exceptions. Revisit with island-level classification and independent anatomy reconstruction.
Taubin comparison after workaround: 9442 eligible vertices, peak correction 0.13565 cm, zero new flips, maximum reported edge stretch 1.61 -> 4.73; keep opt-in.

# Phase 2.5 — Directional expansion
Opt-in per-region X/Y contribution multipliers, 0..2, neutral 1. Baseline hip calibration precedes multipliers. Non-neutral settings temporarily skip radial thigh rounding; inner fill remains independent. Regional overlap means zero contribution does not guarantee zero total displacement. No Z expansion yet.

# Phase 2.6 — Relative silhouette calibration
Optional target taper based on existing measured hip and waist landmarks; target zero lateral growth at waist, not a hard constraint. Original calibration remains default. Final contour diagnostics include masks and postprocessing. Existing solver, reference coordinate frame and contour assumptions remain. Independent waist width/depth, narrowing/widening, torso transitions and abdomen volume are planned. No fixed measurements for Sui Sui or other characters.

# HSIN-003 — Inner thigh gap distortion
User confirmed satisfactory external contour with coupled hip-thigh profile (2.0.8), but reported inner contour distortion on enabling Fill inner thigh gap. Screenshot supplied 2026-11-20 confirms visible inner contour irregularity; external contour remains rounded. Deferred until after current integration phase. Review midline soft floor, abrupt candidate boundaries, interaction with coupled field, and inter-leg contact. Preserve validated external contour. Keep inner fill off during baseline comparisons.

# Phase 2.8 — Arm protection
Optional stronger attenuation of existing arm-weight evidence; fully pins weights >= 0.65, never increases mobility. Applies before frozen-role mask and seam guard; does not change landmarks or hip target. Threshold is experimental and not character-specific. Does not recover missing arm evidence or guarantee protection for accessories with unrelated weights. Independent geometric protection and clothing adaptation pending. Default off.

# Phase 2.9 — Clothing adaptation
Opt-in local skin displacement transfer, close fitting garments only. Four nearest skin samples, same-side weighting, smooth distance falloff, protection masks and correction cap, reject newly reversed faces. No exact collision or skirt adaptation; no anatomical edits. Legacy shading incompatible.

# Phase 3.1 — Inner thigh reconstruction
Experimental replacement for legacy inner fill when selected. Uses bilateral section profiles of the already-deformed skin and a monotone medial compression with vertical taper. Outermost contour, frozen vertices and seam pins excluded; rejects new face reversals and severe area loss on previously valid faces. No exact collision solver or guarantee of complete closure, including pre-existing crossings. Legacy shading unsupported. Legacy gap method retained. HSIN-003 remains open until in-game validation.

# Phase 3.1.1 — Rounded inner knee transition
User reports protrusions removed in Reconstructed mode but abrupt medial contour before knee. New opt-in Rounded transition broadens knee fade from 20% to 55% of measured knee-crotch span; original mode retained. Fraction experimental, no fixed model dimensions, no knee or outer contour expansion. Visual validation pending.

# Phase 3.2 — Waist morphology
Rounded inner gap validated visually by user on Hsin; now sole exposed method. Waist scaling opt-in, neutral 1.0, range .60–1.50 per axis, applied to existing deformed geometry before smoothing/clothing adaptation. Requires continuous skin sections and plausible waist landmark; manual waist override bypasses narrowing evidence only. Frozen vertices stay frozen; Hsin workaround may prevent waist editing until regional roles are available. Safety backoff checks face orientation and area, not exact collisions. No real-mod or Windows validation yet.

# Phase 3.2.1 — Upper gap preservation
Optional Y-shaped upper opening: attenuate medial compression smoothly over upper 32% of measured knee-to-crotch span. Neutral preservation 0 and strength 1 retain validated rounded transition. No exact contact or collision solver; pre-existing overlap and frozen geometry may limit result. Reference buffers inspected without INI; no role identification or redistribution of reference assets.

### 2.2.2 — Y contact (experimental)
Replaces 94% medial compression with bounded wall translation, small positive clearance, rounded knee and independently controlled upper fork height. Reports target and measured sectional gaps. Existing saved upper_gap_preservation values are reused with new semantics. Face checks may reduce closure; no full collision or animation guarantee. Real model validation pending.

- 2.2.3: experimental depth-aware medial contact; upper junction anchor retained, no exact surface collision solver. Upper Y contact now increases closure. Validate on reference mod and Hsin.
- Final GUI usability: English tooltips, ranges, defaults, individual reset and illustrations.

### 2.2.4 — Adaptive Contact Solver
Replace global backoff with incremental per-vertex backtracking, two-ring constraint propagation and synchronized step limits for coincident active vertices. Preserve original medial displacement support and face orientation/area checks. Weighted progress is not a guarantee of physical contact; exact collisions, animated pose and real-model validation remain pending.

### TODO — GUI workspace redesign
- Model workspace: parts/Wardrobe, 3D viewer and measurements, independent resizable panels.
- Morphology editor: separate cards for waist/hips, glutes, thighs/knees, inner contact, calves/ankles, advanced surface/clothing/safety controls.
- Illustrative generic silhouettes driven by sliders and numeric inputs only; no model-derived shapes or live mesh deformation. Actual measurements and 3D inspection remain in the model workspace. Never write buffers from graph updates.
- Explain ranges, neutral values, units, effects, constraints and reset per card; label silhouettes as illustrative, not predictions. Keep log and explicit Preview/Apply accessible.

### 3.2.5 — Localized Inner Y Contact
Restore phase 3.1.1 rounded fill as base, then apply residual depth-aware contact only to the upper 28% of the measured knee-crotch span, with smooth onset and upper anchor. Experimental relative bounds; visual validation pending. No live mesh editor planned for current GUI redesign.

### Phase 3.2.6 — Angular Medial Contact (experimental)
- Replace per-depth Y wall targets with one amplitude per horizontal cut and a normalized medial cosine^4 field. Preserve Rounded Inner Thigh and the prior upper vertical taper.
- Small positive midline clearance at every strength; per-vertex X bound and existing adaptive face guard. Not a full triangle collision detector.
- Generic morphology diagrams only, independent of loaded mesh: illustrative slider response, not a live editor. Actual geometry stays in the separate 3D viewer. Future live editor deferred.
- In-game validation pending; test upper contact 0, 0.5, 1 from front and oblique angles. Check residual gap, curvature and stretch.
