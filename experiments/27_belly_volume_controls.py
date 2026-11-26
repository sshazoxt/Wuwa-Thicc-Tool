from _refinement_lab import *
if __name__=='__main__':
    with PreviewSession(os.environ['THICC_MOD_DIR']) as s:
        base,r,c,v=setup(s)
        compare(s,r,v,{'Depth .60':c.belly(.60),'Narrow':c.belly(.60,.65),'Wide':c.belly(.60,1.7),'Tall':c.belly(.60,1,1.35),'Lower':c.belly(.60,1,1,-.12)},'27 | Belly volume')
    print('===== EXPERIMENT 27 - BELLY VOLUME CONTROLS FINISHED =====',flush=True)
