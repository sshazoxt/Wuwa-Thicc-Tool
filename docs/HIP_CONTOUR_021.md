# 021 — Stable hip contour calibration

Production hip calibration selects each section's original samples once using the existing |X| < 26 filter and torso_half first-gap rule. Subsequent X-only deformations measure the same sample identities. The original section's six-sample minimum is retained; a valid core smaller than six samples is still measured, preserving the old baseline in sparse sections. No global change to torso_half, target curves, solver iterations, clipping, smoothing, roles or Seam Guard.

The ordering contract depends on contour enumerating intersections in triangle/edge order and calibration changing X only. A count mismatch raises an explicit error. Incorrect original contour selection is not repaired by this change.

The experiment runner reports the actual script name on success, failure or cancellation. `_hip_sweep.py` explicitly selects its estimator for all A/B cases, including legacy, so experiments 13–15 remain meaningful after production defaults change. Other old experiments that use the installed engine now naturally test the new default.

Run `python -m unittest discover -s tests -v`. 26 tests passed on the reconstructed project (synthetic fixtures, not real mod buffers). Validate on Windows using the same roles/settings and original buffers at Hips 1.25, 2, 3, 5, then other mods and combined sliders. First compare with Seam Guard off where possible; normal UI retains its saved setting. The full-analysis cache may refresh because engine source changed.
