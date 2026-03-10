"""PCST subgraph activation — Prize-Collecting Steiner Tree selection.

Given a query, selects the optimal subgraph to activate by:
1. Computing query-node relevance scores (prizes)
2. Computing edge costs (inverse semantic similarity)
3. Running PCST to find minimum-cost, maximum-prize subtree
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from cognigraph.activation.relevance import RelevanceScorer

if TYPE_CHECKING:
    from cognigraph.core.graph import CogniGraph

logger = logging.getLogger("cognigraph.activation")


class PCSTActivation:
    """Prize-Collecting Steiner Tree subgraph selection.

    Selects the optimal subset of nodes to activate for a query,
    balancing relevance (prizes) against graph distance (costs).
    This ensures only 4-16 nodes activate per query — not thousands.
    """

    def __init__(
        self,
        max_nodes: int = 50,
        prize_scaling: float = 1.0,
        cost_scaling: float = 1.0,
        pruning: str = "strong",
        relevance_scorer: RelevanceScorer | None = None,
    ) -> None:
        self.max_nodes = max_nodes
        self.prize_scaling = prize_scaling
        self.cost_scaling = cost_scaling
        self.pruning = pruning
        self.relevance_scorer = relevance_scorer or RelevanceScorer()

    def activate(self, graph: CogniGraph, query: str) -> list[str]:
        """Select nodes to activate for a query.

        Returns list of node IDs in the activated subgraph.
        Falls back to top-k if pcst_fast is not installed.
        """
        # 1. Compute relevance scores (prizes)
        relevance = self.relevance_scorer.score(graph, query)

        # 2. Try PCST, fall back to top-k
        try:
            return self._pcst_select(graph, relevance)
        except ImportError:
            logger.warning(
                "pcst_fast not installed, falling back to top-k selection. "
                "Install with: pip install pcst_fast"
            )
            return self._topk_select(relevance)

    def _pcst_select(
        self, graph: CogniGraph, relevance: dict[str, float]
    ) -> list[str]:
        """Run PCST algorithm for optimal subgraph selection."""
        import pcst_fast

        node_ids = list(graph.nodes.keys())
        node_idx = {nid: i for i, nid in enumerate(node_ids)}
        n = len(node_ids)

        # Prizes (relevance scores)
        prizes = np.array(
            [relevance.get(nid, 0.0) * self.prize_scaling for nid in node_ids]
        )

        # Edge arrays
        edges_list = []
        costs = []
        for edge in graph.edges.values():
            src_idx = node_idx.get(edge.source_id)
            tgt_idx = node_idx.get(edge.target_id)
            if src_idx is not None and tgt_idx is not None:
                edges_list.append([src_idx, tgt_idx])
                costs.append(edge.semantic_distance * self.cost_scaling)

        if not edges_list:
            # No edges — just return top-k by relevance
            return self._topk_select(relevance)

        edges_array = np.array(edges_list, dtype=np.int64)
        costs_array = np.array(costs, dtype=np.float64)

        # Run PCST
        selected_vertices, selected_edges = pcst_fast.pcst_fast(
            edges_array,
            prizes,
            costs_array,
            -1,               # No root constraint
            1,                # Single component
            self.pruning,
            0,                # Verbosity
        )

        # Map back to node IDs
        selected = [node_ids[i] for i in selected_vertices]

        # Enforce max_nodes
        if len(selected) > self.max_nodes:
            # Keep the most relevant
            selected.sort(key=lambda nid: relevance.get(nid, 0.0), reverse=True)
            selected = selected[: self.max_nodes]

        logger.info(
            f"PCST activated {len(selected)}/{n} nodes "
            f"(max_nodes={self.max_nodes})"
        )
        return selected

    def _topk_select(self, relevance: dict[str, float]) -> list[str]:
        """Fallback: select top-k nodes by relevance score."""
        sorted_nodes = sorted(relevance.items(), key=lambda x: x[1], reverse=True)
        k = min(self.max_nodes, len(sorted_nodes))
        selected = [nid for nid, _ in sorted_nodes[:k]]
        logger.info(f"Top-k activated {len(selected)} nodes")
        return selected
