# Thicc Tool — WWMI Morphology Editor

**Free and open-source community tool · Experimental development · Windows x64**

Thicc Tool is a geometry and morphology editor for **Wuthering Waves** mods compatible with WWMI (XXMI). It began as a personal research, programming, and 3D mesh experimentation project, developed as a hobby for the enjoyment of creating, learning, and sharing. It is a non-profit passion project.

## Objective

Thicc Tool aims to make it easier to modify the body proportions of existing mods without requiring advanced 3D modeling skills. Its primary focus is on hips, glutes, waist, thighs, and calves, while preserving surface continuity, anatomical transitions, and compatibility with existing clothing wherever possible.

The tool analyzes local mod files. It is not a game model extractor, a replacement for Blender, or a physics manager. It does not require modifying the game executable. No game models or mods are included in this distribution.

## Features

- **Wardrobe:** DrawIndexed listing, automatic and manual classification into Skin, Clothing, and Frozen roles, custom labels, independent anatomy selection, and visibility controls.
- **3D Viewer:** inspect individual or multiple parts, original and current geometry, comparisons, displacement, and wireframe. Double-click Part to view geometry or Label to edit its name.
- **Morphology:** hip, glute, thigh, and calf controls, along with experimental waist, directional expansion, profile, and regularization options.
- **Measurements:** anatomical references and measurements derived from the analyzed geometry.
- **Preview, Apply, and Restore:** calculate changes without replacing active buffers, explicitly apply modifications, or restore original backups.
- **Library:** reference local mod folders and analyze them in batches without duplicating the mods.
- **Persistent cache:** reuse detection evidence and complete analysis results, including Wardrobe, measurements, and diagnostic logs.
- **Launcher:** Python discovery, isolated dependency installation, environment caching, and a startup screen while the graphics engine initializes.

## Implemented Techniques

### Part Recognition

Part recognition is a selection aid rather than an infallible anatomical classifier. It combines geometric, topological, and skeletal evidence, with a practical emphasis on identifying lower-body regions. Results can be corrected manually in Wardrobe using the integrated 3D viewer.

| Detector | Initial weight |
| --- | ---: |
| Surface Classifier (profiles, continuity, and surface relationships) | 40% |
| Individual Stickman (approximate skeletal reconstruction) | 25% |
| Welded Detection (connectivity through coincident positions) | 12% |
| Shape Recognition (PCA and morphological signatures) | 8% |
| Height and position | 6% |
| Naming | 5% |
| Topological veto | 3% |
| Vertex count | 1% |

The weighted classifier combines positive, negative, and neutral evidence. The topological veto contributes a penalty rather than an absolute exclusion. Components 0, 1, and 2 are treated as front hair, back hair, and face, respectively, by the automatic classifier; this convention is provisional. Manual selections take precedence. The weights are experimental and have been evaluated against a limited set of mods, not universally validated.

### Geometry Engine

The code incorporates regional displacement fields, mesh-derived anatomical references, cross-sectional profiles, interpolation and smooth transitions between regions, seam and vertex protection, and reconstruction of surface information.

It also includes experimental modules for coupled hip-thigh profiles, silhouette calibration, X/Y expansion, waist modification, inner-thigh transitions, arm protection, clothing displacement transfer, Taubin smoothing, and final morphological regularization. Some modules are conditional or mutually incompatible. Their presence in the code does not imply that every combination works correctly: a complete audit of their effect on the final buffer remains pending.

### Caching and Performance

SHA-256 hashes of the code, detectors, classifier, geometry, and relevant configuration are used to invalidate cached results when appropriate. Changes to classifier weights may reuse existing detection evidence; changes to roles or morphology parameters may require new measurements. **Force analyze** rebuilds the analysis without using the main caches.

## Status and Known Limitations

**Distribution version: 007. Experimental project under active development.**

