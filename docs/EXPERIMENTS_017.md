# Morphology investigation experiments (016 compatible)

Copy `experiments/` into the project root. No engine or GUI files are replaced.
Save the desired wardrobe roles and sliders first (normal Preview suffices).
Select the individual mod, then use Diagnostic log > Experiments.

1. `preview_no_seam_guard.py`: two production dry runs on a private temporary copy, forcing seam_guard ON then OFF. Prints lower-body lateral p95 and A/B displacement per band and most affected parts. Opens a separate PyVista window showing default-active Skin with linked cameras; close it to finish. No preview is injected into the main GUI.
2. `skin_overlap_report.py`: uses effective roles from production diagnosis; compares Skin/Skin and Skin/Frozen, shared buffer IDs, nearest vertex distances, Z bands and coordinate-quantized identical triangles. Proximity and quantized duplicates are not a general triangle-triangle intersection test. Default INI activation is not live game visibility.
3. `phase_displacement_breakdown.py`: two dry runs tracing actual production statements; reports each existing geometry stage in order. Initial combined field is not split into individual slider contributions. Source anchors are validated before execution; future engine edits may require updating the experiment.

All use saved thicc.json, original Position.buf.orig when present, and isolated copies of Meshes, selected INI and saved configuration/cache. No writes to the source mod, engine or original cache. Temporary copies are removed on normal exit; forced process cancellation can leave a thicc-experiment-model-* directory in the system temporary directory. Texture files are not needed for these geometry-only tests. If original backup is missing, engine uses current buffers as its baseline. The scripts require the installed engine and existing NumPy/SciPy/PyVista environment. No additional packages.

Validation: Python syntax, source anchor matching against 014 engine, synthetic overlapping triangle and reversed winding. Full real-mod pipeline and GUI preview need verification on Windows with the mod buffers.
