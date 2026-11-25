from _hip_sweep import *
if __name__=='__main__':
    with sandbox() as (root,ini):
        saved=load_cfg(root); p,faces=geometry(root,ini); h=max(3.,saved_hips(saved))
        a,qa,ea=run_case(root,saved,h,'legacy')
        b,qb,eb=run_case(root,saved,h,'fixed_outer'); report(b)
        if set(a.active)!=set(b.active): raise RuntimeError('Active configuration differs between previews')
        print('Full Body visible draws:',len(a.active),'Hips:',h,'Seam Guard OFF')
        print('Original residual:',ea,'Experimental residual:',eb)
        viewer(p,faces,[('Original',p),('Legacy Hips %.2f'%h,qa),('Fixed contour Hips %.2f'%h,qb)],a.active,'Full Body | experimental improved Hips')