- Correct classification is not guaranteed for every mod, naming convention, variant, or INI structure. Clothing that replaces body geometry can be ambiguous.
- Split bodies, interchangeable variants, and local bone IDs complicate anatomical reconstruction. Static INI analysis does not simulate every in-game state.
- Extreme deformations may cause stretching, irregularities, intersections, inverted triangles, or shading discontinuities. Existing safeguards reduce some risks but do not constitute a complete collision solver.
- Clothing adaptation is approximate; clipping or separation between clothing and the body may occur. Arm protection depends on the available evidence.
- Correct results are not guaranteed across all poses, animations, or lighting conditions.
- Some experimental options require valid anatomical references or specific deformation and shading modes. A functional audit of all controls is pending.
- Only the Normal Bounce mode is implemented; there is no validated dynamic physics editing system.
- Compatibility with all graphics drivers and Windows hardware has not been validated. First startup may take longer due to dependency installation and graphics engine initialization.

## System Requirements

| Requirement | Target minimum | Recommended |
| --- | --- | --- |
| Operating system | Windows 10 1809 (build 17763), x64 | Windows 11 x64 |
| Windows PowerShell | 5.1 | 5.1 (included in supported Windows versions) |
| Python | CPython 3.10 x64 | CPython 3.12 x64 |
| RAM (estimated) | 4 GB | 8 GB or more |
| Free disk space (estimated) | 2 GB | 3 GB or more |
| Graphics | VTK/OpenGL-compatible driver | Up-to-date driver |
| Internet | Initial dependency download | Not required for startup with a valid cache |

The launcher accepts 64-bit Python 3.10, 3.11, and 3.12. Python 3.13 and later are not enabled in this release. Dependency installation and 3D startup have been tested on Windows with Python 3.10.11 x64; this does not certify every combination of Windows, Python, and hardware.

Direct dependencies pinned in `requirements.txt`: NumPy 1.26.4, SciPy 1.15.3, PySide6 6.8.3, PyVista 0.44.2, PyVistaQt 0.11.3, and VTK 9.3.1. Transitive dependencies are resolved by pip.

## Installation

1. Download the source code or distribution package from GitHub and extract it into a local folder with write permissions. Do not run the program directly from the ZIP archive.
2. Run **`Thicc_tool.bat`**. Python is not required to open the graphical launcher.
3. The launcher searches for a compatible interpreter, even if it is not on PATH. If none is found, it offers installation or manual selection options.
4. On the first run, it creates `.venv`, installs and validates dependencies, and saves the environment cache. Progress is displayed in the launcher's bottom console.
5. The launcher starts Thicc Tool and waits for the graphics engine's readiness signal.

Global Python libraries and the system PATH are not modified. Administrator privileges are normally unnecessary. Organizational execution policies may prevent startup.

| File | Purpose |
| --- | --- |
| `Thicc_tool.bat` | Normal startup through the graphical launcher. |
| `Setup_environment.bat` | Check, repair, or rebuild the environment, change Python, and manage its cache. |
| `Launch_direct.bat` | Start without the graphical launcher; requires a working Python environment. |

If the virtual environment stops working after moving the program folder, use the rebuild option. Close the application before repairing or rebuilding its environment.

## Basic Usage

1. Make an independent backup of the entire mod.
2. Use **Browse** to select the folder containing its INI file and `Meshes` directory.
3. Click **Analyze**. A valid cache will be reused; use **Force analyze** to rerun detectors and measurements.
4. Review Wardrobe. Use the 3D viewer to confirm parts and correct Skin, Clothing, Frozen, and Anatomy selections as needed. Save using **Save and analyze**. **Reset automatic** restores automatic suggestions.
5. Adjust Morphology, starting with moderate values. A value of 1.0 represents the baseline contribution of the main controls; 0 disables that contribution, not necessarily all deformation in the region.
6. Use **Preview (no buffer writes)** and review diagnostics before applying. Preview may save configuration, caches, or create backups, but does not replace active buffers.
7. Click **Apply to mod** to write geometry. Reload the mod in-game (usually F10 in WWMI) and inspect the result in different poses.
8. **Restore original** restores Position.buf and Vector.buf from their `.orig` backups. It does not restore the INI or remove saved settings.

### Files Created or Modified Inside a Mod

