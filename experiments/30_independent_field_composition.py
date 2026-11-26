from _refinement_lab import *
if __name__=='__main__':
    with PreviewSession(os.environ['THICC_MOD_DIR']) as s:
        base,r,c,v=setup(s,2.5)
        fields={'Waist':c.waist(.82,.95),'Belly':c.belly(.35),'Glutes X':r.glutes(.3,0,0),'Glutes Y':r.glutes(0,.4,0),'Thighs':r.thighs(.3,.2),'Glutes Z':r.glutes(0,0,.5)}
        old=r.apply(base.positions,np.sum(list(fields.values()),axis=0),'Global backtracking'); q,f,_=v.compose(fields); print('Independent factors:',f)
        alt=dict(fields); alt.pop('Glutes Z'); altq,af,_=v.compose(alt)
        cases=[('Hips baseline',base.positions),('Global',old),('Independent',q),('Independent no Z',altq)]
        r.report(base.positions,cases); show(s,r,cases,'30 | Independent field composition',view='back',focus='pelvis')
    print('===== EXPERIMENT 30 - INDEPENDENT FIELD COMPOSITION FINISHED =====',flush=True)
