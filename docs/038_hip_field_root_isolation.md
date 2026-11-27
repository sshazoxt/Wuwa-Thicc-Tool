# 038 — Hip Field Root Isolation

Install over patch 037. Refresh Experiments and run 69–73 on Suoming only. All five are batch compatible and use Hips 2, other regions zero, Legacy field and no post-deformation smoothing. Experiment 71 additionally runs a separately labelled Thighs 2 / Hips 0 control (the inherited thigh-driven hip calibration remains active). No production files or source buffers are changed.

- 69: original PCHIP mapping vs linear mapping with identical landmarks and PCHIP without crotch/apex anchors. Linear mapping is a diagnostic control, not a proposed production solution. All downstream measurements are rebuilt per mapping.
- 70: original envelope vs quintic envelope and model-height cubic envelope with equivalent endpoints. This changes field construction, not postprocessing.
- 71: virtual inguinal root vs original skinning root vs no root; thighs-only control. Arm/frozen protections remain unchanged.
- 72: zero Hc, original Hc, no internal convolution (envelope multiplication retained), and one-unit response estimate with original caps. The latter is an approximation, not an exact inverse solve.
- 73: anatomical additive growth, absolute signed target, absolute expansion-only target. Same peak gain and endpoints; the absolute profile specifies width before calibration. Calibration caps, reference and envelope remain unchanged. Lower anchor is clipped to valid sampled calibration coverage. Signed shrinkage may be limited by the original cap. This is a symmetric half-width target, not independent left/right control.

All cases report target, attained expansion, envelope, Hc, vertical map slope and two-sided contour/field gain derivatives, including distance to crotch. Field gain is evaluated at original contour points; its derivative follows that path and is not a fixed-XY partial derivative. The existing profile and quality diagnostics are retained. Comparisons use original geometry, not a previous preview. Batch PNGs use the existing viewer.

Validation: five new unit tests including synthetic cylinder calibration, restoration of experimental functions, mapping and target anchors. Real mod and Windows rendering still require user testing.
