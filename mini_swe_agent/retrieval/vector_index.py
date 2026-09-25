"""Local vector indexing component using FAISS (Step 2.4).

Maintains an in-memory FAISS vector index with associated code chunk metadata.
Operates completely offline with zero cloud dependencies.
"""

from typing import List, Dict, Any, Optional
import numpy as np
import faiss
from .chunker import CodeChunk


class FaissVectorIndex:
    """Local FAISS vector index for code chunks with metadata mapping."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        # IndexFlatIP calculates inner product; on normalized vectors, this equals cosine similarity
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata: List[Dict[str, Any]] = []

    def add(self, embeddings: np.ndarray, chunks: List[CodeChunk]) -> None:
        """
        Add code chunk embeddings and their corresponding metadata to the index.
        """
        if len(embeddings) == 0:
            return

        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        if embeddings.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dimension}, got {embeddings.shape[1]}"
            )

        # Ensure float32 format for FAISS
        embeddings_f32 = np.ascontiguousarray(embeddings, dtype=np.float32)

        start_id = len(self.metadata)
        self.index.add(embeddings_f32)

        for idx, chunk in enumerate(chunks):
            self.metadata.append({
                "index_id": start_id + idx,
                "file_path": chunk.file_path,
                "symbol_name": chunk.symbol_name,
                "symbol_type": chunk.symbol_type,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "code": chunk.code,
                "docstring": chunk.docstring,
                "chunk": chunk,
            })

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for top-k code chunks closest to query_embedding.
        Returns a list of dicts containing score, chunk metadata, and similarity.
        """
        if self.index.ntotal == 0:
            return []

        if query_embedding.ndim == 1:
            query_vector = query_embedding.reshape(1, -1)
        else:
            query_vector = query_embedding

        query_f32 = np.ascontiguousarray(query_vector, dtype=np.float32)
        k = min(top_k, self.index.ntotal)

        distances, indices = self.index.search(query_f32, k)

        results: List[Dict[str, Any]] = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            meta = dict(self.metadata[idx])
            meta["score"] = float(dist)  # Cosine similarity score [-1.0, 1.0]
            results.append(meta)

        return results

    def clear(self) -> None:
        """Clear all indexed vectors and metadata."""
        self.index.reset()
        self.metadata.clear()

    def size(self) -> int:
        """Return the number of indexed vectors."""
        return self.index.ntotal
