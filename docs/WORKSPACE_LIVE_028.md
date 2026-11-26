# 028 — Workspace and bounded live preview

Requires patch 027. No new dependencies. Production deformation formulas, Belly parameters, Apply, Restore and Wardrobe roles are unchanged.

## Workspace
- Wardrobe, Morphology and Measurements share the left tab panel.
- The right 3D viewer stays mounted when switching tabs. Splitters resize both panels and the diagnostic console; the console can be collapsed while its actions remain visible.
- Morphology groups Pelvis, Legs and Abdomen. Existing extra controls are in the collapsible Advanced morphology settings section. Preview, Apply, Restore and Live Preview are outside the tabs.
- Panel sizes, selected tab and console state persist in the existing settings JSON. A matching viewport retains its camera position and projection when refreshed; a different part selection fits normally.

## Live Preview
Enable Live Preview after a successful Analyze. A changed slider starts a single 600 ms timer only after release; further edits reset it. Keyboard/spinbox changes use the same idle delay. A click with no changed value does not normally launch a new preview. There is no periodic preview loop.

The isolated child uses a temporary snapshot of only the relevant INI, mesh buffers and detector cache, and a copy of the current unsaved UI configuration. It returns positions only, bypassing final reporting and vector/shading computation. It never writes the source mod, its configuration or originals. Apply still runs the full production pipeline and writes only after the existing confirmation.

Only one automatic job runs at a time. New edits invalidate the previous generation; obsolete results are discarded. Analyze, manual Preview, Apply, Restore, Wardrobe changes and Experiments invalidate the live job. A file signature check also rejects results after detected external source changes. The GUI's normal modal operations retain their existing behavior.

The automatic calculation is killed when the two-second budget expires (40 ms polling granularity). Rendering is included in an end-to-end timing check but cannot safely be interrupted once the Qt/VTK render starts. If the budget is exceeded, Live Preview disables itself and manual Preview remains available. The 600 ms idle delay is separate. Large mods may not be fast enough for automatic previews, especially when changing Hips/Thighs/Glutes/Calves. No exact two-second real-model performance claim is made.

An ordinary manual Preview creates a private temporary pre-Belly baseline for the current mod/configuration; the next live request can reuse it if only Belly changed and the source signature still matches. This invokes the exact production Belly function, not an approximation. Other changes invalidate the shortcut and require full calculation. A successful full live request also stores a baseline. If baseline capture fails, ordinary Preview still completes. Temporary caches are not part of the mod and are removed on clean shutdown. The renderer updates matching mesh point arrays in-place where possible and preserves camera/zoom.

Console logs include parameters, worker computation time and total display time. To validate on Windows: run Analyze, manual Preview, enable Live Preview, change Belly, then independently test Hips/Thighs and observe the timings. Test a long drag, an unchanged click, rapid repeated edits, switching tabs, manual Apply and Restore. Check that no live result writes buffers and that the final preview matches manual Preview for identical settings. GUI/VTK and real-mod performance were not available in the development environment.
