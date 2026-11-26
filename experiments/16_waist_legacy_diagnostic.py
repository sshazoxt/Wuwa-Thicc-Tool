from _regional_morph import *

if __name__=='__main__':
    with sandbox() as (root,ini):
        saved=load_cfg(root); p,f=geometry(root,ini)
        q0,d=baseline(root,cfg_for(saved),'Waist OFF')
        r=Region(p,f,d); r.locate_waist()
        cases=[('Original',p),('Waist OFF',q0)]
        for label,w,h in [('Legacy width 0.75',.75,1.),('Legacy depth 1.35',1.,1.35)]:
            q,e=baseline(root,cfg_for(saved,waist=dict(enabled=True,width=w,depth=h)),label)
            diff=e['after_waist']-e['before_waist']; ids=np.flatnonzero(np.linalg.norm(diff,axis=1)>1e-5)
            print(label,'stage max XYZ',np.max(abs(diff),axis=0),'actual support Z', (p[ids,2].min(),p[ids,2].max()) if len(ids) else 'none')
            cases.append((label,q))
        r.show(cases,'16 | Legacy waist diagnostics',view='right')
    print('===== EXPERIMENT 16 - WAIST LEGACY DIAGNOSTIC FINISHED =====')
