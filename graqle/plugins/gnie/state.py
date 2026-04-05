"""GNIE State Manager — per-model learning across sessions.

Persists learning state to .graqle/gnie_state.json in the project directory.
State is keyed by model identifier (backend.name), not backend type.

Learns from graq_predict fold-back:
  - WRITTEN -> good routing, boost those nodes
  - SKIPPED_LOW_CONFIDENCE -> learn to avoid

This module NEVER imports CogniNode or Graqle — dependency flows
one way: CogniNode -> GNIE, never reverse.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class GnieState:
    """Persistent GNIE learning state — keyed by model ID."""

    # Counters
    queries_processed: int = 0
    fold_back_writes: int = 0
    fold_back_skips: int = 0

    # Node activation frequency (which nodes contribute to good answers)
    node_scores: Dict[str, float] = field(default_factory=dict)

    # Model performance tracking — keyed by backend.name (e.g. "ollama:qwen2.5:3b")
    model_stats: Dict[str, Dict] = field(default_factory=dict)

    # Metadata
    created_at: str = ""
    updated_at: str = ""
    version: str = "0.1.0"

    def record_query(self, activated_node_ids: List[str], model: str) -> None:
        """Record that a query was processed."""
        self.queries_processed += 1
        self.updated_at = datetime.now().isoformat()

        # Track model usage
        if model not in self.model_stats:
            self.model_stats[model] = {"queries": 0, "writes": 0, "skips": 0}
        self.model_stats[model]["queries"] += 1

    def record_fold_back(
        self,
        status: str,
        activated_node_ids: List[str],
        confidence: float,
        model: str,
    ) -> None:
        """Learn from graq_predict fold-back result.

        status: "WRITTEN" | "SKIPPED_LOW_CONFIDENCE" | "SKIPPED_DUPLICATE" | "DRY_RUN"
        """
        # Auto-init model stats if not present
        if model not in self.model_stats:
            self.model_stats[model] = {"queries": 0, "writes": 0, "skips": 0}

        if status == "WRITTEN":
            self.fold_back_writes += 1
            # Boost scores for nodes that contributed to successful prediction
            for node_id in activated_node_ids:
                self.node_scores[node_id] = self.node_scores.get(node_id, 0.5) + 0.05
                self.node_scores[node_id] = min(1.0, self.node_scores[node_id])
            self.model_stats[model]["writes"] += 1

        elif status == "SKIPPED_LOW_CONFIDENCE":
            self.fold_back_skips += 1
            # Slightly penalize nodes that were activated but produced low confidence
            for node_id in activated_node_ids:
                self.node_scores[node_id] = self.node_scores.get(node_id, 0.5) - 0.02
                self.node_scores[node_id] = max(0.1, self.node_scores[node_id])
            self.model_stats[model]["skips"] += 1

        self.updated_at = datetime.now().isoformat()

    def get_node_boost(self, node_id: str) -> float:
        """Get the GNIE boost score for a node (0.1 to 1.0, default 0.5)."""
        return self.node_scores.get(node_id, 0.5)

    def get_calibration_data(self, model: str) -> Dict:
        """Get fold-back history for confidence calibration."""
        stats = self.model_stats.get(model, {"queries": 0, "writes": 0, "skips": 0})
        return {
            "writes": stats.get("writes", 0),
            "skips": stats.get("skips", 0),
        }

    def save(self, path: str = ".graqle/gnie_state.json") -> None:
        """Save state to disk."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": self.version,
            "created_at": self.created_at or datetime.now().isoformat(),
            "updated_at": self.updated_at,
            "queries_processed": self.queries_processed,
            "fold_back_writes": self.fold_back_writes,
            "fold_back_skips": self.fold_back_skips,
            "model_stats": self.model_stats,
            # Only save top 500 nodes by score (keep file small)
            "node_scores": dict(
                sorted(self.node_scores.items(), key=lambda x: -x[1])[:500]
            ),
        }
        with open(p, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: str = ".graqle/gnie_state.json") -> "GnieState":
        """Load state from disk, or create fresh."""
        p = Path(path)
        if not p.exists():
            state = cls()
            state.created_at = datetime.now().isoformat()
            return state

        with open(p) as f:
            data = json.load(f)

        state = cls()
        state.version = data.get("version", "0.1.0")
        state.created_at = data.get("created_at", "")
        state.updated_at = data.get("updated_at", "")
        state.queries_processed = data.get("queries_processed", 0)
        state.fold_back_writes = data.get("fold_back_writes", 0)
        state.fold_back_skips = data.get("fold_back_skips", 0)
        state.model_stats = data.get("model_stats", {})
        state.node_scores = data.get("node_scores", {})
        return state
