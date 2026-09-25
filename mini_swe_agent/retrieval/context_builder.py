"""Context builder component (Step 2.7).

Transforms semantic retrieval results into compact, structured context
for the SWE agent while enforcing character/chunk budgets.
"""

from pathlib import Path
from typing import List, Dict, Any


class ContextBuilder:
    """Formats retrieved code chunks into structured agent prompt context."""

    def __init__(
        self,
        max_chunks: int = 3,
        max_chars_per_chunk: int = 1500,
        max_total_chars: int = 4000,
    ):
        self.max_chunks = max_chunks
        self.max_chars_per_chunk = max_chars_per_chunk
        self.max_total_chars = max_total_chars

    def build_context(self, retrieved_chunks: List[Dict[str, Any]]) -> str:
        """
        Convert retrieved search results into a clean, markdown-formatted context string.
        """
        if not retrieved_chunks:
            return ""

        chunks_to_include = retrieved_chunks[: self.max_chunks]
        output_parts: List[str] = [
            "### Relevant Repository Code Context (via Semantic Retrieval)",
            "The following code sections were identified as most relevant to the issue:\n",
        ]

        total_chars = sum(len(p) for p in output_parts)

        for idx, item in enumerate(chunks_to_include, 1):
            file_path = item.get("file_path", "unknown")
            symbol_name = item.get("symbol_name", "unknown")
            symbol_type = item.get("symbol_type", "code")
            start_line = item.get("start_line", 1)
            end_line = item.get("end_line", 1)
            score = item.get("score", 0.0)
            raw_code = item.get("code", "").strip()

            # Truncate individual chunk if oversized
            if len(raw_code) > self.max_chars_per_chunk:
                raw_code = raw_code[: self.max_chars_per_chunk] + "\n... [truncated]"

            header = f"[{idx}] {file_path} -> {symbol_type} `{symbol_name}` (lines {start_line}-{end_line}, similarity: {score:.2f}):"
            code_block = f"```{Path(file_path).suffix.lstrip('.') or 'python'}\n{raw_code}\n```"

            chunk_text = f"{header}\n{code_block}\n"

            if total_chars + len(chunk_text) > self.max_total_chars:
                output_parts.append(
                    f"\n(Note: Additional {len(chunks_to_include) - idx + 1} retrieved chunks omitted due to context limit.)"
                )
                break

            output_parts.append(chunk_text)
            total_chars += len(chunk_text)

        return "\n".join(output_parts)
