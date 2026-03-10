"""Query-node relevance scoring for subgraph activation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from cognigraph.activation.embeddings import EmbeddingEngine, cosine_similarity

if TYPE_CHECKING:
    from cognigraph.core.graph import CogniGraph


class RelevanceScorer:
    """Computes relevance scores between a query and graph nodes.

    Scores are used as PCST prizes — higher relevance = higher prize
    = more likely to be included in the activated subgraph.
    """

    def __init__(
        self,
        embedding_engine: EmbeddingEngine | None = None,
    ) -> None:
        self.embedding_engine = embedding_engine or EmbeddingEngine()

    def score(
        self, graph: CogniGraph, query: str
    ) -> dict[str, float]:
        """Compute relevance scores for all nodes."""
        query_embedding = self.embedding_engine.embed(query)

        scores: dict[str, float] = {}
        for node_id, node in graph.nodes.items():
            # Use cached embedding or compute
            if node.embedding is None:
                text = f"{node.label} {node.entity_type} {node.description}"
                node.embedding = self.embedding_engine.embed(text)

            sim = cosine_similarity(query_embedding, node.embedding)
            scores[node_id] = max(sim, 0.0)  # clamp negatives

        return scores
