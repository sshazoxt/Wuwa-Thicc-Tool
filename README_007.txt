THICC TOOL 007 - WINDOWS DISTRIBUTION / LAUNCHER
================================================
Minimum target: Windows 10 1809 (build 17763) or later, x64, Windows
PowerShell 5.1. Windows 11 recommended. CPython 3.10, 3.11, 3.12 x64
accepted; 3.12 preferred for new installations. Python 3.13+ is deliberately
not enabled in this first distribution baseline. Use a writable local folder.
Internet required on initial package download; subsequent valid-cache starts
work offline. Allow at least 2-3 GB for environment and installation files.
The graphics driver must support the VTK/OpenGL viewer; actual GPU and OS
compatibility must be checked on Windows.

START
1. Extract the complete ZIP to a writable folder. Keep all files together.
2. Run Thicc_tool.bat. No Python is needed to open the graphical launcher.
3. On first launch it discovers a suitable interpreter, creates .venv and
   installs the pinned packages. The four-line console shows live progress.
4. If no Python is found, approve optional winget installation, or open the
   official Python download page or select an existing interpreter manually.
   If installing manually, rerun the BAT afterwards. No PATH change required.
5. The launcher remains until the main window is shown and viewer warm-up
   finishes. A failed viewer warm-up is reported; the main tool can retry it.

MAINTENANCE
Setup_environment.bat opens a menu: Check/install, Repair, Change Python,
Rebuild, Info, Clear cache, Launch. Close Thicc Tool before repair/rebuild.
Rebuild renames an existing .venv to a backup folder rather than deleting it.
After verifying a new environment, old .venv.backup-* directories can be
removed manually to recover disk space. A venv is not portable between folders;
rebuild if the tool folder moves or the base interpreter changes.
Launch_direct.bat bypasses the splash, using the existing venv or a manually
selected Python executable. It does not install or validate packages.

CACHE
thicc_environment_cache.json stores requirements/setup hashes, selected
interpreter, fingerprints of the base interpreter and venv executables,
pyvenv.cfg hash, direct package versions and essential module paths.
Valid cache avoids package imports and pip commands in the launcher. Deleting
an essential module invalidates it; arbitrary package corruption may require
Repair. This cache is independent of the per-mod detection/analysis caches.
Environment setup writes logs under logs/. Open log on error. The startup
handshake uses a unique temporary file, not a shared ready.flag. A timeout
reports an error without killing an application that may still be starting.
No global pip install, no system PATH changes, no persistent PowerShell
execution-policy changes. Enterprise policies may still block scripts.

DISTRIBUTION
Direct dependency versions are pinned in requirements.txt; transitive packages
are resolved by pip. The version combination is a candidate baseline, not a
Windows-certified lockfile. First install uses binary wheels only; import and
pip check tests must pass before writing the setup cache. Actual Windows
execution, winget install, and 3D graphics startup remain to be tested.
No .venv, logs, user paths, or generated cache are bundled. The original
personal mod library settings were replaced by empty defaults.
When updating an existing installation, keep the user's thicc_tool_settings.json
and .venv if compatible; copy new code and launcher files into the same folder.
Cover art supplied by the user, resized to 960x540 JPG with title overlay.
Original Wuthering Waves logo and Kuro Games notice retained. Verify permission
to redistribute the cover and existing icon before public distribution.
