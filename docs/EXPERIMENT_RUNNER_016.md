# Experiment runner 016
Place trusted Python diagnostic scripts in `experiments/`. The `tests/` regression suite is unchanged. Click Experiments beside Copy and Clear. Scripts run in a separate Python process, working directory `experiments/`, with the engine on PYTHONPATH and stdout/stderr streamed to the log. Environment: THICC_MOD_DIR, THICC_INI, THICC_ENGINE_DIR, THICC_EXPERIMENT_DIR. THICC_TEST_DIR remains a compatibility alias for existing scripts.

## Upgrade from 015
Extract the patch at repository root. Move any custom scripts from `test/` into `experiments/`, then remove the old `test/` directory, `thicc_tool/test_runner.py` and optionally `docs/TEST_RUNNER_015.md`. ZIP extraction cannot remove old files. Do not remove `tests/`. No engine changes. Scripts have normal filesystem permissions; no shared in-memory context.
