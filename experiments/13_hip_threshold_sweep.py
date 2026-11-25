from _hip_sweep import *
if __name__=='__main__':
    with sandbox() as (root,ini):
        saved=load_cfg(root); results=[]
        for h in sorted(set([.5,1,1.25,1.5,1.75,2,2.5,3,4,5,saved_hips(saved)])):
            mon,q,err=run_case(root,saved,h,'legacy'); results.append((h,err, next((i+1 for i,r in mon.gaps.items() if r),None)))
        print('\nHips | residual ref cm | first iteration with legacy contour cut')
        for row in results: print(*row,sep=' | ')
