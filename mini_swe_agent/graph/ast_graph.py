"""AST-based code graph builder for Stage 3.

Walks a Python workspace, parses each .py file using the built-in ast module,
and constructs a directed NetworkX graph (DiGraph) where:

Nodes represent code entities:
    - module    (one per .py file)
    - class     (ast.ClassDef)
    - function  (ast.FunctionDef / ast.AsyncFunctionDef at module level)
    - method    (ast.FunctionDef / ast.AsyncFunctionDef inside a class)

Directed edges represent relationships:
    - contains  (parent -> child structural containment)
    - imports   (module -> imported module, extracted from ast.Import / ast.ImportFrom)
    - calls     (function/method -> called name, extracted from ast.Call nodes)

Design decisions:
    - Invalid/unparseable .py files are skipped with a warning; scan continues.
    - Node IDs are qualified names such as "shop/cart.py::ShoppingCart::remove_item".
    - Cross-file call resolution is name-based (best-effort); dynamic dispatch is not
      attempted — this is documented as a known limitation.
    - Only .py files are parsed; non-Python files are ignored in this module.
"""

import ast
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_IGNORED_DIRS: Set[str] = {
    "__pycache__", ".git", ".venv", "venv", "env",
    ".tox", "node_modules", "build", "dist", ".mypy_cache",
    ".pytest_cache", "*.egg-info",
}

_NODE_TYPE_MODULE = "module"
_NODE_TYPE_CLASS = "class"
_NODE_TYPE_FUNCTION = "function"
_NODE_TYPE_METHOD = "method"

_EDGE_CONTAINS = "contains"
_EDGE_IMPORTS = "imports"
_EDGE_CALLS = "calls"


# ---------------------------------------------------------------------------
# CodeGraph — lightweight wrapper around nx.DiGraph
# ---------------------------------------------------------------------------
class CodeGraph:
    """Thin wrapper around a nx.DiGraph providing typed access helpers."""

    def __init__(self, graph: nx.DiGraph) -> None:
        self.graph = graph

    # ------------------------------------------------------------------
    # Node queries
    # ------------------------------------------------------------------
    def nodes_of_type(self, node_type: str) -> List[str]:
        """Return all node IDs of a given type."""
        return [
            n for n, data in self.graph.nodes(data=True)
            if data.get("node_type") == node_type
        ]

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Return the metadata dict for a node, or None if not found."""
        return self.graph.nodes.get(node_id)

    # ------------------------------------------------------------------
    # Edge queries
    # ------------------------------------------------------------------
    def edges_of_type(self, edge_type: str) -> List[Tuple[str, str]]:
        """Return all (src, dst) pairs for edges of a given type."""
        return [
            (u, v)
            for u, v, data in self.graph.edges(data=True)
            if data.get("relationship") == edge_type
        ]

    def neighbors_of(self, node_id: str, edge_type: Optional[str] = None) -> List[str]:
        """Return successors of node_id, optionally filtered by edge type."""
        result = []
        for _, successor, data in self.graph.out_edges(node_id, data=True):
            if edge_type is None or data.get("relationship") == edge_type:
                result.append(successor)
        return result

    def predecessors_of(self, node_id: str, edge_type: Optional[str] = None) -> List[str]:
        """Return predecessors of node_id, optionally filtered by edge type."""
        result = []
        for predecessor, _, data in self.graph.in_edges(node_id, data=True):
            if edge_type is None or data.get("relationship") == edge_type:
                result.append(predecessor)
        return result

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def summary(self) -> str:
        """Return a human-readable summary of the graph."""
        node_counts: Dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            nt = data.get("node_type", "unknown")
            node_counts[nt] = node_counts.get(nt, 0) + 1

        edge_counts: Dict[str, int] = {}
        for _, _, data in self.graph.edges(data=True):
            et = data.get("relationship", "unknown")
            edge_counts[et] = edge_counts.get(et, 0) + 1

        lines = [
            f"CodeGraph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges",
            f"  Nodes: {node_counts}",
            f"  Edges: {edge_counts}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal AST visitor — extracts per-file entities
# ---------------------------------------------------------------------------
class _FileVisitor(ast.NodeVisitor):
    """Walks the AST of a single Python file and collects entities."""

    def __init__(self, file_id: str) -> None:
        # file_id is the relative path used as the module node ID
        self.file_id = file_id
        self.entities: List[Dict[str, Any]] = []   # collected nodes
        self.relations: List[Tuple[str, str, str]] = []  # (src, dst, rel_type)
        self._class_stack: List[str] = []  # tracks nesting context

    # ---- Helpers -----------------------------------------------------------

    def _qualified_name(self, symbol: str) -> str:
        """Build a node ID: 'file_id::ClassName::method_name'."""
        parts = [self.file_id] + self._class_stack + [symbol]
        return "::".join(parts)

    def _add_contains(self, parent_id: str, child_id: str) -> None:
        self.relations.append((parent_id, child_id, _EDGE_CONTAINS))

    # ---- Visitors ----------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        """ast.Import: 'import os', 'import os, sys'"""
        for alias in node.names:
            imported_name = alias.name  # e.g. "os" or "os.path"
            self.relations.append((self.file_id, imported_name, _EDGE_IMPORTS))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """ast.ImportFrom: 'from pathlib import Path'"""
        if node.module:
            self.relations.append((self.file_id, node.module, _EDGE_IMPORTS))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Record a class node and process its body."""
        class_id = self._qualified_name(node.name)
        parent_id = (
            "::".join([self.file_id] + self._class_stack) if self._class_stack
            else self.file_id
        )

        self.entities.append({
            "node_id": class_id,
            "node_type": _NODE_TYPE_CLASS,
            "symbol_name": node.name,
            "qualified_name": class_id,
            "file_path": self.file_id,
            "line": node.lineno,
        })
        self._add_contains(parent_id, class_id)

        # Process class body with self nested in class context
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def _visit_function(self, node: ast.FunctionDef) -> None:
        """Shared logic for FunctionDef and AsyncFunctionDef."""
        func_id = self._qualified_name(node.name)
        parent_id = (
            "::".join([self.file_id] + self._class_stack) if self._class_stack
            else self.file_id
        )

        node_type = _NODE_TYPE_METHOD if self._class_stack else _NODE_TYPE_FUNCTION

        self.entities.append({
            "node_id": func_id,
            "node_type": node_type,
            "symbol_name": node.name,
            "qualified_name": func_id,
            "file_path": self.file_id,
            "line": node.lineno,
        })
        self._add_contains(parent_id, func_id)

        # Extract call relationships from this function's body
        call_collector = _CallCollector(func_id)
        call_collector.visit(node)
        self.relations.extend(call_collector.calls)

        # Do NOT recurse with generic_visit here to avoid double-visiting
        # nested functions — we handle them by calling visit on child nodes
        for child in ast.iter_child_nodes(node):
            self.visit(child)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Separate visitor for collecting call() sites within a function body
