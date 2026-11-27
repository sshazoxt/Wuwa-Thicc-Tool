# 029 — Experiment Workspace

Install over 028. No morphology equations or Live Preview code changed.

Experiments tab: select a row and Run selected for the legacy interactive workflow; check multiple rows, move them up/down, then Run automated. The diagnostic-log Experiments button now opens the tab. Cancel stops the current process and remaining queue; interactive writer 32 must be closed normally. The parent window remains enabled and its own Analyze/Preview/Apply process state is separate. While 32 is open, Apply/Restore of its source mod is blocked in the main window. An open experiment run prevents exiting the main application until completion/cancellation.

Batch mode takes one private snapshot of Meshes, root INIs and saved configuration/detection cache. It is shared as the source for the scripts in this run; existing diagnostic scripts make their own working copies. Changes in the real mod after snapshot creation are not reflected in the run. Unsaved sliders are not passed to older scripts; 32 still receives current GUI settings. A source change during copying (file size or mtime) aborts snapshot creation. This is not a security sandbox for arbitrary Python; only execute trusted scripts. No textures are copied.

The subprocess wrapper sets THICC_EXPERIMENT_MODE=legacy or batch. In batch it intercepts conventional pv.Plotter.show(), renders offscreen at twice the configured dimensions, saves a numbered PNG and closes the plotter. It does not automate arbitrary GUI dialogs. 31 and 32 are interactive-only and rejected in batch mode. Custom GUI scripts must implement batch behavior explicitly using THICC_EXPERIMENT_MODE and THICC_EXPERIMENT_OUTPUT. Cancel is available if an unsupported script blocks. Rendering requires a working VTK/OpenGL backend.

Outputs: experiment_results/YYYY-MM-DD_HH-MM-SS_microseconds - Experiment Results/ contains run.json, console.txt, summary.json, numbered PNGs. Each subprocess gets a completion marker with its name, exit code and elapsed time. Queue continues after individual script errors, except launch failures; stop cancels remaining scripts. Sounds use QApplication.beep (subject to OS sound settings). The main console may contain interleaved main-tool messages; the batch console.txt contains only experiment output. Results persist after private model cleanup.

Default workspace ratio 2:1; previously saved splitter sizes take precedence. To use new defaults after an existing saved layout, adjust the splitter once.

Validation: 52 unittest cases passed; three added tests use temporary files and mocked PyVista, not actual VTK/Qt windows. Windows visual, concurrency and screenshot checks remain required. Run a small batch 09, 10, 14 before longer runs. No regression fix for Hips/Thighs is included.
