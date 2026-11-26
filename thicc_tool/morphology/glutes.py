import numpy as np

def accumulate(self, px, py, pz, dx, dy, step, cyb, _, ux, uy, BUTT_AMT):
    ang = np.degrees(np.arccos(np.clip(
        -uy / np.maximum(np.hypot(ux, uy), 1e-9),
        -1.0, 1.0
    )))

    w = (
        (1.0 - step(55.0, 100.0, ang))
        * step(75.0, 85.0, pz)
        * (1.0 - step(93.0, 103.0, pz))
        * (1.0 - step(16.0, 26.0, _))
        * step(1.0, 7.0, _)
        * BUTT_AMT * self.a["butt"]
    )

    soft = np.sqrt(px * px + (py - cyb) ** 2 + 9.0)
    dx += w * px / soft * self.direction["butt"][0]
    dy += w * (py - cyb) / soft * self.direction["butt"][1]


