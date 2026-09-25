# Gemma 4 Developer Agent

An autonomous software engineering agent built for Google's Kaggle **Gemma 4 Developer Agent Competition**.

---

## Project Status

* **Project**: Gemma 4 Developer Agent
* **Current Status**: **Stage 1 — Tool-based Mini SWE Agent completed**
* **Next**: **Stage 2 — Repository-aware semantic code retrieval**

---

## Competition Summary

* **Challenge**: Build an autonomous coding agent using the Gemma 4 model variant (`gemma-4-31b-it-qat-w4a16-ct`) that can navigate repositories, locate buggy code, reason over dependencies, edit files, run tests, and submit a clean unified git diff patch.
* **Evaluation**: SWE-bench style offline sandbox execution against held-out issues in popular open-source repositories.
* **Submission**: A `submission.zip` package with `agent.yaml` at the root, defining system prompts, tools, skills, and configuration.

---

## Stage 1 Completed Capabilities

We have built and verified a lightweight, zero-dependency local SWE Agent:
* **Sandbox Repository** (`sandbox/mini_shop`): An e-commerce package with intentional bugs and `unittest` test suites.
* **Core Tool Suite** (`mini_swe_agent/tools.py`): Sandboxed implementations of `list_files`, `read_file`, `search_code`, `edit_file`, and `run_command`.
* **Agent Controller** (`mini_swe_agent/agent.py`): ReAct execution loop (Plan $\rightarrow$ Act $\rightarrow$ Observe $\rightarrow$ Reflect) with trajectory logging and step budget limits.
* **Pluggable LLM Interface** (`mini_swe_agent/llm.py`): Supports `DeterministicSWEClient` (for repeatable offline CI testing), local `OllamaClient`, and `GeminiClient`.

---

## How to Run the Tests & Demo

### 1. Run All Tests
```powershell
python -m unittest discover -s tests
```
Runs 8 tests in < 2 seconds:
- 6 unit tests for ToolRegistry
- 2 end-to-end integration tests solving Bug #1 and Bug #2 autonomously

### 2. Run the Interactive Demo
```powershell
python run_demo.py
```
Demonstrates the agent receiving the issue descriptions, running tests to observe tracebacks, inspecting code, modifying the source files, verifying passing tests, and generating the fix.

---

## Documentation Links
* [ROADMAP.md](ROADMAP.md) - Master project roadmap and Kaggle competition strategy.
* [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed breakdown of the Stage 1 agent architecture.
