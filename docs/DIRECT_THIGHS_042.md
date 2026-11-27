# 042 — Direct Thigh/Pelvis Transition

Integrates prototype C from the Suoming comparison into Direct Section only.
Legacy and Direct Hips are unchanged. The thigh peak is 93% of the knee-to-crotch span; its upper support ends 65% of the way from crotch to waist. A continuous blend moves the medial anchor and depth reference from independent leg sections to the common pelvic section. The same spatial field is applied through the existing role/protection and export pipeline. Directional controls remain supported. Coefficients are experimental dimensionless ratios, not character-specific measurements. No post-deformation smoothing is introduced.

Validation: 100 unittest tests passed. Real Suoming (422324 vertices), Hips 2 / Thighs 2, Continuous, Seam Guard enabled: dry and write positions exactly identical, finite, original Z and Position.buf.orig preserved. Visual and in-game validation remain necessary, particularly at Hips 5 / Thighs 2. No GUI changes or new dependencies.
