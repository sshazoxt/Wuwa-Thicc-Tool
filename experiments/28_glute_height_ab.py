from _refinement_lab import *
if __name__=='__main__':
    with PreviewSession(os.environ['THICC_MOD_DIR']) as s:
        base,r,c,v=setup(s)
        compare(s,r,v,{'XY':r.glutes(.3,.4,0),'Vertex Z':r.glutes(.3,.4,.5),'Volume height 1.35':c.glute_volume(.3,.4,1.35),'Volume height 1.65':c.glute_volume(.3,.4,1.65)},'28 | Glute height A/B',focus='pelvis')
    print('===== EXPERIMENT 28 - GLUTE HEIGHT AB FINISHED =====',flush=True)
