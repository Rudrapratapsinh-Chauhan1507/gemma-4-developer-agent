"""Failure Analysis and Code Localization for Stage 4.2.

Transforms a failed CommandResult into structured diagnostic information.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any

from .execution import CommandResult
from .tools import ToolRegistry


@dataclass
class FailureAnalysis:
    failed: bool
    failure_type: str
    summary: str
    command: str
    return_code: int
    stdout: str
    stderr: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    candidate_files: List[str] = field(default_factory=list)
    candidate_symbols: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_display_string(self) -> str:
        """Render a human-readable summary for LLM context."""
        if not self.failed:
            return "Command executed successfully."

        lines = [
            f"Failure Analysis: {self.failure_type.upper()}",
            f"Summary: {self.summary}",
            f"Command: {self.command}",
        ]
        if self.candidate_files:
            lines.append(f"Candidate Files: {', '.join(self.candidate_files)}")
        if self.candidate_symbols:
            lines.append(f"Candidate Symbols: {', '.join(self.candidate_symbols)}")

        if self.evidence:
            lines.append("Evidence:")
            for k, v in self.evidence.items():
                if v:
                    lines.append(f"  {k}: {v}")

        return "\n".join(lines)


class FailureAnalyzer:
    """Analyzes a CommandResult to produce structured diagnostic info."""

    def __init__(self, tool_registry: ToolRegistry):
        self.tools = tool_registry

    def analyze(self, result: CommandResult) -> FailureAnalysis:
        if result.success:
            return FailureAnalysis(
                failed=False,
                failure_type="success",
                summary="Command executed successfully.",
                command=result.command,
                return_code=result.return_code,
                stdout=result.stdout,
                stderr=result.stderr,
                confidence=1.0,
            )

        failure_type = self._classify_failure(result)
        evidence = self._extract_evidence(result)
        candidate_files, candidate_symbols = self._localize(evidence)

        # Enrich with Semantic Retrieval
        if self.tools.retriever and evidence.get("error_message"):
            self._enrich_with_retrieval(evidence["error_message"], candidate_files, candidate_symbols)
        elif self.tools.retriever and evidence.get("test_name"):
            self._enrich_with_retrieval(evidence["test_name"], candidate_files, candidate_symbols)

        # Enrich with Code Graph (only if nodes can be resolved)
        if self.tools.code_graph and candidate_files and candidate_symbols:
            self._enrich_with_graph(candidate_files, candidate_symbols)

        summary = f"Command failed with {failure_type}."
        if evidence.get("error_message"):
            summary = evidence["error_message"]

        # Deduplicate
        final_files = []
        for f in candidate_files:
            if f not in final_files:
                final_files.append(f)

        final_symbols = []
        for s in candidate_symbols:
            if s not in final_symbols:
                final_symbols.append(s)

        return FailureAnalysis(
            failed=True,
            failure_type=failure_type,
            summary=summary,
            command=result.command,
            return_code=result.return_code,
            stdout=result.stdout,
            stderr=result.stderr,
            evidence=evidence,
            candidate_files=final_files,
            candidate_symbols=final_symbols,
            confidence=0.8 if final_files or final_symbols else 0.5,
        )

    def _classify_failure(self, result: CommandResult) -> str:
        if result.timed_out:
            return "timeout"
        if result.error_message:
            return "command_error"

        output = result.stdout + "\n" + result.stderr

        if "SyntaxError:" in output or "IndentationError:" in output: return "syntax_error"
        if "ImportError:" in output or "ModuleNotFoundError:" in output: return "import_error"
        if "NameError:" in output: return "name_error"
        if "TypeError:" in output: return "type_error"
        if "AttributeError:" in output: return "attribute_error"
        if "KeyError:" in output: return "key_error"
        if "AssertionError" in output: return "assertion_failure"

        if "FAILED " in output or "FAIL:" in output or "ERROR:" in output:
            return "test_failure"

        if "Exception:" in output or "Traceback (most recent call last):" in output:
            return "runtime_error"

        return "unknown_failure"

    def _extract_evidence(self, result: CommandResult) -> Dict[str, Any]:
        output = result.stdout + "\n" + result.stderr
        evidence = {
            "test_file": None,
            "test_name": None,
            "source_file": None,
            "line_number": None,
            "error_message": None,
        }

        # 1. Pytest style
        pytest_match = re.search(r"FAILED\s+([^\s:]+)::([^\s:]+)::([^\s:]+)", output)
        if pytest_match:
            evidence["test_file"] = pytest_match.group(1)
            evidence["test_name"] = pytest_match.group(3)

        pytest_match_simple = re.search(r"FAILED\s+([^\s:]+)::([^\s]+)", output)
        if not pytest_match and pytest_match_simple:
            evidence["test_file"] = pytest_match_simple.group(1)
            evidence["test_name"] = pytest_match_simple.group(2)

        # 2. Python traceback style
        tb_matches = list(re.finditer(r'File\s+"([^"]+)",\s+line\s+(\d+)(?:,\s+in\s+([^\n]+))?', output))
        if tb_matches:
            last_match = tb_matches[-1]
            evidence["source_file"] = last_match.group(1)
            evidence["line_number"] = last_match.group(2)
            if last_match.group(3):
                if "<module>" not in last_match.group(3) and not evidence["test_name"]:
                    evidence["test_name"] = last_match.group(3).strip()

        # 3. Extract Error message
        err_match = re.search(r"^([A-Z][a-zA-Z0-9_]+Error|AssertionError|Exception):\s*(.*)$", output, re.MULTILINE)
        if err_match:
            evidence["error_message"] = err_match.group(0).strip()
        else:
            err_match_pytest = re.search(r"^E\s+(.*)$", output, re.MULTILINE)
            if err_match_pytest:
                evidence["error_message"] = err_match_pytest.group(1).strip()

        return evidence

    def _localize(self, evidence: Dict[str, Any]) -> tuple[List[str], List[str]]:
        files = []
        symbols = []

        if evidence.get("source_file"):
            files.append(evidence["source_file"])
        if evidence.get("test_file"):
            files.append(evidence["test_file"])

        if evidence.get("test_name"):
            symbols.append(evidence["test_name"])

        return files, symbols

    def _enrich_with_retrieval(self, query: str, files: List[str], symbols: List[str]):
        if not self.tools.retriever:
            return

        try:
            results = self.tools.retriever.retrieve(query, top_k=2)
            for r in results:
                if r.get("file_path") and r["file_path"] not in files:
                    files.append(r["file_path"])
                if r.get("symbol_name") and r["symbol_name"] not in symbols:
                    symbols.append(r["symbol_name"])
        except Exception:
            pass

    def _enrich_with_graph(self, files: List[str], symbols: List[str]):
        if not self.tools.code_graph:
            return

        new_symbols = []
        for f in files:
            for s in symbols:
                node_id = f"{f}::{s}"
                try:
                    from .graph.graph_query import get_code_neighbors
                    neighbors = get_code_neighbors(self.tools.code_graph, node_id, direction="outgoing")
                    for n in neighbors:
                        if n.get("symbol_name"):
                            new_symbols.append(n["symbol_name"])
                except Exception:
                    pass

        for ns in new_symbols:
            if ns not in symbols:
                symbols.append(ns)