```text
MyMod/
├── mod.ini                        # Existing INI (filename may vary)
├── mod.ini.wardrobe.bak           # Initial INI backup when visibility is changed
├── thicc.json                     # Mod settings, labels, and roles
├── thicc_detection_cache.json     # Detection evidence and automatic classification
├── thicc_analysis_cache.json      # Complete analysis, measurements, and console log
├── thicc_shape_cache.json         # Shape recognition cache, when used
├── .thicc_surface_cache.json      # Surface evidence cache, when used
└── Meshes/
    ├── Position.buf              # Existing buffer; Apply may modify it
    ├── Vector.buf                # Existing buffer; Apply may modify it
    ├── Position.buf.orig         # Position backup before modification
    └── Vector.buf.orig           # Surface information backup
```

The actual backup extension is **`.orig`**, not `.org`. Backups are created if absent when deformation operations are run (including Preview). Subsequent modifications start from the original backups to avoid accumulating deformation. Do not delete or replace these backups unless you know exactly which geometry they contain. If the first backup was made from an already modified mod, it may not represent the mod author's original geometry.

Cache files can be deleted and regenerated. `thicc.json` is not a cache: deleting it removes saved settings. **Show / hide** can modify the INI; restoring it requires manually recovering the corresponding backup while accounting for subsequent changes. Internal backups are not a substitute for a full mod backup.

### Files Generated in the Thicc Tool Folder

| File or directory | Purpose |
| --- | --- |
| `.venv/` | Isolated Python environment. |
| `thicc_environment_cache.json` | Environment validation and version information. |
| `thicc_tool_settings.json` | Preferences and local mod library paths. |
| `logs/` | Installation and startup logs. |
| `.venv.backup-*/` | Environment backups created during rebuilds. |

Do not publish personal or generated data, or third-party mod buffers or INI files without authorization.

## Roadmap and Pending Work

- Improve recognition of partial body meshes, alternative variants, and complementary components without relying on fixed character measurements.
- Refine detection weights using more visually verified samples.
- Audit the complete path of every Morphology parameter to the final vertices; repair or remove ineffective controls.
- Improve curve continuity, extreme-range deformation, hip-thigh transitions, knees, and inner-leg contact.
- Improve clothing adaptation, arm displacement, and shading preservation; investigate more accurate collision detection.
- Extend upper-body morphology editing (abdomen, chest, shoulders, and arms) and independent three-dimensional controls.
- Explore graphical silhouette curve editing, presets, and comparison tools.
- Expand testing across Windows systems, hardware, Python versions, and real mods; improve documentation and usability.

Not all of these future features are implemented, and no delivery dates are committed.

## Contributions and Bug Reports

Suggestions, fixes, and contributions are welcome. When reporting an issue, include the Thicc Tool version, Windows version, Python version, reproduction steps, relevant parameters, and diagnostic output. Remove personal paths and any information you do not wish to publish. Avoid attaching third-party assets without permission. Use GitHub Issues or Pull Requests.

## License and Project Philosophy

Thicc Tool is an independent project created and maintained by its developer as a hobby, without a profit motive, for the love of art, programming, and learning.

The original Thicc Tool code is distributed under the **MIT License** (see [LICENSE](LICENSE)). You are free to use, study, modify, and redistribute it under the terms of that license. The license does not prohibit commercial use by third parties. Credit and sharing improvements with the community are appreciated, but contributing is not mandatory.

Dependencies and third-party materials retain their respective licenses and rights. The Thicc Tool license does not grant rights to game assets, other people's mods, trademarks, illustrations, or external libraries.

## Independence and Responsible Use

Thicc Tool is an **unofficial** community tool and is not affiliated with, sponsored by, or endorsed by Kuro Games, WWMI, or XXMI. Wuthering Waves, its assets, and its trademarks belong to their respective owners. External project names are used solely to identify compatibility.

The software is provided as is, without warranty, in accordance with its license and applicable law. Its use may alter local files; maintain backups and review the applicable terms of the game, mods, and any resources you use. Compatibility with the game, its updates, and account policies is not guaranteed.

If a rights holder believes any material in this repository requires review, they may contact the maintainer through GitHub. Requests will be reviewed and addressed as appropriate.

References: [Wuthering Waves — derivative works guidelines](https://wutheringwaves.kurogames.com/p/en/produce.html) · [MIT License](https://choosealicense.com/licenses/mit/).
