"""Mock backend for testing — returns configurable responses."""

from __future__ import annotations

import random

from cognigraph.backends.base import BaseBackend


class MockBackend(BaseBackend):
    """Mock model backend for testing and development.

    Returns configurable responses without any model inference.
    Useful for testing the orchestration pipeline without GPU/API costs.
    """

    def __init__(
        self,
        response: str | None = None,
        responses: list[str] | None = None,
        confidence_range: tuple[float, float] = (0.6, 0.9),
        latency_ms: float = 0.0,
    ) -> None:
        self._response = response
        self._responses = responses or []
        self._call_count = 0
        self._confidence_range = confidence_range
        self._latency_ms = latency_ms

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.3,
        stop: list[str] | None = None,
    ) -> str:
        if self._latency_ms > 0:
            import asyncio
            await asyncio.sleep(self._latency_ms / 1000)

        self._call_count += 1

        if self._response:
            return self._response

        if self._responses:
            idx = (self._call_count - 1) % len(self._responses)
            return self._responses[idx]

        # Generate a default mock response
        conf = random.uniform(*self._confidence_range)
        return (
            f"Based on my specialized knowledge, I can provide the following analysis. "
            f"The query relates to my domain expertise. "
            f"Confidence: {conf:.0%}"
        )

    @property
    def name(self) -> str:
        return "mock"

    @property
    def cost_per_1k_tokens(self) -> float:
        return 0.0

    @property
    def call_count(self) -> int:
        return self._call_count