# ---------------------------------------------------------------------------
class _CallCollector(ast.NodeVisitor):
    """Walks a function body and emits call edges."""

    def __init__(self, caller_id: str) -> None:
        self.caller_id = caller_id
        self.calls: List[Tuple[str, str, str]] = []

    def visit_Call(self, node: ast.Call) -> None:
        callee_name = self._resolve_name(node.func)
        if callee_name:
            self.calls.append((self.caller_id, callee_name, _EDGE_CALLS))
        self.generic_visit(node)

    @staticmethod
    def _resolve_name(node: ast.expr) -> Optional[str]:
        """Extract a dotted name string from a Call's func node."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            owner = _CallCollector._resolve_name(node.value)
            if owner:
                return f"{owner}.{node.attr}"
        return None


# ---------------------------------------------------------------------------
# CodeGraphBuilder — the main public class
# ---------------------------------------------------------------------------
class CodeGraphBuilder:
    """Builds a directed code relationship graph from a Python workspace.

    Usage::

        builder = CodeGraphBuilder("path/to/workspace")
        code_graph = builder.build()
        print(code_graph.summary())
    """

    def __init__(self, workspace_dir: str) -> None:
        self.workspace_dir = Path(workspace_dir).resolve()
        if not self.workspace_dir.exists():
            raise FileNotFoundError(
                f"Workspace directory does not exist: {self.workspace_dir}"
            )
        self.parse_errors: Dict[str, str] = {}  # rel_path -> error message

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self) -> CodeGraph:
        """Parse the workspace and return a populated CodeGraph.

        Files with syntax errors are skipped; errors are logged in
        self.parse_errors and do not abort the overall scan.
        """
        graph = nx.DiGraph()
        python_files = self._discover_python_files()

        for rel_path in python_files:
            abs_path = self.workspace_dir / rel_path
            self._process_file(graph, rel_path, abs_path)

        return CodeGraph(graph)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _discover_python_files(self) -> List[str]:
        """Walk the workspace and return relative paths to all .py files."""
        py_files: List[str] = []

        for root, dirs, files in os.walk(self.workspace_dir):
            # Prune ignored directories in-place to prevent descent
            dirs[:] = [
                d for d in dirs
                if d not in _IGNORED_DIRS and not d.endswith(".egg-info")
            ]

            for filename in files:
                if filename.endswith(".py"):
                    abs_file = Path(root) / filename
                    rel = abs_file.relative_to(self.workspace_dir)
                    py_files.append(rel.as_posix())

        return sorted(py_files)

    def _process_file(
        self, graph: nx.DiGraph, rel_path: str, abs_path: Path
    ) -> None:
        """Parse one Python file and add its nodes/edges to the graph."""
        try:
            source = abs_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source, filename=rel_path)
        except SyntaxError as exc:
            self.parse_errors[rel_path] = f"SyntaxError: {exc}"
            return
        except Exception as exc:  # pragma: no cover
            self.parse_errors[rel_path] = f"ParseError: {exc}"
            return

        # Add module node
        graph.add_node(
            rel_path,
            node_type=_NODE_TYPE_MODULE,
            symbol_name=Path(rel_path).stem,
            qualified_name=rel_path,
            file_path=rel_path,
            line=1,
        )

        # Walk the AST
        visitor = _FileVisitor(rel_path)
        visitor.visit(tree)

        # Add entity nodes
        for entity in visitor.entities:
            node_id = entity["node_id"]
            graph.add_node(node_id, **{k: v for k, v in entity.items() if k != "node_id"})

        # Add relationship edges
        for src, dst, rel_type in visitor.relations:
            # Ensure destination node exists for non-structural edges
            # (imports / calls target may not be in the graph — that is fine,
            # we still record the edge but mark it as unresolved if needed)
            if not graph.has_node(dst):
                graph.add_node(
                    dst,
                    node_type="external",
                    symbol_name=dst,
                    qualified_name=dst,
                    file_path="<external>",
                    line=0,
                )
            graph.add_edge(src, dst, relationship=rel_type)
