"""Independent Anny displacement transfer, without DS field/envelope/gain."""
import json,subprocess,tempfile,sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.interpolate import PchipInterpolator

class NativeAnny:
    def __init__(self,python):self.python=str(python);self.p=None;self.tmp=tempfile.TemporaryDirectory(prefix='anny77-')
    def wait(self,marker):
        while True:
            line=self.p.stdout.readline()
            if not line:raise RuntimeError('Anny worker exited: '+str(self.p.poll()))
            if line.strip()==marker:return
            if line.strip()=='ANNY77_ERROR':raise RuntimeError('Anny worker failed; see console')
            print(line.rstrip(),flush=True)
    def generate(self,values):
        if self.p is None:
            self.p=subprocess.Popen([self.python,'-u',str(Path(__file__).with_name('_anny77_worker.py'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
            self.wait('ANNY77_READY')
        out=Path(self.tmp.name)/'reference.npz'
        self.p.stdin.write(json.dumps(dict(values=values,output=str(out)))+'\n');self.p.stdin.flush();self.wait('ANNY77_OK')
        with np.load(out) as f:return f['base'],f['target'],f['faces']
    def close(self):
        if self.p is not None:
            try:
                self.p.stdin.write('{"close":true}\n');self.p.stdin.flush();self.p.wait(timeout=3)
            except (OSError,subprocess.TimeoutExpired):self.p.kill();self.p.wait()
            self.p.stdout.close();self.p.stdin.close()
        self.tmp.cleanup()

class Transfer:
    def __init__(self,p,base,L,reference,skin_ids,mobility,anatomical_top=None):
        self.p=np.asarray(p,float);self.base=np.asarray(base,float);self.mobility=np.asarray(mobility,float)
        if not np.isfinite(self.mobility).all() or len(self.mobility)!=len(p):raise ValueError('Invalid mobility')
        # Align anatomical heights, not vertex indices; reference and mod topology differ.
        a=np.array([L[k] for k in ('knee','crotch','waist')],float)
        b=np.array([reference[k] for k in ('knee','crotch','waist')],float)
        if min(np.diff(a))<=0 or min(np.diff(b))<=0:raise ValueError('Invalid anatomical landmarks')
        z=p[:,2]
        v=p[np.asarray(skin_ids,int)]
        top=float(anatomical_top if anatomical_top is not None else v[:,2].max())
        ref_top=float(base[:,2].max())
        if top>a[-1] and ref_top>b[-1]:
            a=np.r_[a,top]; b=np.r_[b,ref_top]
        f=PchipInterpolator(a,b,extrapolate=False); zz=np.clip(z,a[0],a[-1])
        slope=np.maximum(f.derivative()(zz),.05*min(np.diff(b)/np.diff(a)))
        rz=f(zz)+(z-zz)*slope
        # Reference hip section; robustly exclude arm samples by central torso proximity.
        band=np.abs(base[:,2]-b[1])<.035*(b[2]-b[0]); q=base[band]
        if len(q)<12:raise ValueError('Insufficient Anny hip reference')
        cx=float(np.median(base[:,0])); rx=float(reference['half_width']); ry=float(reference['half_depth'])
        q=q[np.abs(q[:,0]-cx)<1.1*rx]
        if not len(q):raise ValueError('Missing central reference samples')
        cy=float((q[:,1].min()+q[:,1].max())/2)
        v=p[np.asarray(skin_ids,int)]; vb=v[np.abs(v[:,2]-a[1])<.035*(a[2]-a[0])]
        vb=vb[np.abs(vb[:,0])<1.3*float(L['hip_half'])]
        if len(vb)<12:raise ValueError('Insufficient mod hip reference')
        sx=float(np.max(np.abs(vb[:,0])))/rx; sy=float(np.ptp(vb[:,1])/2)/ry
        if min(sx,sy)<=0 or not np.isfinite([sx,sy]).all():raise ValueError('Invalid reference scale')
        mapped=np.column_stack((p[:,0]/sx+cx,(p[:,1]-float(L['cy']))/sy+cy,rz))
        self.ids=np.flatnonzero(self.mobility>0)
        dist,near=cKDTree(base).query(mapped[self.ids],k=8,workers=-1)
        weights=1/np.maximum(dist,1e-8)**2; weights/=weights.sum(axis=1,keepdims=True)
        self.near=near;self.weights=weights;self.scale=np.column_stack((np.full(len(z),sx),np.full(len(z),sy),1/slope))[self.ids]
        print('Anny77 transfer: reference vertices',len(base),'eligible',len(self.ids),'scale X/Y',sx,sy,'nearest distance p50/p95',np.quantile(dist[:,0],[.5,.95]) if len(dist) else [],flush=True)
    def apply(self,target):
        target=np.asarray(target,float)
        if target.shape!=self.base.shape:raise ValueError('Anny topology changed')
        delta=target-self.base
        d=np.sum(delta[self.near]*self.weights[:,:,None],axis=1)*self.scale
        out=self.p.copy();out[self.ids]+=d*self.mobility[self.ids,None]
        if not np.isfinite(out).all():raise ValueError('Invalid transferred geometry')
        return out
