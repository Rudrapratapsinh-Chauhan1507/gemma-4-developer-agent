"""Code graph package for Stage 3 — Code-Relationship & Graph Retrieval.

Provides AST-based static analysis that builds a directed NetworkX graph
representing the structural and relational landscape of a Python repository.

Public API (Stage 3, Task 1):
    CodeGraphBuilder   — builds the graph from a workspace directory
    CodeGraph          — thin wrapper around a networkx.DiGraph with helpers

Node types:
    "module"   — a Python source file
    "class"    — a class definition
    "function" — a module-level function
    "method"   — a function defined inside a class

Edge (relationship) types:
    "contains" — a module contains a class/function, or a class contains a method
    "imports"  — a module imports another module (or symbol from a module)
    "calls"    — a function/method calls another named function/method
"""

from .ast_graph import CodeGraphBuilder, CodeGraph
from .graph_query import get_code_neighbors, get_code_subgraph

__all__ = ["CodeGraphBuilder", "CodeGraph", "get_code_neighbors", "get_code_subgraph"]
