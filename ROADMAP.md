# Gemma 4 Developer Agent — Engineering Roadmap

## Vision

The long-term objective is to develop a highly capable, autonomous Software Engineering (SWE) agent that can reason about complex codebases, diagnose issues, and generate accurate patches.

## Competition Objective

Designed for the Google Gemma 4 Developer Agent Competition, this project aims to produce an agent that excels at repository understanding, targeted code modification, iterative testing and debugging, and final patch generation within constrained contexts using the Gemma 4 model.

## Architecture Evolution

The project follows a strict incremental architecture evolution:

`Stage 0: Foundation`
↓
`Stage 1: Tool-Using SWE Agent`
↓
`Stage 2: Repository Intelligence`
↓
`Stage 3: Code Graph`
↓
`Stage 4: Self-Debugging`
↓
`Stage 5: Kaggle Harness`
↓
`Stage 6: Evaluation & Optimization`
↓
`Stage 7: Optional Advanced Optimization`
↓
`Stage 8: Final Submission`

## Stage 0 — Foundation
**Status: COMPLETE**

- **Objectives:** Establish project basics, repository structure, and a safe testing sandbox.
- **Implementation:** Created the initial repository structure, baseline architecture planning, roadmap, and the `sandbox/mini_shop` environment.
- **Verification:** Verified safe file isolation and basic project scaffolding.

## Stage 1 — Mini SWE Agent
**Status: COMPLETE**

- **Objectives:** Build the foundational ReAct-style agent loop and sandboxed tool registry.
- **Architecture:** `MiniSWEAgent` integrated with a `ToolRegistry` and extensible LLM clients.
- **Tools:** Implemented `list_files`, `read_file`, `search_code`, `edit_file`, `run_command`, and `get_patch`.
- **LLM Clients:** Added support for a Deterministic test client, Ollama, and Google GenAI.
- **Verification:** Successfully executed bug-fixing tasks in the `sandbox/mini_shop`, generated patches, and passed all unit tests.

## Stage 2 — Repository Intelligence & Semantic Retrieval
**Status: COMPLETE**

- **Implementation:**
  - Repository discovery (filtering hidden/cache directories).
  - Lexical keyword search baseline.
  - Python AST code chunking (functions, classes, methods) with a line-window fallback.
  - Embeddings generation using `SentenceTransformers` (`all-MiniLM-L6-v2`).
  - Fast vector similarity search using `FAISS`.
  - Configurable `SemanticRetriever` and `ContextBuilder`.
- **Agent Integration:** Added the `search_similar_code` tool to the registry.
- **Evaluation:** Evaluated on sandbox issues, demonstrating successful top-K semantic retrieval alongside keyword search.
- **Limitations:** Limited scale (evaluated only on small sandbox repositories).
- **Verification:** 50+ unit tests added for retrieval logic; demo and evaluation scripts verified.

## Stage 3 — Code Graph & Structural Reasoning
**Status: COMPLETE**

### Task 3.1 — AST Code Graph Builder
**Status: COMPLETE**
- **Goal:** Parse Python code into a structural NetworkX graph.
- **Implementation:** Extracts modules, classes, functions, and methods. Maps `contains`, `imports`, and `calls` relationships into a `CodeGraph`.
- **Limitations:** Call resolution is strictly name-based; cross-file symbol resolution is not fully implemented.

### Task 3.2 — Code Neighbor Queries
**Status: COMPLETE**
- **Goal:** Allow the agent to query immediate 1-hop graph relationships.
- **Implementation:** `get_code_neighbors()` API supporting `incoming`, `outgoing`, or `both` directions with deterministic sorting.

### Task 3.3 — Bounded Code Subgraphs
**Status: COMPLETE**
- **Goal:** Allow multi-hop exploration of the code graph.
- **Implementation:** `get_code_subgraph()` API using a bounded BFS traversal (`max_depth`), cleanly handling cycles and duplicate paths while retaining minimum depth metadata.

### Task 3.4 — Agent Integration
**Status: COMPLETE**
- **Goal:** Expose graph capabilities to the SWE Agent.
- **Implementation:** Added `enable_graph` to `MiniSWEAgent` for optional lazy construction. Exposed graph queries via `ToolRegistry`.
- **Verification:** Maintained strict backward compatibility for standard Stage 1/2 operation.

**Stage 3 Verification:**
- 158 / 158 tests passing.
- Full unittest suite successful, seamlessly integrating Stage 1 + Stage 2 + Stage 3 tests.

## Stage 4 — Self-Debugging SWE Agent
**Status: NOT STARTED**

- **Objectives:** Enhance the agent's ability to iteratively fix failing code.
- **Future Work:**
  - Analyze test failures and parse stack traces.
  - Localize failure boundaries.
  - Reason about failed patches and implement intelligent retry logic.
  - Validate fixes against stopping criteria and prevent regressions.

## Stage 5 — Kaggle Harness Integration
**Status: NOT STARTED**

- **Objectives:** Port the agent to the competition environment.
- **Future Work:**
  - Create `agent.yaml` and required competition structure.
  - Ensure competition tool compatibility.
  - Integrate specific Gemma 4 model constraints.
  - Validate submissions against sandbox constraints.

## Stage 6 — Evaluation & Optimization
**Status: NOT STARTED**

- **Objectives:** Measure and improve agent performance.
- **Potential Metrics:**
  - Issue localization accuracy.
  - Patch success and test pass rates.
  - Context and compute/token efficiency.
  - Tool efficiency and latency.

## Stage 7 — Advanced Optimization
**Status: FUTURE / OPTIONAL**

- **Objectives:** Open-ended research optimizations for the Gemma 4 model.
- **Potential Research Directions:**
  - LoRA / PEFT agent-specific fine-tuning.
  - Reward-based optimization (RL / GRPO).
  - Improved code embeddings and graph-aware retrieval pipelines.
  - Structured planning and multi-agent approaches.

## Stage 8 — Final Competition Submission
**Status: FUTURE**

- **Objectives:** Produce the final competition artifact.
- **Potential Milestones:**
  - Final agent freeze.
  - Benchmark evaluation and reproducibility validation.
  - Packaging, documentation, and Kaggle submission.

## Research Questions

As the project evolves, we aim to explore several hypotheses:
1. Does semantic retrieval improve code localization compared with lexical search?
2. Does graph expansion improve localization?
3. When does graph context help versus add noise?
4. Can graph structure reduce unnecessary context?
5. Can retrieval + graph reasoning improve patch success?
6. How effectively can Gemma perform software engineering tasks under constrained context/tool budgets?

## Engineering Principles

- Incremental development.
- Test-first verification.
- Modular architecture with backward compatibility.
- Reproducibility.
- Measurement before optimization.
- Controlled complexity.
- Clear separation between implemented and future functionality.

## Milestone Table

| Stage | Focus | Status | Verification |
| :--- | :--- | :--- | :--- |
| Stage 0 | Foundation | COMPLETE | Verified |
| Stage 1 | Mini SWE Agent | COMPLETE | Verified |
| Stage 2 | Repository Intelligence | COMPLETE | Verified |
| Stage 3 | Code Graph | COMPLETE | Verified |
| Stage 4 | Self-Debugging | NOT STARTED | - |
| Stage 5 | Kaggle Harness | NOT STARTED | - |
| Stage 6 | Evaluation & Optimization | NOT STARTED | - |
| Stage 7 | Advanced Optimization | FUTURE / OPTIONAL | - |
| Stage 8 | Final Submission | FUTURE | - |
