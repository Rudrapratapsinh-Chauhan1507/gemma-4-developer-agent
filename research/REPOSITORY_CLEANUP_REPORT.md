# Repository Cleanup Report

## 1. Current vs Recommended Final Tree
**Current Tree (messy root):** Contains multiple untracked `build_v*.py` scripts, generated `submission_*.zip` files, and various candidate directories (`submission_v*`).
**Recommended Tree:**
- Root remains clean with only core Python execution scripts (`run_*.py`).
- Build scripts move to `scripts/build/`.
- Generated ZIPs and candidate folders are locally preserved but ignored via `.gitignore` to prevent repository pollution.
- Research materials and index stored in `research/`.

## 2. File-by-File Classification
- **Keep Tracked**:
  - `mini_swe_agent/`, `tests/`, `sandbox/` (Core codebase).
  - `run_demo.py`, `run_demo_stage2.py`, `run_evaluation_stage2.py`, `run_evaluation_stage4.py` (Execution entry points left in root to preserve `sys.path` and import structures).
  - `submission/` (Active working directory for the baseline submission configuration).
- **Move and Update References**:
  - `build_v4.py`, `build_v6.py`, `extract_notebooks.py` $\to$ Moved to `scripts/build/` to unclutter the root.
- **Ignore as Generated Artifacts (Preserved Locally)**:
  - `submission_*.zip`, `submission_v*/`, `submission_reference_v*/`, `fallback_submission*.zip`. (Added to `.gitignore`).
- **Needs Explicit User Decision**:
  - Tracked LoRA adapters in `submission/adapters/` (`main_lora/adapter_model.safetensors`, `tool_lora/adapter_model.safetensors`). Currently ~210 KB each, which is extremely small and safe to keep tracked, but if larger versions are added later, Git LFS might be needed.

## 3. Rationale for Moves/Exclusions
- Untracked build scripts were ad-hoc files generated during diagnostics. Moving them to `scripts/build/` keeps the root focused on the actual `mini_swe_agent` package and its runner scripts.
- Excluding `submission_v*/` from Git ensures we don't accidentally commit multiple variations of the same `agent.yaml` configuration, saving repository size, while completely preserving the local environment for offline auditing.

## 4. Tracked Binary / Large-File Concerns
- `submission/adapters/main_lora/adapter_model.safetensors` (0.21 MB)
- `submission/adapters/tool_lora/adapter_model.safetensors` (0.21 MB)
**Conclusion:** The sizes are negligible (< 0.5 MB total). It is perfectly safe to keep them tracked without bloating the repository.

## 5. Tests and Packaging Checks Required
- Standard `pytest` test suite execution to verify core code is unaffected by the `.gitignore` changes and script migrations.
- ZIP hash checks on existing `submission_*.zip` files to ensure they were not modified or corrupted.

## 6. Proposed Commit Sequence
1. `git add .gitignore` (Add the updated ignore rules).
2. `git add README.md research/EXPERIMENT_INDEX.md research/REPOSITORY_CLEANUP_REPORT.md` (Add documentation updates).
3. `git add scripts/build/` (Track the moved build utilities).
4. `git add submission/` (Stage the deliberately preserved updates to `agent.yaml` and `prompts/system.md`).
