from _regional_morph import *

if __name__=='__main__':
    with sandbox() as (root,ini):
        saved=load_cfg(root); p,f=geometry(root,ini); q,d=baseline(root,cfg_for(saved),'Neutral'); r=Region(p,f,d)
        center,valid=r.locate_waist(); lower=max(d['L']['crotch']+.20*r.span,center-.16*r.span)
        cases=[('Original',p)]
        for label,c,w,depth,belly in [('Localized waist',center,.80,.95,0.),('Lower waist trial',lower,.80,.95,0.),('Belly only',center,1.,1.,.35),('Waist + belly',center,.82,.95,.35)]:
            cases.append((label,r.apply(q,r.waist(c,w,depth,belly),label)))
        r.show(cases,'17 | Waist and anterior abdomen',view='right')
    print('===== EXPERIMENT 17 - WAIST BELLY PREVIEW FINISHED =====')
