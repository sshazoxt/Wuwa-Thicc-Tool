import numpy as np

def accumulate(self, px, py, pz, dx, dy, step, LEG_KNOTS):
    # ---- legs (+ optional inner-thigh fill)
    for sgn in (1, -1):
        zk, xk, yk = self.axis[sgn]

        ax = self.curve(zk, xk, pz)
        ay = self.curve(zk, yk, pz)

        ex, ey = px - ax, py - ay
        r = np.hypot(ex, ey)

        soft = np.sqrt(r * r + 1.5 ** 2)
        exu, eyu = ex / soft, ey / soft

        med = np.clip(
            -exu / np.maximum(np.hypot(exu, eyu), 1e-9) * sgn,
            0.0, 1.0
        )

        w_med = (
            1.0 - med * med
            * (0.12 + 0.80 * step(50.0, 70.0, pz))
        )

                    # ---- anatomical thigh deformation
        leg_amount = self.curve(*self.leg, pz)
        root_fade = 1.0
        effective_amount = leg_amount

        if self.root is not None and sgn in self.root:
            angles, root_z = self.root[sgn]

            theta = np.arctan2(ey, sgn * ex)

            # Provisional anatomical landmarks.
            thigh_outer = np.interp(
                0.0, angles, root_z,
                period=2.0 * np.pi
            )

            thigh_inner = np.interp(
                np.pi, angles, root_z,
                period=2.0 * np.pi
            )

            # Continuous anatomical boundary.
            boundary = np.interp(
                theta, angles, root_z,
                period=2.0 * np.pi
            )

            if self.continuous:
                from continuous_field import angular_profile
                key = (id(angles), id(root_z))
                if key not in self._curves:
                    self._curves[key] = (angles, root_z, angular_profile(angles, root_z))
                boundary = self._curves[key][2](theta)

            # One continuous upper profile for the anterior thigh.
            # Broad angular transition, with a continuous second derivative.
            # Preserve full anterior strength and zero posterior strength.
            angular = np.clip((eyu + 0.20) / 1.10, 0.0, 1.0)
            anterior = angular**3 * (10.0 + angular * (-15.0 + 6.0 * angular))
            peak_z = self.leg[0][np.argmax(self.leg[1])]
            peak_amount = np.max(self.leg[1])
            front_root = np.interp(np.pi / 2, angles, root_z,
                                   period=2.0 * np.pi)
            upper_end = np.maximum(
                peak_z + 1.0,
                LEG_KNOTS[-1][0] + boundary - front_root
            )
            t = np.clip((pz - peak_z) / (upper_end - peak_z), 0.0, 1.0)
            q = t**3 * (10.0 + t * (-15.0 + 6.0 * t))
            upper_amount = peak_amount * (1.0 - q)

            root_fade = 1.0 - step(
                boundary + 6.0 + 12.0 * step(0.35, 0.95, eyu),
                boundary + 18.0 + 12.0 * step(0.35, 0.95, eyu),
                pz
            )
            if self.continuous:
                # Single full-length amplitude with anatomical root fade.
                effective_amount = leg_amount * root_fade
            # Blend the combined influence, not two separate fades.
            mix = anterior * step(peak_z - 3.0, peak_z, pz)
            target = np.where(pz >= peak_z, upper_amount, leg_amount)
            if not self.continuous:
                effective_amount = (1.0 - mix) * leg_amount * root_fade + mix * target

        w = (
            effective_amount
            * (1.0 - step(9.5, 16.0, r))
            * w_med
        )

        # Main leg displacement (applied only once).
        blend = step(47.0, 55.0, pz)
        gx = self.direction["calves"][0] + blend * (self.direction["thighs"][0] - self.direction["calves"][0])
        gy = self.direction["calves"][1] + blend * (self.direction["thighs"][1] - self.direction["calves"][1])
        dx += w * exu * gx
        dy += w * eyu * gy

        # ---- optional inner-thigh fill
        if self.inner is not None:
            own = step(0.0, 1.0, px * sgn)

            fill = (
                self.curve(*self.inner, pz)
                * med * med
                * (1.0 - step(9.5, 16.0, r))
                * own
                * root_fade
            )

            dx -= sgn * fill


