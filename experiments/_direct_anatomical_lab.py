"""Experimental in-memory hip field; production engine is not changed."""
import copy
import numpy as np
from scipy.interpolate import PchipInterpolator, CubicHermiteSpline
from morphology.geometry import contour
from _hip_root_lab import isolated


def smooth(t):
    t=np.clip(t,0.,1.)
    return t**3*(10+t*(-15+6*t))


class DirectHip:
    def __init__(self,p,tri,L):
        self.p=np.asarray(p,dtype=float); self.L=dict(L)
        self.lo=L['knee']+.12*(L['hip_z']-L['knee'])
        self.peak=(L['hip_z']+L['crotch'])/2
        self.hi=L['waist']; self.scale=float(L['hip_half'])
        if not self.lo<self.peak<self.hi or self.scale<=0: raise ValueError('Invalid hip landmarks')
        z=np.linspace(L['knee'],self.hi,401); t=self.p[tri]
        bounds=[]
        for h in z:
            c=contour(t,h)
            bounds.append([max(c[:,0]),-min(c[:,0])] if len(c) else [np.nan,np.nan])
        b=np.asarray(bounds); good=np.isfinite(b).all(1)&(b>0).all(1)
        if good.sum()<10 or z[good][0]>self.lo or z[good][-1]<self.hi: raise ValueError('Insufficient closed or open skin contour coverage')
        self.curves=[PchipInterpolator(z[good],b[good,j],extrapolate=False) for j in range(2)]
        x,y,h=self.p.T; self.side=(x<0).astype(int); self.h=h
        hz=np.clip(h,z[good][0],z[good][-1]); w=np.column_stack([c(hz) for c in self.curves]); self.width=w[np.arange(len(x)),self.side]
        r=np.hypot(x,y-L['cy']); self.mask=1-smooth((r-1.35*self.scale)/(.6*self.scale))
        self.envelope=smooth((h-self.lo)/(self.peak-self.lo))*(1-smooth((h-self.peak)/(self.hi-self.peak)))
        self.xfactor=x/np.maximum(self.width,1e-6)*self.mask
        # Depth is a small analytic companion field, not a cached Legacy deformation.
        ux=x/np.sqrt(r*r+(.11*self.scale)**2); uy=(y-L['cy'])/np.sqrt(r*r+(.11*self.scale)**2)
        posterior=smooth((-uy+.75)/1.5)
        self.depthfactor=(.20+.15*posterior)*uy*(.65+.35*ux*ux)*self.mask*smooth((r-.22*self.scale)/(.27*self.scale))
        self.unit=.14265*self.scale  # provisional ratio derived from Suoming Hips 2 reference
        self.base_peak=float(np.max(b[good]))

    def displacement(self,amount,mode='Direct Section'):
        a=float(amount)
        if not np.isfinite(a) or not 0<=a<=5: raise ValueError('Hips must be in 0..5')
        out=np.zeros_like(self.p)
        if a==0: return out
        gain=self.unit*a*self.envelope
        if mode=='Direct Silhouette':
            gain=np.zeros(len(self.p)); alpha=min(a/2.,1.)
            for j,c in enumerate(self.curves):
                ids=(self.side==j)&(self.h>self.lo)&(self.h<self.hi)
                # Blend toward a complete target; exact neutral at 0 and C1 endpoint match.
                top=self.base_peak+.121*self.scale*a/max(alpha,1e-8)
                spline=CubicHermiteSpline([self.lo,self.peak,self.hi],[float(c(self.lo)),top,float(c(self.hi))],[float(c.derivative()(self.lo)),0.,float(c.derivative()(self.hi))])
                gain[ids]=alpha*(spline(self.h[ids])-self.width[ids])
        elif mode!='Direct Section': raise ValueError('Unknown hip mode')
        out[:,0]=gain*self.xfactor
        out[:,1]=self.unit*a*self.envelope*self.depthfactor
        return out


