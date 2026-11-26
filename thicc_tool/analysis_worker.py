"""Isolated analysis: no Tk calls; result published by parent only on success."""
import sys,pickle,traceback
import thicc_edit as te
if __name__=='__main__':
    try:
        mode=sys.argv[3] if len(sys.argv)>3 else 'diagnose'
        if mode=='diagnose':
            from detection_cache import diagnose
            result=diagnose(sys.argv[1],te.run,te.find_ini,force='--force' in sys.argv[4:])
        elif mode=='dry':
            # Optional reusable baseline for the GUI's Belly-only live requests.
            # Failure to prepare it must never prevent an ordinary Preview.
            from pathlib import Path
            from live_preview import capture_baseline, store_baseline
            baseline={}
            def observe(event,d):
                if event=='before_belly':
                    try: baseline.update(capture_baseline(d))
                    except Exception: print('[Live] Baseline capture unavailable; manual preview continues.')
            result=te.run(sys.argv[1],mode,observer=observe)
            if baseline and isinstance(result,dict) and result.get('preview_positions') is not None:
                try: store_baseline(Path(sys.argv[2]).parent/'belly_baseline.pkl',baseline,sys.argv[1],te.find_ini(sys.argv[1]))
                except Exception: print('[Live] Baseline cache unavailable; manual preview continues.')
        else: result=te.run(sys.argv[1],mode)
        with open(sys.argv[2],'wb') as f: pickle.dump(result,f)
    except BaseException:
        traceback.print_exc(); sys.exit(1)
