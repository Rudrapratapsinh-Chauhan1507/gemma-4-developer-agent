# Gemma 4 Developer Agent

An autonomous software engineering agent built for Google's Kaggle **Gemma 4 Developer Agent Competition**.

## Competition Summary
- **Challenge**: Build an autonomous coding agent using the Gemma 4 model variant (`gemma-4-31b-it-qat-w4a16-ct`) that can navigate repositories, locate buggy code, reason over dependencies, edit files, run tests, and submit a clean unified git diff patch.
- **Evaluation**: SWE-bench style offline sandbox execution against held-out issues in popular open-source repositories.
- **Submission**: A `submission.zip` package with `agent.yaml` at the root, defining system prompts, tools, skills, and configuration.

## Project Structure
For the full development roadmap, skills breakdown, stage plan, and planned experiments, please refer to [ROADMAP.md](ROADMAP.md).

## Current Stage: Stage 0 (Architecture & Roadmap)
- Environment setup and requirements inspection.
- Technical roadmap mapped out.
- Local repository initialized.
