"""Convergence detection — determines when message passing should stop."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from cognigraph.core.message import Message

logger = logging.getLogger("cognigraph.convergence")


class ConvergenceDetector:
    """Determines when message-passing reasoning has converged.

    Convergence criteria (ANY triggers stop):
    1. max_rounds reached
    2. Average cosine similarity between rounds exceeds threshold
    3. All node confidences exceed confidence_threshold
    """

    def __init__(
        self,
        max_rounds: int = 5,
        min_rounds: int = 2,
        similarity_threshold: float = 0.95,
        confidence_threshold: float = 0.8,
    ) -> None:
        self.max_rounds = max_rounds
        self.min_rounds = min_rounds
        self.similarity_threshold = similarity_threshold
        self.confidence_threshold = confidence_threshold
        self._round = 0

    def check(
        self,
        current_round: int,
        current_messages: list[Message],
        previous_messages: list[Message] | None,
    ) -> bool:
        """Returns True if reasoning has converged."""
        self._round = current_round

        # Never stop before min_rounds
        if current_round < self.min_rounds:
            return False

        # Always stop at max_rounds
        if current_round >= self.max_rounds:
            logger.info(f"Converged: max_rounds ({self.max_rounds}) reached")
            return True

        # Check confidence threshold
        if current_messages:
            avg_confidence = sum(m.confidence for m in current_messages) / len(
                current_messages
            )
            if avg_confidence >= self.confidence_threshold:
                logger.info(
                    f"Converged: avg confidence {avg_confidence:.2f} >= {self.confidence_threshold}"
                )
                return True

        # Check semantic similarity between rounds
        if previous_messages and current_messages:
            similarity = self._compute_round_similarity(
                current_messages, previous_messages
            )
            if similarity >= self.similarity_threshold:
                logger.info(
                    f"Converged: round similarity {similarity:.3f} >= {self.similarity_threshold}"
                )
                return True

        return False

    def _compute_round_similarity(
        self,
        current: list[Message],
        previous: list[Message],
    ) -> float:
        """Compute average similarity between current and previous round messages.

        Uses simple bag-of-words cosine similarity as a lightweight check.
        For production, swap with sentence-transformers embeddings.
        """
        if not current or not previous:
            return 0.0

        similarities = []
        for curr_msg in current:
            # Find the matching previous message from the same node
            prev_match = [
                p for p in previous if p.source_node_id == curr_msg.source_node_id
            ]
            if prev_match:
                sim = self._text_similarity(curr_msg.content, prev_match[0].content)
                similarities.append(sim)

        return float(np.mean(similarities)) if similarities else 0.0

    @staticmethod
    def _text_similarity(text_a: str, text_b: str) -> float:
        """Lightweight bag-of-words cosine similarity."""
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        return len(intersection) / (len(words_a | words_b) or 1)

    def reset(self) -> None:
        """Reset for a new query."""
        self._round = 0
