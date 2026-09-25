# Stage 1: Mini SWE Agent Architecture

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

## 2. Component Breakdown

### A. Sandboxed Workspace (`sandbox/mini_shop/`)
A realistic Python repository with unit tests (`unittest`), business logic, and intentional bugs:
* `shop/pricing.py`: Bug 1 (discount formula bug).
* `shop/cart.py`: Bug 2 (missing exception handling on non-existent item deletion).
* `tests/test_cart.py`: Automated test cases revealing these exact failures.

### B. Tool Registry (`mini_swe_agent/tools.py`)
Encapsulates all filesystem and execution interactions with strict security and portability boundaries:
1. `list_files(directory=".")`: Recursively lists repository files, filtering `.git`, `__pycache__`, and virtual environments.
2. `read_file(path, start_line=1, end_line=None)`: Displays line-numbered code slices for targeted inspection.
3. `search_code(query, directory=".")`: Substring search across all text files with file and line locations.
4. `edit_file(path, target_string, replacement_string)`:
   * Normalizes CRLF / LF line endings to avoid cross-platform whitespace mismatch.
   * Guarantees single-occurrence replacement; rejects ambiguous matches.
5. `run_command(command)`: Executes shell commands inside the workspace with timeout safeguards, capturing exit code, stdout, and stderr.
6. `get_patch()`: Extracts the unified git diff (`git diff HEAD`).

### C. LLM Reasoning Layer (`mini_swe_agent/llm.py`)
Decoupled through the `BaseLLMClient` interface:
* `DeterministicSWEClient`: Phase-driven state machine (Reproduce -> Inspect -> Fix -> Verify -> Conclude). Enables 100% offline, repeatable CI testing.
* `OllamaClient`: Direct HTTP integration with local Ollama models (e.g. `llama3.2:3b` or local Gemma).
* `GeminiClient`: Direct integration with Google Gemini models using `google.genai`.

### D. Agent Controller (`mini_swe_agent/agent.py`)
* Coordinates step iteration, conversation history, and tool execution.
* Enforces max-step limits (guardrails against runaway loops).
* Records full trajectory (`AgentStep`) for post-mortem analysis and benchmarking.

---

## 3. Resolving Real Failures: Lessons Learned

During Stage 1 development, two real-world cross-platform challenges were identified and solved:
1. **CRLF vs LF Line Endings**: Windows file writes often introduce `\r\n`, whereas string literals in code use `\n`. The `edit_file` tool was updated to normalize line endings during matching while preserving the file's original format.
2. **Terminal Encoding (CP1252 vs UTF-8)**: Raw Unicode emoji characters can cause `UnicodeEncodeError` in standard Windows cmd/PowerShell terminals. The agent logger was equipped with universal ASCII tags (`[START]`, `[THOUGHT]`, `[ACTION]`, `[OBSERVATION]`, `[SUCCESS]`) and a graceful fallback.
