"""Keyword retrieval baseline component (Step 2.2).

Provides term-matching and token-frequency retrieval over repository files.
Serves as an empirical baseline to compare against semantic dense retrieval.
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Set
from .discovery import FileDiscovery


class KeywordRetriever:
    """Keyword-based search baseline across repository files."""

    STOPWORDS: Set[str] = {
        "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by",
        "and", "or", "is", "are", "was", "were", "be", "been", "being",
        "it", "this", "that", "these", "those", "i", "we", "you", "they",
        "as", "from", "so", "if", "not", "but", "than", "too", "very", "can"
    }

    def __init__(self, workspace_dir: str):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.discovery = FileDiscovery(workspace_dir)

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract clean alphanumeric query tokens, filtering out stopwords."""
        tokens = re.findall(r"[A-Za-z0-9_]+", text.lower())
        keywords = [t for t in tokens if len(t) > 2 and t not in self.STOPWORDS]
        return list(dict.fromkeys(keywords))  # Preserves order, removes duplicates

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve top-k files matching keywords in query.
        Returns a list of dicts with file path, score, matched keywords, and preview.
        """
        keywords = self._extract_keywords(query)
        if not keywords:
            return []

        files = self.discovery.discover_files()
        results: List[Dict[str, Any]] = []

        for rel_path in files:
            abs_path = self.workspace_dir / rel_path
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception:
                continue

            total_matches = 0
            matched_terms: Set[str] = set()
            matching_lines: List[Dict[str, Any]] = []

            for line_no, line in enumerate(lines, 1):
                line_lower = line.lower()
                line_matched = [kw for kw in keywords if kw in line_lower]
                if line_matched:
                    total_matches += len(line_matched)
                    matched_terms.update(line_matched)
                    if len(matching_lines) < 3:
                        matching_lines.append({
                            "line_number": line_no,
                            "content": line.strip()
                        })

            if total_matches > 0:
                # Score combines term diversity and raw frequency
                diversity_bonus = len(matched_terms) * 10
                score = diversity_bonus + total_matches

                results.append({
                    "file_path": rel_path.as_posix(),
                    "score": score,
                    "matched_keywords": sorted(list(matched_terms)),
                    "total_occurrences": total_matches,
                    "preview_lines": matching_lines,
                })

        # Sort descending by score
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]
