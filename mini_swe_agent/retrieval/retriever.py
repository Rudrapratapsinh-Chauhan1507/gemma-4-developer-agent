"""Semantic retriever component (Step 2.6).

Coordinates file discovery, code chunking, dense vector embedding,
and FAISS search to retrieve the most semantically relevant code components
for a given software issue.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from .discovery import FileDiscovery
from .chunker import CodeChunker, CodeChunk
from .embedder import CodeEmbedder
from .vector_index import FaissVectorIndex


class SemanticRetriever:
    """End-to-end repository semantic retriever."""

    def __init__(
        self,
        workspace_dir: str,
        embedder: Optional[CodeEmbedder] = None,
        chunker: Optional[CodeChunker] = None,
        vector_index: Optional[FaissVectorIndex] = None,
    ):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.discovery = FileDiscovery(workspace_dir)
        self.chunker = chunker or CodeChunker()
        self.embedder = embedder or CodeEmbedder()
        self.vector_index = vector_index or FaissVectorIndex()
        self._is_indexed = False

    def index_repository(self) -> int:
        """
        Scan workspace files, chunk code, embed chunks, and populate the FAISS index.
        Returns the total number of indexed code chunks.
        """
        self.vector_index.clear()
        files = self.discovery.discover_files()
        all_chunks: List[CodeChunk] = []

        for rel_path in files:
            abs_path = self.workspace_dir / rel_path
            try:
                with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            chunks = self.chunker.chunk_file(rel_path.as_posix(), content)
            all_chunks.extend(chunks)

        if all_chunks:
            embeddings = self.embedder.embed_chunks(all_chunks)
            self.vector_index.add(embeddings, all_chunks)

        self._is_indexed = True
        return len(all_chunks)

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve top-k semantically relevant code chunks for a given issue query.
        """
        if not self._is_indexed:
            self.index_repository()

        if not query.strip() or self.vector_index.size() == 0:
            return []

        query_embedding = self.embedder.embed_query(query)
        results = self.vector_index.search(query_embedding, top_k=top_k)
        return results
