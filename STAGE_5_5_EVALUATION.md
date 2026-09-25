# STAGE 5.5 — Evaluation Infrastructure Investigation

This document outlines the evaluation infrastructure for the Kaggle Gemma 4 Developer Agent competition based on the official `HARNESS_README.md` and current local environment inspection.

## 1. What the Official Evaluator Does
The official `swegemma` evaluator (along with `adk-submission` and `adk-eval-core`) manages a secure, offline two-phase lifecycle:
*   **Phase 1 (Agent Sandbox - Container A):** The harness provisions an isolated Docker container (`network_mode="none"`, `4g` RAM, `2 vCPUs`), stages offline Python wheels, and extracts a repository snapshot with zero future git history. The agent uses tools (`run_command`, `read_file`, `edit_file`, etc.) within this container. Context compaction and output truncation (e.g., 5000 chars for commands) are enforced. Upon `submit_patch()`, the harness extracts `git diff HEAD`.
*   **Phase 2 (Verification Sandbox - Container B):** A fresh container is started with a clean snapshot. The agent's patch is applied using a 4-pass resilient git apply strategy. Target test files are reset to baseline to prevent tampering, and hermetic `pytest` verification is run.
*   **Scoring:** A task is resolved (Score = `1.0`) if and only if `pytest` exits with code `0`.

## 2. What Resources are Available Locally
Our repository currently contains the following legitimate resources for this stage:
*   **Baseline Submission:** A clean, declarative Kaggle submission located in `submission/` (`agent.yaml`, `configs/sampling.yaml`, `prompts/system.md`).
*   **Harness Documentation:** `kaggle_resources/HARNESS_README.md`.
*   **Sample Data:** A subset of competition setup files in `kaggle_resources/`, including `tasks.jsonl`, a repository snapshot (`httpx_3672.tgz`), `eval_config.yaml`, sandbox Dockerfiles (`Dockerfile.sandbox`, `Dockerfile.public`), and sandbox bootstrap scripts (`setup.py`, `imp.py`).
*   **Local Framework:** The Stage 0–4 `MiniSWEAgent` local implementation and its `mini_swe_agent/evaluation.py` testbed.

## 3. What is Unavailable
*   **The Evaluator CLI:** The `swegemma`, `adk-submission`, and `adk-eval-core` Python packages (wheels) are completely missing from the local environment and resources.
*   **Full Datasets:** The complete suite of `.tgz` snapshots, `.json` AST graphs, and `.npz` embedding files for all competition tasks.
*   **Docker Daemon:** Docker is not installed or available in the current local environment, which is a hard prerequisite for `swegemma eval --sandbox docker`.

## 4. What Can and Cannot Currently be Measured
*   **Can be measured:** 
    *   Syntactic correctness of our YAML submission structure.
    *   Local regression testing of our Stage 0–4 Python `MiniSWEAgent` using the custom Stage 4.4 `EvaluationRunner` on mock issues (like `sandbox/mini_shop`).
*   **Cannot be measured:** 
    *   End-to-end task resolution metrics on actual Kaggle problems.
    *   Token consumption and truncation behaviors dictated by the ADK context compactor.
    *   Performance of the Kaggle-specific `search_similar_code` or `get_code_neighbors` tools, as we lack the pre-computed `.npz` embeddings and the harness implementation.

## 5. Recommended Next Evaluation Path
Because the official `swegemma` package and Docker daemon are unavailable locally, **we cannot and should not implement a fake evaluator**. 

The recommended legitimate paths forward are:
1.  **Direct Kaggle Submission (Primary):** Zip the `submission/` directory and upload it directly to Kaggle to obtain an initial public leaderboard score. This serves as the true baseline for our declarative agent.
2.  **Environment Setup (Secondary):** If local evaluation is strictly required in the future, we must install Docker Desktop, obtain the missing `swegemma*.whl` files (likely from the official Kaggle Starter Kit), and download the full 100+ GB `competition_data` corpus.
