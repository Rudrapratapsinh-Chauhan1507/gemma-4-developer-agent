"""Embedding generation component (Step 2.3).

Generates dense semantic vector embeddings for code chunks and software issue queries
using sentence-transformers (all-MiniLM-L6-v2).
"""

from typing import List, Optional
import numpy as np


class CodeEmbedder:
    """Wrapper around sentence-transformers for code and query vectorization."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        """Lazy load SentenceTransformer model to avoid startup delays."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Embed a list of text strings into normalized float32 vectors.
        Shape: (len(texts), embedding_dim)
        """
        if not texts:
            return np.empty((0, 384), dtype=np.float32)

        model = self._get_model()
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return np.asarray(embeddings, dtype=np.float32)

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a single issue description or search query.
        Returns 1D float32 normalized vector of shape (embedding_dim,).
        """
        vectors = self.embed_texts([query])
        return vectors[0]

    def embed_chunks(self, chunks: List["CodeChunk"]) -> np.ndarray:
        """
        Generate embeddings for a list of CodeChunk objects.
        Uses each chunk's structured embedding_text representation.
        """
        texts = [chunk.embedding_text() for chunk in chunks]
        return self.embed_texts(texts)
