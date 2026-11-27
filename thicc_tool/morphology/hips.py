import numpy as np

def accumulate(self, px, py, pz, dx, dy, step, _, ux, uy, capture=False):
    # ---- calibrated multidirectional hip field
    if self.hip is not None:
        wr_hip = (
            step(4.0, 9.0, _)
            * (1.0 - step(21.0, 27.0, _))
        )
        repaired = getattr(self, "legacy_hip_spline", None)
        hip_amount = (repaired(pz) if repaired is not None else
                      (np.interp(pz, *self.hip) if not self.coupled_hips else self._hip_spline(pz))) * wr_hip
        # Broad, smooth lateral response (odd in X).
        lateral = ux * (0.55 + 0.45 * ux * ux)
        # Smaller depth response; greater toward the posterior.
        posterior = step(-0.75, 0.75, -uy)
        depth = (0.20 + 0.15 * posterior) * uy * (0.65 + 0.35 * ux * ux)
        dx += hip_amount * lateral * self.direction["hips"][0]
        dy += hip_amount * depth * self.direction["hips"][1]

    if capture: return {k: v for k, v in locals().items() if k in ("wr_hip", "hip_amount", "lateral", "depth", "pz")}
