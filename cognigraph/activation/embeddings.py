"""Embedding computation for query-node relevance scoring."""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("cognigraph.embeddings")


class EmbeddingEngine:
    """Computes embeddings for queries and node descriptions.

    Uses sentence-transformers if available, falls back to
    simple TF-IDF bag-of-words for zero-dependency operation.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model = None
        self._use_simple = False

    def _load(self) -> None:
        if self._model is not None or self._use_simple:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            logger.info(f"Loaded embedding model: {self._model_name}")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed, using bag-of-words fallback. "
                "Install with: pip install sentence-transformers"
            )
            self._use_simple = True

    def embed(self, text: str) -> np.ndarray:
        """Embed a single text string."""
        self._load()
        if self._use_simple:
            return self._simple_embed(text)
        return self._model.encode(text, normalize_embeddings=True)

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Embed a batch of text strings."""
        self._load()
        if self._use_simple:
            return np.array([self._simple_embed(t) for t in texts])
        return self._model.encode(texts, normalize_embeddings=True)

    @staticmethod
    def _simple_embed(text: str, dim: int = 128) -> np.ndarray:
        """Simple hash-based embedding fallback (no ML dependencies)."""
        words = text.lower().split()
        vec = np.zeros(dim)
        for i, word in enumerate(words):
            h = hash(word) % dim
            vec[h] += 1.0 / (i + 1)  # position-weighted
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))
