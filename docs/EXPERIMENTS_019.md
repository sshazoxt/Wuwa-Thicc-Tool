# 019 — Hip instrumentation

Install on top of 018. Keep preview_no_seam_guard.py (shared sandbox and geometry helpers). No engine or GUI files are replaced. New executable experiments have permanent numeric prefixes; older unnumbered scripts are not renamed because other experiments import them. `_hip_monitor.py` is a helper, not an experiment.

Run 09, 10, 11, 12 in order. All use saved settings, set Butt/Thighs/Calves to zero and Seam Guard OFF in a private temporary copy. Other options remain as saved. For a useful comparison, keep the same mod, roles and Hips setting. If original position backup is absent the current buffer is the baseline. The viewer shows only resolved active Skin pieces.

09: reference versus model Z, original chosen and outer contour, largest contour gaps, target before/after target transformation, envelope, final correction, actual growth and residual. Widths in reference units, Zmodel in model units. Actual measured after calibration and before directional multipliers/rounding.
10: raw Hips outward displacement in model units on original, raw Hips-only contribution and final preview; same scalar range and linked cameras. Also prints field component and edge-gradient reports.
11: additive field components, p95 outward displacement by 1-cm original Z band, hip weight and per-part p99/max edge displacement gradient. Components are checkpoints of the actual field_ref, not independent recalibrated slider runs. Final regularization/masks are not included in raw components.
12: in-memory clone of installed run and field_ref, preserving original formulas and other installed dependencies. Verify final preview against uninstrumented engine (absolute coordinate tolerance 1e-6 cm), fail if not equivalent. Print 09 and 11 reports plus all eight iterations at every reference Z: old Hc, measured growth, error, raw update, clipped, smoothed. NaN growth is reported as NaN (solver substitutes zero error). Source hashes identify installed implementation. Source anchors must match; if changed, fail rather than silently run a different algorithm.

The contour heuristic uses absolute X, cutoff 26 reference cm and torso_half's gap criterion; the report does not prove true triangle intersections. Mesh edge gradient is a local discontinuity indicator, not a direct curvature measure. No production files or original mod files are changed. Temporary files are removed on normal exit.

Validation: syntax and instrumented clone compilation against available 013 source (014–016 did not change Hips); no real mod buffers or Windows viewer execution in this environment.