class Lab:
    def __init__(self,session):
        import thicc_edit as te
        self.session=session; self.p=session.original_geometry; self.faces=session.faces; d={}
        self.cfg=isolated(session.saved,0.,0.)
        def obs(event,local):
            if event=='calibrated':
                d.update(L=dict(local['L']),sc=local['sc'],tri=local['skin_tri'].copy(),skin=list(local['SKIN']),active=list(local['reference']['active']),garments=list(local['GARMENTS']))
            if event=='before_waist': d.update(allow=local['allow'].copy(),guard=local['guard'].copy(),arm=local['arm_influence'].copy(),H=float(local['H']))
        te.run(str(session.root),'dry',config_override=self.cfg,observer=obs,prepared_geometry=session.geometry,zero_calibration=True,positions_only=True)
        self.d=d; self.L=d['L']; self.sc=d['sc']; self.mob=d['allow']*d['guard']; self.mob[d['arm']>=.01]=0
        # Precompute the same source-space arm safety ramp once.
        from scipy.spatial import cKDTree
        locked=d['arm']>=.01
        if locked.any():
            distance=cKDTree(self.p[locked]).query(self.p,k=1,workers=-1)[0]
            t=np.clip(distance/np.clip(d['H']*.035,1.,6.),0.,1.)
            self.mob*=t*t*(3-2*t)
        self.visible=[n for n in d['active'] if n in self.faces and len(self.faces[n])]
        self.skin=[n for n in self.visible if n in d['skin']]
        if not self.skin: raise RuntimeError('No active Skin draws')
        from _hip_root_lab import subset_indices
        tri=np.concatenate([self.faces[n] for n in self.skin]); self.tri=tri[subset_indices(tri,d['tri'])]
        self.hip=DirectHip(self.p,self.tri,self.L)
        self.legacy_cache={}; self.other_cache={}
        print('Direct anatomical lab landmarks:',self.L,flush=True)

    def others(self,glutes,thighs,calves):
        import thicc_edit as te
        key=tuple(map(float,(glutes,thighs,calves)))
        if not any(key): return np.zeros_like(self.p)
        if key not in self.other_cache:
            sc=te.Sculpt(dict(hips=0.,butt=key[0],thighs=key[1],calves=key[2]),False)
            sc.set_frame(self.L); sc.axis=self.sc.axis; sc.root=self.sc.root
            # No Hc and no rounding: isolate existing regional fields.
            dx,dy=sc.field(*self.p.T)
            out=np.column_stack((dx,dy,np.zeros(len(dx))))
            self.other_cache.clear(); self.other_cache[key]=out
        return self.other_cache[key]

    def evaluate(self,hips,glutes,thighs,calves,mode='Direct Section'):
        a=np.asarray([hips,glutes,thighs,calves],float)
        if not np.isfinite(a).all() or (a<0).any() or hips>5 or (a[1:]>2).any(): raise ValueError('Slider outside lab range')
        if not a.any(): return self.p.copy()
        q=self.p+(self.hip.displacement(hips,mode)+self.others(glutes,thighs,calves))*self.mob[:,None]
        q[self.mob==0]=self.p[self.mob==0]
        if not np.isfinite(q).all(): raise ValueError('Nonfinite geometry')
        return q

    def legacy(self,hips,glutes,thighs,calves):
        import thicc_edit as te
        cfg=copy.deepcopy(self.cfg); cfg['amounts']=dict(hips=hips,butt=glutes,thighs=thighs,calves=calves)
        r=te.run(str(self.session.root),'dry',config_override=cfg,prepared_geometry=self.session.geometry,positions_only=True)
        return np.asarray(r['preview_positions'],float)

    def report(self,q):
        from _hip_root_lab import profile,quality
        z,b,f,g=profile(self.p,q,self.faces,self.skin,self.L,self.tri)
        print("Peak lateral gain cm:",np.nanmax(g),"peak width cm:",2*np.nanmax(f),"peak gain curvature:",np.nanmax(np.abs(np.diff(g,n=2,axis=0)/(z[1]-z[0])**2)),flush=True)
        quality(self.p,q,self.tri)
        print("All visible surfaces (including garments):",flush=True)
        quality(self.p,q,np.concatenate([self.faces[n] for n in self.visible]))
