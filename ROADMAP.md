# Gemma 4 Developer Agent - Competition Roadmap & Architecture

Welcome to the **Gemma 4 Developer Agent Competition** project! This document outlines the step-by-step engineering roadmap, technical architecture, skill gaps to bridge, and submission criteria.

---

## 1. Overview & Competition Architecture

### What is the Goal?
In Google's **Gemma 4 Developer Agent Competition** on Kaggle, the goal is to build an autonomous software-engineering agent powered by Gemma 4 (specifically the quantized competition model variant, `gemma-4-31b-it-qat-w4a16-ct`) capable of solving real GitHub issues in software repositories (SWE-bench style).

### The Autonomous SWE Agent Lifecycle
```
       +---------------------------------------------+
       |             Software Issue Prompt           |
       +---------------------------------------------+
                              |
                              v
       +---------------------------------------------+
       |            1. Problem Diagnosis             |
       |  - Understand issue description & error     |
       +---------------------------------------------+
                              |
                              v
       +---------------------------------------------+
       |         2. Code Exploration & Search        |
       |  - search_similar_code (semantic search)    |
       |  - get_code_neighbors / subgraph (graph)    |
       |  - read_file (inspect target modules)       |
       +---------------------------------------------+
                              |
                              v
       +---------------------------------------------+
       |           3. Patch Generation & Edit        |
       |  - edit_file / write_file                   |
       +---------------------------------------------+
                              |
                              v
       +---------------------------------------------+
       |         4. Verification & Self-Debug        |
       |  - run_command (run test suites / pytest)   |
       |  - Analyze test outputs / tracebacks        |
       +---------------------------------------------+
                       |             ^
             Tests Fail|             | Retry / Fix
                       v             |
             +-----------------------+
                       | Tests Pass / Budget Exhausted
                       v
       +---------------------------------------------+
       |              5. Submission                  |
       |  - submit_patch (git add -N . & git diff)   |
       +---------------------------------------------+
```

### The Kaggle Competition Environment & Harness
1. **Isolated Sandbox**: Runs offline without internet access inside a containerized `/workspace`.
2. **Provided Standard Tools**:
   * `read_file(path: str, start_line: int, end_line: int) -> str`
   * `edit_file(path: str, start_line: int, end_line: int, text: str) -> str`
   * `write_file(path: str, text: str) -> str`
   * `run_command(command: str) -> str`: Executes `/bin/bash -c` in `/workspace`.
   * `get_status() -> str`: Live execution budget and patch status.
   * `submit_patch() -> str`: Stages untracked files with `git add -N .` and returns the unified diff (`git diff HEAD`).
   * `search_similar_code(query: str, k: int = 10) -> str`: Semantic search over AST nodes backed by precomputed NumPy vector embeddings.
   * `get_code_neighbors(node: str, edge_type: str | None = None, max_neighbors: int = 50) -> str`: Returns incoming/outgoing neighbors in the NetworkX AST call/dependency graph.
   * `get_code_subgraph(nodes: list[str]) -> str`: Returns the induced subgraph for a given list of symbols.
3. **Kaggle Submission Format**:
   * A zip archive named `submission.zip`.
   * Must contain `agent.yaml` at the root (declarative Google ADK Agent configuration).
   * Bundled prompts (`prompts/`), skills (`skills/`), and optional configurations (`configs/sampling.yaml`) or LoRA adapters (`adapters/`).

---

## 2. Skills Inventory

### Skills You Already Have
* **Programming & Engineering**: B.E. in IT, practical Python & ML engineering, clean modular code design.
* **Data Science & ML**: NumPy, Pandas, Scikit-learn, XGBoost, vector math, basic NLP.
* **APIs & Web**: REST APIs, web scraping, Gemini/OpenAI API calling, JSON parsing.
* **Basic LLM/RAG Stack**: Embeddings, SentenceTransformers, vector databases (FAISS / Chroma), basic LangChain and LangGraph concepts.
* **Full-stack Awareness**: MERN stack (useful for local debugging dashboards if ever needed).

### Skills We Will Learn Together
* **SWE Agentic Loops**: Tool-use state machines (Plan -> Act -> Observe -> Reflect).
* **Graph-based Code Intelligence**: Parsing ASTs, navigating NetworkX call and dependency graphs, symbol neighbor analysis.
* **Vector Code Retrieval**: Vector similarity search on pre-computed code symbol embeddings using NumPy.
* **Code Surgery & Patch Management**: Generating syntactically valid edits, handling unified diffs, line ranges, and Git staging safely.
* **Test-Driven Self-Repair**: Capturing test tracebacks, isolating failure causes, preventing regression loops, and managing token/step budgets.
* **Agent Specification Standard**: Structuring declarative `agent.yaml` files adhering to the Google ADK and Kaggle competition harness.

---

## 3. Project Stages

| Stage | Focus | Description |
|---|---|---|
| **Stage 0** | **Orientation & Roadmap** | Inspect official requirements, map architecture, setup repo, define testbench strategy. |
| **Stage 1** | **Minimal Local SWE Agent** | Build a minimal local ReAct agent: receives an issue, reads files, reasons, edits code, runs tests, fixes failures, produces a git patch. |
| **Stage 2** | **Repository Navigation & Semantic Retrieval** | Implement offline semantic search tool (`search_similar_code`) using NumPy cosine similarity and symbol metadata. |
| **Stage 3** | **Code-Relationship & Graph Retrieval** | Implement graph-aware tools (`get_code_neighbors`, `get_code_subgraph`) using NetworkX AST call/dependency graphs. |
| **Stage 4** | **Test-Driven Self-Debugging** | Implement automated failure reflection, traceback parsing, regression guardrails, and budget awareness via `get_status`. |
| **Stage 5** | **Kaggle Harness Compatibility** | Adapt the agent runtime to match exact competition harness interfaces, argument schemas, and tool specifications. |
| **Stage 6** | **Submission Packaging (`agent.yaml`)** | Create valid `agent.yaml`, prompt templates, configs, and automated validation script for `submission.zip`. |
| **Stage 7** | **Ablation & Benchmarking Experiments** | Run controlled comparative experiments across agent variants (Basic vs Semantic vs Graph vs Self-Debugging vs Combined). |
| **Stage 8** | **Advanced Exploration (Optional)** | Evaluate if LoRA/PEFT, multi-agent delegation, or specialized prompt tuning add measurable value beyond prompt-engineered baselines. |

