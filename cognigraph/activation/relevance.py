"""Query-node relevance scoring for subgraph activation.

v2: Chunk-aware + property-aware scoring.
- Node embedding includes label + type + description + top chunk summaries
- Property-aware boosts for framework/article matches
- Content-hash caching for embedding invalidation
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, TYPE_CHECKING

import numpy as np

from cognigraph.activation.embeddings import EmbeddingEngine, cosine_similarity

if TYPE_CHECKING:
    from cognigraph.core.graph import CogniGraph

logger = logging.getLogger("cognigraph.relevance")


class RelevanceScorer:
    """Computes relevance scores between a query and graph nodes.

    Scores are used as PCST prizes — higher relevance = higher prize
    = more likely to be included in the activated subgraph.
    """

    def __init__(
        self,
        embedding_engine: EmbeddingEngine | None = None,
        chunk_aware: bool = True,
        property_boost: bool = True,
    ) -> None:
        self.embedding_engine = embedding_engine or EmbeddingEngine()
        self.chunk_aware = chunk_aware
        self.property_boost = property_boost

    def score(
        self, graph: CogniGraph, query: str
    ) -> dict[str, float]:
        """Compute relevance scores for all nodes."""
        query_embedding = self.embedding_engine.embed(query)
        query_lower = query.lower()

        scores: dict[str, float] = {}
        for node_id, node in graph.nodes.items():
            # Build embedding text — chunk-aware (v2)
            emb_text = self._build_embedding_text(node)
            content_hash = hashlib.md5(emb_text.encode()).hexdigest()

            # Recompute embedding if content changed or not cached
            cached_hash = node.properties.get("_emb_hash", "")
            if node.embedding is None or cached_hash != content_hash:
                node.embedding = self.embedding_engine.embed(emb_text)
                node.properties["_emb_hash"] = content_hash

            sim = cosine_similarity(query_embedding, node.embedding)
            score = max(sim, 0.0)

            # Property-aware boosts (v2)
            if self.property_boost:
                score = self._apply_property_boosts(score, node, query_lower)

            scores[node_id] = score

        return scores

    def _build_embedding_text(self, node: Any) -> str:
        """Build embedding text — includes chunks for chunk-aware activation."""
        parts = [node.label, node.entity_type, node.description]

        if self.chunk_aware:
            chunks = node.properties.get("chunks", [])
            for chunk in chunks[:3]:  # top 3 chunks
                if isinstance(chunk, dict):
                    text = chunk.get("text", "")
                elif isinstance(chunk, str):
                    text = chunk
                else:
                    continue
                # Take first 200 chars of each chunk
                if text:
                    parts.append(text[:200])

        return " ".join(p for p in parts if p)

    @staticmethod
    def _apply_property_boosts(
        score: float, node: Any, query_lower: str
    ) -> float:
        """Apply property-aware boosts based on query-node property matches."""
        boost = 0.0

        # Framework name boost: query mentions framework AND node has matching framework
        framework = node.properties.get("framework", "")
        if framework and framework.lower() in query_lower:
            boost += 0.25

        # Article number boost: query mentions article AND node has matching articles
        articles = node.properties.get("articles", [])
        if articles:
            if isinstance(articles, str):
                articles = [articles]
            for art in articles:
                art_str = str(art).lower()
                # Match patterns like "art. 14", "article 14", "art 14"
                art_num = re.sub(r"[^0-9]", "", art_str)
                if art_num and (
                    f"art. {art_num}" in query_lower
                    or f"article {art_num}" in query_lower
                    or f"art {art_num}" in query_lower
                ):
                    boost += 0.3
                    break

        # Entity type name in query
        if node.entity_type.lower().replace("_", " ") in query_lower:
            boost += 0.1

        return min(score + boost, 1.0)
