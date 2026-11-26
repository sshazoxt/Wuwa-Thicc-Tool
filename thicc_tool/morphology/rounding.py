import numpy as np

def accumulate(self, px, py, pz, dx, dy, step):
    if self.rounding is not None:
        zz, aa, table = self.rounding
        for sign in (1, -1):
            zk, xk, yk = self.axis[sign]
            ex = px + dx - self.curve(zk, xk, pz)
            ey = py + dy - self.curve(zk, yk, pz)
            theta = np.arctan2(ey, sign * ex)
            radius = np.hypot(ex, ey)
            iz = np.clip(np.searchsorted(zz, pz)-1, 0, len(zz)-2)
            ia = np.clip(np.searchsorted(aa, theta)-1, 0, len(aa)-2)
            u = np.clip((pz-zz[iz])/(zz[iz+1]-zz[iz]),0,1)
            v = np.clip((theta-aa[ia])/(aa[ia+1]-aa[ia]),0,1)
            # Cubic interpolation with shared slopes, not a stop at each grid node.
            def weights(t):
                return (-.5*t+t*t-.5*t**3, 1-2.5*t*t+1.5*t**3,
                        .5*t+2*t*t-1.5*t**3, -.5*t*t+.5*t**3)
            dr = np.zeros_like(radius)
            for i, wi in enumerate(weights(u)):
                for j, wj in enumerate(weights(v)):
                    dr += wi*wj*table[np.clip(iz+i-1,0,len(zz)-1),
                                      np.clip(ia+j-1,0,len(aa)-1)]
            dr *= (px*sign > 0) * (pz >= zz[0]) * (pz <= zz[-1]) * (theta > 0) * (theta < np.pi/2)
            if self.continuous:
                dr *= step(zz[0],zz[2],pz)*(1-step(zz[-3],zz[-1],pz))
                dr *= step(0,np.pi/12,theta)*(1-step(5*np.pi/12,np.pi/2,theta))
            dr *= step(1.0,3.0,radius)*(1-step(13.,19.,radius))
            dx += dr*ex/np.maximum(radius,1e-9)
            dy += dr*ey/np.maximum(radius,1e-9)

