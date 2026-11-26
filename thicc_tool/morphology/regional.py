"""Experimental regional fields; not enabled in production."""
import numpy as np

def ids_for(faces,names):
    arrays=[faces[n].ravel() for n in names if n in faces]
    return np.unique(np.concatenate(arrays)) if arrays else np.empty(0,dtype=np.int64)

def smooth(t):
    t=np.clip(t,0.,1.); return t**3*(10+t*(-15+6*t))


def bump(z,lo,center,hi):
    if not lo<center<hi: raise ValueError('Invalid regional support')
    return smooth(np.where(z<center,(z-lo)/(center-lo),(hi-z)/(hi-center)))


class Region:
    def __init__(self,p,faces,d):
        self.p=p; self.d=d; self.faces=faces; self.L=d['L']; self.span=self.L['crotch']-self.L['knee']; self._section_cache={}
        if self.span<=0: raise ValueError('Invalid anatomical span')
        self.visible=[n for n in d['active'] if n in faces and len(faces[n])]
        if not self.visible: raise ValueError('Full Body reference unresolved; no active geometry to compare')
        names=[n for n in d['skin'] if n in self.visible]
        if not names: raise ValueError('No active Skin reference')
        self.skin=ids_for(faces,names)
        tri=np.concatenate([faces[n] for n in names]); self.tri=tri[(d['arm'][tri]<.01).all(1)]
        if not len(self.tri): raise ValueError('No non-arm triangles in active Skin')
        self.eligible=ids_for(faces,d['skin']+d['garments'])
        self.mob=np.zeros(len(p)); self.mob[self.eligible]=(d['allow']*d['guard'])[self.eligible]
        self.allfaces=np.concatenate([f for f in faces.values() if len(f)])
        print('Measurement Skin:',names,'| visible draws:',len(self.visible))
        print('Engine landmarks:',self.L)

    def sections(self,zs):
        import thicc_edit as te
        key=tuple(float(z) for z in zs)
        if key in self._section_cache: return self._section_cache[key]
        tr=self.p[self.tri]; out=[]
        for z in key:
            c=te.contour(tr,float(z))
            if len(c)<6: out.append([np.nan]*4)
            else: out.append([c[:,0].min(),c[:,0].max(),c[:,1].min(),c[:,1].max()])
        values=np.asarray(out); values.setflags(write=False); self._section_cache[key]=values
        return values

    def centers(self,zs,z):
        v=self.sections(zs); good=np.isfinite(v).all(1)
        if good.sum()<3: raise ValueError('Insufficient surface cuts for local centers')
        return np.column_stack([np.interp(z,zs[good],v[good,j]) for j in range(4)])

    def locate_waist(self):
        from torso_profile import sections
        L=self.L; g=L['crotch']; s=self.span; w=L['waist']
        lo=g+.25*s; hi=min(g+1.35*s,w+.25*s,float(self.p[self.skin,2].max())-.02*s)
        if hi<=lo: raise ValueError('No valid torso search interval')
        zs=np.linspace(lo,hi,49); profile=sections(self.p,self.tri,zs,s)
        valid=np.array([r is not None and r[0][0] and r[1]==1 for r in profile])
        width=np.array([r[0][2] if ok else np.nan for r,ok in zip(profile,valid)])
        depth=np.array([r[0][3] if ok else np.nan for r,ok in zip(profile,valid)])
        print('Z | closed central section | width | depth')
        for z,v,x,y in zip(zs,valid,width,depth): print('%.3f | %s | %.3f | %.3f'%(z,v,x,y))
        candidates=[]
        for i in range(2,len(zs)-2):
            if not valid[i-2:i+3].all(): continue
            if width[i]<=width[i-1] and width[i]<=width[i+1]:
                left=width[max(0,i-9):i]; right=width[i+1:i+10]
                if np.isfinite(left).any() and np.isfinite(right).any():
                    prominence=min(np.nanmax(left),np.nanmax(right))-width[i]
                    if prominence>0: candidates.append((float(prominence),float(zs[i])))
        print('Waist narrowing candidates (local prominence, model Z):',sorted(candidates,reverse=True))
        if not candidates:
            print('No closed local minimum with support on both sides; using engine waist for experimental comparison only.')
            return w,False
        center=max(candidates)[1]
        print('Experimental waist center:',center,'offset from engine:',center-w)
        return center,True

    def waist(self,center,width=1.,depth=1.,belly=0.):
        p=self.p; z=p[:,2]; L=self.L; s=self.span; g=L['crotch']
        if not g<center: raise ValueError('Waist must be above groin')
        lo=max(g+.08*(center-g),center-.42*s); hi=center+.19*s
        e=bump(z,lo,center,hi)
        bounds=self.centers(np.linspace(lo,hi,25),z)
        xc=(bounds[:,0]+bounds[:,1])*.5; yc=(bounds[:,2]+bounds[:,3])*.5
        out=np.zeros_like(p)
        out[:,0]=(p[:,0]-xc)*(width-1)*e
        out[:,1]=(p[:,1]-yc)*(depth-1)*e
        b0=g+.08*(center-g); b1=g+.57*(center-g); b2=center+.06*(center-g)
        if belly:
            b=self.centers(np.linspace(b0,b2,25),z); cy=(b[:,2]+b[:,3])*.5
            front=smooth((p[:,1]-cy)/np.maximum(.5*(b[:,3]-b[:,2]),1e-6))
            out[:,1]+=belly*.5*(b[:,3]-b[:,2])*bump(z,b0,b1,b2)*front
        print('Waist support %.3f..%.3f center %.3f | width %.3f depth %.3f | belly %.3f center %.3f'%(lo,hi,center,width,depth,belly,b1))
        return out

    def belly(self,center,amount):
        """Anterior abdomen field, with waist scales held neutral."""
        return self.waist(center,1.,1.,amount)

    def glutes(self,width=0.,depth=0.,height=0.):
        return self.butt(width,depth,height)

    def butt(self,width=0.,depth=0.,height=0.):
        p=self.p; z=p[:,2]; L=self.L; s=self.span; g=L['crotch']
        lo=g-.32*s; hi=L['waist']-.12*s
        if hi<=lo: raise ValueError('Invalid gluteal region')
        center=float(np.clip(L['apex'],lo+.25*(hi-lo),hi-.25*(hi-lo)))
        b=self.centers(np.linspace(lo,hi,31),z); xc=(b[:,0]+b[:,1])*.5; yc=(b[:,2]+b[:,3])*.5
        ry=np.maximum(.5*(b[:,3]-b[:,2]),1e-6)
        # In WWMI the original gluteal apex is the negative Y side.
        back=smooth((yc-p[:,1])/(.65*ry)); e=bump(z,lo,center,hi)*back
        out=np.column_stack(((p[:,0]-xc)*width,(p[:,1]-yc)*depth,(z-center)*height))*e[:,None]
        print('Glute support %.3f..%.3f center %.3f | X %.2f Y %.2f Z %.2f'%(lo,hi,center,width,depth,height))
        return out

    def thighs(self,width=.25,depth=.20):
        import thicc_edit as te
        p=self.p; z=p[:,2]; L=self.L; s=self.span; lo=L['knee']; hi=L['crotch']; center=lo+.65*s
        e=bump(z,lo,center,hi); tr=p[self.tri]; zs=np.linspace(lo+.01*s,hi-.01*s,41)
        out=np.zeros_like(p)
        for side in (-1,1):
            vals=[]
            for h in zs:
                c=te.contour(tr,h); c=c[c[:,0]*side>0]
                vals.append([np.nan,np.nan] if len(c)<6 else [(c[:,0].min()+c[:,0].max())*.5,(c[:,1].min()+c[:,1].max())*.5])
            v=np.asarray(vals); good=np.isfinite(v).all(1)
            if good.sum()<3: raise ValueError('Insufficient bilateral thigh cuts')
            ids=np.flatnonzero(p[:,0]*side>0); x=p[ids,0]; y=p[ids,1]
            ax=np.interp(z[ids],zs[good],v[good,0]); ay=np.interp(z[ids],zs[good],v[good,1]); w=e[ids]
            dx=(x-ax)*width*w
            # Preserve side and a fraction of the original medial clearance.
            dx=side*np.maximum(side*dx,-.85*np.abs(x))
            out[ids,0]=dx; out[ids,1]=(y-ay)*depth*w
        print('Thigh independent local-axis support %.3f..%.3f peak %.3f'%(lo,hi,center))
        return out

    def prepare_delta(self,delta):
        from anatomical_transition import blend_at_arm_boundary
        from scipy.spatial import cKDTree
        d=np.asarray(delta,float)*self.mob[:,None]
        # Fade only remote garment geometry; near-surface clothing uses the same field.
        g=np.setdiff1d(ids_for(self.faces,self.d['garments']),ids_for(self.faces,self.d['skin']))
        g=g[np.linalg.norm(d[g],axis=1)>1e-9]
        if len(g):
            dist=cKDTree(self.p[np.unique(self.tri)]).query(self.p[g],k=1)[0]
            d[g]*=(1-smooth((dist-.04*self.span)/(.35*self.span)))[:,None]
        # Apply production arm fade to the added displacement only.
        d=blend_at_arm_boundary(self.p,self.p+d,self.d['arm'],self.d['allow'],self.d['H'])-self.p
        d[self.mob==0]=0
        return d

    def apply(self,base,delta,label):
        d=self.prepare_delta(delta)
        # Do not conceal rejected geometry: report safety backtracking explicitly.
        f=self.allfaces[np.any(np.linalg.norm(d,axis=1)[self.allfaces]>1e-8,axis=1)]
        def normal(q):
            t=q[f]; return np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0])
        n0=normal(self.p); nb=normal(base); an=np.linalg.norm(nb,axis=1)
        good=(np.linalg.norm(n0,axis=1)>1e-9)&(an>1e-9)&(np.sum(n0*nb,axis=1)>0)
        for factor in (1.,.5,.25,.125):
            q=base+factor*d; nn=normal(q)
            bad=good&((np.sum(n0*nn,axis=1)<=0)|(np.linalg.norm(nn,axis=1)<.15*an))
            if not bad.any():
                print(label,'accepted factor',factor,'max XYZ',np.max(abs(q-base),axis=0),'new reversed/near-degenerate faces',int(bad.sum()))
                return q
            print(label,'factor',factor,'rejected faces',int(bad.sum()))
        print(label,'REJECTED; showing base unchanged'); return base.copy()

    def report(self,base,cases):
        print('\n===== REGIONAL METRICS | original model coordinates =====')
        z=self.p[self.skin,2]; L=self.L; zs=np.linspace(L['knee'],L['waist']+.3*self.span,18)
        import thicc_edit as te
        for h in zs:
            c0=te.contour(self.p[self.tri],h)
            if len(c0)<6: continue
            row=[]
            for label,q in cases:
                c=te.contour(q[self.tri],h)
                if len(c)<6: row.append(label+': missing');continue
                row.append('%s: width %+.3f rear %+.3f front %+.3f'%(label,np.ptp(c[:,0])-np.ptp(c0[:,0]),c0[:,1].min()-c[:,1].min(),c[:,1].max()-c0[:,1].max()))
            print('Z %.2f | '%h+' | '.join(row))
        for label,q in cases:
            delta=q-self.p; m=self.d['allow']==0
            print(label,'skin max abs XYZ',np.max(abs(delta[self.skin]),axis=0),'pinned max',np.max(abs(delta[m]),initial=0.))

