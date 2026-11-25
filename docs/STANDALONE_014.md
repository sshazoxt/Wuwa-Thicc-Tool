# 014 — Standalone component guards

Offline reconstruction assumes an unknown simple external scalar guard active only if it is a top-level if enclosing every direct draw in the component, has no alternative branch, and its variable is neither declared in Constants nor referenced by a Key section. Local variant conditions remain evaluated normally. No INI writes or external namespace access. This is a heuristic, not a game runtime emulator. CommandList-only draws and compound predicates are not inferred. The INI finder excludes filenames containing DISABLED case-insensitively.

Tested against mod(5).ini (10 active of 14, zero unresolved) and mod2.ini (32 active of 59, zero unresolved; existing custom shader warning). Five synthetic guard tests. Surface All-NaN and ARF upper coverage unknown are outside this patch.
