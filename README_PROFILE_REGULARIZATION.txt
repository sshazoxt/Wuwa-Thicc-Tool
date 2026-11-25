THICC TOOL - PROFILE REGULARIZATION V2 (EXPERIMENTAL)

Replace thicc_edit.py, thicc_tool_gui.pyw and final_regularization.py
with the files from this ZIP. Make a backup first.

Change: local Taubin smoothing in the final module is replaced by a large-scale
spatial adjustment of displacements (height and angle around each side of the
body), with safeguards against new triangle inversions.

Other deformation fields are not altered. The interface and parameters remain.
Test with Strength=1.00 and Noise tolerance=0.00 to evaluate the maximum effect.

LIMITATION: if the mesh already has inverted triangles, the safety control
may greatly reduce the final effect. Check the 'fallback scale' message in the log.
The code was tested with available real buffers containing 81632 vertices, but
it has not been verified that they are exactly those from the last in-game test.
