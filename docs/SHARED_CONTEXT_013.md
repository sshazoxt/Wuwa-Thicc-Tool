# 013 — Shared Analysis Context

Per-engine-invocation context owns lazy part geometry: validated global triangles, sorted unique vertex IDs, local triangle indices, original points, Z bounds and counts; it also memoizes vertex unions and successful raw bone-buffer loads. Fusion, indexed/welded evidence, Shape, Surface/Surface Relations, ARF and the morphology stage consume the same data. Different welding methods and tolerances remain separate. Regional pair filters remain dependent on pair bounds. No changes to detector weights, role rules, ARF conditions, morphological formulas or viewer.

`AnalysisOptions.debug` defaults to false; the existing diagnostic blocks are retained for future Debug Mode. The legacy WWMI structural report is also disabled in normal analysis; DrawIndexed validation remains mandatory. No GUI Debug control yet. Debug mode is not persisted in detection cache; future GUI wiring must bypass or distinguish normal snapshots.

Context is scoped to a single `run()` and original positions; it is not serialized. Separate analysis worker processes (Analyze, Preview, Apply) still load their own buffers, though existing disk detection/analysis caches remain available. No reuse of derived geometry across modified positions or changed inputs. Raw bone IDs are shared, but stage-specific namespace transformations, skeleton masks, and weld tolerances remain distinct. Cache fingerprints include the context module.

Run `python -m unittest discover -s tests` from repository root. Synthetic tests cover shared object identity, lazy loads, isolation, indexed/welded/Shape/Surface equivalence and bone reuse. Real mods and Windows GUI require validation. No measured real-world speedup claimed.
