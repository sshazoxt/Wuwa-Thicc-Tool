"""Controlled follow-up of experiment 45; all changes are experiment-local."""
import numpy as np
from _hip_root_lab import run, view, compare, report_profile
from _relative_field_lab import trial
from preview_no_seam_guard import sandbox, geometry, load_cfg
from experiment_parameters import experiment_amounts

TITLES={49:'HIP TARGET FACTOR ISOLATION',50:'HIP FIELD TERM ISOLATION',51:'HIP-THIGH TARGET COUPLING'}

def case_plan(num,h,t):
    if num==49:
        return [('Legacy',set(),h,0.),('Anatomical gain',{'target'},h,0.),('Relative mix only',{'relative_mix'},h,0.),('No hip floor',{'no_floor'},h,0.),('Gain + relative mix',{'target','relative_mix'},h,0.)]
    if num==50:
        return [('Legacy',set(),h,0.),('Linear lateral',{'linear_lateral'},h,0.),('No depth',{'no_hip_depth'},h,0.),('Anatomical gain',{'target'},h,0.),('Gain + linear lateral',{'target','linear_lateral'},h,0.)]
    if num==51:
        return [('Legacy combined',set(),h,t),('Anatomical gain',{'target'},h,t),('Gain + relative mix',{'target','relative_mix'},h,t),('Gain + hip-only target',{'target','hip_only_target'},h,t),('Gain + both changes',{'target','relative_mix','hip_only_target'},h,t)]
    raise ValueError(num)

def execute(num):
    with sandbox() as (root,ini):
        p,faces=geometry(root,ini); saved=load_cfg(root)
        a=experiment_amounts(saved,{'hips':3.98,'thighs':2.}); h,t=a['hips'],a['thighs']
        print('Selected input Hips:',h,'Thighs:',t,'No post smoothing; isolated experimental controls.')
        cases=[('Original',p)]; base=None
        for name,flags,ha,ta in case_plan(num,h,t):
            with trial(flags): q,d=run(root,p,faces,saved,hips=ha,thighs=ta)
            if base is None: base=q; first=d
            else: compare(base,q,name)
            report_profile(p,q,faces,d,name)
            print('TARGET',name,'Z ref | original outline | desired outline | attained outline | Hc')
            for z,b,tgt,actual,hc in zip(d['zs'],d['baseline'],d['target'],d['actual'],d['hc']):
                print(f'{z:.3f} {b:.5f} {b+tgt:.5f} {b+actual:.5f} {hc:.5f}')
            cases.append((name,q))
        view(p,faces,cases,first,f'{num} | {TITLES[num]}')
    print(f'===== EXPERIMENT {num} - {TITLES[num]} FINISHED =====',flush=True)
