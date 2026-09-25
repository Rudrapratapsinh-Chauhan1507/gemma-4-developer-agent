"""Code chunking component (Step 2.5).

Splits source files into semantically meaningful code units (classes, functions, methods)
using Python's built-in `ast` parser, with a line-window fallback for syntax-broken
or non-Python files.

Tradeoff Documentation:
- AST Parsing: Guarantees chunks match exact semantic symbol boundaries (e.g. entire functions or
  methods with their docstrings). High semantic coherence for vector embeddings.
- Line Window Fallback: Necessary for non-Python files or files with temporary syntax errors.
  May split logical units across chunk boundaries, but ensures zero unhandled exceptions.
"""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class CodeChunk:
    """Represents a discrete semantic chunk of source code."""
    file_path: str
    symbol_name: str
    symbol_type: str  # 'function', 'method', 'class', 'module', 'block'
    start_line: int
    end_line: int
    code: str
    docstring: Optional[str] = None

    def embedding_text(self) -> str:
        """Format text representation optimized for semantic vector embedding."""
        parts = [f"File: {self.file_path}", f"Symbol: {self.symbol_name} ({self.symbol_type})"]
        if self.docstring:
            parts.append(f"Description: {self.docstring.strip()}")
        parts.append(f"Code:\n{self.code.strip()}")
        return "\n".join(parts)


class CodeChunker:
    """Extracts code chunks from files using AST parsing or sliding fallback."""

    def __init__(self, fallback_chunk_lines: int = 50, fallback_overlap: int = 10):
        self.fallback_chunk_lines = fallback_chunk_lines
        self.fallback_overlap = fallback_overlap

    def chunk_file(self, file_path: str, content: str) -> List[CodeChunk]:
        """
        Chunk file content. Attempts AST parsing for Python files; falls back to line windows.
        """
        if not content.strip():
            return []

        if file_path.endswith(".py"):
            try:
                chunks = self._chunk_python_ast(file_path, content)
                if chunks:
                    return chunks
            except Exception:
                # If AST parsing fails due to syntax error, fall through to line-based chunking
                pass

        return self._chunk_line_window(file_path, content)

    def _chunk_python_ast(self, file_path: str, content: str) -> List[CodeChunk]:
        """Parse Python source code using AST and extract functions and classes."""
        tree = ast.parse(content)
        lines = content.splitlines(keepends=True)
        chunks: List[CodeChunk] = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                chunks.append(self._build_chunk(file_path, lines, node, "function", node.name))

            elif isinstance(node, ast.ClassDef):
                # 1. Add class overview chunk
                class_doc = ast.get_docstring(node)
                class_start = node.lineno
                class_end = node.end_lineno if hasattr(node, "end_lineno") else len(lines)
                class_code = "".join(lines[class_start - 1 : class_end])
                chunks.append(CodeChunk(
                    file_path=file_path,
                    symbol_name=node.name,
                    symbol_type="class",
                    start_line=class_start,
                    end_line=class_end,
                    code=class_code,
                    docstring=class_doc,
                ))

                # 2. Add individual methods as discrete searchable units
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_name = f"{node.name}.{item.name}"
                        chunks.append(self._build_chunk(file_path, lines, item, "method", method_name))

        # If file had only top-level code or imports without functions/classes
        if not chunks:
            chunks.append(CodeChunk(
                file_path=file_path,
                symbol_name=Path(file_path).stem,
                symbol_type="module",
                start_line=1,
                end_line=len(lines),
                code=content,
                docstring=ast.get_docstring(tree),
            ))

        return chunks

    def _build_chunk(
        self,
        file_path: str,
        lines: List[str],
        node: ast.AST,
        symbol_type: str,
        name: str
    ) -> CodeChunk:
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", len(lines))
        chunk_lines = lines[start_line - 1 : end_line]
        chunk_code = "".join(chunk_lines)
        docstring = ast.get_docstring(node)

        return CodeChunk(
            file_path=file_path,
            symbol_name=name,
            symbol_type=symbol_type,
            start_line=start_line,
            end_line=end_line,
            code=chunk_code,
            docstring=docstring,
        )

    def _chunk_line_window(self, file_path: str, content: str) -> List[CodeChunk]:
        """Fallback chunking for non-Python or unparseable files."""
        lines = content.splitlines(keepends=True)
        total_lines = len(lines)
        chunks: List[CodeChunk] = []

        if total_lines <= self.fallback_chunk_lines:
            return [CodeChunk(
                file_path=file_path,
                symbol_name=Path(file_path).name,
                symbol_type="block",
                start_line=1,
                end_line=total_lines,
                code=content,
            )]

        step = max(1, self.fallback_chunk_lines - self.fallback_overlap)
        for start_idx in range(0, total_lines, step):
            end_idx = min(total_lines, start_idx + self.fallback_chunk_lines)
            chunk_code = "".join(lines[start_idx:end_idx])
            chunks.append(CodeChunk(
                file_path=file_path,
                symbol_name=f"{Path(file_path).stem}:L{start_idx + 1}-L{end_idx}",
                symbol_type="block",
                start_line=start_idx + 1,
                end_line=end_idx,
                code=chunk_code,
            ))
            if end_idx >= total_lines:
                break

        return chunks
