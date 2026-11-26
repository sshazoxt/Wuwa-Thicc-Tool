from _regional_morph import *

if __name__=='__main__':
    with sandbox() as (root,ini):
        saved=load_cfg(root); p,f=geometry(root,ini); q,d=baseline(root,cfg_for(saved),'Neutral'); r=Region(p,f,d)
        cases=[('Original',p)]
        for label,x,y,z in [('Width X',.30,0.,0.),('Depth Y',0.,.40,0.),('Height Z',0.,0.,.50),('Combined XYZ',.30,.40,.50)]:
            cases.append((label,r.apply(q,r.butt(x,y,z),label)))
        r.show(cases,'18 | Independent gluteal axes',view='right')
    print('===== EXPERIMENT 18 - GLUTES XYZ PREVIEW FINISHED =====')
