# 023 — Modular Morphology Architecture

This is a behavior-preserving refactoring of the production 021 engine and the 022 experimental regional fields. It does not promote the new regional prototypes to production, modify detection weights, change Seam Guard, or alter the existing numerical field composition. The old leg field deliberately remains a coupled thighs/calves operation until regional isolation is validated.

## Production components

- `morphology/geometry.py`: shared plane/triangle intersection.
- `morphology/calibration.py`: original Fixed Core outline selection, eight-step hip calibration, explicit observation and optional experimental outline factory.
- `morphology/glutes.py`, `hips.py`, `legs.py`, `rounding.py`: existing field stages, accumulated in their original order and arithmetic. `Sculpt` remains the compatibility facade in `thicc_edit.py`.
- Existing `waist_morphology.py`, `seam_guard.py`, `clothing_adaptation.py`, `inner_thigh.py`, etc. remain production modules. No new waist/glute XYZ formula is enabled in Apply.
- `morphology/regional.py`: reusable 022 experimental waist, belly, glute XYZ and local thigh operations. Fields are computed on original coordinates; applying them includes the same experimental mobility, clothing, and face-safety handling as 022. `belly` and `glutes` are convenience methods. Section bounds are cached per regional object and slice grid.
- `morphology/engine.py`: `PreviewSession`, `PreparedGeometry`, `MorphologyResult`. Loads original positions, indices, face indices and AnalysisContext once per session; subsequent previews reuse this original geometry and the context's bone and topology caches. It does not yet cache the complete anatomy reconstruction or model-specific calibration across previews.
- `morphology/viewer.py`: shared PyVista viewer with synchronized cameras, explicit camera directions, wireframe and PNG screenshot.

## Experimental API

```python
from morphology import PreviewSession
from morphology.viewer import ExperimentViewer

with PreviewSession(mod_path) as session:
    base = session.preview({"amounts": {"hips": 0, "butt": 0,
                                       "thighs": 0, "calves": 0},
                            "waist_morphology": {"enabled": False}})
    region = session.regional(base)
    center, reliable = region.locate_waist()
    delta = region.belly(center, .35) + region.glutes(.30, .40, .25)
    result = region.apply(base.positions, delta, "Combined")
    ExperimentViewer(session.original_geometry, session.faces,
                     [("Original", session.original_geometry), ("Modified", result)],
                     region.visible).show(view="right")
```

`PreviewSession` defaults to a private temporary copy of the selected mod. `private=False` is reserved for scripts that already own a disposable sandbox. Each preview starts from the original geometry; settings passed to `preview()` override saved settings in memory. Nested dictionaries are replaced, not merged; supply all necessary keys. The session is not an Apply or Restore API. The legacy dry pipeline may create backup/config/cache files in the private copy. Do not mutate the snapshot while a session is active.

The production `run()` supports explicit dry-only observer events (`hip_target_initial`, `hip_target_final`, `hip_iteration_before`, `hip_iteration_clipped`, `hip_iteration_smoothed`, `calibrated`, `before_field`, `after_field`, `before_waist`, `after_waist`). `field_observer` provides cumulative field stages (butt, hips, legs/inner fill, rounding). Callbacks are synchronous and must not mutate their inputs. Existing experiments 09–15 now use these hooks instead of compiling modified copies of `run` and `Sculpt.field_ref`. The older canonical-reference experiment still uses its isolated source-based implementation because reference selection has not yet been modularized. The production calibration/field formulas retain their previous order, including the coupling between Hips and Thighs.

## Viewer

Click inside a comparison window before using shortcuts: 1 Front, 2 Back, 3 Left, 4 Right, 5 Perspective, F Fit (return to initial view), W Wireframe, S high-resolution screenshot (saved in the user's home directory, path printed to console). Cameras are linked; comparisons start in the same view and use common bounds. The 16, 17, 18, 22, 23, 24 experiments start in a side view. Viewer functionality requires PyVista/VTK and still needs Windows validation.

## Experiments

21 API equivalence (direct dry vs session dry on real selected mod); 22 waist multiview; 23 belly multiview; 24 glutes XYZ multiview; 25 regional composition. The experimental runner hides helper scripts beginning with `_` and preserves named completion messages. Existing 16–20 scripts remain compatible; the 022 regional module is now a thin adapter to the shared package.

## Verification

The regression fixture `tests/fixtures/morphology_021.npz` contains synthetic geometry and numeric results produced by the unmodified 021 field and calibration code. Four configurations (legacy, continuous/relative, coupled, continuous/coupled; with varied inner fill, direction and rounding) were compared exactly in the development environment. The test allows 1e-9 absolute tolerance for platform-specific floating point differences. Run `python -m unittest discover -s tests -v` from the project root. 30 tests passed in the development container. Real mod buffers, complete game rendering, and the Windows GUI were not validated here.

## Next stage

Separate full anatomical preparation from preview execution, with explicit dependency-based invalidation of roles, landmarks, buffers and settings. Improve the experimental regional safety limiter and evaluate waist and belly localization from side/front views before enabling new formulas in production. Keep Fixed Core and the current detector pipeline stable.
