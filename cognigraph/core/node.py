"""CogniNode — a knowledge graph node with an embedded reasoning agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from cognigraph.core.message import Message
from cognigraph.core.state import NodeState
from cognigraph.core.types import ModelBackend, NodeStatus, ReasoningType


NODE_REASONING_PROMPT = """You are a specialized knowledge agent for the entity: {label} ({entity_type}).

Your knowledge:
{description}

{properties_text}

Query: {query}

{context_text}

Based on your specialized knowledge, provide a focused reasoning response.
Be precise and cite your knowledge. State your confidence (0-100%).
If you detect contradictions with neighbor messages, explicitly flag them."""


@dataclass
class CogniNode:
    """A knowledge graph node with an embedded SLM agent.

    Each CogniNode wraps a KG entity and its associated model backend.
    The agent is lazily initialized — the model is only loaded when the
    node is activated as part of a reasoning subgraph.
    """

    # Identity
    id: str
    label: str
    entity_type: str = "Entity"

    # Knowledge
    properties: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    embedding: np.ndarray | None = field(default=None, repr=False)

    # Agent
    backend: ModelBackend | None = field(default=None, repr=False)
    adapter_id: str | None = None
    system_prompt: str | None = None
    max_tokens: int = 512
    temperature: float = 0.3

    # State
    state: NodeState = field(default_factory=NodeState)
    status: NodeStatus = NodeStatus.IDLE

    # Edges (IDs only — graph owns the edge objects)
    incoming_edges: list[str] = field(default_factory=list)
    outgoing_edges: list[str] = field(default_factory=list)

    def activate(self, backend: ModelBackend) -> None:
        """Assign a model backend and mark as activated."""
        self.backend = backend
        self.status = NodeStatus.ACTIVATED
        self.state.reset()

    def deactivate(self) -> None:
        """Unload agent, free resources."""
        self.backend = None
        self.status = NodeStatus.IDLE

    async def reason(
        self, query: str, incoming_messages: list[Message]
    ) -> Message:
        """Produce a reasoning output given query + incoming messages.

        This is the core reasoning step — the node uses its local knowledge
        plus messages from neighbors to produce a new message.
        """
        if self.backend is None:
            raise RuntimeError(f"Node {self.id} has no backend assigned. Call activate() first.")

        self.status = NodeStatus.REASONING

        # Build context from incoming messages
        context_text = ""
        if incoming_messages:
            context_parts = ["Messages from neighbor agents:"]
            for msg in incoming_messages:
                context_parts.append(msg.to_prompt_context())
            context_text = "\n\n".join(context_parts)

        # Build properties text
        props_text = ""
        if self.properties:
            props_lines = [f"- {k}: {v}" for k, v in self.properties.items()]
            props_text = "Properties:\n" + "\n".join(props_lines)

        # Build prompt
        prompt = NODE_REASONING_PROMPT.format(
            label=self.label,
            entity_type=self.entity_type,
            description=self.description,
            properties_text=props_text,
            query=query,
            context_text=context_text,
        )

        if self.system_prompt:
            prompt = f"System: {self.system_prompt}\n\n{prompt}"

        # Generate response
        response = await self.backend.generate(
            prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        # Parse confidence from response (simple extraction)
        confidence = self._extract_confidence(response)

        # Detect reasoning type
        reasoning_type = self._detect_reasoning_type(response, incoming_messages)

        # Update state
        self.state.update(response, confidence)
        self.status = NodeStatus.CONVERGED

        # Create outgoing message
        return Message(
            source_node_id=self.id,
            target_node_id="__broadcast__",  # orchestrator routes
            round=self.state.current_round,
            content=response,
            reasoning_type=reasoning_type,
            confidence=confidence,
            evidence=[self.id],
            parent_messages=[m.id for m in incoming_messages],
            token_count=len(response.split()),  # approximate
        )

    def _extract_confidence(self, response: str) -> float:
        """Extract confidence percentage from response text."""
        import re

        patterns = [
            r"confidence[:\s]+(\d+)%",
            r"(\d+)%\s*confiden",
            r"confidence[:\s]+0\.(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                val = int(match.group(1))
                if val > 1:
                    return min(val / 100.0, 1.0)
                return val
        return 0.5  # default

    def _detect_reasoning_type(
        self, response: str, incoming: list[Message]
    ) -> ReasoningType:
        """Detect the reasoning type from response content."""
        lower = response.lower()
        if any(word in lower for word in ["contradict", "conflict", "disagree", "however"]):
            return ReasoningType.CONTRADICTION
        if any(word in lower for word in ["therefore", "combining", "synthesiz", "overall"]):
            return ReasoningType.SYNTHESIS
        if "?" in response and response.count("?") > response.count("."):
            return ReasoningType.QUESTION
        if incoming:
            return ReasoningType.SYNTHESIS
        return ReasoningType.ASSERTION

    @property
    def degree(self) -> int:
        """Total number of edges (incoming + outgoing)."""
        return len(self.incoming_edges) + len(self.outgoing_edges)

    @property
    def is_hub(self) -> bool:
        """Whether this node is a high-connectivity hub (degree > 5)."""
        return self.degree > 5