---

## 4. Technology Choices

* **Primary Language**: Python 3.12 (clean, modular, standard library oriented).
* **Graph Handling**: `networkx` (built-in support for serialized JSON AST graphs).
* **Vector Retrieval**: `numpy` (fast cosine similarity over pre-computed `.npz` / `.npy` embeddings, zero heavy dependencies).
* **Configuration**: `pyyaml` (for parsing and generating `agent.yaml` and `sampling.yaml`).
* **Tool & Process Execution**: Python `subprocess` with timeout and stdout/stderr capture (mirrors Kaggle's `/bin/bash -c`).
* **Testing Framework**: `pytest` for unit testing our tools, agent state machine, and mock harness.
* **No PyTorch or Heavy Frameworks Needed initially**: Keeps development fast, debuggable, transparent, and completely lightweight.

---

## 5. Directory & File Structure Plan

```text
gemma-dev-agent/
│
├── ROADMAP.md                  # This master document
├── README.md                   # Project overview & running instructions
│
├── harness/                    # Local Kaggle environment emulator
│   ├── __init__.py
│   ├── workspace.py            # Local /workspace sandbox manager
│   ├── tools.py                # File & shell tools (read, edit, write, run_command, submit_patch)
│   ├── code_graph.py           # NetworkX graph loader (get_code_neighbors, get_code_subgraph)
│   └── code_search.py          # NumPy semantic search (search_similar_code)
│
├── agent/                      # The Autonomous Agent
│   ├── __init__.py
│   ├── state.py                # Agent state, history, and budget tracking
│   ├── prompt_builder.py       # System prompt & task formatting
│   ├── llm_interface.py        # Abstract LLM caller (mock / local Gemma / API)
│   ├── controller.py           # Core agent loop: Plan -> Act -> Observe -> Reflect
│   └── debugger.py             # Test traceback parser & fix proposer
│
├── submission/                 # Kaggle Submission Artifacts
│   ├── agent.yaml              # Root competition ADK configuration
│   ├── configs/
│   │   └── sampling.yaml       # Sampling parameters (temperature, top_p, etc.)
│   ├── prompts/
│   │   └── system_prompt.txt   # Battle-tested system instructions
│   └── skills/                 # Declarative skill manifests
│
├── benchmarks/                 # Mini-benchmark suite for experiments
│   ├── cases/                  # Real or synthetic bugs to test agent
│   │   ├── case_01_off_by_one/
│   │   ├── case_02_missing_kwarg/
│   │   └── case_03_dependency_break/
│   └── run_experiments.py      # Automated benchmarking script (Stages 7)
│
└── tests/                      # Unit tests for our code
    ├── test_tools.py           # Test edit_file, submit_patch, run_command
    ├── test_graph.py           # Test graph queries & subgraph extraction
    ├── test_search.py          # Test numpy semantic retrieval
    └── test_agent_loop.py      # Test end-to-end agent on mini case
```

---

## 6. Planned Experiments (Stage 7)

We will measure **Solve Rate (%)**, **Average Steps to Fix**, **Token / Budget Consumption**, and **Patch Accuracy**:

* **Experiment A (Baseline Agent)**: Issue prompt + basic file tools (`read_file`, `edit_file`, `submit_patch`) without search or test feedback.
* **Experiment B (Agent + Semantic Retrieval)**: Baseline + `search_similar_code` to quickly pinpoint relevant files in multi-module repos.
* **Experiment C (Agent + Graph Retrieval)**: Baseline + `get_code_neighbors` & `get_code_subgraph` to track cross-file dependencies and callers.
* **Experiment D (Agent + Self-Debugging)**: Baseline + `run_command` test loop with traceback reflection before calling `submit_patch`.
* **Experiment E (Full System)**: Semantic search + graph context + test-driven repair + budget management.

---

## 7. Kaggle Submission Requirements Checklist

* [ ] Archive named `submission.zip`.
* [ ] `agent.yaml` located at the root of `submission.zip`.
* [ ] Model correctly configured to the required Gemma variant (`gemma-4-31b-it-qat-w4a16-ct`).
* [ ] Completely offline: all retrieval and reasoning rely strictly on local files, pre-computed graphs, and pre-computed embeddings.
* [ ] Compatible tool signatures: matches `read_file`, `edit_file`, `write_file`, `run_command`, `submit_patch`, `get_status`, `search_similar_code`, `get_code_neighbors`, and `get_code_subgraph`.
* [ ] Submission size within competition limit (< 500MB uncompressed for configs/adapters, unless weights bundled).
* [ ] Validated with local submission test script before uploading.

---

## 8. What is Optional / Advanced (Deferred to Stage 8)
* Fine-tuning Gemma 4 using LoRA / QLoRA / PEFT.
* Reinforcement Learning (RL / GRPO) on trajectory traces.
* Complex Multi-Agent orchestration frameworks (e.g. Swarm/LangGraph hierarchies).
* Custom web dashboard or MERN UI.
