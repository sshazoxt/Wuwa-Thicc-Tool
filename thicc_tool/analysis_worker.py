"""Isolated analysis: no Tk calls; result published by parent only on success."""
import sys,pickle,traceback
import thicc_edit as te
if __name__=='__main__':
    try:
        mode=sys.argv[3] if len(sys.argv)>3 else 'diagnose'
        if mode=='diagnose':
            from detection_cache import diagnose
            result=diagnose(sys.argv[1],te.run,te.find_ini,force='--force' in sys.argv[4:])
        else: result=te.run(sys.argv[1],mode)
        with open(sys.argv[2],'wb') as f: pickle.dump(result,f)
    except BaseException:
        traceback.print_exc(); sys.exit(1)
