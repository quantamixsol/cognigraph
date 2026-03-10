"""Aggregation strategies — synthesize multi-node reasoning into a final answer."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from cognigraph.core.message import Message
from cognigraph.core.types import ReasoningType

if TYPE_CHECKING:
    from cognigraph.core.types import ModelBackend

logger = logging.getLogger("cognigraph.aggregation")


AGGREGATION_PROMPT = """You are a reasoning aggregator. Multiple specialized agents have analyzed a query from different perspectives. Synthesize their outputs into a single, coherent answer.

Query: {query}

Agent Outputs:
{agent_outputs}

Instructions:
1. Identify areas of agreement across agents
2. Flag any contradictions between agents
3. Synthesize a unified answer weighted by confidence
4. State overall confidence (0-100%)
5. List key evidence sources

Provide a clear, structured response."""


class Aggregator:
    """Aggregates multi-node reasoning outputs into a final answer.

    Supports multiple strategies:
    - weighted_synthesis: LLM synthesizes all outputs (default)
    - confidence_weighted: Simple concatenation weighted by confidence
    - majority_vote: Take the most common conclusion
    """

    def __init__(
        self,
        strategy: str = "weighted_synthesis",
        backend: ModelBackend | None = None,
    ) -> None:
        self.strategy = strategy
        self.backend = backend

    async def aggregate(
        self,
        query: str,
        messages: dict[str, Message],
        backend: ModelBackend | None = None,
    ) -> str:
        """Aggregate node outputs into a final answer."""
        effective_backend = backend or self.backend

        if self.strategy == "weighted_synthesis" and effective_backend:
            return await self._weighted_synthesis(query, messages, effective_backend)
        elif self.strategy == "majority_vote":
            return self._majority_vote(messages)
        else:
            return self._confidence_weighted(messages)

    async def _weighted_synthesis(
        self,
        query: str,
        messages: dict[str, Message],
        backend: ModelBackend,
    ) -> str:
        """Use an LLM to synthesize all agent outputs."""
        # Sort by confidence (highest first)
        sorted_msgs = sorted(
            messages.values(), key=lambda m: m.confidence, reverse=True
        )

        # Build context
        parts = []
        for msg in sorted_msgs:
            parts.append(
                f"[Agent: {msg.source_node_id} | "
                f"Type: {msg.reasoning_type.value} | "
                f"Confidence: {msg.confidence:.0%}]\n{msg.content}"
            )

        agent_outputs = "\n\n---\n\n".join(parts)
        prompt = AGGREGATION_PROMPT.format(query=query, agent_outputs=agent_outputs)

        return await backend.generate(prompt, max_tokens=1024, temperature=0.2)

    def _confidence_weighted(self, messages: dict[str, Message]) -> str:
        """Simple concatenation weighted by confidence."""
        sorted_msgs = sorted(
            messages.values(), key=lambda m: m.confidence, reverse=True
        )

        parts = []
        for msg in sorted_msgs:
            if msg.confidence >= 0.3:  # filter low-confidence
                prefix = ""
                if msg.reasoning_type == ReasoningType.CONTRADICTION:
                    prefix = "[CONFLICT] "
                parts.append(f"{prefix}{msg.content} (confidence: {msg.confidence:.0%})")

        return "\n\n".join(parts) if parts else "No confident reasoning produced."

    def _majority_vote(self, messages: dict[str, Message]) -> str:
        """Return the output with highest aggregate confidence."""
        if not messages:
            return "No reasoning produced."
        best = max(messages.values(), key=lambda m: m.confidence)
        return best.content
