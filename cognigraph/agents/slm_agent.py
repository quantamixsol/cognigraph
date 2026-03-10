"""SLMAgent — default agent that wraps any model backend."""

from __future__ import annotations

from typing import Any

from cognigraph.agents.base_agent import BaseAgent
from cognigraph.core.message import Message
from cognigraph.core.types import ModelBackend


class SLMAgent(BaseAgent):
    """Default agent — forwards query + context to backend model.

    Works with any ModelBackend (local SLM, API, Ollama, custom).
    """

    def __init__(
        self,
        backend: ModelBackend,
        system_prompt: str | None = None,
        max_tokens: int = 512,
        temperature: float = 0.3,
    ) -> None:
        super().__init__(backend)
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def reason(
        self, query: str, context: list[Message], node_info: dict[str, Any]
    ) -> str:
        """Generate reasoning from query + context."""
        parts = []

        if self.system_prompt:
            parts.append(f"System: {self.system_prompt}")

        parts.append(f"Entity: {node_info.get('label', 'Unknown')}")
        parts.append(f"Description: {node_info.get('description', '')}")
        parts.append(f"Query: {query}")

        if context:
            parts.append("Neighbor messages:")
            for msg in context:
                parts.append(msg.to_prompt_context())

        prompt = "\n\n".join(parts)
        return await self.backend.generate(
            prompt,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
