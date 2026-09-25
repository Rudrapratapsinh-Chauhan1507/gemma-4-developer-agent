# Gemma 4 Developer Agent

An autonomous software engineering agent built for Google's Kaggle **Gemma 4 Developer Agent Competition**.

---

## Project Status

* **Project**: Gemma 4 Developer Agent
* **Current Status**: **Stage 2 — Repository-aware semantic code retrieval completed**
* **Next**: **Stage 3 — (See ROADMAP.md)**

---

## Competition Summary

* **Challenge**: Build an autonomous coding agent using the Gemma 4 model variant (`gemma-4-31b-it-qat-w4a16-ct`) that can navigate repositories, locate buggy code, reason over dependencies, edit files, run tests, and submit a clean unified git diff patch.
* **Evaluation**: SWE-bench style offline sandbox execution against held-out issues in popular open-source repositories.
* **Submission**: A `submission.zip` package with `agent.yaml` at the root, defining system prompts, tools, skills, and configuration.

---

## Capabilities Overview

### Stage 1: Core Agent
* **Sandbox Repository** (`sandbox/mini_shop`): An e-commerce package with intentional bugs and test suites.
* **Core Tool Suite**: Sandboxed implementations of `list_files`, `read_file`, `search_code`, `edit_file`, and `run_command`.
* **Agent Controller**: ReAct execution loop (Plan $\rightarrow$ Act $\rightarrow$ Observe $\rightarrow$ Reflect).
* **Pluggable LLM Interface**: Supports `DeterministicSWEClient`, local `OllamaClient`, and `GeminiClient`.

### Stage 2: Repository-Aware Retrieval
* **File Discovery**: Filters out binary, generated, and ignored directories (e.g. `.git`, `__pycache__`).
* **Code Chunking**: AST-based chunking that safely extracts classes, functions, and methods, falling back to line-windows for unstructured or broken code.
* **Semantic Embeddings**: Uses `sentence-transformers` (`all-MiniLM-L6-v2`) to embed chunks locally.
* **FAISS Vector Index**: Fast and exact cosine-similarity (`IndexFlatIP`) nearest-neighbor search.
* **Baseline Keyword Retrieval**: Token-matching fallback baseline.
* **Context Builder**: Formats retrieved chunks neatly while respecting character and token budgets, injecting context prior to the first ReAct loop.

---

## How to Run the Tests & Demos

### 1. Run All Tests
```powershell
python -m unittest discover -s tests
```
Runs 59 passing tests, validating both the Stage 1 Core Agent and all Stage 2 Semantic Retrieval modules.

### 2. Run the Stage 1 Demo
```powershell
python run_demo.py
```
Demonstrates the agent solving bugs autonomously using standard tools.

### 3. Run the Stage 2 Semantic Retrieval Demo
```powershell
python run_demo_stage2.py
```
Demonstrates the semantic search pipeline on the "discount percentage calculation" bug, showing indexing, keyword ranking, semantic ranking, and the resulting ContextBuilder block.

### 4. Run the Stage 2 Local Evaluation
```powershell
python run_evaluation_stage2.py
```
On the two-issue local sandbox evaluation, both approaches retrieved the relevant target within top-5; semantic retrieval ranked the relevant code component #1 in both cases, while keyword retrieval ranked ISSUES.md #1.

---

## Documentation Links
* [ROADMAP.md](ROADMAP.md) - Master project roadmap and Kaggle competition strategy.
* [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed breakdown of the agent architecture and retrieval pipeline.
