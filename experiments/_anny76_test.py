"""Synthetic transfer sanity check (no Anny or GUI required)."""
import numpy as np
from _anny76_transfer import Transfer

def main():
    z,theta=np.meshgrid(np.linspace(0,120,241),np.linspace(0,2*np.pi,64,endpoint=False)); p=np.stack((15*np.cos(theta),10*np.sin(theta),z),-1).reshape(-1,3)
    L=dict(knee=30,crotch=60,waist=90,hip_half=15,cy=0); ref=dict(knee=.3,crotch=.6,waist=.9,half_width=.15,half_depth=.10)
    base=p/100.; mobility=np.ones(len(p)); mobility[p[:,2]>100]=0
    t=Transfer(p,base,L,ref,np.arange(len(p)),mobility)
    assert np.array_equal(t.apply(base),p)
    target=base.copy(); target[:,0]+=0.03*np.cos(theta).ravel()*np.exp(-((z.ravel()-60)/20)**2)
    q=t.apply(target); assert np.array_equal(q[mobility==0],p[mobility==0]); assert np.isfinite(q).all(); assert np.max(abs(q[:,0]-p[:,0]))>2.9
    print('EXPERIMENT 76 - SYNTHETIC TRANSFER TEST COMPLETED')
if __name__=='__main__':main()
