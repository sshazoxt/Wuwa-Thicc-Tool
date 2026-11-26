import os
import numpy as np
from morphology import PreviewSession
from morphology.viewer import ExperimentViewer
from morphology.refinement import RegionalControls, FieldComposer
from _regional_morph import cfg_for

def setup(session,hips=0):
    base=session.preview(cfg_for(session.saved,{'hips':hips})); r=session.regional(base); center,_=r.locate_waist()
    return base,r,RegionalControls(r,center),FieldComposer(r,base.positions)

def show(session,r,cases,title,view='right',focus='torso',overlays=None,skin=True):
    L=r.L; s=r.span
    bounds={'torso':(L['crotch']-.2*s,L['waist']+.45*s),'pelvis':(L['crotch']-.5*s,L['waist']+.1*s),'legs':(0,L['waist']),'full':None}[focus]
    names=[n for n in r.visible if n in r.d['skin']] if skin else r.visible
    ExperimentViewer(session.original_geometry,session.faces,cases,names,title).show(view=view,columns=3,focus=bounds,overlays=overlays)

def compare(session,r,composer,fields,title,view='right',focus='torso'):
    cases=[('Baseline',composer.base)]
    for name,d in fields.items():
        q,f,_=composer.compose({name:d}); cases.append((f'{name} | {f[name]:.0%}',q))
    r.report(composer.base,cases); show(session,r,cases,title,view,focus)
