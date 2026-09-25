"""Tool implementations for the Mini SWE Agent.

Provides safe, sandboxed workspace operations:
1. list_files: Explore repository structure
2. read_file: View file contents with line numbers
3. search_code: Find occurrences of strings/symbols across files
4. edit_file: Perform deterministic exact-match text replacement (CRLF/LF agnostic)
5. run_command: Run shell commands/tests and capture outputs
"""

import os
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional


class ToolRegistry:
    """Manages execution of sandboxed developer tools within a workspace."""

    def __init__(self, workspace_dir: str, retriever: Optional[Any] = None, code_graph: Optional[Any] = None):
        self.workspace_dir = Path(workspace_dir).resolve()
        if not self.workspace_dir.exists():
            raise FileNotFoundError(f"Workspace directory does not exist: {self.workspace_dir}")
        self.retriever = retriever
        self.code_graph = code_graph  # CodeGraph instance, or None if graph not enabled

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve a relative path inside the workspace and ensure it cannot escape."""
        resolved = (self.workspace_dir / relative_path).resolve()
        try:
            resolved.relative_to(self.workspace_dir)
        except ValueError:
            raise PermissionError(f"Access denied: path '{relative_path}' points outside workspace.")
        return resolved

    def list_files(self, directory: str = ".") -> str:
        """
        List all files in the given directory (recursive), excluding hidden/cache folders.
        """
        target_dir = self._resolve_path(directory)
        if not target_dir.is_dir():
            return f"Error: '{directory}' is not a directory."

        ignored_patterns = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", ".egg-info"}
        file_list: List[str] = []

        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in ignored_patterns and not d.startswith(".")]
            for f in sorted(files):
                if f.endswith((".pyc", ".pyo")):
                    continue
                full_path = Path(root) / f
                rel_path = full_path.relative_to(self.workspace_dir).as_posix()
                file_list.append(rel_path)

        if not file_list:
            return "No files found."
        return "\n".join(file_list)

    def read_file(self, path: str, start_line: int = 1, end_line: Optional[int] = None) -> str:
        """
        Read file contents with 1-indexed line numbers.
        """
        file_path = self._resolve_path(path)
        if not file_path.is_file():
            return f"Error: File '{path}' does not exist."

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            return f"Error reading file '{path}': {e}"

        total_lines = len(lines)
        start = max(1, start_line)
        end = total_lines if end_line is None else min(total_lines, end_line)

        if start > total_lines:
            return f"File '{path}' has {total_lines} lines. Requested start_line={start} is out of range."

        formatted_lines = []
        for idx in range(start, end + 1):
            line_content = lines[idx - 1].rstrip("\r\n")
            formatted_lines.append(f"{idx:4d} | {line_content}")

        header = f"--- {path} (lines {start}-{end} of {total_lines}) ---\n"
        return header + "\n".join(formatted_lines)

    def search_code(self, query: str, directory: str = ".") -> str:
        """
        Search for query string across all text files in directory.
        """
        if not query.strip():
            return "Error: query cannot be empty."

        target_dir = self._resolve_path(directory)
        matches = []
        ignored_patterns = {".git", "__pycache__", ".pytest_cache", ".venv"}

        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in ignored_patterns and not d.startswith(".")]
            for f in sorted(files):
                if f.endswith((".py", ".md", ".txt", ".yaml", ".json", ".ini")):
                    file_path = Path(root) / f
                    rel_path = file_path.relative_to(self.workspace_dir).as_posix()
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
                            for line_num, line in enumerate(file, 1):
                                if query in line:
                                    matches.append(f"{rel_path}:{line_num}: {line.strip()}")
                    except Exception:
                        continue

        if not matches:
            return f"No matches found for query: '{query}'"
        return "\n".join(matches[:50])

    def edit_file(self, path: str, target_string: str, replacement_string: str) -> str:
        """
        Replace target_string with replacement_string in the specified file.
        Robust to line ending differences (CRLF vs LF).
        Fails clearly if target_string does not match or occurs multiple times.
        """
        file_path = self._resolve_path(path)
        if not file_path.is_file():
            return f"Error: File '{path}' does not exist."

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_content = f.read()
        except Exception as e:
            return f"Error reading file '{path}': {e}"

        # Detect line endings
        uses_crlf = "\r\n" in raw_content

        # Normalize to LF for matching
        normalized_content = raw_content.replace("\r\n", "\n")
        normalized_target = target_string.replace("\r\n", "\n")
        normalized_replacement = replacement_string.replace("\r\n", "\n")

        count = normalized_content.count(normalized_target)
        if count == 0:
            return (
                f"Error: target_string not found in '{path}'. "
                f"Please inspect the file using read_file to ensure whitespace and code match exactly."
            )
        if count > 1:
            return (
                f"Error: target_string occurs {count} times in '{path}'. "
                f"Include more surrounding context lines in target_string to make it unique."
            )

        new_content = normalized_content.replace(normalized_target, normalized_replacement, 1)

        # Restore original line endings if needed
        if uses_crlf:
            new_content = new_content.replace("\n", "\r\n")

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            return f"Error writing to file '{path}': {e}"

        return f"Successfully updated '{path}'."

    def run_command(self, command: str, timeout_seconds: int = 30) -> str:
        """
        Execute a shell command inside the workspace directory.
        Captures and returns exit code, stdout, and stderr.
        """
        try:
            result = subprocess.run(
                command,
                cwd=str(self.workspace_dir),
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            output = []
            output.append(f"Exit Code: {result.returncode}")
            if result.stdout.strip():
                output.append("--- STDOUT ---")
                output.append(result.stdout.strip())
            if result.stderr.strip():
                output.append("--- STDERR ---")
                output.append(result.stderr.strip())
            if not result.stdout.strip() and not result.stderr.strip():
                output.append("(No output)")
            return "\n".join(output)
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout_seconds} seconds."
        except Exception as e:
            return f"Execution error: {e}"

    def get_patch(self) -> str:
        """
        Return the git diff of changes made in the workspace.
        """
        diff_res = subprocess.run(
            f'git diff HEAD -- "{self.workspace_dir}"',
            cwd=str(self.workspace_dir),
            shell=True,
            capture_output=True,
            text=True,
        )
        return diff_res.stdout

    def search_similar_code(self, query: str, k: int = 5) -> str:
        """
        Semantic code retrieval across indexed repository components.
        """
        if self.retriever is None:
            return "Semantic retriever is not configured for this workspace."
        results = self.retriever.retrieve(query, top_k=k)
        if not results:
            return f"No semantically similar code found for '{query}'."
        lines = [f"Found {len(results)} semantically similar code components:"]
        for idx, r in enumerate(results, 1):
            lines.append(
                f"{idx}. {r['file_path']} -> {r['symbol_type']} `{r['symbol_name']}` "
                f"(lines {r['start_line']}-{r['end_line']}, similarity: {r['score']:.2f})"
            )
        return "\n".join(lines)

    def get_code_neighbors(self, node_id: str, direction: str = "both") -> str:
        """
        Return the immediate graph neighbors of a code node.

        node_id:   A qualified node ID such as 'shop/cart.py::ShoppingCart::remove_item'
        direction: 'incoming', 'outgoing', or 'both' (default)
        """
        if self.code_graph is None:
            return "Code graph is not configured for this workspace."
        try:
            from .graph.graph_query import get_code_neighbors as _gcn
            results = _gcn(self.code_graph, node_id, direction=direction)
        except (ValueError, TypeError) as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Graph query failed: {e}"

        if not results:
            if not self.code_graph.graph.has_node(node_id):
                return f"Node '{node_id}' not found in the code graph."
            return f"Node '{node_id}' has no {direction} neighbors."

        lines = [f"Neighbors of '{node_id}' (direction={direction}):"]
        for r in results:
            arrow = "->" if r["direction"] == "outgoing" else "<-"
            lines.append(
                f"  [{r['direction']}] {r['relationship']} {arrow} {r['neighbor_id']}"
                f"  ({r['node_type']}, {r['file_path']}:{r['line']})"
            )
        return "\n".join(lines)

    def get_code_subgraph(
        self, node_id: str, max_depth: int = 2, direction: str = "both"
    ) -> str:
        """
        Return a bounded multi-hop subgraph rooted at a code node.

        node_id:   A qualified node ID such as 'shop/cart.py::ShoppingCart'
        max_depth: How many hops to traverse (default 2)
        direction: 'incoming', 'outgoing', or 'both' (default)
        """
        if self.code_graph is None:
            return "Code graph is not configured for this workspace."
        try:
            from .graph.graph_query import get_code_subgraph as _gcs
            result = _gcs(self.code_graph, node_id, max_depth=max_depth, direction=direction)
        except (ValueError, TypeError) as e:
            return f"Error: {e}"
        except Exception as e:
            return f"Graph subgraph query failed: {e}"

        if result["root"] is None:
            return f"Node '{node_id}' not found in the code graph."

        root = result["root"]
        nodes = result["nodes"]
        edges = result["edges"]

        lines = [
            f"Subgraph rooted at '{node_id}' (max_depth={max_depth}, direction={direction}):",
            f"  Root: {root['node_type']} `{root['symbol_name']}` at {root['file_path']}:{root['line']}",
            f"  Discovered {len(nodes)} node(s), {len(edges)} edge(s).",
        ]
        if nodes:
            lines.append("  Nodes:")
            for n in nodes:
                lines.append(
                    f"    [depth {n['depth']}] {n['node_id']}"
                    f"  ({n['node_type']}, {n['file_path']}:{n['line']})"
                )
        if edges:
            lines.append("  Edges:")
            for e in edges:
                lines.append(
                    f"    {e['source']} --[{e['relationship']}]--> {e['target']}"
                )
        return "\n".join(lines)

    def execute(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Dispatch a tool call by name with arguments."""
        tool_map = {
            "list_files": lambda a: self.list_files(a.get("directory", ".")),
            "read_file": lambda a: self.read_file(
                a.get("path", ""),
                a.get("start_line", 1),
                a.get("end_line"),
            ),
            "search_code": lambda a: self.search_code(
                a.get("query", ""),
                a.get("directory", "."),
            ),
            "search_similar_code": lambda a: self.search_similar_code(
                a.get("query", ""),
                a.get("k", 5),
            ),
            "get_code_neighbors": lambda a: self.get_code_neighbors(
                a.get("node_id", ""),
                a.get("direction", "both"),
            ),
            "get_code_subgraph": lambda a: self.get_code_subgraph(
                a.get("node_id", ""),
                a.get("max_depth", 2),
                a.get("direction", "both"),
            ),
            "edit_file": lambda a: self.edit_file(
                a.get("path", ""),
                a.get("target_string", ""),
                a.get("replacement_string", ""),
            ),
            "run_command": lambda a: self.run_command(
                a.get("command", ""),
                a.get("timeout_seconds", 30),
            ),
            "get_patch": lambda a: self.get_patch(),
        }

        if tool_name not in tool_map:
            return f"Error: Unknown tool '{tool_name}'. Available tools: {list(tool_map.keys())}"

        try:
            return tool_map[tool_name](args)
        except Exception as e:
            return f"Tool execution failed: {e}"
