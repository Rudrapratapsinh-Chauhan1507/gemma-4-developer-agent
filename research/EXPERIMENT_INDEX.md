# Gemma 4 Developer Agent — Experiment Index

This document tracks the history and purpose of local candidate submissions (`submission_v*.zip`). The actual directories and ZIP files are ignored by Git but preserved locally.

| Version | Status / Public Score | ZIP SHA-256 | Description |
|---|---|---|---|
| **V2** | 0.05 | `c11030b...` | Reference implementation of multi-agent codebase (Kaggle submission 56765141). |
| **V3** | Exception | `b854428...` | Tested `skip_summarization: false`; resulted in notebook exception (likely context overflow). |
| **V4** | 0.06 | `6136acd...` | Two-agent design. Reverted to `skip_summarization: true`. Used explicit constraints on tools like banning `search_similar_code`. (Baseline for multi-agent). |
| **V5** | 0.06 | `b10957a...` | Single-agent lean design based on Kaggle public 0.10 notebook. Restored 9 tools. Used `max_tool_calls: 40`, `timeout_seconds: 60`. |
| **V6** | 0.05 | `0fe7964...` | Single-agent variant attempting to fix `rg` bug with `git grep` and stricter whitespace handling, but grouped too many constraints. |
| **V7** | Original: 0.06; retry: pending | `bf031aa...` | Single-agent variant starting from V5, incorporating the fixed `git grep` and indentation warning. |
| **V8** | Candidate; not submitted | `99bd7d8...` | Same prompt as V7 but omits `eval_config.yaml` to test the effect of harness-default evaluation budgets. |
