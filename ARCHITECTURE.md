# Agent Architecture

## 1. System Philosophy: Closed-Loop ReAct

Traditional LLM applications operate in an **open loop**:
```
User Prompt -> LLM -> Text Output (No verification)
```

In contrast, an autonomous Software Engineering Agent operates in a **closed-loop ReAct (Reason + Act)** cycle:
```
                                +-------------------+
                                |    User Issue     |
                                +-------------------+
                                          |
                                          v
                +---------------------------------------------------+
                |               Autonomous Agent Loop               |
                |                                                   |
                |  1. [THOUGHT] Reason over current state & error   |
                |  2. [ACTION] Select tool & structured parameters  |
                +---------------------------------------------------+
                                   |             ^
                      Execute Tool |             | Observation
                                   v             |
                +---------------------------------------------------+
                |            Sandboxed Workspace Host               |
                |                                                   |
                |  - list_files, read_file, search_code             |
                |  - edit_file (safe exact-match code replacement)  |
                |  - run_command (subprocess execution / unittest)  |
                +---------------------------------------------------+
                                          |
                                    Passing Tests
                                          v
                                +-------------------+
                                |   submit_patch    |
                                +-------------------+
```

---

## 2. Stage 2: Repository-Aware Retrieval Pipeline

Before the ReAct loop starts, the agent uses an **additive** semantic retrieval pipeline to ground its initial context. (If retrieval is disabled, the Stage 1 behavior remains fully intact).

```
Issue Description
       ↓
[ Repository Discovery ]      (Filters out binaries, .git, pycache)
       ↓
[ Code Chunking ]             (AST parses classes/functions, with line-window fallback)
       ↓
[ Embedding ]                 (sentence-transformers: all-MiniLM-L6-v2)
       ↓
[ FAISS Vector Index ]        (IndexFlatIP for fast cosine similarity)
       ↓
[ Semantic Retrieval ]        (Retrieves top-K nearest code chunks)
       ↓
[ Context Builder ]           (Formats into a budget-constrained markdown context)
       ↓
MiniSWEAgent                  (Initial prompt injected with repository context)
       ↓
ReAct Loop
```

**Keyword Baseline**: A `KeywordRetriever` token-matching baseline is also implemented to benchmark and evaluate the semantic system.

---

## 3. Core Component Breakdown

### A. Sandboxed Workspace (`sandbox/mini_shop/`)
A realistic Python repository with unit tests (`unittest`), business logic, and intentional bugs:
* `shop/pricing.py`: Bug 1 (discount formula bug).
* `shop/cart.py`: Bug 2 (missing exception handling on non-existent item deletion).
* `tests/test_cart.py`: Automated test cases revealing these exact failures.

### B. Tool Registry (`mini_swe_agent/tools.py`)
Encapsulates all filesystem and execution interactions with strict security and portability boundaries:
1. `list_files(directory=".")`: Recursively lists repository files.
2. `read_file(path, start_line=1, end_line=None)`: Displays line-numbered code slices.
3. `search_code(query, directory=".")`: Substring search across all text files.
4. `search_similar_code(query, k=5)`: Semantic retrieval exposed as a tool for the agent during the ReAct loop.
5. `edit_file(path, target_string, replacement_string)`: Normalizes CRLF / LF line endings and guarantees single-occurrence safe replacement.
6. `run_command(command)`: Executes shell commands inside the workspace with timeouts.
7. `get_patch()`: Extracts the unified git diff scoped to the workspace.

### C. LLM Reasoning Layer (`mini_swe_agent/llm.py`)
Decoupled through the `BaseLLMClient` interface:
* `DeterministicSWEClient`: Phase-driven state machine enabling 100% offline, repeatable CI testing.
* `OllamaClient`: HTTP integration with local Ollama models.
* `GeminiClient`: Integration with Google Gemini models.

### D. Agent Controller (`mini_swe_agent/agent.py`)
* Coordinates step iteration, conversation history, and tool execution.
* Records full trajectory (`AgentStep`) for post-mortem analysis and benchmarking.
